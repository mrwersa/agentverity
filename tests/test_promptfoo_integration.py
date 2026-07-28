"""Promptfoo exports feed the same admission checks without another call."""

from __future__ import annotations

import json

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    EvidenceError,
    assess_evidence,
    evidence_from_promptfoo,
    load_promptfoo,
)


def suite():
    return DecisionSuite(
        contract=DecisionContract(allowed={"approve", "review"}),
        cases=(
            DecisionCase("routine request", "approve"),
            DecisionCase("ambiguous request", "review"),
        ),
    )


def row(test_index, output=None, *, provider="local", prompt_id="router", **extra):
    case_input = suite().cases[test_index % 2].input
    response = {} if output is None else {"output": output}
    return {
        "testIdx": test_index,
        "promptIdx": 0,
        "promptId": prompt_id,
        "provider": {"id": provider},
        "prompt": {"raw": case_input},
        "response": response,
        "failureReason": 0,
        **extra,
    }


def export(*rows):
    return {
        "version": 3,
        "timestamp": "2026-07-28T12:00:00Z",
        "results": list(rows),
    }


def test_promptfoo_repeats_are_assessed_without_reinvoking_the_target():
    payload = export(
        row(0, "approve"),
        row(0, "approve"),
        row(1, "review"),
        row(1, "approve"),
    )

    evidence = evidence_from_promptfoo(payload, suite())
    result = assess_evidence(evidence, suite(), epsilon=0.5)

    assert evidence.provenance["harness"] == "promptfoo"
    assert result.meter.pair_flips == 1
    assert result.route_stability.flip_pairs[0].decisions == ("approve", "review")


def test_current_promptfoo_repeat_indices_are_mapped_by_rendered_input():
    payload = {
        "evalId": "eval-example",
        "results": {
            "version": 4,
            "timestamp": "2026-07-28T12:00:00Z",
            "results": [
                row(0, "approve"),
                row(2, "approve"),
                row(1, "review"),
                row(3, "review"),
            ],
        },
    }

    evidence = evidence_from_promptfoo(payload, suite())

    assert evidence.cases[0].observations == ("approve", "approve")
    assert evidence.cases[1].observations == ("review", "review")
    assert evidence.provenance["export_version"] == 4
    assert evidence.provenance["collected_at"] == "2026-07-28T12:00:00Z"


def test_assertion_failures_remain_observations_because_promptfoo_owns_correctness():
    payload = export(
        row(0, "approve", success=False),
        row(0, "approve", success=False),
        row(1, "review"),
        row(1, "review"),
    )
    evidence = evidence_from_promptfoo(payload, suite())

    assert evidence.cases[0].observations == ("approve", "approve")
    assert evidence.cases[0].errors == 0


def test_provider_errors_make_evidence_incomplete():
    payload = export(
        row(0, "approve"),
        row(0, "approve"),
        row(0, error="timeout", failureReason=2),
        row(1, "review"),
        row(1, "review"),
    )
    evidence = evidence_from_promptfoo(payload, suite())
    result = assess_evidence(evidence, suite(), epsilon=0.5)

    assert evidence.cases[0].errors == 1
    assert result.status == "incomplete"


def test_structured_outputs_use_a_dot_path():
    payload = export(
        row(0, {"decision": {"route": "approve"}}),
        row(0, '{"decision":{"route":"approve"}}'),
        row(1, {"decision": {"route": "review"}}),
        row(1, {"decision": {"route": "review"}}),
    )
    evidence = evidence_from_promptfoo(
        payload,
        suite(),
        decision_path="decision.route",
    )

    assert evidence.cases[0].observations == ("approve", "approve")


def test_a_custom_input_path_maps_structured_promptfoo_cases():
    payload = export(
        row(0, "approve", vars={"ticket": "routine request"}),
        row(2, "approve", vars={"ticket": "routine request"}),
        row(1, "review", vars={"ticket": "ambiguous request"}),
        row(3, "review", vars={"ticket": "ambiguous request"}),
    )
    evidence = evidence_from_promptfoo(payload, suite(), input_path="vars.ticket")

    assert evidence.cases[1].observations == ("review", "review")


def test_a_provider_prompt_matrix_is_refused_until_one_cell_is_selected():
    payload = export(
        row(0, "approve", provider="a"),
        row(0, "approve", provider="a"),
        row(1, "review", provider="a"),
        row(1, "review", provider="a"),
        row(0, "approve", provider="b"),
        row(0, "approve", provider="b"),
        row(1, "review", provider="b"),
        row(1, "review", provider="b"),
    )

    with pytest.raises(EvidenceError, match="multiple provider/prompt cells"):
        evidence_from_promptfoo(payload, suite())

    evidence = evidence_from_promptfoo(payload, suite(), provider="b")
    assert evidence.provenance["provider"] == "b"


