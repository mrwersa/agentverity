"""The typed absence of a decision. See DESIGN.md ADR 2.

The defect these types fix is that `Observation.key` compared two reworded
refusals as different decisions, measuring wording rather than choice. The
trap in the obvious repair is that a single sentinel merges six distinct
events, so a run of extraction failures would certify as perfectly stable.
"""

from __future__ import annotations

import pytest

from agentverity import (
    Decision,
    NoDecision,
    Observation,
    OutcomeNotScorable,
    as_outcome,
)
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

    def test_open_ended_is_refused_rather_than_filtered(self):
        """Filtering it and keeping the repeat count overstates the report.

        Dropping the runs that did not decide, pairing what remains, and still
        reporting 146 repeats would say the verdict held across reruns where no
        verdict existed. Categorical stability is undefined there.
        """
        from agentverity.meter import score_runs

        with pytest.raises(OutcomeNotScorable, match="undefined"):
            score_runs([[Observation(verdict=NoDecision("open_ended"))] * 4], k=4)

    def test_both_scoring_paths_share_one_gate(self):
        """The per-route path accepted what the pooled path refused."""
        from agentverity.meter import score_runs
        from agentverity.stratified import stratify_runs

        for reason in ("extraction_failed", "open_ended"):
            series = [Observation(verdict=NoDecision(reason))] * 4
            with pytest.raises(OutcomeNotScorable):
                score_runs([series], k=4)
            with pytest.raises(OutcomeNotScorable):
                stratify_runs([("route_a", series)], k=4, epsilon=0.05)

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

        with pytest.raises(OutcomeNotScorable, match="does not allow it"):
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


def test_one_exception_type_covers_every_unscorable_path():
    """Review found TypeError in one path and ValueError in another.

    They are the same condition: this evidence cannot be scored as it stands.
    Two types meant a caller catching one missed the other, which is a smaller
    version of the disagreement this whole change removes. It was not a
    deliberate distinction, it was two local consistencies that disagreed.
    """
    from agentverity import DecisionCase, DecisionContract, DecisionSuite
    from agentverity.decision_contract import assess_decision_coverage
    from agentverity.meter import score_runs

    suite = DecisionSuite(
        contract=DecisionContract(
            allowed=frozenset({"refund"}), required=frozenset({"refund"})
        ),
        cases=(DecisionCase(input="a", expected="refund"),),
    )
    paths = [
        lambda: score_runs(
            [[Observation(verdict=NoDecision("extraction_failed"))] * 4], k=4
        ),
        lambda: score_runs(
            [[Observation(verdict=NoDecision("open_ended"))] * 4], k=4
        ),
        lambda: assess_decision_coverage(suite, observed=(NoDecision("refused"),)),
    ]
    for call in paths:
        with pytest.raises(OutcomeNotScorable):
            call()
    # and it stays catchable as ValueError, which is what the meter raised before
    for call in paths:
        with pytest.raises(ValueError):
            call()


class TestPersistenceRefusals:
    """Unversioned formats must refuse the tag, not quietly carry it.

    `json_value` gained tagged serialisation for the run report, and
    `create_snapshot` calls the same function, so snapshots silently began
    storing a shape the unchanged schema version does not describe.
    """

    def test_a_snapshot_stores_what_a_contract_could_declare(self):
        """ADR 4. A baseline has to be able to hold a declared refusal."""
        from agentverity.reporting import json_value

        assert json_value(Decision("refund"), strict=True) == "refund"
        assert json_value(NoDecision("refused"), strict=True) == {
            "kind": "no_decision",
            "reason": "refused",
        }

    def test_a_snapshot_still_refuses_what_no_contract_could_declare(self):
        """Unreachable through the runner, enforced here regardless.

        A guarantee that depends on an upstream check holding is not a
        guarantee.
        """
        from agentverity.reporting import json_value

        for reason in ("extraction_failed", "malformed_response", "runtime_error",
                       "open_ended"):
            with pytest.raises(OutcomeNotScorable, match="cannot be stored"):
                json_value(NoDecision(reason), strict=True)

    def test_the_run_report_still_serialises_it_tagged(self):
        """The report is regenerated from the run, so a new shape costs nothing."""
        from agentverity.reporting import json_value

        assert json_value(NoDecision("refused")) == {
            "kind": "no_decision",
            "reason": "refused",
        }

    def test_strict_reaches_into_containers(self):
        from agentverity.reporting import json_value

        with pytest.raises(OutcomeNotScorable):
            json_value({"a": [NoDecision("runtime_error")]}, strict=True)

    def test_evidence_now_stores_a_typed_outcome_tagged(self):
        """v2 carries the tag, so the refusal that stood in for it is gone."""
        from agentverity.evidence import EvidenceCase

        payload = EvidenceCase(
            input="x", observations=(NoDecision("refused"), Decision("refund"))
        ).to_dict()

        # A decision is a plain string; only a no-decision needs an object.
        assert payload["observations"] == [
            {"kind": "no_decision", "reason": "refused"},
            "refund",
        ]

    def test_a_plain_string_still_stores(self):
        from agentverity.evidence import EvidenceCase

        payload = EvidenceCase(input="x", observations=("refund", "refund")).to_dict()

        assert payload["observations"] == ["refund", "refund"]


