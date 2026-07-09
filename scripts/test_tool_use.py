#!/usr/bin/env python3
"""
Matrice tool use NVIDIA NIM — Phase 1 priorité 0
=================================================

Pour chaque modele unique dans MODEL_CHAINS de crew/crew.py, envoie un appel
litellm.completion avec UN outil simple (get_weather) et UN prompt qui demande
explicitement de l'utiliser. Classe la reponse en 4 categories :

  NATIVE    : response.choices[0].message.tool_calls non vide        ← le seul
              format que CrewAI/LiteLLM parse correctement.
  MALFORMED : pas de tool_calls, mais le texte contient un essai
              de tool call (XML <tool_call>, JSON inline, etc.)
  TEXT      : pas de tool_calls, le modele ignore l'outil et repond en texte.
  ERROR     : exception HTTP / timeout / refus.

Sauve le resultat dans scripts/tool_use_matrix.md pour reference durable.

Usage :
    python scripts/test_tool_use.py

Necessite les memes deps que crew/crew.py (uv tool env). Lance via le bon
python : %USERPROFILE%\\AppData\\Roaming\\uv\\tools\\crewai\\Scripts\\python.exe
"""

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Charge .env (meme logique que crew.py)
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"

if not API_KEY:
    print("ERREUR : NVIDIA_API_KEY manquante dans .env")
    sys.exit(1)

# LiteLLM lit ces variables pour le provider openai-compatible
os.environ["OPENAI_API_KEY"] = API_KEY
os.environ["OPENAI_API_BASE"] = NVIDIA_BASE

# Pas de tracing/telemetrie
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"

import litellm  # noqa: E402

# Importe la liste de modeles SANS importer crew.crew entierement (qui crash
# si CREW_PROJECT n'est pas pose). On parse le fichier source a la place.
def load_model_chains() -> dict:
    src = (ROOT / "crew" / "crew.py").read_text(encoding="utf-8")
    # Extrait le dict MODEL_CHAINS = { ... } de maniere brute mais fiable.
    match = re.search(r"MODEL_CHAINS\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
    if not match:
        print("ERREUR : impossible de trouver MODEL_CHAINS dans crew/crew.py")
        sys.exit(1)
    body = "{" + match.group(1) + "\n}"
    # eval contraint : pas de noms, juste litteraux
    return eval(body, {"__builtins__": {}}, {})


MODEL_CHAINS = load_model_chains()

# Deduplication des modeles uniques
ALL_MODELS = []
seen = set()
for role, chain in MODEL_CHAINS.items():
    for m in chain:
        if m not in seen:
            seen.add(m)
            ALL_MODELS.append(m)

# Outil simple, format OpenAI standard
TOOLS = [{
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
        },
    },
}]

MESSAGES = [
    {
        "role": "user",
        "content": (
            "What is the weather in Paris right now? "
            "You MUST call the get_weather tool to find out. "
            "Do not answer from memory."
        ),
    }
]

# Marqueurs d'un essai malformé (texte qui CONTIENT un tool call cassé)
MALFORMED_HINTS = [
    "<tool_call",
    "<function=",
    "<|tool",
    '"name": "get_weather"',
    "get_weather(",
    "function_call",
    "```json",
    "```tool",
]


def classify(response, error=None) -> tuple[str, str]:
    """Retourne (category, note) pour une reponse litellm."""
    if error is not None:
        return "ERROR", str(error)[:200]

    try:
        msg = response.choices[0].message
    except Exception as e:
        return "ERROR", f"reponse mal formee : {e}"

    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        # Verifie que c'est bien un appel a get_weather avec city=Paris
        try:
            tc = tool_calls[0]
            fn_name = tc.function.name if hasattr(tc, "function") else tc.get("function", {}).get("name", "")
            return "NATIVE", f"tool_call={fn_name}"
        except Exception:
            return "NATIVE", "tool_calls present (parsing partiel)"

    content = (msg.content or "").strip()
    if not content:
        return "MALFORMED", "ni tool_calls ni content"

    lower = content.lower()
    for hint in MALFORMED_HINTS:
        if hint.lower() in lower:
            return "MALFORMED", f"texte contient '{hint}' (essai tool call casse)"

    # Pas de tool call, pas d'essai casse, juste du texte
    return "TEXT", f"texte simple ({len(content)} chars)"


