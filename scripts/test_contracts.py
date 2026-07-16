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
VIOLATION_SEVERITY_BLOCKER = contracts.VIOLATION_SEVERITY_BLOCKER
ACTION_HINT_USE_REQUIRED_TOOL = contracts.ACTION_HINT_USE_REQUIRED_TOOL
ACTION_HINT_EXPAND_OUTPUT = contracts.ACTION_HINT_EXPAND_OUTPUT
ACTION_HINT_INCLUDE_REQUIRED_PATTERN = contracts.ACTION_HINT_INCLUDE_REQUIRED_PATTERN
DEFAULT_CORRECTION_ATTEMPT_BUDGET = contracts.DEFAULT_CORRECTION_ATTEMPT_BUDGET
CORRECTION_PLAN_NO_ACTION = contracts.CORRECTION_PLAN_NO_ACTION
CORRECTION_PLAN_AVAILABLE = contracts.CORRECTION_PLAN_AVAILABLE
CORRECTION_PLAN_BUDGET_EXHAUSTED = contracts.CORRECTION_PLAN_BUDGET_EXHAUSTED
INTERACTION_STATUS_PENDING = contracts.INTERACTION_STATUS_PENDING
INTERACTION_STATUS_BLOCKED_BUDGET_EXHAUSTED = contracts.INTERACTION_STATUS_BLOCKED_BUDGET_EXHAUSTED
INTERACTION_REQUEST_TASK_RERUN = contracts.INTERACTION_REQUEST_TASK_RERUN
INTERACTION_REQUEST_OUTPUT_EXPANSION = contracts.INTERACTION_REQUEST_OUTPUT_EXPANSION
INTERACTION_REQUEST_VERDICT_REVISION = contracts.INTERACTION_REQUEST_VERDICT_REVISION

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
check("payload : severite blocker", payload["violations"][0]["severity"] == VIOLATION_SEVERITY_BLOCKER)
check("payload : action hint outil requis", payload["violations"][0]["action_hint"] == ACTION_HINT_USE_REQUIRED_TOOL)
check("payload : action hint output court", payload["violations"][1]["action_hint"] == ACTION_HINT_EXPAND_OUTPUT)
plan = bad_tracker.correction_plan_payload()
check("correction plan : statut disponible", plan["status"] == CORRECTION_PLAN_AVAILABLE, str(plan))
check("correction plan : compte actions", plan["actions_count"] == 1, str(plan))
check("correction plan : compte relancable", plan["rerunnable_count"] == 1, str(plan))
check("correction plan : signale relance", plan["has_rerunnable_actions"])
clean_plan = tracker.correction_plan_payload()
check("correction plan : rien a corriger", clean_plan["status"] == CORRECTION_PLAN_NO_ACTION, str(clean_plan))
exhausted_plan = bad_tracker.correction_plan_payload(
    attempts_budget=1,
    attempts_used_by_task={"research": 1},
)
check("correction plan : budget epuise", exhausted_plan["status"] == CORRECTION_PLAN_BUDGET_EXHAUSTED, str(exhausted_plan))
check("correction plan : compte epuise", exhausted_plan["exhausted_count"] == 1, str(exhausted_plan))
actions = bad_tracker.corrective_actions()
check("correction : une action par task violee", len(actions) == 1, str(actions))
check("correction : task research ciblee", actions[0].task_name == "research", actions[0].task_name)
check("correction : priorite outil requis", actions[0].action_hint == ACTION_HINT_USE_REQUIRED_TOOL)
check("correction : interaction rerun task", actions[0].interaction_type == INTERACTION_REQUEST_TASK_RERUN)
check("correction : interaction id stable", actions[0].interaction_id == "research:TestAgent:request_task_rerun")
check("correction : budget defaut expose", actions[0].attempts_budget == DEFAULT_CORRECTION_ATTEMPT_BUDGET)
check("correction : relance autorisee", actions[0].should_rerun)
check("correction : tentative restante", actions[0].attempts_remaining == 1)
interaction = actions[0].as_interaction_dict()
check("interaction envelope : id conserve", interaction["interaction_id"] == actions[0].interaction_id)
check("interaction envelope : type conserve", interaction["interaction_type"] == INTERACTION_REQUEST_TASK_RERUN)
check("interaction envelope : statut pending", interaction["status"] == INTERACTION_STATUS_PENDING, str(interaction))
check("interaction envelope : source gouvernance", interaction["source"] == "contract_governance")
check("interaction envelope : target agent", interaction["target_agent"] == "TestAgent")
check("interaction envelope : dispatch autorise", interaction["should_dispatch"])
tracker_interactions = bad_tracker.corrective_interactions()
check("tracker interactions : une enveloppe", len(tracker_interactions) == 1, str(tracker_interactions))
exhausted_action = bad_tracker.corrective_actions(
    attempts_budget=1,
    attempts_used_by_task={"research": 1},
)[0]
check("correction : budget epuise bloque relance", not exhausted_action.should_rerun)
exhausted_interaction = exhausted_action.as_interaction_dict()
check("interaction envelope : statut budget epuise", exhausted_interaction["status"] == INTERACTION_STATUS_BLOCKED_BUDGET_EXHAUSTED, str(exhausted_interaction))
check("interaction envelope : dispatch bloque", not exhausted_interaction["should_dispatch"])
check("correction summary : plan visible", "Plan correctif borne" in bad_tracker.correction_summary())
try:
    bad_tracker.corrective_actions(attempts_budget=-1)
    check("correction : budget negatif refuse", False, "pas d'exception")
