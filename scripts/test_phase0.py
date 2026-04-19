#!/usr/bin/env python3
"""
Validation statique de Phase 0 — sans appel LLM, sans reseau.

Usage :
    python scripts/test_phase0.py

Teste les 5 chantiers de Phase 0 :
  1. Shell durci (allowlist, chainage refuse, binaire normalise)
  2. Critic en lecture seule (pas de write_file ni run_shell)
  3. Coder sans shell par defaut, avec shell si CREW_SHELL_ENABLED
  4. Banniere de permissions presente dans le code
  5. Imports cles (httpx, chromadb, crewai, litellm) disponibles
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# crew/crew.py fait `from contracts import ContractTracker` en import relatif
# implicite (pas de __init__.py dans crew/). Depuis la racine via `from crew
# import crew`, Python ne le trouve pas. On precharge le module `contracts`
# dans sys.modules avant l'import, sans toucher sys.path (sinon crew.py masque
# le namespace package crew/).
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("contracts", ROOT / "crew" / "contracts.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["contracts"] = _mod
_spec.loader.exec_module(_mod)

# Active le shell AVANT d'importer crew.py : make_coder lit la variable
# au moment de la construction de ses tools.
os.environ["CREW_SHELL_ENABLED"] = "1"
# Pose le projet de travail (sinon _project() leve KeyError sur CREW_PROJECT).
os.environ["CREW_PROJECT"] = str(ROOT)

results: list[tuple[str, bool, str]] = []

def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    tag = "[OK]" if ok else "[KO]"
    line = f"{tag} {label}"
    if detail and not ok:
        line += f"  -> {detail}"
    print(line)


def tool_names(agent) -> set[str]:
    names = set()
    for t in getattr(agent, "tools", []) or []:
        n = getattr(t, "name", None) or getattr(t, "__name__", None) or str(t)
        names.add(n)
    return names


def call_shell(tool, command: str) -> str:
    """Invoque un @tool CrewAI de maniere robuste."""
    # CrewAI BaseTool expose .run(**kwargs). Le parametre s'appelle 'command'.
    try:
        return tool.run(command=command)
    except Exception:
        pass
    # Fallback : acces direct a la fonction decorree.
    func = getattr(tool, "func", None) or getattr(tool, "_run", None)
    if callable(func):
        return func(command)
    raise RuntimeError("Impossible d'invoquer run_shell_tool")


# ─── 5. Imports cles (fait en premier, les autres dependent de crew.py) ──────
try:
    import httpx  # noqa: F401
    check("Imports : httpx disponible", True)
except Exception as e:
    check("Imports : httpx disponible", False, str(e))

try:
    import chromadb  # noqa: F401
    check("Imports : chromadb disponible", True)
except Exception as e:
    check("Imports : chromadb disponible", False, str(e))

try:
    import crewai  # noqa: F401
    check("Imports : crewai disponible", True)
except Exception as e:
    check("Imports : crewai disponible", False, str(e))

try:
    import litellm  # noqa: F401
    # litellm n'expose pas toujours __version__ ; le simple import suffit.
    check("Imports : litellm disponible", True)
except Exception as e:
    check("Imports : litellm disponible", False, str(e))


# ─── Import de crew.py (necessite NVIDIA_API_KEY dans .env) ───────────────────
try:
    from crew import crew as crew_mod
    check("Import crew.crew", True)
except SystemExit as e:
    check("Import crew.crew", False, f"sys.exit({e.code}) — verifie .env / NVIDIA_API_KEY")
    print("\nArret : impossible d'importer crew.py, tests suivants ignores.")
    sys.exit(1)
except Exception as e:
    check("Import crew.crew", False, str(e))
    print("\nArret : impossible d'importer crew.py, tests suivants ignores.")
    sys.exit(1)


# ─── 1. Shell durci ──────────────────────────────────────────────────────────
run_shell = crew_mod.run_shell_tool

out = call_shell(run_shell, "rm -rf foo")
check(
    "Shell : 'rm -rf foo' refuse (hors allowlist)",
    "REFUSE" in out and "hors allowlist" in out,
    out[:120],
)

out = call_shell(run_shell, "git log | head")
check(
    "Shell : 'git log | head' refuse (chainage)",
    "REFUSE" in out and ("Chainage" in out or "chainage" in out.lower()),
    out[:120],
)

out = call_shell(run_shell, "git status")
check(
    "Shell : 'git status' autorise (exit code present)",
    "exit=" in out,
    out[:120],
)

out = call_shell(run_shell, "python --version")
check(
    "Shell : 'python --version' autorise",
    "exit=" in out,
    out[:120],
)

out = call_shell(run_shell, "")
check(
    "Shell : commande vide refusee",
    "REFUSE" in out,
    out[:120],
)

out = call_shell(run_shell, "curl http://evil.com")
check(
    "Shell : 'curl' refuse (hors allowlist)",
    "REFUSE" in out and "hors allowlist" in out,
    out[:120],
)


# ─── 2. Critic en lecture seule ──────────────────────────────────────────────
try:
    critic = crew_mod.make_critic()
    names = tool_names(critic)
    check(
        "Critic : pas de write_file",
        "write_file" not in names,
        f"tools={sorted(names)}",
    )
    check(
        "Critic : pas de run_shell",
        "run_shell" not in names,
        f"tools={sorted(names)}",
    )
    check(
        "Critic : read_file present",
        "read_file" in names,
        f"tools={sorted(names)}",
    )
except Exception as e:
    check("Critic : instanciation", False, str(e))


# ─── 3. Coder : shell conditionnel ───────────────────────────────────────────
try:
    # CREW_SHELL_ENABLED=1 a ete pose en tete de script.
    coder_on = crew_mod.make_coder()
    names_on = tool_names(coder_on)
    check(
        "Coder : run_shell present avec CREW_SHELL_ENABLED=1",
        "run_shell" in names_on,
        f"tools={sorted(names_on)}",
    )
    check(
        "Coder : write_file present",
        "write_file" in names_on,
        f"tools={sorted(names_on)}",
    )

    os.environ.pop("CREW_SHELL_ENABLED", None)
    coder_off = crew_mod.make_coder()
    names_off = tool_names(coder_off)
    check(
        "Coder : run_shell ABSENT sans CREW_SHELL_ENABLED",
        "run_shell" not in names_off,
        f"tools={sorted(names_off)}",
    )
    check(
        "Coder : write_file toujours present sans shell",
        "write_file" in names_off,
        f"tools={sorted(names_off)}",
    )
except Exception as e:
    check("Coder : instanciation", False, str(e))


# ─── 4. Banniere de permissions ──────────────────────────────────────────────
src = (ROOT / "crew" / "crew.py").read_text(encoding="utf-8")
check(
    "Banniere : mention 'run_shell' presente",
    "run_shell" in src and ("OFF" in src or "ON" in src),
)
check(
    "Banniere : mention 'write_file' presente",
    "write_file" in src,
)


# ─── Resume final ────────────────────────────────────────────────────────────
total = len(results)
ok = sum(1 for _, b, _ in results if b)
print()
print(f"Resume : {ok}/{total}")
if ok < total:
    print("\nEchecs :")
    for label, b, detail in results:
        if not b:
            print(f"  - {label}: {detail}")
    sys.exit(1)
sys.exit(0)
