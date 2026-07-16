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

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

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
    CORRECTION_LEDGER_SCHEMA_VERSION,
    _correction_attempt_ledger_payload,
    _load_correction_attempt_ledger,
    _resolve_correction_ledger_json_path,
    _resolve_governance_json_path,
    _write_correction_attempt_ledger,
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


def task_output(description: str, raw: str, tools: list[str] | None = None):
    tool_calls = [
        {"function": {"name": tool_name}}
        for tool_name in (tools or [])
    ]
    messages = [{"tool_calls": tool_calls}] if tool_calls else []
    return SimpleNamespace(
        agent="TestAgent",
        raw=raw,
        description=description,
        messages=messages,
    )


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


# ─── Gouvernance JSON path guard ─────────────────────────────────────────────
relative_governance_path = _resolve_governance_json_path(ROOT, "reports/governance.json")
check(
    "governance json : chemin relatif reste dans le projet",
    ROOT.resolve() in relative_governance_path.parents,
    str(relative_governance_path),
)
try:
    _resolve_governance_json_path(ROOT, str(ROOT.parent / "outside.json"))
    check("governance json : chemin hors projet refuse", False, "pas d'exception")
except ValueError:
    check("governance json : chemin hors projet refuse", True)
except Exception as e:
    check("governance json : chemin hors projet refuse", False, f"{type(e).__name__}: {e}")

relative_ledger_path = _resolve_correction_ledger_json_path(ROOT, "reports/correction-ledger.json")
check(
    "correction ledger : chemin relatif reste dans le projet",
    ROOT.resolve() in relative_ledger_path.parents,
    str(relative_ledger_path),
)
try:
    _resolve_correction_ledger_json_path(ROOT, str(ROOT.parent / "ledger.json"))
    check("correction ledger : chemin hors projet refuse", False, "pas d'exception")
except ValueError:
    check("correction ledger : chemin hors projet refuse", True)
except Exception as e:
    check("correction ledger : chemin hors projet refuse", False, f"{type(e).__name__}: {e}")

with tempfile.TemporaryDirectory(dir=ROOT) as tmpdir:
    ledger_path = Path(tmpdir) / "ledger.json"
    ledger_path.write_text(json.dumps({
        "schema_version": CORRECTION_LEDGER_SCHEMA_VERSION,
        "attempts_used_by_task": {"research": 1},
        "attempts_used_by_interaction_id": {"research:TestAgent:request_task_rerun": 2},
    }), encoding="utf-8")
    by_task, by_interaction = _load_correction_attempt_ledger(ROOT, str(ledger_path))
check("correction ledger : schema version courante acceptee", by_task == {"research": 1}, str(by_task))
check("correction ledger : task chargee", by_task == {"research": 1}, str(by_task))
check(
    "correction ledger : interaction chargee",
    by_interaction == {"research:TestAgent:request_task_rerun": 2},
    str(by_interaction),
)
with tempfile.TemporaryDirectory(dir=ROOT) as tmpdir:
    bad_schema_path = Path(tmpdir) / "ledger.json"
    bad_schema_path.write_text(json.dumps({
        "schema_version": CORRECTION_LEDGER_SCHEMA_VERSION + 1,
        "attempts_used_by_task": {"research": 1},
    }), encoding="utf-8")
    try:
        _load_correction_attempt_ledger(ROOT, str(bad_schema_path))
        check("correction ledger : schema version inconnue refusee", False, "pas d'exception")
    except ValueError:
        check("correction ledger : schema version inconnue refusee", True)
    except Exception as e:
        check("correction ledger : schema version inconnue refusee", False, f"{type(e).__name__}: {e}")
with tempfile.TemporaryDirectory(dir=ROOT) as tmpdir:
    bad_ledger_path = Path(tmpdir) / "ledger.json"
    bad_ledger_path.write_text(json.dumps({"attempts_used_by_task": {"research": -1}}), encoding="utf-8")
    try:
        _load_correction_attempt_ledger(ROOT, str(bad_ledger_path))
        check("correction ledger : valeur negative refusee", False, "pas d'exception")
    except ValueError:
        check("correction ledger : valeur negative refusee", True)
    except Exception as e:
        check("correction ledger : valeur negative refusee", False, f"{type(e).__name__}: {e}")

ledger_tracker = ContractTracker()
ledger_description = "Ledger bad research"
ledger_tracker.register(ledger_description, "research")
ledger_tracker.on_task_done(task_output(ledger_description, "court", tools=[]))
ledger_payload = _correction_attempt_ledger_payload(
    ledger_tracker,
    correction_attempt_budget=2,
    attempts_used_by_task={"research": 1},
)
ledger_interaction_id = "research:TestAgent:request_task_rerun"
check(
    "correction ledger out : schema version present",
    ledger_payload["schema_version"] == CORRECTION_LEDGER_SCHEMA_VERSION,
    str(ledger_payload),
)
check(
    "correction ledger out : tentatives task conservees",
    ledger_payload["attempts_used_by_task"] == {"research": 1},
    str(ledger_payload),
)
check(
    "correction ledger out : interaction pending sans consommation",
    ledger_payload["pending_interaction_ids"] == [ledger_interaction_id],
    str(ledger_payload),
)
check("correction ledger out : aucune interaction bloquee", ledger_payload["blocked_interaction_ids"] == [])
exhausted_ledger_payload = _correction_attempt_ledger_payload(
    ledger_tracker,
    correction_attempt_budget=1,
    attempts_used_by_interaction_id={ledger_interaction_id: 1},
)
check(
    "correction ledger out : interaction bloquee si budget epuise",
    exhausted_ledger_payload["blocked_interaction_ids"] == [ledger_interaction_id],
    str(exhausted_ledger_payload),
)
with tempfile.TemporaryDirectory(dir=ROOT) as tmpdir:
    out_ledger_path = _write_correction_attempt_ledger(
        ROOT,
        str(Path(tmpdir) / "ledger-out.json"),
        ledger_tracker,
        correction_attempt_budget=2,
        attempts_used_by_task={"research": 1},
    )
    out_ledger_payload = json.loads(out_ledger_path.read_text(encoding="utf-8"))
check("correction ledger out : fichier ecrit", out_ledger_payload["interactions_count"] == 1, str(out_ledger_payload))
try:
    _write_correction_attempt_ledger(
        ROOT,
        str(ROOT.parent / "ledger-out.json"),
        ledger_tracker,
        correction_attempt_budget=1,
    )
    check("correction ledger out : chemin hors projet refuse", False, "pas d'exception")
except ValueError:
    check("correction ledger out : chemin hors projet refuse", True)
except Exception as e:
    check("correction ledger out : chemin hors projet refuse", False, f"{type(e).__name__}: {e}")
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
