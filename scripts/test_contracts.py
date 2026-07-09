#!/usr/bin/env python3
"""
Tests unitaires des contrats et de l'etat de gouvernance (Phase 2 slice A).

Usage :
    python scripts/test_contracts.py

Offline : pas de CrewAI, pas de LLM, pas de reseau.
"""

import json
import importlib.util
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent.parent
CONTRACTS_PATH = ROOT / "crew" / "contracts.py"

spec = importlib.util.spec_from_file_location("contracts", CONTRACTS_PATH)
contracts = importlib.util.module_from_spec(spec)
sys.modules["contracts"] = contracts
spec.loader.exec_module(contracts)

ContractTracker = contracts.ContractTracker
GOVERNANCE_OK = contracts.GOVERNANCE_OK
GOVERNANCE_BLOCKED_CONTRACT_VIOLATIONS = contracts.GOVERNANCE_BLOCKED_CONTRACT_VIOLATIONS
CONTRACT_BLOCK_EXIT_CODE = contracts.CONTRACT_BLOCK_EXIT_CODE

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    tag = "[OK]" if ok else "[KO]"
    line = f"{tag} {label}"
    if detail and not ok:
        line += f"  -> {detail}"
    print(line)


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


# -- Valid research task: tool usage + enough output ------------------------
research_description = "Analyse le projet test"
tracker = ContractTracker()
tracker.register(research_description, "research")
tracker.on_task_done(task_output(
    research_description,
    "Rapport structure avec suffisamment de contenu. " * 8,
    tools=["read_file"],
))
report = tracker.governance_report()
check("governance : status OK sans violation", report.status == GOVERNANCE_OK, report.status)
check("governance : should_block False sans violation", not report.should_block, repr(report))
check("summary : OK mentionne contrats respectes", "respecte" in tracker.summary(), tracker.summary())


# -- Invalid research task: no tools + too short ----------------------------
bad_description = "Analyse le projet casse"
bad_tracker = ContractTracker()
bad_tracker.register(bad_description, "research")
bad_tracker.on_task_done(task_output(bad_description, "trop court", tools=[]))
bad_report = bad_tracker.governance_report()
check(
    "governance : status bloque avec violation",
    bad_report.status == GOVERNANCE_BLOCKED_CONTRACT_VIOLATIONS,
    bad_report.status,
)
check("governance : should_block True avec violation", bad_report.should_block, repr(bad_report))
check("governance : compte violations expose", bad_report.violations_count == 2, str(bad_report))
check("governance summary : BLOCKED visible", "BLOCKED_CONTRACT_VIOLATIONS" in bad_tracker.governance_summary())
check("exit code : non-strict reste a 0 malgre blocage", bad_tracker.exit_code(False) == 0)
check(
    "exit code : strict retourne code de blocage",
    bad_tracker.exit_code(True) == CONTRACT_BLOCK_EXIT_CODE,
    str(bad_tracker.exit_code(True)),
)
check("exit code : strict sans violation reste a 0", tracker.exit_code(True) == 0)
payload = bad_tracker.governance_payload(strict_contracts=True)
check("payload : status stable", payload["status"] == GOVERNANCE_BLOCKED_CONTRACT_VIOLATIONS)
check("payload : violations serialisees", len(payload["violations"]) == 2)
check("payload : premiere violation detaillee", payload["violations"][0]["rule"] == "required_tools")
json_payload = json.loads(bad_tracker.governance_json(strict_contracts=True))
check("json : payload parsable", json_payload["exit_code"] == CONTRACT_BLOCK_EXIT_CODE)
with tempfile.TemporaryDirectory() as tmpdir:
    output_path = bad_tracker.write_governance_json(
        Path(tmpdir) / "governance.json",
        strict_contracts=True,
    )
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
check("json file : rapport ecrit", written_payload["violations_count"] == 2)


# -- Review contract accepts either expected verdict ------------------------
review_description = "Review le travail"
review_tracker = ContractTracker()
review_tracker.register(review_description, "review")
review_tracker.on_task_done(task_output(
    review_description,
    "CHANGES_NEEDED\nFinding detaille avec plus de cinquante caracteres pour satisfaire le contrat.",
    tools=["read_file"],
))
check("review : CHANGES_NEEDED satisfait le contrat", not review_tracker.has_violations())


# -- Unknown task stays ignored ---------------------------------------------
ignored_tracker = ContractTracker()
ignored_tracker.on_task_done(task_output("task inconnue", "x", tools=[]))
check("tracker : task non enregistree ignoree", not ignored_tracker.has_violations())


# -- Final result ------------------------------------------------------------
total = len(results)
ok = sum(1 for _, passed, _ in results if passed)
print()
print(f"Resume : {ok}/{total}")
if ok < total:
    print("\nEchecs :")
    for label, passed, detail in results:
        if not passed:
            print(f"  - {label}: {detail}")
    sys.exit(1)
sys.exit(0)
