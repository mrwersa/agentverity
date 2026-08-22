"""Representative offline paths pin every documented CLI exit class."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentverity import DecisionCase, DecisionContract, DecisionSuite
from agentverity.cli import main
from agentverity.decision_contract import save_decision_suite

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (ROOT / "tests/fixtures/compatibility/v0.19.0/cli-exit-contract.json").read_text(
        encoding="utf-8"
    )
)


def _invoke(argv: list[str]) -> int:
    """Normalize argparse usage exits and command return codes."""
    try:
        return main(argv)
    except SystemExit as exc:
        assert isinstance(exc.code, int)
        return exc.code


def _suite(path: Path) -> Path:
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"approve", "review"}),
        cases=(
            DecisionCase("alpha", "approve"),
            DecisionCase("beta", "review"),
        ),
    )
    save_decision_suite(suite, path)
    return path


def _evidence(path: Path, *, blind: bool = False, flipping: bool = False) -> Path:
    approve = ["approve", "review"] * 4 if flipping else ["approve"] * 8
    review = ["approve"] * 8 if blind else ["review"] * 8
    path.write_text(
        json.dumps(
            {
                "schema": "agentverity.evidence/v2",
                "layer": "verdict",
                "isolation": "fresh-session",
                "cases": [
                    {"input": "alpha", "expected": "approve", "observations": approve},
                    {"input": "beta", "expected": "review", "observations": review},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "scenario, expected",
    CONTRACT["commands"]["run"].items(),
)
def test_run_exit_contract(scenario, expected, monkeypatch, tmp_path, capsys):
    inputs = tmp_path / "inputs.txt"
    inputs.write_text("alpha\nbeta\n", encoding="utf-8")

    def factory():
        if scenario == "finding":
            return lambda _text: {"verdict": "approve"}
        return lambda text: {"verdict": "approve" if text == "alpha" else "review"}

    if scenario == "refusal":
        monkeypatch.setattr(
            "agentverity.cli._load_agent",
            lambda _spec: (_ for _ in ()).throw(ImportError("missing")),
        )
    else:
        monkeypatch.setattr("agentverity.cli._load_agent", lambda _spec: factory)
    code = _invoke(
        [
            "run",
            "--agent",
            "fixture:factory",
            "--inputs",
            str(inputs),
            "--k",
            "4",
            "--epsilon",
            "0.5",
            "--no-relations",
        ]
    )
    assert code == expected
    capsys.readouterr()


@pytest.mark.parametrize("scenario, expected", CONTRACT["commands"]["plan"].items())
def test_plan_exit_contract(scenario, expected, tmp_path, capsys):
    argv = ["plan", "--suite", str(_suite(tmp_path / "suite.json"))]
    if scenario == "usage_error":
        argv = ["plan"]
    assert _invoke(argv) == expected
    capsys.readouterr()


@pytest.mark.parametrize("scenario, expected", CONTRACT["commands"]["assess"].items())
def test_assess_exit_contract(scenario, expected, tmp_path, capsys):
    path = tmp_path / "evidence.json"
    if scenario == "refusal":
        path.write_text("not json", encoding="utf-8")
    else:
        _evidence(path, blind=scenario == "finding")
    assert _invoke(["assess", "--evidence", str(path), "--epsilon", "0.5"]) == expected
    capsys.readouterr()


@pytest.mark.parametrize(
    "scenario, expected", CONTRACT["commands"]["compare-evidence"].items()
)
def test_compare_evidence_exit_contract(scenario, expected, tmp_path, capsys):
    before = _evidence(tmp_path / "before.json")
    after = tmp_path / "after.json"
    if scenario == "refusal":
        after.write_text("not json", encoding="utf-8")
    else:
        _evidence(after, flipping=scenario == "drift")
    assert (
        _invoke(["compare-evidence", str(before), str(after), "--epsilon", "0.5"])
        == expected
    )
    capsys.readouterr()


def _agent_factory(changed: bool = False):
    def factory():
        def agent(text):
            normal = "approve" if text == "alpha" else "review"
            changed_value = "review" if text == "alpha" else "approve"
            return {"verdict": changed_value if changed else normal}

        return agent

    return factory


@pytest.mark.parametrize("scenario, expected", CONTRACT["commands"]["snapshot"].items())
def test_snapshot_exit_contract(scenario, expected, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("agentverity.cli._load_agent", lambda _spec: _agent_factory())
    argv = [
        "snapshot",
        "--agent",
        "fixture:factory",
        "--suite",
        str(_suite(tmp_path / "suite.json")),
        "--output",
        str(tmp_path / "snapshot.json"),
        "--k",
        "4",
        "--epsilon",
        "0.5",
    ]
    if scenario == "admitted":
        argv.append("--accept-reference")
    assert _invoke(argv) == expected
    capsys.readouterr()


@pytest.mark.parametrize("scenario, expected", CONTRACT["commands"]["check"].items())
def test_check_exit_contract(scenario, expected, monkeypatch, tmp_path, capsys):
    suite = _suite(tmp_path / "suite.json")
    snapshot = tmp_path / "snapshot.json"
    monkeypatch.setattr("agentverity.cli._load_agent", lambda _spec: _agent_factory())
    assert (
        _invoke(
            [
                "snapshot",
                "--agent",
                "fixture:factory",
                "--suite",
                str(suite),
                "--output",
                str(snapshot),
                "--k",
                "4",
                "--epsilon",
                "0.5",
                "--accept-reference",
            ]
        )
        == 0
    )
    capsys.readouterr()
    if scenario == "refusal":
        snapshot.write_text("not json", encoding="utf-8")
    elif scenario == "drift":
        monkeypatch.setattr(
            "agentverity.cli._load_agent", lambda _spec: _agent_factory(True)
        )
    assert (
        _invoke(
            [
                "check",
                "--agent",
                "fixture:factory",
                "--suite",
                str(suite),
                "--snapshot",
                str(snapshot),
            ]
        )
        == expected
    )
    capsys.readouterr()


def test_exit_contract_names_every_cli_command():
    assert CONTRACT["baseline"] == "agentverity==0.19.0"
    assert CONTRACT["schema"] == "agentverity.cli-exit-contract/v1"
    assert set(CONTRACT["commands"]) == {
        "run",
        "plan",
        "assess",
        "compare-evidence",
        "snapshot",
        "check",
    }
