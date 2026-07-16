"""
Output contracts for NEXUS tasks (Phase 1).

Each task has a contract defining minimum requirements for a valid output.
The contract checker verifies tool usage (extracted from TaskOutput.messages)
and output quality (from TaskOutput.raw) after each task.

Violations are logged and collected — not silently accepted.
No automatic retry yet (planned for Phase 2).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Governance status
# ---------------------------------------------------------------------------

GOVERNANCE_PAYLOAD_SCHEMA_VERSION = 1
GOVERNANCE_OK = "OK"
GOVERNANCE_BLOCKED_CONTRACT_VIOLATIONS = "BLOCKED_CONTRACT_VIOLATIONS"
CONTRACT_BLOCK_EXIT_CODE = 2
VIOLATION_SEVERITY_BLOCKER = "blocker"
ACTION_HINT_USE_REQUIRED_TOOL = "rerun_task_with_required_tool"
ACTION_HINT_EXPAND_OUTPUT = "rerun_task_with_more_complete_output"
ACTION_HINT_INCLUDE_REQUIRED_PATTERN = "rerun_task_with_required_verdict_or_pattern"
INTERACTION_REQUEST_TASK_RERUN = "request_task_rerun"
INTERACTION_REQUEST_OUTPUT_EXPANSION = "request_output_expansion"
INTERACTION_REQUEST_VERDICT_REVISION = "request_verdict_revision"
DEFAULT_CORRECTION_ATTEMPT_BUDGET = 1
CORRECTION_PLAN_NO_ACTION = "NO_CORRECTION_NEEDED"
CORRECTION_PLAN_AVAILABLE = "CORRECTION_AVAILABLE"
CORRECTION_PLAN_BUDGET_EXHAUSTED = "CORRECTION_BUDGET_EXHAUSTED"
INTERACTION_STATUS_PENDING = "PENDING"
INTERACTION_STATUS_BLOCKED_BUDGET_EXHAUSTED = "BLOCKED_BUDGET_EXHAUSTED"


@dataclass
class GovernanceReport:
    """Final governance state produced after contract validation."""
    status: str
    violations_count: int
    should_block: bool


@dataclass
class CorrectiveAction:
    """Bounded corrective action proposed after contract violations."""
    task_name: str
    agent: str
    action_hint: str
    interaction_type: str
    interaction_id: str
    reason: str
    violations_count: int
    attempts_budget: int = DEFAULT_CORRECTION_ATTEMPT_BUDGET
    attempts_used: int = 0

    @property
    def attempts_remaining(self) -> int:
        return max(0, self.attempts_budget - self.attempts_used)

    @property
    def should_rerun(self) -> bool:
        return self.attempts_remaining > 0

    def as_dict(self) -> dict:
        """Return a stable machine-readable representation."""
        return {
            "task_name": self.task_name,
            "agent": self.agent,
            "action_hint": self.action_hint,
            "interaction_type": self.interaction_type,
            "interaction_id": self.interaction_id,
            "reason": self.reason,
            "violations_count": self.violations_count,
            "attempts_budget": self.attempts_budget,
            "attempts_used": self.attempts_used,
            "attempts_remaining": self.attempts_remaining,
            "should_rerun": self.should_rerun,
        }

    def as_interaction_dict(self) -> dict:
        """Return a stable typed interaction envelope for future orchestration."""
        status = (
            INTERACTION_STATUS_PENDING
            if self.should_rerun
            else INTERACTION_STATUS_BLOCKED_BUDGET_EXHAUSTED
        )
        return {
            "interaction_id": self.interaction_id,
            "interaction_type": self.interaction_type,
            "status": status,
            "source": "contract_governance",
            "target_agent": self.agent,
            "task_name": self.task_name,
            "action_hint": self.action_hint,
            "reason": self.reason,
            "attempts_budget": self.attempts_budget,
            "attempts_used": self.attempts_used,
            "attempts_remaining": self.attempts_remaining,
            "should_dispatch": self.should_rerun,
        }


# ---------------------------------------------------------------------------
# Contract definitions
# ---------------------------------------------------------------------------

@dataclass
class TaskContract:
    """What a task MUST produce for its output to be considered valid."""
    task_name: str
    # Tool usage: at least one of these tools must have been called
    required_tools_any: list[str] = field(default_factory=list)
    # Minimum output length (chars) — catches empty/stub responses
    min_output_length: int = 0
    # Regex patterns — at least one must match for the output to pass
    # (empty list = no text pattern required)
    required_patterns: list[str] = field(default_factory=list)


# Pre-built contracts for each task in the NEXUS pipeline.
# Kept minimal and universal: verify the agent *acted*, not that it formatted
# perfectly.  See DOCUMENT_MAITRE_PROJET.md Phase 1 §1.

TASK_CONTRACTS: dict[str, TaskContract] = {
    "research": TaskContract(
        task_name="research",
        required_tools_any=["read_file", "list_files", "grep"],
        min_output_length=200,
    ),
    "plan": TaskContract(
        task_name="plan",
        min_output_length=100,
        # Must contain some form of numbered plan or step keyword
        required_patterns=[
            r"\d+[\.\)]",       # "1." or "1)"
            r"(?i)step\b",
            r"(?i)[eé]tape\b",
        ],
    ),
    "code": TaskContract(
        task_name="code",
        required_tools_any=["read_file"],
        min_output_length=50,
    ),
    "review": TaskContract(
        task_name="review",
        required_tools_any=["read_file"],
        min_output_length=50,
        required_patterns=[
            r"(?i)\bAPPROVED\b",
            r"(?i)\bCHANGES_NEEDED\b",
        ],
    ),
    "rework": TaskContract(
        task_name="rework",
        # Rework is conditional: if APPROVED, Coder just says so (no tools needed).
        # If CHANGES_NEEDED, Coder should read+write. We only enforce a minimal output.
        min_output_length=20,
    ),
    "final": TaskContract(
        task_name="final",
        # Synthesis task — must be substantial, no specific pattern required.
        min_output_length=100,
    ),
    "scan": TaskContract(
        task_name="scan",
        required_tools_any=["list_files"],
        min_output_length=50,
    ),
}


# ---------------------------------------------------------------------------
# Violation tracking
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    """A single contract violation."""
    task_name: str
    agent: str
    rule: str
    detail: str
    severity: str = VIOLATION_SEVERITY_BLOCKER
    action_hint: str = ""

    def as_dict(self) -> dict:
        """Return a stable machine-readable representation."""
        return {
            "task_name": self.task_name,
            "agent": self.agent,
            "rule": self.rule,
            "detail": self.detail,
            "severity": self.severity,
            "action_hint": self.action_hint,
        }


def _extract_tools_from_messages(messages: list) -> set[str]:
    """Extract tool names from TaskOutput.messages.

    CrewAI stores the full LLM conversation in TaskOutput.messages.
    Native tool calls appear as assistant messages with a 'tool_calls' list,
    each containing {"function": {"name": "..."}}.
    """
    tools: set[str] = set()
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        for tc in msg.get("tool_calls", []):
            if isinstance(tc, dict):
                func = tc.get("function", {})
                if isinstance(func, dict) and func.get("name"):
                    tools.add(func["name"])
    return tools


class ContractTracker:
    """Validates task outputs against their contracts.

    Usage in crew.py:
        tracker = ContractTracker()
        tracker.register(research_task.description, "research")
        crew = Crew(..., task_callback=tracker.on_task_done)
        crew.kickoff()
        print(tracker.summary())
    """

    def __init__(self) -> None:
        self.violations: list[Violation] = []
        # task_name -> contract mapping (set by register())
        self._contracts: dict[str, TaskContract] = {}
        # task description prefix -> task_name (for lookup in on_task_done)
        self._task_map: dict[str, str] = {}

    def register(self, task_description: str, contract_key: str) -> None:
        """Associate a task's description (first 80 chars) with a contract key."""
        prefix = task_description[:80]
        self._task_map[prefix] = contract_key
        self._contracts[contract_key] = TASK_CONTRACTS[contract_key]

    # -- task_callback (called after each task completes) ------------------

    def on_task_done(self, task_output) -> None:
        """CrewAI task_callback: receives TaskOutput."""
        agent_name = task_output.agent or "unknown"
        raw = task_output.raw or ""
        description = task_output.description or ""
        messages = getattr(task_output, "messages", []) or []

        # Find which contract applies to this task
        prefix = description[:80]
        contract_key = self._task_map.get(prefix)
        if not contract_key:
            return
        contract = self._contracts.get(contract_key)
        if not contract:
            return

        tools_used = _extract_tools_from_messages(messages)

        self._check_tools(contract_key, agent_name, contract, tools_used)
        self._check_length(contract_key, agent_name, contract, raw)
        self._check_patterns(contract_key, agent_name, contract, raw)

    # -- Individual checks -------------------------------------------------

    def _check_tools(self, task_name: str, agent: str, contract: TaskContract,
                     tools_used: set[str]) -> None:
        if not contract.required_tools_any:
            return
        if not tools_used & set(contract.required_tools_any):
            v = Violation(
                task_name=task_name,
                agent=agent,
                rule="required_tools",
                detail=(
                    f"Aucun des outils requis appele. "
                    f"Attendu >= 1 parmi {contract.required_tools_any}. "
                    f"Appeles : {sorted(tools_used) if tools_used else '(aucun)'}."
                ),
                action_hint=ACTION_HINT_USE_REQUIRED_TOOL,
            )
            self.violations.append(v)
            print(f"  [CONTRAT VIOLE] {task_name} ({agent}) : {v.detail}")

    def _check_length(self, task_name: str, agent: str, contract: TaskContract,
                      raw: str) -> None:
        if contract.min_output_length and len(raw) < contract.min_output_length:
            v = Violation(
                task_name=task_name,
                agent=agent,
                rule="min_output_length",
                detail=(
                    f"Output trop court ({len(raw)} chars, "
                    f"minimum {contract.min_output_length})."
                ),
                action_hint=ACTION_HINT_EXPAND_OUTPUT,
            )
            self.violations.append(v)
            print(f"  [CONTRAT VIOLE] {task_name} ({agent}) : {v.detail}")

    def _check_patterns(self, task_name: str, agent: str, contract: TaskContract,
                        raw: str) -> None:
        if not contract.required_patterns:
            return
        for pattern in contract.required_patterns:
            if re.search(pattern, raw):
                return  # At least one pattern matched
        v = Violation(
            task_name=task_name,
            agent=agent,
            rule="required_patterns",
            detail=(
                f"Aucun pattern attendu dans l'output. "
                f"Patterns : {contract.required_patterns}."
            ),
            action_hint=ACTION_HINT_INCLUDE_REQUIRED_PATTERN,
        )
        self.violations.append(v)
        print(f"  [CONTRAT VIOLE] {task_name} ({agent}) : {v.detail}")

    # -- Report ------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable summary of contract validation."""
        if not self.violations:
            return "[CONTRATS] Tous les agents ont respecte leur contrat."

        lines = [f"[CONTRATS] {len(self.violations)} violation(s) detectee(s) :"]
        for v in self.violations:
            lines.append(f"  - {v.task_name} ({v.agent}) [{v.rule}] : {v.detail}")
        return "\n".join(lines)

    def has_violations(self) -> bool:
        return len(self.violations) > 0

    def governance_report(self) -> GovernanceReport:
        """Return the final governance state for the run."""
        if self.has_violations():
            return GovernanceReport(
                status=GOVERNANCE_BLOCKED_CONTRACT_VIOLATIONS,
                violations_count=len(self.violations),
                should_block=True,
            )
        return GovernanceReport(
            status=GOVERNANCE_OK,
            violations_count=0,
            should_block=False,
        )

    def governance_summary(self) -> str:
        """Return a human-readable governance summary for the user/CLI."""
        report = self.governance_report()
        if report.should_block:
            return (
                f"[GOUVERNANCE] {report.status} - "
                f"{report.violations_count} violation(s) de contrat detectee(s). "
                "Le resultat doit etre traite comme bloque jusqu'a correction ou validation humaine."
            )
        return "[GOUVERNANCE] OK - aucun blocage contractuel detecte."

    def should_block(self) -> bool:
        """Whether automation should treat this run as blocked."""
        return self.governance_report().should_block

    def exit_code(self, strict_contracts: bool = False) -> int:
        """Return the CLI exit code implied by governance policy."""
        if strict_contracts and self.should_block():
            return CONTRACT_BLOCK_EXIT_CODE
        return 0

    def corrective_actions(
        self,
        attempts_budget: int = DEFAULT_CORRECTION_ATTEMPT_BUDGET,
        attempts_used_by_task: dict[str, int] | None = None,
        attempts_used_by_interaction_id: dict[str, int] | None = None,
    ) -> list[CorrectiveAction]:
        """Return one bounded corrective action per violated task."""
        if attempts_budget < 0:
            raise ValueError("attempts_budget must be >= 0")
        attempts_used_by_task = attempts_used_by_task or {}
        attempts_used_by_interaction_id = attempts_used_by_interaction_id or {}
        priority = {
            ACTION_HINT_USE_REQUIRED_TOOL: 0,
            ACTION_HINT_INCLUDE_REQUIRED_PATTERN: 1,
            ACTION_HINT_EXPAND_OUTPUT: 2,
        }
        interaction_by_hint = {
            ACTION_HINT_USE_REQUIRED_TOOL: INTERACTION_REQUEST_TASK_RERUN,
            ACTION_HINT_INCLUDE_REQUIRED_PATTERN: INTERACTION_REQUEST_VERDICT_REVISION,
            ACTION_HINT_EXPAND_OUTPUT: INTERACTION_REQUEST_OUTPUT_EXPANSION,
        }
        grouped: dict[tuple[str, str], list[Violation]] = {}
        for violation in self.violations:
            grouped.setdefault((violation.task_name, violation.agent), []).append(violation)

        actions: list[CorrectiveAction] = []
        for task_name, agent in sorted(grouped):
            violations = grouped[(task_name, agent)]
            selected = min(
                violations,
                key=lambda v: priority.get(v.action_hint, 99),
            )
            rules = ", ".join(v.rule for v in violations)
            interaction_type = interaction_by_hint.get(
                selected.action_hint,
                INTERACTION_REQUEST_TASK_RERUN,
            )
            interaction_id = f"{task_name}:{agent}:{interaction_type}"
            attempts_used = attempts_used_by_interaction_id.get(
                interaction_id,
                attempts_used_by_task.get(task_name, 0),
            )
            actions.append(CorrectiveAction(
                task_name=task_name,
                agent=agent,
                action_hint=selected.action_hint,
                interaction_type=interaction_type,
                interaction_id=interaction_id,
                reason=f"{len(violations)} violation(s): {rules}",
                violations_count=len(violations),
                attempts_budget=attempts_budget,
                attempts_used=attempts_used,
            ))
        return actions

    def correction_summary(
        self,
        attempts_budget: int = DEFAULT_CORRECTION_ATTEMPT_BUDGET,
        attempts_used_by_task: dict[str, int] | None = None,
        attempts_used_by_interaction_id: dict[str, int] | None = None,
    ) -> str:
        """Return a human-readable bounded correction plan."""
        actions = self.corrective_actions(
            attempts_budget=attempts_budget,
            attempts_used_by_task=attempts_used_by_task,
            attempts_used_by_interaction_id=attempts_used_by_interaction_id,
        )
        if not actions:
            return "[CORRECTION] Aucune correction contractuelle necessaire."

        lines = [
            "[CORRECTION] Plan correctif borne : "
            f"{len(actions)} task(s) candidate(s), budget={attempts_budget} relance(s)/task."
        ]
        for action in actions:
            status = "relance autorisee" if action.should_rerun else "budget epuise"
            lines.append(
                f"  - {action.task_name} ({action.agent}) : {status}; "
                f"action={action.action_hint}; "
                f"interaction={action.interaction_type}; "
                f"id={action.interaction_id}; "
                f"tentatives={action.attempts_used}/{action.attempts_budget}; "
                f"raison={action.reason}."
            )
        return "\n".join(lines)

    def corrective_interactions(
        self,
        attempts_budget: int = DEFAULT_CORRECTION_ATTEMPT_BUDGET,
        attempts_used_by_task: dict[str, int] | None = None,
        attempts_used_by_interaction_id: dict[str, int] | None = None,
    ) -> list[dict]:
        """Return typed interaction envelopes derived from corrective actions."""
        return [
            action.as_interaction_dict()
            for action in self.corrective_actions(
                attempts_budget=attempts_budget,
                attempts_used_by_task=attempts_used_by_task,
                attempts_used_by_interaction_id=attempts_used_by_interaction_id,
            )
        ]

    def correction_plan_payload(
        self,
        attempts_budget: int = DEFAULT_CORRECTION_ATTEMPT_BUDGET,
        attempts_used_by_task: dict[str, int] | None = None,
        attempts_used_by_interaction_id: dict[str, int] | None = None,
    ) -> dict:
        """Return a compact machine-readable correction plan summary."""
        actions = self.corrective_actions(
            attempts_budget=attempts_budget,
            attempts_used_by_task=attempts_used_by_task,
            attempts_used_by_interaction_id=attempts_used_by_interaction_id,
        )
        rerunnable_count = sum(1 for action in actions if action.should_rerun)
        exhausted_count = len(actions) - rerunnable_count

        if not actions:
            status = CORRECTION_PLAN_NO_ACTION
        elif rerunnable_count:
            status = CORRECTION_PLAN_AVAILABLE
        else:
            status = CORRECTION_PLAN_BUDGET_EXHAUSTED

        return {
            "status": status,
            "actions_count": len(actions),
            "rerunnable_count": rerunnable_count,
            "exhausted_count": exhausted_count,
            "has_rerunnable_actions": rerunnable_count > 0,
            "attempts_budget": attempts_budget,
        }

    def governance_payload(
        self,
        strict_contracts: bool = False,
        correction_attempt_budget: int = DEFAULT_CORRECTION_ATTEMPT_BUDGET,
    ) -> dict:
        """Return a stable JSON-ready governance payload."""
        report = self.governance_report()
        return {
            "schema_version": GOVERNANCE_PAYLOAD_SCHEMA_VERSION,
            "status": report.status,
            "should_block": report.should_block,
            "violations_count": report.violations_count,
            "exit_code": self.exit_code(strict_contracts=strict_contracts),
            "strict_contracts": strict_contracts,
            "correction_attempt_budget": correction_attempt_budget,
            "correction_plan": self.correction_plan_payload(
                attempts_budget=correction_attempt_budget,
            ),
            "corrective_interactions": self.corrective_interactions(
                attempts_budget=correction_attempt_budget,
            ),
            "corrective_actions": [
                action.as_dict()
                for action in self.corrective_actions(
                    attempts_budget=correction_attempt_budget,
                )
            ],
            "violations": [violation.as_dict() for violation in self.violations],
        }

    def governance_json(
        self,
        strict_contracts: bool = False,
        correction_attempt_budget: int = DEFAULT_CORRECTION_ATTEMPT_BUDGET,
    ) -> str:
        """Return the governance payload as deterministic JSON."""
        return json.dumps(
            self.governance_payload(
                strict_contracts=strict_contracts,
                correction_attempt_budget=correction_attempt_budget,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    def write_governance_json(
        self,
        path: str | Path,
        strict_contracts: bool = False,
        correction_attempt_budget: int = DEFAULT_CORRECTION_ATTEMPT_BUDGET,
    ) -> Path:
        """Write the governance payload to disk and return the path."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self.governance_json(
                strict_contracts=strict_contracts,
                correction_attempt_budget=correction_attempt_budget,
            ) + "\n",
            encoding="utf-8",
        )
        return output_path