except ValueError:
    check("correction : budget negatif refuse", True)

json_payload = json.loads(bad_tracker.governance_json(strict_contracts=True))
check("json : payload parsable", json_payload["exit_code"] == CONTRACT_BLOCK_EXIT_CODE)
check("json : corrective actions presentes", len(json_payload["corrective_actions"]) == 1)
check("json : corrective interactions presentes", len(json_payload["corrective_interactions"]) == 1)
check("json : interaction envelope pending", json_payload["corrective_interactions"][0]["status"] == INTERACTION_STATUS_PENDING)
check("json : correction plan present", json_payload["correction_plan"]["status"] == CORRECTION_PLAN_AVAILABLE)
check("json : correction budget present", json_payload["correction_attempt_budget"] == DEFAULT_CORRECTION_ATTEMPT_BUDGET)
custom_budget_payload = json.loads(bad_tracker.governance_json(
    strict_contracts=True,
    correction_attempt_budget=3,
))
check("json : correction budget custom present", custom_budget_payload["correction_attempt_budget"] == 3)
check("json : action budget custom propage", custom_budget_payload["corrective_actions"][0]["attempts_budget"] == 3)
check("json : interaction type present", custom_budget_payload["corrective_actions"][0]["interaction_type"] == INTERACTION_REQUEST_TASK_RERUN)
check("json : interaction id present", custom_budget_payload["corrective_actions"][0]["interaction_id"] == "research:TestAgent:request_task_rerun")
with tempfile.TemporaryDirectory() as tmpdir:
    output_path = bad_tracker.write_governance_json(
        Path(tmpdir) / "governance.json",
        strict_contracts=True,
        correction_attempt_budget=2,
    )
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
check("json file : rapport ecrit", written_payload["violations_count"] == 2)
check("json file : action hint conserve", written_payload["violations"][0]["action_hint"] == ACTION_HINT_USE_REQUIRED_TOOL)
check("json file : correction budget custom conserve", written_payload["corrective_actions"][0]["attempts_budget"] == 2)



# -- Pattern violation maps to verdict/pattern corrective action ------------
pattern_description = "Review sans verdict"
pattern_tracker = ContractTracker()
pattern_tracker.register(pattern_description, "review")
pattern_tracker.on_task_done(task_output(
    pattern_description,
    "Finding detaille sans le verdict contractuel attendu, avec assez de contenu pour passer la longueur.",
    tools=["read_file"],
))
pattern_actions = pattern_tracker.corrective_actions()
check("correction : pattern manquant cible verdict", pattern_actions[0].action_hint == ACTION_HINT_INCLUDE_REQUIRED_PATTERN)
check("correction : interaction verdict revision", pattern_actions[0].interaction_type == INTERACTION_REQUEST_VERDICT_REVISION)
check("correction : verdict interaction id stable", pattern_actions[0].interaction_id == "review:TestAgent:request_verdict_revision")

# -- Length-only violation maps to output expansion interaction ---------------
length_description = "Synthese trop courte"
length_tracker = ContractTracker()
length_tracker.register(length_description, "final")
length_tracker.on_task_done(task_output(length_description, "court", tools=[]))
length_actions = length_tracker.corrective_actions()
check("correction : longueur cible expansion", length_actions[0].action_hint == ACTION_HINT_EXPAND_OUTPUT)
check("correction : interaction output expansion", length_actions[0].interaction_type == INTERACTION_REQUEST_OUTPUT_EXPANSION)
check("correction : output interaction id stable", length_actions[0].interaction_id == "final:TestAgent:request_output_expansion")
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
