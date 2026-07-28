"""Tests for assessing evidence collected by another harness."""

from __future__ import annotations

import json

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    EvidenceCase,
    EvidenceError,
    EvidenceSet,
    assess_evidence,
    load_evidence,
    save_evidence,
)
from agentverity.evidence import EVIDENCE_SCHEMA


def evidence(**overrides):
    defaults = {
        "cases": (
            EvidenceCase("routine request", ("approve",) * 26, expected="approve"),
            EvidenceCase("ambiguous request", ("review", "deny") * 13, expected="review"),
            EvidenceCase("prohibited request", ("deny",) * 26, expected="deny"),
        ),
        "isolation": "fresh-session",
    }
    return EvidenceSet(**{**defaults, **overrides})


def matching_suite():
    return DecisionSuite(
        contract=DecisionContract(allowed={"approve", "review", "deny"}),
        cases=(
            DecisionCase("routine request", "approve"),
            DecisionCase("ambiguous request", "review"),
            DecisionCase("prohibited request", "deny"),
        ),
    )


class TestAggregatesAreRefused:
    """A flip rate cannot be turned back into the disjoint pairs it came from,
    and a pooled number cannot be split by route. Refusing loudly is better
    than assessing something the file cannot support."""

    def test_a_case_without_observations_is_rejected(self):
        payload = {
            "schema": EVIDENCE_SCHEMA,
            "cases": [{"input": "routine", "flip_rate": 0.1, "runs": 20}],
        }
        with pytest.raises(EvidenceError, match="no 'observations'"):
            EvidenceSet.from_dict(payload)

    def test_the_refusal_explains_why_rather_than_only_that(self):
        payload = {"schema": EVIDENCE_SCHEMA, "cases": [{"input": "x", "pass_rate": 1.0}]}
        with pytest.raises(EvidenceError) as info:
            EvidenceSet.from_dict(payload)

        message = str(info.value)
        assert "disjoint pairs cannot be" in message
        assert "split by route" in message

    def test_observations_must_be_a_list_not_a_count(self):
        payload = {
            "schema": EVIDENCE_SCHEMA,
            "cases": [{"input": "x", "observations": 20}],
        }
        with pytest.raises(EvidenceError, match="must be a list"):
            EvidenceSet.from_dict(payload)

    def test_a_single_observation_cannot_form_a_comparison(self):
        with pytest.raises(EvidenceError, match="at least two are needed"):
            EvidenceCase("x", ("approve",))


class TestSchemaValidation:
    @pytest.mark.parametrize(
        "payload, message",
        [
            ([], "root must be an object"),
            ({"schema": "other/v9", "cases": []}, "unsupported evidence schema"),
            ({"schema": EVIDENCE_SCHEMA, "cases": {}}, "cases must be a list"),
            ({"schema": EVIDENCE_SCHEMA, "cases": ["x"]}, "must be an object"),
        ],
    )
    def test_malformed_files_are_rejected(self, payload, message):
        with pytest.raises(EvidenceError, match=message):
            EvidenceSet.from_dict(payload)

    def test_an_unknown_layer_is_rejected(self):
        with pytest.raises(EvidenceError, match="unknown observation layer"):
            evidence(layer="vibes")

    def test_an_unknown_isolation_is_rejected(self):
        with pytest.raises(EvidenceError, match="unknown isolation"):
            evidence(isolation="probably fine")

    def test_duplicate_inputs_are_rejected(self):
        with pytest.raises(EvidenceError, match="duplicate case input"):
            EvidenceSet(
                cases=(
                    EvidenceCase("same", ("a", "a")),
                    EvidenceCase("same", ("a", "a")),
                )
            )

    def test_an_empty_evidence_set_is_rejected(self):
        with pytest.raises(EvidenceError, match="at least one case"):
            EvidenceSet(cases=())

    def test_a_non_string_observation_is_rejected(self):
        with pytest.raises(EvidenceError, match="non-string observation"):
            EvidenceCase("x", ({"verdict": "approve"}, "approve"))


class TestIndependenceIsRecordedNotAssumed:
    """An import can violate independence in ways a self-run cannot: a shared
    conversation, a warm cache, one session reused across repeats."""

    def test_a_shared_session_is_flagged_as_narrowing_the_interval(self):
        caveat = evidence(isolation="shared-session").independence_caveat
        assert "not independent" in caveat
        assert "narrower" in caveat

    def test_an_unrecorded_isolation_says_the_assumption_is_unverified(self):
        caveat = evidence(isolation="unknown").independence_caveat
        assert "assumed rather than established" in caveat

    def test_a_fresh_session_carries_no_caveat(self):
        assert evidence(isolation="fresh-session").independence_caveat is None


class TestPairArithmetic:
    def test_an_odd_observation_is_unused_because_pairs_must_not_overlap(self):
        assert EvidenceCase("x", ("a",) * 16).usable_pairs == 8
        assert EvidenceCase("x", ("a",) * 17).usable_pairs == 8

    def test_total_pairs_sums_across_cases(self):
        assert evidence().total_pairs == 13 * 3


