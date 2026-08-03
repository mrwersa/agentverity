"""Assess evidence a run collected somewhere else.

Most teams already run their agent repeatedly through a harness they chose:
promptfoo, DeepEval, LangSmith, a bespoke script. Asking them to run it again
through this package to get an admission decision doubles the bill for the same
information. This module reads the observations they already have.

What imported evidence supports and what it cannot:

- The meter, blindness, declared coverage, and per-route stability all work,
  because every one of those is a measurement over recorded decisions.
- Metamorphic relations do not. A relation transforms an input and asks the
  agent the transformed question, which needs calls nobody has made. An
  assessment from imported evidence reports no relation results rather than
  pretending the ones it did not run held.

The schema deliberately refuses aggregates. A flip rate cannot be turned back
into the disjoint pairs it came from, and an average over a suite cannot be
split by route. Individual observations, grouped by case and kept in order,
are the minimum that supports the analysis this package exists to do.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .decision import NO_DECISION_REASONS, Decision, NoDecision
from .observation import Observation

EVIDENCE_SCHEMA = "agentverity.evidence/v1"

LAYERS = ("verdict", "text", "tools")

# How the producer separated one trial from the next. Recorded rather than
# inferred, because the statistics assume independent trials and an imported
# file can violate that in ways a self-run cannot: a shared conversation, a
# warm provider cache, one session reused across repeats. A reader deserves to
# know which of those applied.
ISOLATION_LEVELS = (
    "fresh-session",
    "fresh-instance",
    "shared-session",
    "unknown",
)


class EvidenceError(ValueError):
    """Raised when an evidence file cannot support an assessment."""


@dataclass(frozen=True)
class EvidenceCase:
    """One input and the decisions observed across repeated runs of it."""

    input: str
    observations: tuple[str | tuple[str, ...] | Decision | NoDecision, ...]
    expected: str | None = None
    errors: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.input, str) or not self.input.strip():
            raise EvidenceError("case input must be a non-empty string")

        observations = tuple(
            tuple(value) if isinstance(value, list) else value
            for value in self.observations
        )
        if len(observations) < 2:
            raise EvidenceError(
                f"case {self.input!r} carries {len(observations)} observation(s); "
                "at least two are needed to form one comparison"
            )
        if any(
            not isinstance(value, (str, tuple, Decision, NoDecision))
            or (
                isinstance(value, tuple)
                and any(not isinstance(item, str) for item in value)
            )
            for value in observations
        ):
            raise EvidenceError(
                f"case {self.input!r} has an unsupported observation; record a "
                "decision or text as a string, a tool path as a string list, or "
                "a typed Decision or NoDecision"
            )
        if self.expected is not None and (
            not isinstance(self.expected, str) or not self.expected.strip()
        ):
            raise EvidenceError("case expected decision must be a non-empty string")
        if not isinstance(self.errors, int) or self.errors < 0:
            raise EvidenceError("case errors must be a non-negative integer")
        object.__setattr__(self, "observations", observations)

    @property
    def usable_pairs(self) -> int:
        """Disjoint comparisons this case contributes.

        An odd observation is unused, because pairs must not overlap. Sixteen
        observations give eight comparisons, and so do seventeen.
        """
        return len(self.observations) // 2

    def to_observations(self, layer: str) -> tuple[Observation, ...]:
        """Render recorded values at the layer the evidence declares."""
        if layer == "tools":
            if any(not isinstance(value, tuple) for value in self.observations):
                raise EvidenceError(
                    f"case {self.input!r}: tools observations must be lists of "
                    "tool names"
                )
            return tuple(
                Observation(tools=value)
                for value in self.observations
                if isinstance(value, tuple)
            )
        # The text layer needs actual text. A typed outcome carries none, so it
        # is only meaningful on the verdict layer.
        allowed = (str,) if layer == "text" else (str, Decision, NoDecision)
        if any(not isinstance(value, allowed) for value in self.observations):
            raise EvidenceError(
                f"case {self.input!r}: {layer} observations must be strings"
                + ("" if layer == "text" else " or typed outcomes")
            )
        if layer == "text":
            return tuple(
                Observation(text=value)
                for value in self.observations
                if isinstance(value, str)
            )
        return tuple(
            Observation(text=value if isinstance(value, str) else "", verdict=value)
            for value in self.observations
            if isinstance(value, (str, Decision, NoDecision))
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "input": self.input,
            "observations": [
                _encode_observation(value) for value in self.observations
            ],
        }
        if self.expected is not None:
            payload["expected"] = self.expected
        if self.errors:
            payload["errors"] = self.errors
        return payload


@dataclass(frozen=True)
class EvidenceSet:
    """Recorded observations from a run this package did not make."""

    cases: tuple[EvidenceCase, ...]
    layer: str = "verdict"
    isolation: str = "unknown"
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cases = tuple(self.cases)
        if not cases:
            raise EvidenceError("evidence must contain at least one case")
        if any(not isinstance(case, EvidenceCase) for case in cases):
            raise EvidenceError("evidence cases must be EvidenceCase values")
        seen: set[str] = set()
        for case in cases:
            if case.input in seen:
                raise EvidenceError(f"duplicate case input: {case.input!r}")
            seen.add(case.input)
        if self.layer not in LAYERS:
            raise EvidenceError(
                f"unknown observation layer {self.layer!r}; expected one of "
                + ", ".join(LAYERS)
            )
        if self.isolation not in ISOLATION_LEVELS:
            raise EvidenceError(
                f"unknown isolation {self.isolation!r}; expected one of "
                + ", ".join(ISOLATION_LEVELS)
            )
        for case in cases:
            case.to_observations(self.layer)
        object.__setattr__(self, "cases", cases)

    @property
    def inputs(self) -> tuple[str, ...]:
        return tuple(case.input for case in self.cases)

    @property
    def intended(self) -> tuple[str | None, ...]:
        return tuple(case.expected for case in self.cases)

    @property
    def total_pairs(self) -> int:
        return sum(case.usable_pairs for case in self.cases)

    @property
    def independence_caveat(self) -> str | None:
        """A warning when the recorded isolation undermines the statistics."""
        if self.isolation == "shared-session":
            return (
                "trials came from one shared session, so repeats are not "
                "independent and the interval is narrower than the evidence "
                "supports"
            )
        if self.isolation == "unknown":
            return (
                "the file does not record how trials were isolated, so "
                "independence is assumed rather than established"
            )
        return None


    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": EVIDENCE_SCHEMA,
            "layer": self.layer,
            "isolation": self.isolation,
            "cases": [case.to_dict() for case in self.cases],
        }
        if self.provenance:
            payload["provenance"] = dict(sorted(self.provenance.items()))
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> EvidenceSet:
        """Parse a versioned evidence file, refusing aggregates."""
        if not isinstance(value, dict):
            raise EvidenceError("evidence root must be an object")
        schema = value.get("schema")
        if schema != EVIDENCE_SCHEMA:
            raise EvidenceError(
                f"unsupported evidence schema: {schema!r}; this build reads "
                f"{EVIDENCE_SCHEMA}"
            )
        raw_cases = value.get("cases")
        if not isinstance(raw_cases, list):
            raise EvidenceError("evidence cases must be a list")

        cases = []
        for index, entry in enumerate(raw_cases):
            if not isinstance(entry, dict):
                raise EvidenceError(f"cases[{index}] must be an object")
            if "observations" not in entry:
                # The common shape of an exported summary. Saying why it cannot
                # work matters more than saying that it cannot.
                raise EvidenceError(
                    f"cases[{index}] has no 'observations'. A flip rate or pass "
                    "count cannot be assessed: disjoint pairs cannot be "
                    "recovered from an average, and a pooled number cannot be "
                    "split by route. Export the individual decisions per case."
                )
            observations = entry["observations"]
            if not isinstance(observations, list):
                raise EvidenceError(
                    f"cases[{index}]: observations must be a list of decisions "
                    "in the order they were produced"
                )
            cases.append(
                EvidenceCase(
                    input=entry.get("input", ""),
                    observations=tuple(
                        _decode_observation(item, index) for item in observations
                    ),
                    expected=entry.get("expected"),
                    errors=entry.get("errors", 0),
                )
            )

        provenance = value.get("provenance", {}) or {}
        if not isinstance(provenance, dict):
            raise EvidenceError("provenance must be an object")
        return cls(
            cases=tuple(cases),
            layer=value.get("layer", "verdict"),
            isolation=value.get("isolation", "unknown"),
            provenance=provenance,
        )


def load_evidence(path: str | Path) -> EvidenceSet:
    """Read an evidence file from disk."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot load evidence: {exc}") from exc
    return EvidenceSet.from_dict(value)



