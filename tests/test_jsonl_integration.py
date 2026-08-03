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


def test_the_cli_honours_a_path_that_matches_the_other_importers_default(
    tmp_path, capsys
):
    """`--input-path prompt.raw` on a JSONL file must mean what it says.

    The CLI shares two path flags between --promptfoo and --jsonl, and the
    first version gave them a Promptfoo default and treated that default as
    "unset" for JSONL. So a log whose input really did sit at `prompt.raw`
    had the flag silently discarded and failed on a field it was never asked
    to read. Each importer owns its own default now, and the CLI forwards a
    path only when the caller named one.
    """
    from agentverity.cli import main

    path = tmp_path / "runs.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"prompt": {"raw": "a"}, "decision": decision})
            for decision in ("x", "x")
        ),
        encoding="utf-8",
    )

    # 2 is a refusal, which is what the discarded flag produced. 1 is the
    # blindness check failing one case whose answer never varies, which is the
    # file being read. `undecided` also exits 2, so 1 is the unambiguous half.
    code = main(["assess", "--jsonl", str(path), "--input-path", "prompt.raw"])

    assert code == 1, "the named path was not used"
    assert "no 'prompt.raw'" not in capsys.readouterr().err


def test_a_tool_path_file_is_reachable_from_the_cli(tmp_path, capsys):
    """The importer accepted tool paths that the CLI could not ask for.

    `--jsonl` advertised "a list of tool names" as a decision, and the library
    honoured it, but `assess` had no `--layer` flag. So the only way to reach
    it was the Python API, and the CLI failed with "verdict observations must
    be strings" naming a layer the caller never chose.
    """
    from agentverity.cli import main

    path = tmp_path / "runs.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"input": "a", "decision": ["get_balance", "pay"]})
            for _ in range(2)
        ),
        encoding="utf-8",
    )

    # 1 is the blindness check failing one case whose answer never varies,
    # which is the file being read. 2 was the refusal.
    assert main(["assess", "--jsonl", str(path), "--layer", "tools"]) == 1
    assert "must be strings" not in capsys.readouterr().err


def test_layer_is_refused_where_it_would_be_ignored(tmp_path, capsys):
    """An evidence file records its own layer, so the flag cannot also set it.

    Accepting and discarding it is the same defect as the `prompt.raw`
    sentinel: a flag the caller set that quietly does nothing.
    """
    from agentverity.cli import main

    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema": "agentverity.evidence/v2",
                "layer": "verdict",
                "isolation": "unknown",
                "cases": [{"input": "a", "observations": ["x", "x"]}],
            }
        ),
        encoding="utf-8",
    )

    assert main(["assess", "--evidence", str(evidence), "--layer", "tools"]) == 2
    assert "--layer applies to --jsonl" in capsys.readouterr().err


def test_a_refusal_names_the_line_it_read(tmp_path, capsys):
    """A ten-thousand line log is the ordinary case, not the exception."""
    from agentverity.cli import main

    path = tmp_path / "runs.jsonl"
    path.write_text(
        '{"input": "a", "decision": "x"}\n'
        '{"input": "a", "decision": "x"}\n'
        '{"prompt": "a"}\n',
        encoding="utf-8",
    )

    assert main(["assess", "--jsonl", str(path)]) == 2
    assert "line 3" in capsys.readouterr().err


def test_an_object_decision_must_say_it_is_a_no_decision():
    """An object is the typed shape, and the only typed shape is a no-decision."""
    with pytest.raises(EvidenceError, match="'no_decision'"):
        evidence_from_jsonl(
            _lines([{"input": "a", "decision": {"kind": "verdict", "label": "x"}}] * 2)
        )


def test_a_suite_must_be_a_suite():
    with pytest.raises(TypeError, match="DecisionSuite"):
        evidence_from_jsonl(
            _lines([{"input": "a", "decision": "x"}] * 2),
            suite={"cases": [{"input": "a", "expected": "x"}]},
        )


def test_an_input_that_is_not_a_string_is_refused():
    """Reachable from a genuinely malformed log, so it names the line."""
    with pytest.raises(EvidenceError, match="line 1"):
        evidence_from_jsonl(_lines([{"input": 4471, "decision": "x"}] * 2))


def test_an_empty_decision_is_refused_as_an_empty_probe_already_is():
    """`Decision("")` is refused by the type, so importing one is inconsistent.

    Accepted, it reads out of the report as "the agent answered '' on 100% of
    the probes". A run that produced nothing is a no-decision, and the reason
    vocabulary exists to say which kind.
    """
    with pytest.raises(EvidenceError, match="empty decision"):
        evidence_from_jsonl(_lines([{"input": "a", "decision": ""}] * 2))


def test_the_refusal_says_the_whole_import_stopped():
    """A 10,000-line log with one stray input is refused entirely.

    Deliberate, and the message has to say so, because the alternative reading
    is that the offender was dropped and the rest assessed.
    """
    lines = _lines(
        [{"input": "a", "decision": "x"}] * 2 + [{"input": "b", "decision": "y"}]
    )
    with pytest.raises(EvidenceError, match="1 of 2 inputs appear once"):
        evidence_from_jsonl(lines)


@pytest.mark.parametrize(
    ("source", "flag", "value"),
    [
        ("--jsonl", "--provider", "openai:gpt-4o"),
        ("--jsonl", "--prompt-id", "p1"),
        ("--evidence", "--input-path", "a.b"),
        ("--evidence", "--decision-path", "a.b"),
        ("--evidence", "--layer", "tools"),
    ],
)
def test_assess_refuses_a_flag_its_source_would_discard(
    tmp_path, capsys, source, flag, value
):
    """One set of options serves three sources, so the unusable ones refuse.

    `--layer` already refused, and the same argument covers `--provider` and
    `--prompt-id` on a JSONL file and the path flags on an evidence file: a
    flag the caller set that quietly does nothing is the `prompt.raw` sentinel
    with a different name.
    """
    from agentverity.cli import main

    if source == "--jsonl":
        path = tmp_path / "runs.jsonl"
        path.write_text(
            '{"input": "a", "decision": "x"}\n{"input": "a", "decision": "x"}\n',
            encoding="utf-8",
        )
    else:
        path = tmp_path / "evidence.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "agentverity.evidence/v2",
                    "layer": "verdict",
                    "isolation": "unknown",
                    "cases": [{"input": "a", "observations": ["x", "x"]}],
                }
            ),
            encoding="utf-8",
        )

    assert main(["assess", source, str(path), flag, value]) == 2
    assert f"{flag} applies to" in capsys.readouterr().err
