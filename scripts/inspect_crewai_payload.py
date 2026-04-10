#!/usr/bin/env python3
"""
Inspecte le payload exact que CrewAI envoie a litellm.completion pour le Coder
==============================================================================

Hypothese active (Phase 1 §0.c) : la divergence entre la matrice tool use
(scripts/test_tool_use.py, qui marche) et le run reel CrewAI (intentions vides
+ XML casse) vient d'une difference dans le payload envoye a NIM.

Ce script :
1. Importe crew.crew (pose CREW_PROJECT, CREW_SHELL_ENABLED).
2. Cree un Agent Coder reel via make_coder().
3. Monkey-patche litellm.completion AVANT tout appel.
4. Lance un mini-Crew avec une task qui force l'usage d'un tool.
5. Le patch intercepte le 1er appel, dumpe les params dans
   scripts/coder_payload.json, et leve une RuntimeError.
6. On catche l'exception, on exit clean. Cout NIM : ZERO appel reel.

Resultat attendu : on voit literalement messages + tools + params que CrewAI
envoie au Coder, et on peut comparer avec ce que test_tool_use.py envoie.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Pose les vars d'env attendues par crew.crew (sans crew.crew, _project() crash).
os.environ.setdefault("CREW_PROJECT", str(ROOT))
# On laisse CREW_SHELL_ENABLED non pose : on teste le mode "normal" (pas de shell)
# pour matcher le run de validation Phase 0.

# Charge .env pour API_KEY (meme logique que crew.py)
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

if not os.environ.get("NVIDIA_API_KEY"):
    print("ERREUR : NVIDIA_API_KEY manquante")
    sys.exit(1)

os.environ["OPENAI_API_KEY"] = os.environ["NVIDIA_API_KEY"]
os.environ["OPENAI_API_BASE"] = "https://integrate.api.nvidia.com/v1"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"

# IMPORTANT : monkey-patch AVANT d'importer crew.crew (qui importe litellm)
import litellm  # noqa: E402

PAYLOAD_FILE = ROOT / "scripts" / "coder_payload.json"


class _Intercept(RuntimeError):
    """Exception levee apres capture du payload pour stopper l'execution."""


_original_completion = litellm.completion


SECRET_KEYS = {"api_key", "openai_api_key", "anthropic_api_key", "nvidia_api_key", "azure_api_key"}


def _intercept(*args, **kwargs):
    # Filtre les kwargs serialisables seulement, et REDACT les secrets.
    safe = {}
    for k, v in kwargs.items():
        if k.lower() in SECRET_KEYS:
            safe[k] = "<REDACTED>"
            continue
        try:
            json.dumps(v, default=str)
            safe[k] = v
        except Exception:
            safe[k] = f"<non-serializable: {type(v).__name__}>"
    PAYLOAD_FILE.write_text(json.dumps(safe, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"[intercept] payload capture dans {PAYLOAD_FILE}")
    print(f"[intercept] model = {kwargs.get('model', '?')}")
    print(f"[intercept] {len(kwargs.get('messages', []))} messages, {len(kwargs.get('tools') or [])} tools")
    raise _Intercept("payload intercepted - aucun appel NIM effectue")


litellm.completion = _intercept

# Maintenant on importe crew.crew (qui va creer FallbackLLM avec litellm patche)
from crew.crew import make_coder  # noqa: E402
from crewai import Task, Crew, Process  # noqa: E402


def main():
    print()
    print("=" * 70)
    print("  Inspection payload CrewAI -> litellm.completion (Coder)")
    print("=" * 70)
    print()

    coder = make_coder()
    print(f"  Coder LLM    : {coder.llm.model}")
    print(f"  Coder tools  : {[t.name for t in coder.tools]}")
    print()

    task = Task(
        description=(
            "Lis le fichier README.md du projet et resume-le en 3 lignes. "
            "Tu DOIS appeler read_file pour le lire."
        ),
        expected_output="Un resume de 3 lignes du README.",
        agent=coder,
    )

    crew = Crew(
        agents=[coder],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    try:
        crew.kickoff()
    except _Intercept:
        print()
        print("  [OK] Payload capture, execution stoppee avant tout appel NIM.")
        print(f"  Lis : {PAYLOAD_FILE}")
    except Exception as e:
        # Si crewai a wrappe notre exception
        if "_Intercept" in str(type(e).__name__) or "payload intercepted" in str(e):
            print()
            print("  [OK] Payload capture (via wrap), execution stoppee.")
            print(f"  Lis : {PAYLOAD_FILE}")
        else:
            print()
            print(f"  [ERR] Exception inattendue : {type(e).__name__}: {e}")
            raise


if __name__ == "__main__":
    main()
