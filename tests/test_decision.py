"""The typed absence of a decision. See DESIGN.md ADR 2.

The defect these types fix is that `Observation.key` compared two reworded
refusals as different decisions, measuring wording rather than choice. The
trap in the obvious repair is that a single sentinel merges six distinct
events, so a run of extraction failures would certify as perfectly stable.
"""

from __future__ import annotations

import pytest

from agentverity import Decision, NoDecision, Observation, as_outcome
from agentverity.decision import (
    DECLARABLE_REASONS,
    INCOMPLETE_REASONS,
    NO_DECISION_REASONS,
)


class TestEquality:
    def test_two_reworded_refusals_are_one_decision(self):
        """The whole point. Wording must not move the decision."""
        first = Observation(text="I cannot help with that.", verdict=NoDecision("refused"))
        second = Observation(text="Sorry, I am unable to assist.", verdict=NoDecision("refused"))

        assert first.key("verdict") == second.key("verdict")

    def test_the_old_text_fallback_still_applies_to_a_truly_unset_verdict(self):
        """Unchanged for callers that have not adopted the types."""
        first = Observation(text="I cannot help with that.")
        second = Observation(text="Sorry, I am unable to assist.")

        assert first.key("verdict") != second.key("verdict")

    def test_a_no_decision_never_equals_a_decision_with_the_same_string(self):
        assert NoDecision("refused") != Decision("refused")
        assert Observation(verdict=NoDecision("refused")).key("verdict") != (
            Observation(verdict="refused").key("verdict")
        )

    def test_different_reasons_are_different_outcomes(self):
        assert NoDecision("refused") != NoDecision("no_tool_selected")


class TestTheIncompleteSplit:
    """Six events, two groups. Merging them is what a sentinel would do."""

    def test_harness_failures_make_the_evidence_incomplete(self):
        for reason in ("extraction_failed", "malformed_response", "runtime_error"):
            assert NoDecision(reason).is_incomplete, reason

    def test_what_the_agent_did_is_not_incomplete(self):
        for reason in ("refused", "no_tool_selected", "open_ended"):
            assert not NoDecision(reason).is_incomplete, reason

    def test_the_two_groups_partition_the_declarable_ones(self):
        assert INCOMPLETE_REASONS <= NO_DECISION_REASONS
        assert DECLARABLE_REASONS <= NO_DECISION_REASONS
        assert not (INCOMPLETE_REASONS & DECLARABLE_REASONS), (
            "a reason cannot be both something the agent chose and a harness failure"
        )

    def test_open_ended_is_comparable_to_nothing(self):
        assert not NoDecision("open_ended").comparable
        assert NoDecision("refused").comparable
        assert Decision("refund").comparable


class TestRefusals:
    def test_an_unknown_reason_is_refused_with_the_vocabulary(self):
        with pytest.raises(ValueError, match="unknown no-decision reason"):
            NoDecision("made_up")

    def test_an_empty_label_is_refused(self):
        with pytest.raises(ValueError, match="non-empty string label"):
            Decision("")


class TestReadingStoredValues:
    def test_a_bare_string_is_a_decision_because_that_is_what_it_meant(self):
        """Evidence written before ADR 2 stored adapter-invented labels.

        Reading `"no_tool_selected"` back as a NoDecision would change the
        meaning of committed files. The schema version distinguishes them.
        """
        assert as_outcome("no_tool_selected") == Decision("no_tool_selected")
        assert as_outcome("refund") == Decision("refund")

    def test_a_typed_value_passes_through(self):
        assert as_outcome(NoDecision("refused")) == NoDecision("refused")

    def test_nothing_else_is_readable(self):
        for value in (None, 3, [], ""):
            with pytest.raises(ValueError, match="cannot read an outcome"):
                as_outcome(value)


class TestObservationOutcome:
    def test_a_string_verdict_is_a_decision(self):
        assert Observation(verdict="refund").outcome == Decision("refund")

    def test_prose_with_no_verdict_is_open_ended(self):
        assert Observation(text="here is an essay").outcome == NoDecision("open_ended")

    def test_a_typed_absence_is_reported_as_itself(self):
        obs = Observation(verdict=NoDecision("extraction_failed"))

        assert obs.outcome == NoDecision("extraction_failed")
        assert obs.is_incomplete