def test_model(model: str) -> tuple[str, str]:
    print(f"  testing {model} ... ", end="", flush=True)
    try:
        resp = litellm.completion(
            model=model,
            messages=MESSAGES,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1,
            timeout=60,
            api_key=API_KEY,
            api_base=NVIDIA_BASE,
        )
        cat, note = classify(resp)
    except Exception as e:
        cat, note = classify(None, error=e)
    print(cat)
    return cat, note


def main():
    print()
    print("=" * 70)
    print("  Matrice tool use NVIDIA NIM")
    print("=" * 70)
    print(f"  {len(ALL_MODELS)} modeles uniques a tester (sequentiel)")
    print("  Tool : get_weather(city) | Prompt : meteo Paris")
    print()

    results: list[tuple[str, str, str]] = []  # (model, category, note)

    for model in ALL_MODELS:
        cat, note = test_model(model)
        results.append((model, cat, note))
        time.sleep(1)  # politesse anti rate-limit

    # Construit le mapping role -> [(model, cat)]
    role_results: dict[str, list[tuple[str, str]]] = {}
    cat_by_model = {m: c for m, c, _ in results}
    for role, chain in MODEL_CHAINS.items():
        role_results[role] = [(m, cat_by_model.get(m, "?")) for m in chain]

    # Affichage tableau
    print()
    print("=" * 70)
    print("  Resultats")
    print("=" * 70)
    print()
    width = max(len(m) for m, _, _ in results) + 2
    print(f"  {'MODELE':<{width}} {'STATUT':<10} NOTE")
    print(f"  {'-' * width} {'-' * 10} {'-' * 30}")
    for m, cat, note in results:
        icon = {"NATIVE": "[OK]", "TEXT": "[TXT]", "MALFORMED": "[BAD]", "ERROR": "[ERR]"}.get(cat, "[?]")
        print(f"  {m:<{width}} {icon:<10} {note}")

    # Compte par categorie
    counts = {}
    for _, c, _ in results:
        counts[c] = counts.get(c, 0) + 1
    print()
    print(f"  Total : {len(results)} | " + " | ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    # Recommandations par role
    print()
    print("=" * 70)
    print("  Diagnostic par role")
    print("=" * 70)
    print()
    for role, chain_with_cat in role_results.items():
        primary, primary_cat = chain_with_cat[0]
        first_native = next((m for m, c in chain_with_cat if c == "NATIVE"), None)
        if primary_cat == "NATIVE":
            verdict = "OK (primaire NATIVE)"
        elif first_native:
            verdict = f"BASCULER vers {first_native} (primaire {primary_cat})"
        else:
            verdict = f"AUCUN modele NATIVE dans la chaine (primaire {primary_cat})"
        print(f"  {role:<11} : {verdict}")
        for m, c in chain_with_cat:
            print(f"               - {m} [{c}]")

    # Sauvegarde markdown
    md_path = ROOT / "scripts" / "tool_use_matrix.md"
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# Matrice tool use NIM",
        "",
        f"Genere le {today} par `scripts/test_tool_use.py`.",
        "",
        "Le critere `NATIVE` est le SEUL utilisable par CrewAI/LiteLLM : c'est",
        "le format OpenAI `tool_calls` standard. Les autres categories revelent",
        "un modele qui ne sait pas appeler un outil de maniere parsable.",
        "",
        "## Resultats par modele",
        "",
        "| Modele | Statut | Note |",
        "|---|---|---|",
    ]
    for m, cat, note in results:
        lines.append(f"| `{m}` | **{cat}** | {note} |")
    lines += [
        "",
        "## Diagnostic par role",
        "",
        "| Role | Primaire | Statut | Action |",
        "|---|---|---|---|",
    ]
    for role, chain_with_cat in role_results.items():
        primary, primary_cat = chain_with_cat[0]
        first_native = next((m for m, c in chain_with_cat if c == "NATIVE"), None)
        if primary_cat == "NATIVE":
            action = "rien a faire"
        elif first_native:
            action = f"basculer vers `{first_native}`"
        else:
            action = "**aucun modele NATIVE — chercher hors chaine**"
        lines.append(f"| {role} | `{primary}` | {primary_cat} | {action} |")
    lines += [
        "",
        "## Chaines completes",
        "",
    ]
    for role, chain_with_cat in role_results.items():
        lines.append(f"### {role}")
        lines.append("")
        for m, c in chain_with_cat:
            lines.append(f"- `{m}` — **{c}**")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print()
    print(f"  Matrice ecrite dans : {md_path}")
    print()


if __name__ == "__main__":
    main()
