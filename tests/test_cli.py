"""Tests for agentverity.cli."""

from __future__ import annotations

import pytest

from agentverity.cli import main


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
