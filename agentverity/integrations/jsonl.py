"""Read repeated decisions from a JSONL file any harness can produce.

The Promptfoo and DeepEval bridges each understand one tool's export. This one
understands nothing: it reads a line per run, and the caller says which fields
carry the input and the decision. That covers a harness with no bridge, a
production log, and a CSV converted to JSONL, which between them are most of
the evidence teams already hold.

The line is the unit, deliberately. A file of aggregates cannot be assessed,
and a file of grouped arrays hides whether two entries were separate runs or
one run reported twice. One line per run leaves the ordering visible, and
ordering is what disjoint pairing depends on.

Example::

    {"input": "charged twice for 4471", "decision": "billing"}
    {"input": "charged twice for 4471", "decision": "card_security"}

    from agentverity.integrations.jsonl import evidence_from_jsonl
    evidence = evidence_from_jsonl(lines, suite=suite)

Order matters. Runs of the same input are paired in the order they appear, so
a file sorted by decision reports a stability that the run never had.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ..decision import NO_DECISION_REASONS, NoDecision
from ..decision_contract import DecisionSuite
from ..evidence import EvidenceCase, EvidenceError, EvidenceSet


def _dig(row: Mapping[str, Any], path: str) -> Any:
    """Read a dotted path out of one row, or raise saying which part failed."""
    value: Any = row
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise EvidenceError(
                f"no {path!r} in this line; {part!r} is missing. Name the "
                "field with --input-path or --decision-path."
            )
        value = value[part]
    return value


def _observation(value: Any, line_number: int) -> Any:
    """Read one recorded decision, typed or plain."""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    if isinstance(value, Mapping):
        if value.get("kind") != "no_decision":
            raise EvidenceError(
                f"line {line_number}: an object decision records a no-decision "
                f"and needs 'kind': 'no_decision', got {value.get('kind')!r}"
            )
        reason = value.get("reason")
        if not isinstance(reason, str) or reason not in NO_DECISION_REASONS:
            raise EvidenceError(
                f"line {line_number}: unknown no-decision reason {reason!r}; "
                f"expected one of {', '.join(sorted(NO_DECISION_REASONS))}"
            )
        return NoDecision(reason)
    raise EvidenceError(
        f"line {line_number}: a decision must be a string, a list of tool "
        f"names, or a no-decision object, got {type(value).__name__}"
    )


def evidence_from_jsonl(
    lines: Iterable[str],
    *,
    suite: DecisionSuite | None = None,
    input_path: str = "input",
    decision_path: str = "decision",
    layer: str = "verdict",
    isolation: str = "unknown",
) -> EvidenceSet:
    """Read one line per run into an evidence set.

    Args:
        lines: An iterable of JSON objects, one per run, in the order produced.
        suite: Optional declared suite. When given, each case's `expected` is
            taken from it by matching the input, so a route the suite names is
            identifiable even when the agent answered it wrongly.
        input_path: Dotted path to the probe text. Runs sharing it are one case.
        decision_path: Dotted path to the recorded decision.
        layer: The layer the decisions represent.
        isolation: How the runs were separated. Left `unknown` unless the
            caller can state it, and reported rather than assumed.

    Returns:
        An `EvidenceSet` in the order the file gave, ready to assess.

    Raises:
        EvidenceError: If a line is not an object, a named path is absent, or a
            decision is a shape no run produces.
    """
    expected_for = {}
    if suite is not None:
        if not isinstance(suite, DecisionSuite):
            raise TypeError("jsonl import requires a DecisionSuite")
        expected_for = {case.input: case.expected for case in suite.cases}

    grouped: dict[str, list[Any]] = {}
    for number, raw in enumerate(lines, start=1):
        text = raw.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise EvidenceError(f"line {number} is not valid JSON: {exc}") from exc
        if not isinstance(row, Mapping):
            raise EvidenceError(
                f"line {number} is {type(row).__name__}, not an object. One "
                "JSON object per run, in the order they were produced."
            )
        probe = _dig(row, input_path)
        if not isinstance(probe, str) or not probe.strip():
            raise EvidenceError(
                f"line {number}: {input_path!r} must be a non-empty string"
            )
        grouped.setdefault(probe, []).append(
            _observation(_dig(row, decision_path), number)
        )

    if not grouped:
        raise EvidenceError(
            "no runs found. Expected one JSON object per line, each carrying "
            f"{input_path!r} and {decision_path!r}."
        )

    thin = [probe for probe, runs in grouped.items() if len(runs) < 2]
    if thin:
        raise EvidenceError(
            f"{len(thin)} input(s) appear once, so no comparison can be formed "
            f"from them, starting with {thin[0]!r}. Stability is a property of "
            "repeats: a single run per input tells you what happened once."
        )

    return EvidenceSet(
        cases=tuple(
            EvidenceCase(
                input=probe,
                observations=tuple(runs),
                expected=expected_for.get(probe),
            )
            for probe, runs in grouped.items()
        ),
        layer=layer,
        isolation=isolation,
    )


def load_jsonl(path: str | Path, **kwargs: Any) -> EvidenceSet:
    """Read a JSONL file from disk. See `evidence_from_jsonl` for the options."""
    with Path(path).open(encoding="utf-8") as handle:
        return evidence_from_jsonl(handle, **kwargs)
