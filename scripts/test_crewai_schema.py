#!/usr/bin/env python3
"""
Test de confirmation hypothese 2 (Phase 1 §0.c)
================================================

But : prouver que les modeles qui cassent en CrewAI (Qwen 3 Coder, Kimi K2)
echouent SPECIFIQUEMENT a cause du schema reel CrewAI, pas a cause d'une
incapacite generale de tool use.

Protocole :
  Pour chaque modele suspect, on envoie 2 appels :
    A) Schema SIMPLE : get_weather(city) — 1 param required, strict:true
       → attendu NATIVE (deja valide par test_tool_use_strict.py)
    B) Schema CREWAI REEL : read_file(path, offset, limit) — 3 params
       ALL required (meme ceux avec defaults Python), strict:true,
       additionalProperties:false
       → si MALFORMED/TEXT ici alors que A=NATIVE : hypothese 2 confirmee

Modeles testes :
  - Qwen 3 Coder 480B (coder primaire, casse en CrewAI)
  - Kimi K2 thinking (critic primaire, casse en CrewAI)
  - Qwen 3.5 397B (researcher, controle positif — marche en CrewAI)

Cout NIM : 6 appels (2 par modele). ~2 min.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"

if not API_KEY:
    print("ERREUR : NVIDIA_API_KEY manquante")
    sys.exit(1)

os.environ["OPENAI_API_KEY"] = API_KEY
os.environ["OPENAI_API_BASE"] = NVIDIA_BASE
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"

import litellm  # noqa: E402

MODELS = [
    ("Qwen 3 Coder 480B",  "openai/qwen/qwen3-coder-480b-a35b-instruct"),
    ("Kimi K2 thinking",    "openai/moonshotai/kimi-k2-thinking"),
    ("Qwen 3.5 397B (ctrl)", "openai/qwen/qwen3.5-397b-a17b"),
]

# --- Schema A : SIMPLE (1 param, le meme qui marche dans test_tool_use.py) ---
TOOLS_SIMPLE = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a given city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Name of the city",
                },
            },
            "required": ["city"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}]

MESSAGES_SIMPLE = [{
    "role": "user",
    "content": (
        "What is the weather in Paris right now? "
        "You MUST call the get_weather tool to find out. "
        "Do not answer from memory."
    ),
}]

# --- Schema B : CREWAI REEL pour read_file ---
# Reproduit exactement ce que CrewAI genere via convert_tools_to_openai_schema :
# - strict: true
# - additionalProperties: false
# - TOUS les params dans required (meme offset et limit qui ont des defaults)
# - descriptions coherentes avec la docstring du tool
TOOLS_CREWAI = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": (
            "Lit un fichier. offset = position de depart en caracteres, "
            "limit = taille max lue. Pour les gros fichiers, appeler "
            "plusieurs fois avec des offsets differents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
                "offset": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                    "description": "Start position in characters",
                    "default": 0,
                },
                "limit": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                    "description": "Maximum characters to read",
                    "default": 40000,
                },
            },
            "required": ["path", "offset", "limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}]

MESSAGES_CREWAI = [{
    "role": "user",
    "content": (
        "Read the file README.md from the project. "
        "You MUST call the read_file tool to do this. "
        "Do not answer from memory."
    ),
}]


def classify(response, error=None):
    """Classifie la reponse en NATIVE / TEXT / MALFORMED / ERROR."""
    if error is not None:
        return "ERROR", str(error)[:200]
    try:
        msg = response.choices[0].message
    except Exception as e:
        return "ERROR", f"reponse mal formee : {e}"

    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        try:
            tc = tool_calls[0]
            fn_name = tc.function.name if hasattr(tc, "function") else tc.get("function", {}).get("name", "")
            args_str = tc.function.arguments if hasattr(tc, "function") else str(tc.get("function", {}).get("arguments", ""))
            return "NATIVE", f"tool_call={fn_name}({args_str[:80]})"
        except Exception:
            return "NATIVE", "tool_calls present"

    content = (msg.content or "").strip()
    if not content:
        return "MALFORMED", "ni tool_calls ni content"
    if "<tool_call" in content.lower() or "<function=" in content.lower():
        # Extrait un bout du XML casse pour diagnostic
        snippet = content[:150].replace("\n", " ")
        return "MALFORMED", f"XML tool_call casse: {snippet}"
    if "read_file" in content.lower() or "get_weather" in content.lower():
        return "TEXT", f"mentionne l'outil en texte ({len(content)} chars)"
    return "TEXT", f"texte simple ({len(content)} chars)"


def test_model(label, model, tools, messages, schema_label):
    """Teste un modele avec un schema donne. Retourne (categorie, note)."""
    print(f"  {label:25s} | {schema_label:12s} | ", end="", flush=True)
    try:
        resp = litellm.completion(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            timeout=90,
            api_key=API_KEY,
            api_base=NVIDIA_BASE,
        )
        cat, note = classify(resp)
    except Exception as e:
        cat, note = classify(None, error=e)
    print(f"{cat:10s} | {note}")
    return cat, note


def main():
    print()
    print("=" * 78)
    print("  Confirmation hypothese 2 : schema CrewAI reel vs schema simple")
    print("=" * 78)
    print()
    print(f"  {'Modele':25s} | {'Schema':12s} | {'Resultat':10s} | Detail")
    print(f"  {'-'*25} | {'-'*12} | {'-'*10} | {'-'*30}")

    results = {}
    for label, model in MODELS:
        cat_simple, _ = test_model(label, model, TOOLS_SIMPLE, MESSAGES_SIMPLE, "SIMPLE")
        cat_crewai, _ = test_model(label, model, TOOLS_CREWAI, MESSAGES_CREWAI, "CREWAI REEL")
        results[label] = (cat_simple, cat_crewai)
        print()

    # Verdict
    print("=" * 78)
    print("  VERDICT")
    print("=" * 78)
    print()

    hypothesis_confirmed = False
    for label, (simple, crewai) in results.items():
        if simple == "NATIVE" and crewai != "NATIVE":
            print(f"  {label}: SIMPLE=NATIVE, CREWAI={crewai}")
            print("    -> Le schema CrewAI casse ce modele. HYPOTHESE 2 CONFIRMEE.")
            hypothesis_confirmed = True
        elif simple == "NATIVE" and crewai == "NATIVE":
            print(f"  {label}: SIMPLE=NATIVE, CREWAI=NATIVE")
            print("    -> Le schema CrewAI ne casse PAS ce modele.")
        else:
            print(f"  {label}: SIMPLE={simple}, CREWAI={crewai}")
            print("    -> Resultat non concluant (schema simple deja en echec).")

    print()
    if hypothesis_confirmed:
        print("  CONCLUSION : Le schema strict CrewAI (required sur params a defaults)")
        print("  est bien la cause racine du bug 'intentions vides'.")
        print("  -> Piste de fix : retirer strict:true OU ajuster les required.")
    else:
        print("  CONCLUSION : Hypothese 2 NON confirmee par ce test.")
        print("  -> Investiguer d'autres pistes (prompt ReAct, system messages, etc.)")
    print()


if __name__ == "__main__":
    main()
