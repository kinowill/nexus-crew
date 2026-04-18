#!/usr/bin/env python3
"""
Batch test tool use NIM — variance intrinseque
==============================================

But : mesurer si l'intermittence "intentions vides" observee en runs NEXUS
reels (journal 2026-04-19) vient de la variance NIM elle-meme, independamment
de CrewAI.

Protocole :
  - Un seul modele teste par lancement (argument CLI).
  - N appels identiques avec le MEME schema (schema CrewAI reel, deja
    normalise par _strip_strict_tools). Meme prompt. temperature=0.1.
  - Appels sequentiels (pas de concurrence).
  - On classifie chaque reponse : NATIVE / TEXT / MALFORMED / ERROR.
  - Verdict : si toutes NATIVE -> fix deterministe cote NIM, le bug est
    cote CrewAI/orchestration. Si variance -> NIM est intermittent.

Usage :
  python scripts/test_tool_use_batch.py                # defaut = researcher
  python scripts/test_tool_use_batch.py --role coder --n 10
  python scripts/test_tool_use_batch.py --role critic --n 5
"""

import argparse
import copy
import os
import sys
import time
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

import litellm  # noqa: E402

# Modeles primaires par role (identiques a MODEL_CHAINS dans crew/crew.py)
PRIMARY_BY_ROLE = {
    "researcher": "openai/qwen/qwen3.5-397b-a17b",
    "architect":  "openai/qwen/qwen3.5-397b-a17b",
    "coder":      "openai/qwen/qwen3-coder-480b-a35b-instruct",
    "critic":     "openai/moonshotai/kimi-k2-thinking",
    "scanner":    "openai/meta/llama-3.3-70b-instruct",
}

# Schema CREWAI REEL pour read_file, avant normalisation (= ce que CrewAI envoie)
TOOLS_CREWAI_RAW = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": (
            "Lit un fichier. offset = position de depart en caracteres, "
            "limit = taille max lue."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "offset": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                    "description": "Start position",
                    "default": 0,
                },
                "limit": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                    "description": "Maximum characters",
                    "default": 40000,
                },
            },
            "required": ["path", "offset", "limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}]

MESSAGES = [{
    "role": "user",
    "content": (
        "Read the file README.md from the project. "
        "You MUST call the read_file tool to do this. "
        "Do not answer from memory."
    ),
}]


def strip_strict_tools(tools):
    """Replique exacte de crew.crew._strip_strict_tools (2026-04-10)."""
    cleaned = copy.deepcopy(tools)
    for t in cleaned:
        if not isinstance(t, dict):
            continue
        func = t.get("function", {})
        func.pop("strict", None)
        params = func.get("parameters", {})
        params.pop("additionalProperties", None)
        props = params.get("properties", {})
        required = params.get("required", [])
        if required and props:
            truly_required = [r for r in required if "default" not in props.get(r, {})]
            params["required"] = truly_required
    return cleaned


def classify(response, error=None):
    if error is not None:
        return "ERROR", str(error)[:120]
    try:
        msg = response.choices[0].message
    except Exception as e:
        return "ERROR", f"resp mal formee : {e}"

    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        return "NATIVE", f"tool_calls={len(tool_calls)}"

    content = (msg.content or "").strip()
    if not content:
        return "MALFORMED", "ni tool_calls ni content"
    low = content.lower()
    if "<tool_call" in low or "<function=" in low:
        return "MALFORMED", f"XML casse: {content[:80]}"
    return "TEXT", f"texte nu ({len(content)} chars)"


def fire(model, tools):
    try:
        resp = litellm.completion(
            model=model,
            messages=MESSAGES,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            timeout=90,
            api_key=API_KEY,
            api_base=NVIDIA_BASE,
        )
        return classify(resp)
    except Exception as e:
        return classify(None, error=e)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=list(PRIMARY_BY_ROLE), default="researcher")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Pause entre appels (s). 0 = rafale serree.")
    args = parser.parse_args()

    model = PRIMARY_BY_ROLE[args.role]
    tools = strip_strict_tools(TOOLS_CREWAI_RAW)

    print()
    print("=" * 70)
    print(f"  Batch tool use NIM — role={args.role}  N={args.n}  sleep={args.sleep}s")
    print(f"  Modele : {model}")
    print("=" * 70)
    print()

    counts = {"NATIVE": 0, "TEXT": 0, "MALFORMED": 0, "ERROR": 0}
    t0 = time.time()
    for i in range(1, args.n + 1):
        cat, note = fire(model, tools)
        counts[cat] = counts.get(cat, 0) + 1
        print(f"  #{i:02d}  {cat:10s} | {note}")
        if args.sleep > 0 and i < args.n:
            time.sleep(args.sleep)
    dt = time.time() - t0

    print()
    print("=" * 70)
    print(f"  RESULTAT ({dt:.1f}s)")
    print("=" * 70)
    for k in ("NATIVE", "TEXT", "MALFORMED", "ERROR"):
        pct = 100.0 * counts[k] / args.n
        print(f"  {k:10s} : {counts[k]:3d}/{args.n}  ({pct:5.1f} %)")
    print()
    if counts["NATIVE"] == args.n:
        print("  -> 100% NATIVE. Le fix est deterministe cote NIM pour ce modele.")
        print("  -> Le bug 'intentions vides' vient d'ailleurs (CrewAI, delegation,")
        print("     messages, system prompts, tours successifs).")
    elif counts["NATIVE"] == 0:
        print("  -> 0% NATIVE. Le modele refuse systematiquement le tool use avec")
        print("     ce schema. Probleme structurel (a re-investiguer).")
    else:
        print("  -> VARIANCE NIM confirmee : le modele alterne NATIVE et non-NATIVE")
        print("     sur des appels strictement identiques. Hypothese 2 validee.")
    print()


if __name__ == "__main__":
    main()