def _encode_observation(value: Any) -> Any:
    """Write one observation, in the smallest form that stays unambiguous.

    A decision is a bare string, whether it arrived as one or as a
    ``Decision``. The two are the same decision and comparison treats them as
    one, so tagging both would triple the size of a repeat-heavy file to record
    a distinction nothing acts on.

    A no-decision is an object, because its reason must not be confused with a
    label of the same name. So the reading rule is one line: a string is a
    decision, an object is a no-decision and says why.
    """
    if isinstance(value, Decision):
        return value.label
    if isinstance(value, NoDecision):
        return {"kind": "no_decision", "reason": value.reason}
    return list(value) if isinstance(value, tuple) else value


def _decode_observation(value: Any, index: int) -> Any:
    """Read one observation.

    A bare string is accepted and stays a bare string, because a hand-written
    file may reasonably carry plain labels and comparison normalises the two
    anyway. Written files always tag.
    """
    if not isinstance(value, dict):
        return value
    kind = value.get("kind")
    if kind == "no_decision":
        reason = value.get("reason")
        if not isinstance(reason, str) or reason not in NO_DECISION_REASONS:
            raise EvidenceError(
                f"cases[{index}]: unknown no-decision reason {reason!r}; "
                f"expected one of {', '.join(sorted(NO_DECISION_REASONS))}"
            )
        return NoDecision(reason)
    raise EvidenceError(
        f"cases[{index}]: an observation object records a no-decision and "
        f"needs 'kind': 'no_decision', got {kind!r}. A decision is written as "
        "a plain string."
    )


