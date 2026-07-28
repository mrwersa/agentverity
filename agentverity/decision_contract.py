"""Declared decision contracts and structured test suites.

The blindness scan answers a minimum dynamic question: did one observed
decision dominate the probe set? A declared contract answers a different
question: did the test designer include every required decision, did the agent
produce them, and did it emit anything outside the allowed set?

This module deliberately does not score per-case correctness. A quality
evaluator or reviewed assertion still owns that judgement.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DECISION_SUITE_SCHEMA = "agentverity.decision-suite/v1"


def _normalise_labels(value: Any, *, field_name: str) -> frozenset[str]:
    """Return a validated immutable set of non-empty decision labels."""
    if isinstance(value, str):
        raise TypeError(f"{field_name} must be a collection of decision labels")
    try:
        labels = frozenset(value)
    except TypeError as exc:
        raise TypeError(f"{field_name} must be a collection of strings") from exc
    if any(not isinstance(label, str) or not label.strip() for label in labels):
        raise ValueError(f"{field_name} must contain non-empty strings")
    return labels


@dataclass(frozen=True)
class DecisionContract:
    """The finite decision universe an application asks a suite to exercise.

    ``allowed`` defines the complete known label set. ``required`` defaults to
    every allowed label but can omit genuinely optional routes. ``critical``
    records the high-consequence subset for reporting and future policy
    extensions. Version 0.9 does not assign a separate statistical threshold
    to critical labels.
    """

    allowed: frozenset[str]
    required: frozenset[str] | None = None
    critical: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        allowed = _normalise_labels(self.allowed, field_name="allowed")
        required = (
            allowed
            if self.required is None
            else _normalise_labels(self.required, field_name="required")
        )
        critical = _normalise_labels(self.critical, field_name="critical")
        if not allowed:
            raise ValueError("allowed must contain at least one decision")
        if not required:
            raise ValueError("required must contain at least one decision")
        if not required <= allowed:
            unknown = ", ".join(sorted(required - allowed))
            raise ValueError(f"required decisions are not allowed: {unknown}")
        if not critical <= required:
            unknown = ", ".join(sorted(critical - required))
            raise ValueError(f"critical decisions must also be required: {unknown}")
        object.__setattr__(self, "allowed", allowed)
        object.__setattr__(self, "required", required)
        object.__setattr__(self, "critical", critical)

    def to_dict(self) -> dict[str, list[str]]:
        """Return a stable JSON-compatible representation."""
        assert self.required is not None
        return {
            "allowed": sorted(self.allowed),
            "required": sorted(self.required),
            "critical": sorted(self.critical),
        }

    @classmethod
    def from_dict(cls, value: Any) -> DecisionContract:
        """Parse a contract from a JSON-compatible mapping."""
        if not isinstance(value, dict):
            raise TypeError("decision contract must be an object")
        try:
            return cls(
                allowed=value["allowed"],
                required=value.get("required"),
                critical=value.get("critical", ()),
            )
        except KeyError as exc:
            raise ValueError("decision contract is missing 'allowed'") from exc


@dataclass(frozen=True)
class DecisionCase:
    """One test input and the decision the test designer intends it to reach."""

    input: str
    expected: str

    def __post_init__(self) -> None:
        if not isinstance(self.input, str) or not self.input.strip():
            raise ValueError("case input must be a non-empty string")
        if not isinstance(self.expected, str) or not self.expected.strip():
            raise ValueError("case expected decision must be a non-empty string")

    def to_dict(self) -> dict[str, str]:
        """Return the portable representation used by decision-suite files."""
        return {"input": self.input, "expected": self.expected}


@dataclass(frozen=True)
class DecisionSuite:
    """A declared contract plus the reviewed cases intended to exercise it."""

    contract: DecisionContract
    cases: tuple[DecisionCase, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.contract, DecisionContract):
            raise TypeError("decision suite contract must be a DecisionContract")
        cases = tuple(self.cases)
        if not cases:
            raise ValueError("decision suite must contain at least one case")
        if any(not isinstance(case, DecisionCase) for case in cases):
            raise TypeError("decision suite cases must be DecisionCase values")
        inputs = [case.input for case in cases]
        duplicates = sorted(
            text for text, count in Counter(inputs).items() if count > 1
        )
        if duplicates:
            shown = ", ".join(repr(value) for value in duplicates[:3])
            raise ValueError(f"decision suite contains duplicate inputs: {shown}")
        unexpected = sorted(
            {case.expected for case in cases} - self.contract.allowed
        )
        if unexpected:
            raise ValueError(
                "case expectations are outside the allowed contract: "
                + ", ".join(unexpected)
            )
        object.__setattr__(self, "cases", cases)

    @property
    def inputs(self) -> tuple[str, ...]:
        """Raw target inputs in suite order."""
        return tuple(case.input for case in self.cases)

    @property
    def expected(self) -> tuple[str, ...]:
        """Intended decision labels in suite order."""
        return tuple(case.expected for case in self.cases)

    @property
    def missing_required_cases(self) -> tuple[str, ...]:
        """Required decisions with no intended case in the suite."""
        assert self.contract.required is not None
        return tuple(
            sorted(self.contract.required - frozenset(self.expected))
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned, portable suite representation."""
        return {
            "schema": DECISION_SUITE_SCHEMA,
            "contract": self.contract.to_dict(),
            "cases": [case.to_dict() for case in self.cases],
        }

    @classmethod
    def from_dict(cls, value: Any) -> DecisionSuite:
        """Parse and validate a versioned decision suite."""
        if not isinstance(value, dict):
            raise TypeError("decision suite root must be an object")
        if value.get("schema") != DECISION_SUITE_SCHEMA:
            raise ValueError(
                f"unsupported decision suite schema: {value.get('schema')!r}"
            )
        raw_cases = value.get("cases")
        if not isinstance(raw_cases, list):
            raise TypeError("decision suite cases must be a list")
        try:
            cases = tuple(
                DecisionCase(
                    input=case["input"],
                    expected=case["expected"],
                )
                for case in raw_cases
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid decision case: {exc}") from exc
        return cls(
            contract=DecisionContract.from_dict(value.get("contract")),
            cases=cases,
        )


@dataclass(frozen=True)
class DecisionCount:
    """One decision label and its number of intended or observed cases."""

    decision: str
    count: int


@dataclass(frozen=True)
class DecisionCoverageResult:
    """Intended and observed coverage of one declared decision contract."""

    contract: DecisionContract
    intended_counts: tuple[DecisionCount, ...]
    observed_counts: tuple[DecisionCount, ...]
    missing_intended: tuple[str, ...]
    missing_observed: tuple[str, ...]
    unknown_observed: tuple[str, ...]

    @property
    def satisfied(self) -> bool:
        """Whether all required decisions were intended and observed."""
        return not (
            self.missing_intended
            or self.missing_observed
            or self.unknown_observed
        )

    @property
    def intended_coverage(self) -> float:
        """Share of required decisions represented by reviewed cases."""
        assert self.contract.required is not None
        return (
            len(self.contract.required) - len(self.missing_intended)
        ) / len(self.contract.required)

    @property
    def observed_coverage(self) -> float:
        """Share of required decisions returned at least once by the target."""
        assert self.contract.required is not None
        return (
            len(self.contract.required) - len(self.missing_observed)
        ) / len(self.contract.required)

    @property
    def missing_critical(self) -> tuple[str, ...]:
        """Critical decisions absent from cases or observations."""
        missing = set(self.missing_intended) | set(self.missing_observed)
        return tuple(sorted(missing & self.contract.critical))

    @property
    def advice(self) -> str:
        """A concise next action for the contract result."""
        if self.missing_intended:
            return (
                "add reviewed cases for required decisions: "
                + ", ".join(self.missing_intended)
            )
        if self.unknown_observed:
            return (
                "the agent emitted decisions outside the contract: "
                + ", ".join(self.unknown_observed)
            )
        if self.missing_observed:
            return (
                "required decisions were represented by cases but not returned: "
                + ", ".join(self.missing_observed)
            )
        return "all required decisions were represented and observed"


def assess_decision_coverage(
    suite: DecisionSuite,
    observed: tuple[Any | None, ...],
    *,
    all_observed: tuple[Any | None, ...] | None = None,
) -> DecisionCoverageResult:
    """Compare intended and observed decisions without judging correctness.

    ``observed`` contains one primary result per case and therefore drives
    route counts and required-route coverage. ``all_observed`` may include
    repeated trials. It is used to detect any out-of-contract label without
    making repeated calls look like additional test cases.
    """
    if len(observed) != len(suite.cases):
        raise ValueError("observed decisions must align with decision suite cases")
    primary_labels = [
        value if isinstance(value, str) else f"<non-string:{type(value).__name__}>"
        for value in observed
        if value is not None
    ]
    every_label = [
        value if isinstance(value, str) else f"<non-string:{type(value).__name__}>"
        for value in (all_observed if all_observed is not None else observed)
        if value is not None
    ]
    intended_counter = Counter(suite.expected)
    observed_counter = Counter(primary_labels)
    required = suite.contract.required
    assert required is not None
    return DecisionCoverageResult(
        contract=suite.contract,
        intended_counts=tuple(
            DecisionCount(decision, intended_counter[decision])
            for decision in sorted(intended_counter)
        ),
        observed_counts=tuple(
            DecisionCount(decision, observed_counter[decision])
            for decision in sorted(observed_counter)
        ),
        missing_intended=tuple(
            sorted(required - frozenset(intended_counter))
        ),
        missing_observed=tuple(
            sorted(required - frozenset(observed_counter))
        ),
        unknown_observed=tuple(
            sorted(frozenset(every_label) - suite.contract.allowed)
        ),
    )


def load_decision_suite(path: str | Path) -> DecisionSuite:
    """Load a versioned decision suite from UTF-8 JSON."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load decision suite: {exc}") from exc
    return DecisionSuite.from_dict(value)


def save_decision_suite(suite: DecisionSuite, path: str | Path) -> None:
    """Write a versioned decision suite as formatted UTF-8 JSON."""
    Path(path).write_text(
        json.dumps(suite.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