class TestAssessment:
    def test_the_same_checks_run_without_making_a_single_call(self):
        result = assess_evidence(evidence(), matching_suite(), epsilon=0.05)

        assert result.meter is not None
        assert result.blindness is not None
        assert result.decision_coverage is not None
        assert result.route_stability is not None

    def test_the_unstable_route_is_named_from_imported_data(self):
        result = assess_evidence(evidence(), matching_suite(), epsilon=0.05)
        assert result.route_stability.stochastic == ("review",)

    def test_flip_pairs_survive_the_import(self):
        result = assess_evidence(evidence(), matching_suite(), epsilon=0.05)
        assert result.route_stability.flip_pairs[0].decisions == ("deny", "review")

    def test_relation_results_are_empty_rather_than_assumed_to_hold(self):
        """A relation needs the agent to answer a transformed question. No such
        call exists in an imported file, and claiming a pass would be the
        vacuous green this package exists to name."""
        result = assess_evidence(evidence(), matching_suite())
        assert list(result.relation_results) == []

    def test_intended_decisions_can_come_from_the_file_without_a_suite(self):
        result = assess_evidence(evidence(), epsilon=0.05)

        assert result.route_stability is not None
        assert result.decision_coverage is None

    def test_evidence_without_expectations_yields_no_route_split(self):
        plain = EvidenceSet(
            cases=(EvidenceCase("a", ("approve",) * 4), EvidenceCase("b", ("deny",) * 4))
        )
        assert assess_evidence(plain).route_stability is None

    def test_a_suite_describing_different_inputs_is_refused(self):
        """A contract checked against a different run would report coverage
        the run never had."""
        other = DecisionSuite(
            contract=DecisionContract(allowed={"approve"}),
            cases=(DecisionCase("something else entirely", "approve"),),
        )
        with pytest.raises(EvidenceError, match="does not describe this evidence"):
            assess_evidence(evidence(), other)

    def test_per_route_targets_are_honoured_on_imported_evidence(self):
        suite = DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "review", "deny"},
                stability_targets={"approve": 0.5},
            ),
            cases=matching_suite().cases,
        )
        result = assess_evidence(evidence(), suite, epsilon=0.05)
        by_route = {r.decision: r for r in result.route_stability.routes}

        assert by_route["approve"].epsilon == 0.5
        assert by_route["deny"].epsilon == 0.05

    def test_the_result_renders_through_the_ordinary_report(self):
        summary = assess_evidence(evidence(), matching_suite(), epsilon=0.05).summary()

        assert "VERDICT-STOCHASTICITY METER" in summary
        assert "STABILITY BY ROUTE" in summary


class TestRoundTrip:
    def test_evidence_survives_a_file_round_trip(self, tmp_path):
        path = tmp_path / "runs.json"
        original = evidence(provenance={"model": "example-v3"})
        save_evidence(original, path)
        restored = load_evidence(path)

        assert restored.inputs == original.inputs
        assert restored.isolation == "fresh-session"
        assert restored.provenance == {"model": "example-v3"}
        assert restored.cases[1].observations == original.cases[1].observations

    def test_a_missing_file_is_an_evidence_error(self, tmp_path):
        with pytest.raises(EvidenceError, match="cannot load evidence"):
            load_evidence(tmp_path / "absent.json")

    def test_malformed_json_is_an_evidence_error(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(EvidenceError, match="cannot load evidence"):
            load_evidence(path)

    def test_provenance_must_be_an_object(self):
        with pytest.raises(EvidenceError, match="provenance must be"):
            EvidenceSet.from_dict(
                {
                    "schema": EVIDENCE_SCHEMA,
                    "cases": [{"input": "x", "observations": ["a", "a"]}],
                    "provenance": "example-v3",
                }
            )

    def test_the_shipped_example_assesses(self):
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "examples/imported_evidence.json"
        result = assess_evidence(load_evidence(path), epsilon=0.05)

        assert result.route_stability.stochastic == ("card_security",)
        assert json.loads(path.read_text())["schema"] == EVIDENCE_SCHEMA


class TestCaseFieldValidation:
    @pytest.mark.parametrize("bad", ["", "   ", 5])
    def test_a_blank_input_is_rejected(self, bad):
        with pytest.raises(EvidenceError, match="input must be a non-empty string"):
            EvidenceCase(bad, ("a", "a"))

    @pytest.mark.parametrize("bad", ["", "  ", 7])
    def test_a_blank_expected_decision_is_rejected(self, bad):
        with pytest.raises(EvidenceError, match="expected decision must be"):
            EvidenceCase("x", ("a", "a"), expected=bad)

    @pytest.mark.parametrize("bad", [-1, "two"])
    def test_a_bad_error_count_is_rejected(self, bad):
        with pytest.raises(EvidenceError, match="errors must be a non-negative"):
            EvidenceCase("x", ("a", "a"), errors=bad)

    def test_error_counts_survive_serialisation_and_zero_is_omitted(self):
        assert EvidenceCase("x", ("a", "a"), errors=2).to_dict()["errors"] == 2
        assert "errors" not in EvidenceCase("x", ("a", "a")).to_dict()

    def test_cases_must_be_evidence_case_values(self):
        with pytest.raises(EvidenceError, match="must be EvidenceCase values"):
            EvidenceSet(cases=({"input": "x"},))

    def test_intended_exposes_declared_expectations(self):
        assert evidence().intended == ("approve", "review", "deny")


def test_the_documented_refusal_message_is_the_real_one():
    """docs/imported-evidence.md quotes the error verbatim. A doc that drifts
    from the code teaches the wrong thing confidently."""
    with pytest.raises(EvidenceError) as info:
        EvidenceSet.from_dict(
            {
                "schema": EVIDENCE_SCHEMA,
                "cases": [{"input": "...", "flip_rate": 0.12, "runs": 20}],
            }
        )
    message = str(info.value)
    assert "cases[0] has no 'observations'" in message
    assert "Export the individual decisions per case." in message


@pytest.mark.parametrize(
    "isolation, caveated",
    [
        ("fresh-session", False),
        ("fresh-instance", False),
        ("shared-session", True),
        ("unknown", True),
    ],
)
def test_the_documented_isolation_table_matches_behaviour(isolation, caveated):
    result = evidence(isolation=isolation).independence_caveat
    assert (result is not None) is caveated