def test_plain_provider_ids_and_missing_prompt_ids_have_stable_cell_names():
    payload = export(
        row(0, "approve", provider="local"),
        row(0, "approve", provider="local"),
        row(1, "review", provider="local"),
        row(1, "review", provider="local"),
    )
    for result in payload["results"]:
        result["provider"] = "local"
        result.pop("promptId")

    evidence = evidence_from_promptfoo(payload, suite())

    assert evidence.provenance["provider"] == "local"
    assert evidence.provenance["prompt_id"] == "0"


def test_a_filter_that_matches_no_cell_is_refused():
    payload = export(
        row(0, "approve"),
        row(0, "approve"),
        row(1, "review"),
        row(1, "review"),
    )
    with pytest.raises(EvidenceError, match="no Promptfoo rows match"):
        evidence_from_promptfoo(payload, suite(), provider="absent")


def test_missing_or_short_cases_are_refused():
    payload = export(row(0, "approve"), row(0, "approve"), row(1, "review"))
    with pytest.raises(EvidenceError, match="run with --repeat 2"):
        evidence_from_promptfoo(payload, suite())


def test_missing_responses_are_recorded_as_errors_before_short_run_refusal():
    payload = export(
        row(0, "approve"),
        row(0, "approve"),
        row(1),
        row(1),
    )
    with pytest.raises(EvidenceError, match="0 usable observation"):
        evidence_from_promptfoo(payload, suite())


def test_an_unmatched_rendered_input_is_refused():
    payload = export(
        row(0, "approve", prompt={"raw": "not reviewed"}),
        row(2, "approve", prompt={"raw": "not reviewed"}),
    )
    with pytest.raises(EvidenceError, match="does not match a reviewed"):
        evidence_from_promptfoo(payload, suite())


def test_promptfoo_export_loads_from_disk(tmp_path):
    path = tmp_path / "promptfoo.json"
    path.write_text(
        json.dumps(
            export(
                row(0, "approve"),
                row(0, "approve"),
                row(1, "review"),
                row(1, "review"),
            )
        ),
        encoding="utf-8",
    )

    evidence = load_promptfoo(path, suite(), isolation="fresh-instance")

    assert evidence.isolation == "fresh-instance"


def test_a_bad_promptfoo_file_is_a_clean_evidence_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(EvidenceError, match="cannot load Promptfoo export"):
        load_promptfoo(path, suite())


@pytest.mark.parametrize("input_path", ["", 3])
def test_input_path_must_be_a_non_empty_string(input_path):
    with pytest.raises(EvidenceError, match="input path"):
        evidence_from_promptfoo(export(), suite(), input_path=input_path)


@pytest.mark.parametrize(
    "output, decision_path, message",
    [
        ({"route": "approve"}, None, "structured rather than a string"),
        ("not json", "route", "is not JSON"),
        ({"other": "approve"}, "route", "has no path"),
        ({"route": 3}, "route", "is not a string"),
    ],
)
def test_bad_decision_shapes_are_refused(output, decision_path, message):
    payload = export(
        row(0, output),
        row(0, output),
        row(1, output),
        row(1, output),
    )
    with pytest.raises(EvidenceError, match=message):
        evidence_from_promptfoo(
            payload,
            suite(),
            decision_path=decision_path,
        )


def test_the_suite_type_is_checked():
    with pytest.raises(TypeError, match="requires a DecisionSuite"):
        evidence_from_promptfoo(export(), object())


@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "root must be an object"),
        ({"version": 3}, "has no result rows"),
        ({"results": ["bad"]}, "rows must be objects"),
        ({"results": {"version": 4}}, "has no result rows"),
    ],
)
def test_malformed_exports_are_refused(payload, message):
    with pytest.raises(EvidenceError, match=message):
        evidence_from_promptfoo(payload, suite())


def test_the_shipped_promptfoo_export_reproduces_the_readme_numbers():
    """The README opens with this table. A doc that drifts from the code
    teaches the wrong thing confidently, so the figures are generated."""
    from pathlib import Path

    from agentverity import assess_evidence, load_decision_suite, load_promptfoo

    root = Path(__file__).resolve().parent.parent
    suite = load_decision_suite(root / "examples/payment_decisions.json")
    evidence = load_promptfoo(
        root / "examples/promptfoo_bridge/results.json", suite
    )
    result = assess_evidence(evidence, suite, epsilon=0.05)

    assert result.meter.pair_trials == 78
    assert result.meter.pair_flips == 9
    assert result.route_stability.stochastic == ("card_security",)
    by_route = {r.decision: r for r in result.route_stability.routes}
    assert by_route["card_security"].pair_flips == 9
    assert by_route["card_security"].pair_trials == 13
    assert result.route_stability.flip_pairs[0].decisions == (
        "card_security",
        "merchant_dispute",
    )
    # The contract check passes, which is the point: it would not have caught
    # the unstable route on its own.
    assert result.decision_coverage.satisfied is True
