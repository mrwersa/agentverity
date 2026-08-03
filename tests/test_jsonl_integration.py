"""The importer that understands nothing.

Promptfoo and DeepEval each need a bridge that knows their export. This one
reads a line per run and the caller names the fields, which covers a harness
with no bridge, a production log, and a CSV converted to JSONL.
"""

from __future__ import annotations

import json

import pytest

from agentverity import NoDecision, assess_evidence, evidence_from_jsonl
from agentverity.evidence import EvidenceError


def _lines(rows):
    return [json.dumps(row) for row in rows]


class TestReadingRuns:
    def test_runs_of_one_input_become_one_case_in_order(self):
        evidence = evidence_from_jsonl(
            _lines(
                [
                    {"input": "a", "decision": "billing"},
                    {"input": "b", "decision": "refund"},
                    {"input": "a", "decision": "card_security"},
                    {"input": "b", "decision": "refund"},
                ]
            )
        )

        by_input = {case.input: case.observations for case in evidence.cases}
        assert by_input["a"] == ("billing", "card_security")
        assert by_input["b"] == ("refund", "refund")

    def test_the_file_order_is_the_pairing_order(self):
        """Disjoint pairing reads consecutive runs, so a sorted file lies."""
        as_run = evidence_from_jsonl(
            _lines([{"input": "a", "decision": d} for d in "xyxy"])
        )
        as_sorted = evidence_from_jsonl(
            _lines([{"input": "a", "decision": d} for d in "xxyy"])
        )

        # The same four runs. In the order produced the route flips on every
        # pair; sorted by decision it pairs x with x and y with y and reads
        # perfectly stable. Sorting a log before importing it manufactures a
        # result, which is why the line is the unit and the order is kept.
        assert assess_evidence(as_run, epsilon=0.4).meter.flip_rate == 1.0
        assert assess_evidence(as_sorted, epsilon=0.4).meter.flip_rate == 0.0

    def test_dotted_paths_reach_into_a_nested_row(self):
        evidence = evidence_from_jsonl(
            _lines(
                [
                    {"probe": {"text": "a"}, "result": {"route": "billing"}},
                    {"probe": {"text": "a"}, "result": {"route": "billing"}},
                ]
            ),
            input_path="probe.text",
            decision_path="result.route",
        )

        assert evidence.cases[0].observations == ("billing", "billing")

    def test_a_tool_path_is_a_list_of_names(self):
        evidence = evidence_from_jsonl(
            _lines(
                [
                    {"input": "a", "decision": ["search", "answer"]},
                    {"input": "a", "decision": ["search", "answer"]},
                ]
            ),
            layer="tools",
        )

        assert evidence.cases[0].observations == (("search", "answer"),) * 2

    def test_a_no_decision_is_read_typed(self):
        evidence = evidence_from_jsonl(
            _lines(
                [
                    {"input": "a", "decision": "refund"},
                    {"input": "a", "decision": {"kind": "no_decision", "reason": "refused"}},
                ]
            )
        )

        assert evidence.cases[0].observations == ("refund", NoDecision("refused"))

    def test_a_suite_supplies_the_intended_route(self):
        from agentverity import DecisionCase, DecisionContract, DecisionSuite

        suite = DecisionSuite(
            contract=DecisionContract(allowed=frozenset({"billing", "refund"})),
            cases=(
                DecisionCase(input="a", expected="billing"),
                DecisionCase(input="b", expected="refund"),
            ),
        )
        evidence = evidence_from_jsonl(
            _lines(
                [
                    {"input": "a", "decision": "refund"},
                    {"input": "a", "decision": "refund"},
                    {"input": "b", "decision": "refund"},
                    {"input": "b", "decision": "refund"},
                ]
            ),
            suite=suite,
        )

        # the route stays identifiable even where the agent answered it wrongly
        assert {c.input: c.expected for c in evidence.cases} == {
            "a": "billing",
            "b": "refund",
        }


class TestRefusals:
    def test_an_input_appearing_once_is_refused(self):
        """Stability is a property of repeats."""
        with pytest.raises(EvidenceError, match="appear once"):
            evidence_from_jsonl(
                _lines(
                    [
                        {"input": "a", "decision": "x"},
                        {"input": "a", "decision": "x"},
                        {"input": "b", "decision": "y"},
                    ]
                )
            )

    def test_a_missing_field_names_the_part_that_failed(self):
        with pytest.raises(EvidenceError, match="'route' is missing"):
            evidence_from_jsonl(
                _lines([{"input": "a", "result": {}}] * 2),
                decision_path="result.route",
            )

    def test_a_line_that_is_not_an_object_is_refused(self):
        with pytest.raises(EvidenceError, match="not an object"):
            evidence_from_jsonl(['["a", "b"]', '["a", "b"]'])

    def test_invalid_json_names_the_line(self):
        with pytest.raises(EvidenceError, match="line 2 is not valid JSON"):
            evidence_from_jsonl(['{"input": "a", "decision": "x"}', "{oops"])

    def test_an_unknown_no_decision_reason_is_refused(self):
        with pytest.raises(EvidenceError, match="unknown no-decision reason"):
            evidence_from_jsonl(
                _lines(
                    [{"input": "a", "decision": {"kind": "no_decision", "reason": "made_up"}}] * 2
                )
            )

    def test_a_number_is_not_a_decision(self):
        with pytest.raises(EvidenceError, match="must be a string"):
            evidence_from_jsonl(_lines([{"input": "a", "decision": 3}] * 2))

    def test_an_empty_file_says_what_was_expected(self):
        with pytest.raises(EvidenceError, match="no runs found"):
            evidence_from_jsonl([])

    def test_blank_lines_are_skipped_not_refused(self):
        evidence = evidence_from_jsonl(
            ['{"input": "a", "decision": "x"}', "", "  ", '{"input": "a", "decision": "x"}']
        )

        assert evidence.cases[0].observations == ("x", "x")


def test_one_observation_per_case_remains_undecided():
    """The claim the roadmap makes about this importer, asserted.

    It removes the second bill, not the first. A harness that ran each case
    once has no stability evidence to import, however convenient the format.
    """
    evidence = evidence_from_jsonl(
        _lines([{"input": "a", "decision": "x"}, {"input": "a", "decision": "x"}])
    )
    result = assess_evidence(evidence, epsilon=0.05)

    assert "undecided" in result.meter.call


def test_isolation_is_recorded_rather_than_assumed():
    evidence = evidence_from_jsonl(
        _lines([{"input": "a", "decision": "x"}] * 2)
    )

    assert evidence.isolation == "unknown"
    assert evidence.independence_caveat is not None
