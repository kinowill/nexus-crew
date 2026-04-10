"""
Output contracts for NEXUS tasks (Phase 1).

Each task has a contract defining minimum requirements for a valid output.
The contract checker verifies tool usage (extracted from TaskOutput.messages)
and output quality (from TaskOutput.raw) after each task.

Violations are logged and collected — not silently accepted.
No automatic retry yet (planned for Phase 2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


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