def test_the_agentkit_workaround_is_what_this_replaces():
    """The collector invents a label because leaving the verdict unset is worse.

    `no_tool_selected` appears 176 times across the nova run and covers more
    than one event. On one probe it appears 80 times out of 146, which a naive
    reading scores as a strongly stable decision. Nothing decided anything.
    """
    import collections
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "agentkit"
    nova = json.loads((root / "evidence-nova.json").read_text())
    counts = [
        collections.Counter(case["observations"])["no_tool_selected"]
        for case in nova["cases"]
    ]

    assert sum(counts) == 176
    assert max(counts) == 80
    # and the label the collector invented is out of contract on purpose
    suite = json.loads((root / "suite.json").read_text())
    assert "no_tool_selected" not in suite["contract"]["allowed"]


class TestEnforcement:
    """The value objects were safe; the paths that consume them were not.

    Review found that `is_incomplete` and `comparable` were documented and
    ignored, that a NoDecision reaching the contract was stringified into one
    mangled label, and that the JSON report could not hold what the package
    exported. A type whose safety properties are documented but not enforced
    is worse than no type.
    """

    def test_repeated_harness_failures_are_refused_not_scored(self):
        """Zero-flip pairs over extraction failures would certify the failure."""
        from agentverity.meter import score_runs

        series = [Observation(verdict=NoDecision("extraction_failed"))] * 4

        with pytest.raises(ValueError, match="harness failed"):
            score_runs([series], k=4)

    def test_each_incomplete_reason_is_refused(self):
        from agentverity.meter import score_runs

        for reason in ("extraction_failed", "malformed_response", "runtime_error"):
            with pytest.raises(ValueError, match="harness failed"):
                score_runs([[Observation(verdict=NoDecision(reason))] * 4], k=4)

    def test_open_ended_contributes_no_pairs(self):
        """Comparable to nothing means it cannot be half of a comparison."""
        from agentverity.meter import score_runs

        with pytest.raises(ValueError, match="comparable observations"):
            score_runs([[Observation(verdict=NoDecision("open_ended"))] * 4], k=4)

    def test_a_no_decision_reaching_the_contract_is_refused_not_mangled(self):
        """It used to become "<non-string:NoDecision>", folding every reason."""
        from agentverity import DecisionCase, DecisionContract, DecisionSuite
        from agentverity.decision_contract import assess_decision_coverage

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed=frozenset({"refund"}), required=frozenset({"refund"})
            ),
            cases=(DecisionCase(input="a", expected="refund"),),
        )

        with pytest.raises(TypeError, match="cannot yet declare no-decision"):
            assess_decision_coverage(suite, observed=(NoDecision("refused"),))

    def test_the_json_report_can_hold_a_typed_outcome(self):
        """It raised TypeError, so any adapter emitting one died at serialisation."""
        from agentverity.reporting import json_value

        assert json_value(Decision("refund")) == {
            "kind": "decision",
            "label": "refund",
        }
        assert json_value(NoDecision("refused")) == {
            "kind": "no_decision",
            "reason": "refused",
        }

    def test_the_tag_distinguishes_a_label_from_a_reason(self):
        """`Decision("refused")` and `NoDecision("refused")` must not collide."""
        from agentverity.reporting import json_value

        assert json_value(Decision("refused")) != json_value(NoDecision("refused"))

    def test_both_access_paths_agree_on_a_decision(self):
        """`key` returned the Decision while `outcome` said open_ended."""
        observation = Observation(verdict=Decision("refund"))

        assert observation.key("verdict") == observation.outcome == Decision("refund")

    def test_a_string_verdict_is_untouched_by_all_of_this(self):
        from agentverity.meter import score_runs

        result = score_runs([[Observation(verdict="refund")] * 4], k=4)

        assert result.flip_rate == 0.0
