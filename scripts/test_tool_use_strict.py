#!/usr/bin/env python3
"""
Test ciblé : tool use NIM AVEC `strict: true`
==============================================

Hypothèse à valider : CrewAI ajoute `"strict": true` au schema OpenAI tool
(crewai/utilities/agent_utils.py:207). Certains serveurs vLLM côté NIM ne
supportent pas correctement ce flag, ce qui ferait que les modèles répondent
en texte (ou en `<tool_call>` XML cassé) au lieu de `tool_calls` natif.

Ce script rejoue 3 modèles représentatifs :
  - Qwen 3.5 397B (researcher, marche en CrewAI)         → contrôle "OK"
  - Qwen 3 Coder 480B (coder primaire, casse en CrewAI)  → suspect
  - Kimi K2 thinking (critic primaire, casse en CrewAI)  → suspect

Avec un schema STRICT (additionalProperties:false, required complet) +
`strict: true`. Si l'hypothèse est correcte :
  - Qwen 3.5 397B → NATIVE (déjà natif sans strict aussi)
  - Qwen 3 Coder 480B → ERROR ou TEXT/MALFORMED
  - Kimi K2 thinking → ERROR ou TEXT/MALFORMED
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
    "openai/qwen/qwen3.5-397b-a17b",          # researcher = OK en CrewAI
    "openai/qwen/qwen3-coder-480b-a35b-instruct",  # coder = casse en CrewAI
    "openai/moonshotai/kimi-k2-thinking",     # critic = casse en CrewAI
]

# Schema STRICT à la sauce CrewAI : strict: true + additionalProperties: false
TOOLS_STRICT = [{
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


def classify(response, error=None):
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
            return "NATIVE", f"tool_call={fn_name}"
        except Exception:
            return "NATIVE", "tool_calls present"
    content = (msg.content or "").strip()
    if not content:
        return "MALFORMED", "ni tool_calls ni content"
    if "<tool_call" in content.lower() or "<function=" in content.lower():
        return "MALFORMED", f"texte XML tool_call casse ({len(content)} chars)"
    return "TEXT", f"texte simple ({len(content)} chars)"


def main():
    print()
    print("=" * 70)
    print("  Test tool use NIM avec strict: true (a la CrewAI)")
    print("=" * 70)
    print()

    for model in MODELS:
        print(f"  testing {model} ... ", end="", flush=True)
        try:
            resp = litellm.completion(
                model=model,
                messages=MESSAGES,
                tools=TOOLS_STRICT,
                tool_choice="auto",
                temperature=0.1,
                timeout=60,
                api_key=API_KEY,
                api_base=NVIDIA_BASE,
            )
            cat, note = classify(resp)
        except Exception as e:
            cat, note = classify(None, error=e)
        print(f"{cat:10s} | {note}")

    print()


if __name__ == "__main__":
    main()
