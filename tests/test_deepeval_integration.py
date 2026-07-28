"""The DeepEval bridge reuses precomputed outputs and imports nothing."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agentverity import EvidenceError, evidence_from_deepeval
from agentverity.integrations import deepeval as bridge


@dataclass
class FakeDeepEvalCase:
    input: str
    actual_output: object
    expected_output: str | None = None


def test_repeated_deepeval_cases_are_grouped_without_calling_anything():
    cases = [
        FakeDeepEvalCase("routine", "approve"),
        FakeDeepEvalCase("routine", "approve"),
        FakeDeepEvalCase("ambiguous", "review"),
        FakeDeepEvalCase("ambiguous", "deny"),
    ]

    evidence = evidence_from_deepeval(
        cases,
        expected=lambda case: case.expected_output,
        isolation="fresh-session",
    )

    assert len(evidence.cases) == 2
    assert evidence.cases[1].observations == ("review", "deny")
    assert evidence.provenance["harness"] == "deepeval"


def test_structured_outputs_use_an_explicit_decision_extractor():
    cases = [
        FakeDeepEvalCase("routine", {"route": "approve"}),
        FakeDeepEvalCase("routine", {"route": "approve"}),
    ]

    evidence = evidence_from_deepeval(
        cases,
        decision=lambda output: output["route"],
    )

    assert evidence.cases[0].observations == ("approve", "approve")


def test_missing_outputs_are_recorded_as_errors_not_passing_observations():
    cases = [
        FakeDeepEvalCase("routine", "approve"),
        FakeDeepEvalCase("routine", None),
        FakeDeepEvalCase("routine", "approve"),
    ]

    evidence = evidence_from_deepeval(cases)

    assert evidence.cases[0].errors == 1


def test_one_usable_output_is_refused():
    with pytest.raises(EvidenceError, match="run each case at least twice"):
        evidence_from_deepeval(
            [
                FakeDeepEvalCase("routine", "approve"),
                FakeDeepEvalCase("routine", None),
            ]
        )


def test_free_text_requires_a_decision_extractor_when_not_a_string():
    with pytest.raises(EvidenceError, match="provide decision="):
        evidence_from_deepeval(
            [
                FakeDeepEvalCase("routine", object()),
                FakeDeepEvalCase("routine", object()),
            ]
        )


def test_inconsistent_expected_decisions_are_refused():
    cases = [
        FakeDeepEvalCase("routine", "approve", "approve"),
        FakeDeepEvalCase("routine", "approve", "deny"),
    ]
    with pytest.raises(EvidenceError, match="disagree on the intended"):
        evidence_from_deepeval(
            cases,
            expected=lambda case: case.expected_output,
        )


def test_invalid_inputs_and_expected_labels_are_refused():
    with pytest.raises(EvidenceError, match="no non-empty string input"):
        evidence_from_deepeval([FakeDeepEvalCase("", "approve")])

    cases = [
        FakeDeepEvalCase("routine", "approve", ""),
        FakeDeepEvalCase("routine", "approve", ""),
    ]
    with pytest.raises(EvidenceError, match="invalid intended decision"):
        evidence_from_deepeval(cases, expected=lambda case: case.expected_output)


def test_empty_input_collection_is_refused():
    with pytest.raises(EvidenceError, match="contains no test cases"):
        evidence_from_deepeval([])


def test_provenance_is_extended_without_a_deepeval_install(monkeypatch):
    def missing(_name):
        raise bridge.PackageNotFoundError

    monkeypatch.setattr(bridge, "version", missing)
    evidence = evidence_from_deepeval(
        [
            FakeDeepEvalCase("routine", "approve"),
            FakeDeepEvalCase("routine", "approve"),
        ],
        provenance={"model": "local"},
    )

    assert evidence.provenance == {"harness": "deepeval", "model": "local"}