def save_evidence(evidence: EvidenceSet, path: str | Path) -> None:
    """Write an evidence file as formatted UTF-8 JSON."""
    Path(path).write_text(
        json.dumps(evidence.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def assess_evidence(
    evidence: EvidenceSet,
    suite: Any | None = None,
    *,
    epsilon: float = 0.05,
) -> Any:
    """Apply the admission checks to observations collected elsewhere.

    Returns the same ``RunResult`` a live run produces, so the report, JSON,
    JUnit, OpenTelemetry, and snapshot paths all work unchanged.

    Relation results are empty. A relation needs the agent to answer a
    transformed question, and no such calls exist in an imported file. Leaving
    them empty is the honest outcome: claiming a relation held when it never
    ran is exactly the vacuous green this package exists to name.

    Args:
        evidence: Recorded observations, grouped per case.
        suite: Optional declared decision suite. Its case inputs must match the
            evidence, so a contract is never checked against a different run.
        epsilon: Default flip-rate tolerance.

    Raises:
        EvidenceError: If a declared suite does not describe this evidence.
    """
    from .blindness import score as blindness_score
    from .decision_contract import assess_decision_coverage
    from .execution import RunError, input_fingerprint
    from .meter import score_runs
    from .runner import RunConfig, RunResult
    from .stratified import stratify_runs

    series = [case.to_observations(evidence.layer) for case in evidence.cases]
    intended: tuple[str, ...] = ()
    targets: dict[str, float] = {}

    if suite is not None:
        if tuple(suite.inputs) != evidence.inputs:
            raise EvidenceError(
                "the declared suite does not describe this evidence: its case "
                "inputs differ. A contract checked against a different run "
                "would report coverage the run never had."
            )
        intended = suite.expected
        targets = dict(suite.contract.stability_targets)
    elif all(case.expected is not None for case in evidence.cases):
        intended = tuple(case.expected or "" for case in evidence.cases)

    meter_result = score_runs(
        series,
        k=min(len(item) for item in series),
        layer=evidence.layer,
        epsilon=epsilon,
    )
    first_observations = [item[0] for item in series]
    blindness_result = blindness_score(first_observations, layer=evidence.layer)

    route_stability = None
    if intended:
        route_stability = stratify_runs(
            list(zip(intended, series, strict=True)),
            k=min(len(item) for item in series),
            layer=evidence.layer,
            epsilon=epsilon,
            targets=targets,
        )

    decision_coverage = None
    if suite is not None:
        observed = tuple(item[0].key(evidence.layer) for item in series)
        decision_coverage = assess_decision_coverage(
            suite,
            observed,
            all_observed=tuple(
                observation.key(evidence.layer)
                for item in series
                for observation in item
            ),
            per_case=tuple(
                tuple(observation.key(evidence.layer) for observation in item)
                for item in series
            ),
        )

    repeats = min(len(item) for item in series)
    errors = tuple(
        RunError(
            phase="imported-evidence",
            input_index=index,
            input_fingerprint=input_fingerprint(case.input),
            exception_type="ImportedExecutionError",
            message="a recorded run failed before producing a decision",
        )
        for index, case in enumerate(evidence.cases)
        for _ in range(case.errors)
    )
    observed_keys = tuple(item[0].key(evidence.layer) for item in series)
    return RunResult(
        config=RunConfig(
            k=repeats,
            epsilon=epsilon,
            layer=evidence.layer,
            run_meter=True,
            run_blindness=True,
            error_policy="record",
        ),
        meter=meter_result,
        blindness=blindness_result,
        relation_results=[],
        decision_coverage=decision_coverage,
        route_stability=route_stability,
        errors=errors,
        caveats=(
            (evidence.independence_caveat,)
            if evidence.independence_caveat is not None
            else ()
        ),
        input_fingerprints=tuple(
            input_fingerprint(case.input) for case in evidence.cases
        ),
        observed_keys=observed_keys,
        intended_decisions=intended,
        requested_inputs=len(evidence.cases),
    )
