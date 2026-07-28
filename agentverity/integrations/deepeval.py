"""Build evidence from repeated DeepEval test cases without another agent run."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from agentverity.evidence import EvidenceCase, EvidenceError, EvidenceSet


def _deepeval_version() -> str | None:
    try:
        return version("deepeval")
    except PackageNotFoundError:
        return None


def evidence_from_deepeval(
    test_cases: Iterable[Any],
    *,
    decision: Callable[[Any], str] | None = None,
    expected: Callable[[Any], str | None] | None = None,
    isolation: str = "unknown",
    provenance: dict[str, Any] | None = None,
) -> EvidenceSet:
    """Group repeated ``LLMTestCase`` objects into AgentVerity evidence.

    DeepEval evaluates the quality of each ``actual_output``. AgentVerity
    consumes the same precomputed outputs to ask whether the categorical
    decision is stable and whether the suite reaches its declared routes.
    This helper deliberately uses structural typing and has no DeepEval runtime
    dependency.

    Args:
        test_cases: Repeated DeepEval ``LLMTestCase``-like objects. Each must
            expose ``input`` and ``actual_output``.
        decision: Optional extractor from ``actual_output`` to a decision label.
            Without one, the output itself must be a string label.
        expected: Optional extractor from a test case to its intended decision.
            Prefer passing a reviewed ``DecisionSuite`` to ``assess_evidence``.
        isolation: How repeated calls were separated.
        provenance: Additional source metadata.
    """
    grouped: dict[str, list[str]] = {}
    expected_by_input: dict[str, str | None] = {}
    errors: dict[str, int] = {}

    for index, test_case in enumerate(test_cases):
        input_value = getattr(test_case, "input", None)
        if not isinstance(input_value, str) or not input_value.strip():
            raise EvidenceError(
                f"DeepEval test case {index} has no non-empty string input"
            )
        grouped.setdefault(input_value, [])
        errors.setdefault(input_value, 0)

        output = getattr(test_case, "actual_output", None)
        if output is None:
            errors[input_value] += 1
            continue
        label = decision(output) if decision is not None else output
        if not isinstance(label, str) or not label.strip():
            raise EvidenceError(
                f"DeepEval test case {index} did not yield a non-empty decision "
                "label; provide decision= for structured or free-text outputs"
            )
        grouped[input_value].append(label)

        intended = expected(test_case) if expected is not None else None
        if intended is not None:
            if not isinstance(intended, str) or not intended.strip():
                raise EvidenceError(
                    f"DeepEval test case {index} has an invalid intended decision"
                )
            prior = expected_by_input.setdefault(input_value, intended)
            if prior != intended:
                raise EvidenceError(
                    f"DeepEval repeats for {input_value!r} disagree on the "
                    "intended decision"
                )
        else:
            expected_by_input.setdefault(input_value, None)

    if not grouped:
        raise EvidenceError("DeepEval evidence contains no test cases")

    cases = []
    for input_value, observations in grouped.items():
        if len(observations) < 2:
            raise EvidenceError(
                f"DeepEval input {input_value!r} has {len(observations)} usable "
                "observation(s); run each case at least twice"
            )
        cases.append(
            EvidenceCase(
                input=input_value,
                observations=tuple(observations),
                expected=expected_by_input[input_value],
                errors=errors[input_value],
            )
        )

    source = {"harness": "deepeval"}
    installed = _deepeval_version()
    if installed is not None:
        source["harness_version"] = installed
    source.update(provenance or {})
    return EvidenceSet(
        cases=tuple(cases),
        isolation=isolation,
        provenance=source,
    )
