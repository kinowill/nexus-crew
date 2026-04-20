#!/usr/bin/env python3
"""
Tests unitaires de la resilience NIM (Phase 1 §3 + §3bis).

Usage :
    python scripts/test_resilience.py

Couvre :
  - _is_rate_limit_error : classification d'exceptions (429, rate limit, autres)
  - _output_looks_malformed :
      * XML Hermes <tool_call> / <function= (journal 2026-04-19)
      * Intention 0-tools courte (journal 2026-04-20)
      * Non-regression : final answers courts legitimes non flaggues
      * Non-regression : sorties longues non flaggues
      * had_tools=False : filtre inerte
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# crew/crew.py fait `from contracts import ContractTracker` en import implicite.
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("contracts", ROOT / "crew" / "contracts.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["contracts"] = _mod
_spec.loader.exec_module(_mod)

# Pose CREW_PROJECT pour que crew.py s'importe proprement.
os.environ.setdefault("CREW_PROJECT", str(ROOT))

from crew.crew import (  # noqa: E402
    _is_rate_limit_error,
    _output_looks_malformed,
    MALFORMED_SHORT_TEXT_MAX,
    RATE_LIMIT_BACKOFFS,
)

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    tag = "[OK]" if ok else "[KO]"
    line = f"{tag} {label}"
    if detail and not ok:
        line += f"  -> {detail}"
    print(line)


# ─── _is_rate_limit_error ────────────────────────────────────────────────────
class RateLimitError(Exception):
    pass


class _LiteLLMRateLimitError(Exception):
    pass


check(
    "rate_limit : classe 'RateLimitError' detectee",
    _is_rate_limit_error(RateLimitError("whatever")),
)
check(
    "rate_limit : classe '_LiteLLMRateLimitError' detectee (substring)",
    _is_rate_limit_error(_LiteLLMRateLimitError("whatever")),
)
check(
    "rate_limit : message '429' detecte",
    _is_rate_limit_error(Exception("HTTP 429 from NIM")),
)
check(
    "rate_limit : 'rate limit' dans message",
    _is_rate_limit_error(Exception("rate limit exceeded")),
)
check(
    "rate_limit : 'too many requests' dans message",
    _is_rate_limit_error(Exception("Too Many Requests")),
)
check(
    "rate_limit : exception generique non detectee",
    not _is_rate_limit_error(ValueError("bad input")),
)
check(
    "rate_limit : timeout non detecte comme rate limit",
    not _is_rate_limit_error(TimeoutError("connection timed out")),
)


# ─── _output_looks_malformed : XML Hermes (non-regression §3) ────────────────
check(
    "malformed : <tool_call> XML Hermes detecte (had_tools=True)",
    _output_looks_malformed("<tool_call>{\"name\":\"read\"}</tool_call>", True),
)
check(
    "malformed : <function= XML Hermes detecte (had_tools=True)",
    _output_looks_malformed("<function=read_file>...</function>", True),
)
check(
    "malformed : XML Hermes ignore si had_tools=False",
    not _output_looks_malformed("<tool_call>...</tool_call>", False),
)


# ─── _output_looks_malformed : intention 0-tools courte (§3bis nouveau) ──────
# Cas reel journal 2026-04-20 : Researcher 132 chars type "Je vais lire le README".
check(
    "malformed : intention FR 'Je vais' courte + tools",
    _output_looks_malformed(
        "Je vais lire le README pour comprendre le projet puis synthetiser.",
        True,
    ),
)
check(
    "malformed : intention EN 'Let me' courte + tools",
    _output_looks_malformed(
        "Let me check the README file first to understand the project.",
        True,
    ),
)
check(
    "malformed : intention EN 'I need to' courte + tools",
    _output_looks_malformed(
        "I need to read the source files before answering.",
        True,
    ),
)
check(
    "malformed : ReAct 'Thought:' sans action, court + tools",
    _output_looks_malformed(
        "Thought: I should probably look at the main module first.",
        True,
    ),
)
check(
    "malformed : intention FR 'D'abord' courte + tools",
    _output_looks_malformed(
        "D'abord je vais lister les fichiers puis lire les plus pertinents.",
        True,
    ),
)


# ─── _output_looks_malformed : non-regression (ne pas flagger) ───────────────
# Final answer court legitime : VERDICT Critic, pas de marqueur d'intention.
check(
    "non-regression : 'VERDICT: APPROVED' court non flagge",
    not _output_looks_malformed("VERDICT: APPROVED\nLe code est propre.", True),
)
check(
    "non-regression : 'VERDICT: CHANGES_NEEDED' court non flagge",
    not _output_looks_malformed(
        "VERDICT: CHANGES_NEEDED\nFindings: imports manquants ligne 12.",
        True,
    ),
)
check(
    "non-regression : reponse technique courte sans intention non flaggee",
    not _output_looks_malformed("42", True),
)
check(
    "non-regression : code snippet court non flagge",
    not _output_looks_malformed("def foo():\n    return None", True),
)

# Intention courte SANS tools : ne doit pas etre flaggee (filtre inerte).
check(
    "non-regression : intention courte ignoree si had_tools=False",
    not _output_looks_malformed("Je vais faire X", False),
)

# Intention longue (> MALFORMED_SHORT_TEXT_MAX) : c'est probablement une reponse
# finale qui explique son raisonnement. On ne flagge pas.
long_with_intention = (
    "Je vais expliquer ce que fait ce projet. "
    + "A " * (MALFORMED_SHORT_TEXT_MAX // 2)
)
check(
    f"non-regression : intention longue (>{MALFORMED_SHORT_TEXT_MAX} chars) non flaggee",
    not _output_looks_malformed(long_with_intention, True),
    f"len={len(long_with_intention)}",
)

# Type non-str (ex: dict retourne par un modele structured output).
check(
    "non-regression : out non-str non flagge",
    not _output_looks_malformed({"answer": "x"}, True),
)


# ─── Configuration : constantes exposees coherentes ──────────────────────────
check(
    "config : RATE_LIMIT_BACKOFFS non vide",
    isinstance(RATE_LIMIT_BACKOFFS, list) and len(RATE_LIMIT_BACKOFFS) > 0,
)
check(
    "config : MALFORMED_SHORT_TEXT_MAX raisonnable (100-500)",
    100 <= MALFORMED_SHORT_TEXT_MAX <= 500,
    f"val={MALFORMED_SHORT_TEXT_MAX}",
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