def test_key_and_outcome_agree_on_an_empty_verdict():
    """They disagreed: outcome said open-ended while key returned ""."""
    observation = Observation(verdict="", text="here is some prose")

    assert observation.key("verdict") == "here is some prose"
    assert observation.outcome == NoDecision("open_ended")


def test_a_non_string_verdict_keeps_its_old_meaning():
    """The empty-string fix must not swallow a sequence verdict."""
    observation = Observation(verdict=["search", "answer"])

    assert observation.key("verdict") == ["search", "answer"]


class TestOneCanonicalComparison:
    """Fixing the meter and leaving three consumers was the real defect.

    Review put it precisely: every semantic comparison needs one canonical
    function, while storage keeps the original representation. These are the
    four seams where a bare label meets a tagged one.
    """

    def test_blindness_sees_one_decision_not_two(self):
        """A constant gate reported skew 0.5 across two identical decisions."""
        from agentverity.blindness import detect

        result = detect(
            lambda text: Observation(
                verdict="allow" if text == "a" else Decision("allow")
            ),
            ["a", "b"],
        )

        assert result.blind is True
        assert result.skew == 1.0
        assert result.distinct == 1

    def test_a_typed_decision_satisfies_a_string_contract(self):
        """It became "<non-string:Decision>": unknown and missing at once."""
        from agentverity import DecisionCase, DecisionContract, DecisionSuite
        from agentverity.decision_contract import assess_decision_coverage

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed=frozenset({"refund"}), required=frozenset({"refund"})
            ),
            cases=(DecisionCase(input="a", expected="refund"),),
        )
        result = assess_decision_coverage(suite, observed=(Decision("refund"),))

        assert result.missing_observed == ()
        assert result.unknown_observed == ()
        assert {c.decision: c.count for c in result.observed_counts} == {"refund": 1}

    def test_an_invariant_relation_does_not_fire_on_representation(self):
        from agentverity import builtin_relations

        invariant = next(r for r in builtin_relations() if r.rtype == "invariant")

        assert invariant.check(
            Observation(verdict="refund"), Observation(verdict=Decision("refund"))
        )

    def test_a_no_decision_still_stops_the_contract(self):
        """Unwrapping Decision must not also unwrap the thing that is not one."""
        from agentverity import DecisionCase, DecisionContract, DecisionSuite
        from agentverity.decision_contract import assess_decision_coverage

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed=frozenset({"refund"}), required=frozenset({"refund"})
            ),
            cases=(DecisionCase(input="a", expected="refund"),),
        )

        with pytest.raises(OutcomeNotScorable):
            assess_decision_coverage(suite, observed=(NoDecision("refused"),))

    def test_a_v2_file_assessed_against_a_string_contract(self, tmp_path):
        """The end-to-end case review asked for, through the real loader."""
        import json

        from agentverity import (
            DecisionCase,
            DecisionContract,
            DecisionSuite,
            EvidenceCase,
            EvidenceSet,
            assess_evidence,
            load_evidence,
            save_evidence,
        )
        from agentverity.evidence import EVIDENCE_SCHEMA

        path = tmp_path / "evidence.json"
        save_evidence(
            EvidenceSet(
                cases=(
                    EvidenceCase(
                        input="a",
                        expected="refund",
                        observations=(Decision("refund"),) * 4,
                    ),
                    EvidenceCase(
                        input="b",
                        expected="escalate",
                        observations=("escalate",) * 4,
                    ),
                )
            ),
            path,
        )
        assert json.loads(path.read_text())["schema"] == EVIDENCE_SCHEMA

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed=frozenset({"refund", "escalate"}),
                required=frozenset({"refund", "escalate"}),
            ),
            cases=(
                DecisionCase(input="a", expected="refund"),
                DecisionCase(input="b", expected="escalate"),
            ),
        )
        result = assess_evidence(load_evidence(path), suite=suite, epsilon=0.05)

        assert result.decision_coverage.missing_observed == ()
        assert result.decision_coverage.unknown_observed == ()
        assert result.decision_coverage.satisfied
        assert result.meter.flip_rate == 0.0
