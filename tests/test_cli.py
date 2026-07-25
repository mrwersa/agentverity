"""Tests for agentverity.cli."""

from __future__ import annotations

import json

import pytest

from agentverity.cli import main
from agentverity.observation import Observation


def _write_inputs(path: str, lines: list[str]) -> None:
    with open(path, "w") as f:
        f.writelines(line + "\n" for line in lines)


class TestCLI:
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

    def test_run_false_agent_spec(self, tmp_path):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["hello"])

        with pytest.raises(ValueError, match="--agent"):
            main([
                "run",
                "--agent", "not_a_dotted_path",
                "--inputs", str(inputs_file),
            ])

    def test_run_bad_module(self, tmp_path):
        inputs_file = tmp_path / "inputs.txt"
        _write_inputs(str(inputs_file), ["hello"])

        with pytest.raises(ModuleNotFoundError):
            main([
                "run",
                "--agent", "nonexistent_module:func",
                "--inputs", str(inputs_file),
            ])

    def test_no_subcommand(self):
        with pytest.raises(SystemExit):
            main([])

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
        assert report["schema"] == "agentverity.run/v1"
        assert report["relations"] == []
        assert report["complete"] is True

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
