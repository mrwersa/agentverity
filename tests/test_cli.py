"""Tests for agentverity.cli."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from agentverity.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
from agentverity.decision_contract import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    save_decision_suite,
)
from agentverity.observation import Observation


def _write_inputs(path: str, lines: list[str]) -> None:
    with open(path, "w") as f:
        f.writelines(line + "\n" for line in lines)


class TestCLI:
    def test_help_uses_public_description(self, capsys):
        with pytest.raises(SystemExit) as raised:
            main(["--help"])

        assert raised.value.code == 0
        help_text = " ".join(capsys.readouterr().out.split())
        assert (
            "Qualify repeated categorical AI-agent evidence before it becomes "
            "a regression reference." in help_text
        )

    def test_run_deterministic_agent(self, capsys, tmp_path):
        inputs_file = tmp_path / "inputs.txt"
        # 100 inputs, balanced so the blindness detector does not fire,
        # and the meter is powered enough to call "deterministic".
        inputs = [f"input_{i}" for i in range(50)] + [f"secret_{i}" for i in range(50)]
        _write_inputs(str(inputs_file), inputs)

        exit_code = main([
            "run",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs_file),
            "--k", "10",
        ])
        captured = capsys.readouterr()
        assert "VERDICT-STOCHASTICITY METER" in captured.out
        assert "verdict-deterministic" in captured.out
        assert "RELATION RESULTS" in captured.out
        assert exit_code == 0

    def test_run_constant_agent_exits_1(self, capsys, tmp_path):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["hello", "world", "foo", "bar"])

        exit_code = main([
            "run",
            "--agent", "examples.toy_agent:constant_gate",
            "--inputs", str(inputs_file),
        ])
        captured = capsys.readouterr()
        assert "BLIND" in captured.out
        assert exit_code == 1

    def test_run_false_agent_spec(self, tmp_path, capsys):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["hello"])

        exit_code = main([
            "run",
            "--agent", "not_a_dotted_path",
            "--inputs", str(inputs_file),
        ])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "run refused" in captured.err
        assert "--agent" in captured.err

    def test_run_bad_module(self, tmp_path, capsys):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["hello"])

        exit_code = main([
            "run",
            "--agent", "nonexistent_module:func",
            "--inputs", str(inputs_file),
        ])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "run refused" in captured.err
        assert "No module named" in captured.err

    def test_run_missing_inputs_file(self, tmp_path, capsys):
        exit_code = main([
            "run",
            "--agent", "examples.toy_agent:constant_gate",
            "--inputs", str(tmp_path / "nope.txt"),
        ])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "run refused" in captured.err

    def test_run_factory_exception_is_not_a_refusal(self, tmp_path):
        agent_file = tmp_path / "broken.py"
        agent_file.write_text(
            "def factory():\n"
            "    return 'x' + 1\n",
            encoding="utf-8",
        )
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["hello"])

        with pytest.raises(TypeError):
            main([
                "run",
                "--agent", f"{agent_file}:factory",
                "--inputs", str(inputs_file),
            ])

    def test_run_loads_agent_from_python_file(self, capsys, tmp_path):
        agent_file = tmp_path / "router.py"
        agent_file.write_text(
            "def build():\n"
            "    def route(text):\n"
            "        verdict = 'a' if text.startswith('a') else 'b'\n"
            "        return {'verdict': verdict}\n"
            "    return route\n",
            encoding="utf-8",
        )
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["alpha", "beta"])

        exit_code = main([
            "run",
            "--agent", f"{agent_file}:build",
            "--inputs", str(inputs_file),
            "--no-relations",
        ])

        assert exit_code == 0
        assert "TRUSTWORTHY" in capsys.readouterr().out

    def test_no_subcommand(self):
        with pytest.raises(SystemExit):
            main([])

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        assert "agentverity" in capsys.readouterr().out

    def test_json_diagnostics_only_report(self, capsys, tmp_path):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(
            str(inputs_file),
            ["public-a", "public-b", "secret-a", "secret-b"],
        )
        exit_code = main([
            "run",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs_file),
            "--k", "4",
            "--epsilon", "0.5",
            "--no-relations",
            "--format", "json",
        ])
        report = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        assert report["schema"] == "agentverity.run/v2"
        assert report["relations"] == []
        assert report["complete"] is True

    def test_junit_report_is_valid_xml_and_preserves_exit_semantics(
        self,
        capsys,
        tmp_path,
    ):
        from xml.etree import ElementTree as ET

        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["hello", "world", "foo", "bar"])
        exit_code = main([
            "run",
            "--agent", "examples.toy_agent:constant_gate",
            "--inputs", str(inputs_file),
            "--format", "junit",
        ])
        root = ET.fromstring(capsys.readouterr().out)
        assert exit_code == 1
        assert root.attrib["failures"] == "1"

    def test_undecided_meter_is_unsupported_evidence_not_green(
        self,
        capsys,
        tmp_path,
    ):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(
            str(inputs_file),
            ["public-a", "public-b", "secret-a", "secret-b"],
        )
        exit_code = main([
            "run",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs_file),
            "--k", "2",
            "--epsilon", "0.01",
            "--no-relations",
        ])
        assert exit_code == 2
        assert "NO ANSWER YET" in capsys.readouterr().out

    def test_snapshot_then_check(self, capsys, tmp_path):
        inputs_file = tmp_path / "inputs.txt"
        snapshot_file = tmp_path / "baseline.json"
        _write_inputs(
            str(inputs_file),
            ["public-a", "public-b", "secret-a", "secret-b"],
        )
        snapshot_exit = main([
            "snapshot",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs_file),
            "--output", str(snapshot_file),
            "--k", "4",
            "--epsilon", "0.5",
            "--accept-reference",
        ])
        assert snapshot_exit == 0
        assert snapshot_file.exists()
        capsys.readouterr()

        check_exit = main([
            "check",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs_file),
            "--snapshot", str(snapshot_file),
        ])
        captured = capsys.readouterr()
        assert check_exit == 0
        assert "snapshot clean" in captured.out

    def test_snapshot_without_approval_is_refused(self, capsys, tmp_path):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(
            str(inputs_file),
            ["public-a", "public-b", "secret-a", "secret-b"],
        )
        exit_code = main([
            "snapshot",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs_file),
            "--output", str(tmp_path / "baseline.json"),
            "--k", "4",
            "--epsilon", "0.5",
        ])
        assert exit_code == 2
        assert "explicit approval" in capsys.readouterr().err

    def test_progress_uses_fingerprint_not_input_text(self, capsys, tmp_path):
        inputs_file = tmp_path / "inputs.txt"
        sensitive = "secret-customer-reference"
        _write_inputs(str(inputs_file), [sensitive, "ordinary"])
        main([
            "run",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--inputs", str(inputs_file),
            "--k", "2",
            "--epsilon", "0.9",
            "--no-relations",
            "--progress",
        ])
        captured = capsys.readouterr()
        assert "[meter]" in captured.err
        assert "sha256=" in captured.err
        assert sensitive not in captured.err

    def test_snapshot_provider_failure_is_a_refusal_not_a_traceback(
        self,
        capsys,
        monkeypatch,
        tmp_path,
    ):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["good", "bad"])

        def factory():
            def agent(text: str) -> Observation:
                if text == "bad":
                    raise RuntimeError("provider unavailable")
                return Observation(verdict="allow")

            return agent

        monkeypatch.setattr("agentverity.cli._load_agent", lambda _spec: factory)
        exit_code = main([
            "snapshot",
            "--agent", "ignored:factory",
            "--inputs", str(inputs_file),
            "--output", str(tmp_path / "baseline.json"),
            "--k", "2",
            "--epsilon", "0.9",
            "--accept-reference",
        ])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "run is incomplete" in captured.err

    def test_run_accepts_a_declared_decision_suite(self, capsys, tmp_path):
        suite_file = tmp_path / "suite.json"
        save_decision_suite(
            DecisionSuite(
                contract=DecisionContract(allowed={"allow", "block"}),
                cases=(
                    DecisionCase("ordinary request", "allow"),
                    DecisionCase("contains a secret", "block"),
                ),
            ),
            suite_file,
        )

        exit_code = main([
            "run",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--suite", str(suite_file),
            "--k", "4",
            "--epsilon", "0.5",
            "--no-relations",
            "--format", "json",
        ])
        report = json.loads(capsys.readouterr().out)

        assert exit_code == 0
        assert report["decision_contract"]["satisfied"] is True
        assert report["decision_contract"]["observed_coverage"] == 1.0

    def test_suite_snapshot_then_check(self, capsys, tmp_path):
        suite_file = tmp_path / "suite.json"
        snapshot_file = tmp_path / "baseline.json"
        save_decision_suite(
            DecisionSuite(
                contract=DecisionContract(allowed={"allow", "block"}),
                cases=(
                    DecisionCase("ordinary request", "allow"),
                    DecisionCase("contains a secret", "block"),
                ),
            ),
            suite_file,
        )

        snapshot_exit = main([
            "snapshot",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--suite", str(suite_file),
            "--output", str(snapshot_file),
            "--k", "4",
            "--epsilon", "0.5",
            "--accept-reference",
        ])
        assert snapshot_exit == 0
        capsys.readouterr()

        check_exit = main([
            "check",
            "--agent", "examples.toy_agent:deterministic_gate",
            "--suite", str(suite_file),
            "--snapshot", str(snapshot_file),
        ])
        assert check_exit == 0
        assert "snapshot clean" in capsys.readouterr().out


def test_snapshot_refuses_impossible_config_without_calling_the_agent(tmp_path):
    """An unreachable bound is arithmetic, so do not pay a model to discover it."""
    module = tmp_path / "counting_agent.py"
    module.write_text(
        "CALLS = []\n"
        "def build():\n"
        "    def fn(text):\n"
        "        CALLS.append(text)\n"
        "        return {'text': text, 'verdict': 'a' if 'x' in text else 'b'}\n"
        "    return fn\n"
    )
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("x one\nx two\ny three\ny four\n")

    sys.path.insert(0, str(tmp_path))
    try:
        code = main([
            "snapshot", "--agent", "counting_agent:build",
            "--inputs", str(seeds), "--output", str(tmp_path / "b.json"),
            "--accept-reference", "--k", "5", "--epsilon", "0.01",
        ])
        import counting_agent

        assert code == 2
        assert counting_agent.CALLS == [], "agent was called despite an impossible bound"
        assert not (tmp_path / "b.json").exists()
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("counting_agent", None)


def test_plan_prints_a_budget_without_calling_the_agent(tmp_path, capsys):
    """Knowing the bill in advance is the difference between adopting a
    tighter tolerance and discovering it on a provider invoice."""

    suite = {
        "schema": "agentverity.decision-suite/v1",
        "contract": {
            "allowed": ["approve", "deny"],
            "critical": ["deny"],
            "stability_targets": {"deny": 0.01},
        },
        "cases": [
            {"input": "routine", "expected": "approve"},
            {"input": "prohibited", "expected": "deny"},
        ],
    }
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite), encoding="utf-8")

    assert main(["plan", "--suite", str(path), "--epsilon", "0.05"]) == 0
    out = capsys.readouterr().out
    assert "zero-flip call plan" in out
    assert "approve" in out and "deny" in out
    assert "total" in out
    assert "minimum needed to certify quiet routes" in out


@pytest.mark.parametrize(
    ("observed", "earliest"),
    (("1/73", 110), ("3/73", 173), ("4/73", 202), ("8/73", 311)),
)
def test_plan_prices_the_audited_all_agree_continuations(
    observed, earliest, capsys
):
    """The CLI exposes reviewed inverse boundaries without rederiving them."""
    assert main([
        "plan", "--observed", observed, "--epsilon", "0.05",
    ]) == 0

    out = capsys.readouterr().out
    assert f"earliest:     {earliest} total pairs" in out
    assert "assumption:   every additional pair agrees" in out
    assert "cannot create early admission" in out


@pytest.mark.parametrize(
    ("maximum", "reachable"),
    (("201", "no"), ("202", "yes")),
)
def test_plan_checks_a_predeclared_maximum(maximum, reachable, capsys):
    assert main([
        "plan", "--observed", "4/73", "--epsilon", "0.05",
        "--max-pairs", maximum,
    ]) == 0

    out = capsys.readouterr().out
    assert f"maximum:      {maximum} total pairs" in out
    assert f"reachable:    {reachable}" in out


@pytest.mark.parametrize("observed", ("three/73", "1", "-1/73", "0/0", "4/3"))
def test_plan_refuses_malformed_observed_counts(observed, capsys):
    option = f"--observed={observed}" if observed.startswith("-") else "--observed"
    argv = ["plan", option] if option != "--observed" else ["plan", option, observed]
    assert main(argv) == 2
    assert "plan refused:" in capsys.readouterr().err


def test_plan_refuses_an_invalid_tolerance(capsys):
    assert main(["plan", "--observed", "1/73", "--epsilon", "0"]) == 2
    assert "epsilon must be between 0 and 1" in capsys.readouterr().err


def test_maximum_pairs_applies_only_to_observed_planning(tmp_path, capsys):
    suite = {
        "schema": "agentverity.decision-suite/v1",
        "contract": {"allowed": ["approve"]},
        "cases": [{"input": "routine", "expected": "approve"}],
    }
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite), encoding="utf-8")

    assert main(["plan", "--suite", str(path), "--max-pairs", "100"]) == 2
    assert "--max-pairs applies to --observed" in capsys.readouterr().err


def test_plan_requires_exactly_one_planning_source(tmp_path):
    path = tmp_path / "suite.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as missing:
        main(["plan"])
    with pytest.raises(SystemExit) as conflicting:
        main(["plan", "--suite", str(path), "--observed", "1/73"])

    assert missing.value.code == conflicting.value.code == 2


def test_run_refuses_an_underfunded_route_plan_before_agent_calls(
    tmp_path,
    capsys,
    monkeypatch,
):
    calls = []

    def factory():
        def agent(text):
            calls.append(text)
            return {"verdict": text}

        return agent

    monkeypatch.setattr("agentverity.cli._load_agent", lambda _spec: factory)
    suite = DecisionSuite(
        contract=DecisionContract(
            allowed={"approve", "deny"},
            stability_targets={"deny": 0.05},
        ),
        cases=(
            DecisionCase("approve", "approve"),
            DecisionCase("deny", "deny"),
        ),
    )
    path = tmp_path / "suite.json"
    save_decision_suite(suite, path)

    exit_code = main(
        [
            "run",
            "--agent",
            "ignored:factory",
            "--suite",
            str(path),
            "--budget",
            "10",
            "--epsilon",
            "0.5",
            "--no-relations",
        ]
    )

    assert exit_code == 2
    assert calls == []
    assert "above budget=10" in capsys.readouterr().err


def test_assess_reports_on_imported_evidence_without_calling_anything(capsys):
    """The point of the command: a team that already ran their agent gets an
    admission decision without paying for the calls twice."""
    path = EXAMPLES / "imported_evidence.json"

    assert main(["assess", "--evidence", str(path), "--epsilon", "0.05"]) == 0
    out = capsys.readouterr().out
    assert "STABILITY BY ROUTE" in out
    assert "card_security" in out


def test_assess_prints_the_independence_caveat_when_isolation_is_unknown(
    tmp_path, capsys
):
    payload = {
        "schema": "agentverity.evidence/v2",
        "cases": [
            {"input": "a", "observations": ["approve", "approve"]},
            {"input": "b", "observations": ["deny", "deny"]},
        ],
    }
    path = tmp_path / "runs.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    main(["assess", "--evidence", str(path)])
    assert "assumed rather than established" in capsys.readouterr().out


def test_assess_writes_the_same_json_report_a_live_run_would(tmp_path):
    out = tmp_path / "report.json"
    main([
        "assess",
        "--evidence", str(EXAMPLES / "imported_evidence.json"),
        "--json", str(out),
    ])
    payload = json.loads(out.read_text())

    assert "meter" in payload
    assert payload["schema"].startswith("agentverity.run/")


def test_assess_imports_promptfoo_without_calling_the_target(tmp_path, capsys):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "schema": "agentverity.decision-suite/v1",
                "contract": {"allowed": ["approve", "review"]},
                "cases": [
                    {"input": "routine", "expected": "approve"},
                    {"input": "ambiguous", "expected": "review"},
                ],
            }
        ),
        encoding="utf-8",
    )
    rows = []
    for test_index, decision in ((0, "approve"), (1, "review")):
        for _ in range(4):
            rows.append(
                    {
                        "testIdx": test_index,
                        "promptId": "router",
                        "provider": {"id": "local"},
                        "prompt": {
                            "raw": "routine" if test_index == 0 else "ambiguous"
                        },
                        "response": {"output": decision},
                    "failureReason": 0,
                }
            )
    export_path = tmp_path / "promptfoo.json"
    export_path.write_text(
        json.dumps({"version": 3, "results": rows}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "assess",
            "--promptfoo",
            str(export_path),
            "--suite",
            str(suite_path),
            "--epsilon",
            "0.5",
        ]
    )

    assert exit_code == 0
    assert "DECLARED DECISION CONTRACT" in capsys.readouterr().out


def test_promptfoo_import_requires_a_reviewed_suite(tmp_path, capsys):
    path = tmp_path / "promptfoo.json"
    path.write_text(json.dumps({"version": 3, "results": []}), encoding="utf-8")

    assert main(["assess", "--promptfoo", str(path)]) == 2
    assert "--promptfoo requires --suite" in capsys.readouterr().err


def test_a_bad_evidence_file_is_a_clean_cli_refusal(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")

    assert main(["assess", "--evidence", str(path)]) == 2
    assert "assessment refused:" in capsys.readouterr().err
