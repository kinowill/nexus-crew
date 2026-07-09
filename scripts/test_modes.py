#!/usr/bin/env python3
"""
Tests unitaires des modes d'usage v1 (Phase 1 §2).

Usage :
    python scripts/test_modes.py

Couvre :
  - build_crew(mode=X) produit la bonne composition de tasks/agents
  - Les contrats enregistres correspondent aux tasks du mode
  - mode invalide leve ValueError
  - --deep prepend scan_task quel que soit le mode
  - mode par defaut = "edit" (non-regression)

Offline : pas de kickoff() LLM, on inspecte juste la structure du Crew construit.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util as _ilu  # noqa: E402
_spec = _ilu.spec_from_file_location("contracts", ROOT / "crew" / "contracts.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["contracts"] = _mod
_spec.loader.exec_module(_mod)

os.environ.setdefault("CREW_PROJECT", str(ROOT))

from crew.crew import (  # noqa: E402
    build_crew,
    VALID_MODES,
    DEFAULT_MODE,
)
from contracts import ContractTracker  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    tag = "[OK]" if ok else "[KO]"
    line = f"{tag} {label}"
    if detail and not ok:
        line += f"  -> {detail}"
    print(line)


def agent_roles(crew) -> list[str]:
    return [getattr(a, "role", "?") for a in crew.agents]


def agent_delegation_flags(crew) -> list[bool]:
    return [bool(getattr(a, "allow_delegation", False)) for a in crew.agents]


# ─── Constantes publiques ────────────────────────────────────────────────────
check(
    "constantes : VALID_MODES contient read/edit/review/debug",
    set(VALID_MODES) == {"read", "edit", "review", "debug"},
    f"val={VALID_MODES}",
)
check(
    "constantes : DEFAULT_MODE == 'edit' (non-regression)",
    DEFAULT_MODE == "edit",
    f"val={DEFAULT_MODE!r}",
)


# ─── mode = "read" ───────────────────────────────────────────────────────────
tracker = ContractTracker()
crew = build_crew("explique ce projet", ROOT, deep=False,
                  tracker=tracker, mode="read")
check(
    "read : 1 task (research only)",
    len(crew.tasks) == 1,
    f"n={len(crew.tasks)}",
)
check(
    "read : agents = [Researcher]",
    agent_roles(crew) == ["Researcher"],
    f"roles={agent_roles(crew)}",
)
check(
    "read : pas de Coder",
    "Coder" not in agent_roles(crew),
)
check(
    "read : pas de Critic",
    "Critic" not in agent_roles(crew),
)
check(
    "read : 1 contrat enregistre (research)",
    len(tracker._contracts) == 1,
    f"n={len(tracker._contracts)}",
)


# ─── mode = "review" ─────────────────────────────────────────────────────────
tracker = ContractTracker()
crew = build_crew("relis le code", ROOT, deep=False,
                  tracker=tracker, mode="review")
check(
    "review : 3 tasks (research + review + final)",
    len(crew.tasks) == 3,
    f"n={len(crew.tasks)}",
)
check(
    "review : agents = [Researcher, Critic, Architect]",
    set(agent_roles(crew)) == {"Researcher", "Critic", "Architect"},
    f"roles={agent_roles(crew)}",
)
check(
    "review : pas de Coder",
    "Coder" not in agent_roles(crew),
)
check(
    "review : 3 contrats enregistres",
    len(tracker._contracts) == 3,
)


# ─── mode = "edit" (defaut, non-regression) ──────────────────────────────────
tracker = ContractTracker()
crew = build_crew("refactor X", ROOT, deep=False,
                  tracker=tracker, mode="edit")
check(
    "edit : 6 tasks (research + plan + code + review + rework + final)",
    len(crew.tasks) == 6,
    f"n={len(crew.tasks)}",
)
check(
    "edit : agents = [Researcher, Architect, Coder, Critic]",
    set(agent_roles(crew)) == {"Researcher", "Architect", "Coder", "Critic"},
    f"roles={agent_roles(crew)}",
)
check(
    "edit : 6 contrats enregistres",
    len(tracker._contracts) == 6,
)


# ─── mode = "debug" (alias edit) ─────────────────────────────────────────────
tracker = ContractTracker()
crew_debug = build_crew("debug X", ROOT, deep=False,
                        tracker=tracker, mode="debug")
check(
    "debug : meme pipeline que edit (6 tasks)",
    len(crew_debug.tasks) == 6,
)
check(
    "debug : meme agents que edit",
    set(agent_roles(crew_debug)) == {"Researcher", "Architect", "Coder", "Critic"},
)


# ─── Mode invalide ───────────────────────────────────────────────────────────
try:
    build_crew("x", ROOT, deep=False, mode="nope")
    check("mode invalide : ValueError leve", False, "pas d'exception")
except ValueError as e:
    check(
        "mode invalide : ValueError leve avec message explicite",
        "nope" in str(e) and "attendu" in str(e),
        str(e),
    )
except Exception as e:
    check("mode invalide : ValueError leve", False, f"{type(e).__name__}: {e}")


# ─── --deep prepend scan_task quel que soit le mode ─────────────────────────
for m, base_n in [("read", 1), ("review", 3), ("edit", 6), ("debug", 6)]:
    crew = build_crew("x", ROOT, deep=True, mode=m)
    expected = base_n + 1
    check(
        f"deep + mode={m} : {expected} tasks (scan prepended)",
        len(crew.tasks) == expected,
        f"n={len(crew.tasks)}",
    )
    check(
        f"deep + mode={m} : Scanner present",
        "Scanner" in agent_roles(crew),
        f"roles={agent_roles(crew)}",
    )
    check(
        f"deep + mode={m} : delegation desactivee",
        not any(agent_delegation_flags(crew)),
        f"flags={agent_delegation_flags(crew)}",
    )


# ─── Default mode == edit (non-regression) ──────────────────────────────────
crew_default = build_crew("x", ROOT, deep=False)  # pas de mode=
check(
    "defaut sans mode= : 6 tasks (= edit)",
    len(crew_default.tasks) == 6,
    f"n={len(crew_default.tasks)}",
)
check(
    "defaut sans mode= : delegation desactivee",
    not any(agent_delegation_flags(crew_default)),
    f"flags={agent_delegation_flags(crew_default)}",
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
