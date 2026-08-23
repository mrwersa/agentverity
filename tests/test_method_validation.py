"""Executable checks for the reproducible statistical validation asset."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_method import SCHEMA, main, simulate

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "docs" / "evidence" / "method-validation.json"


def _rows(result, *, rule: str, correlation: float):
    return [
        row
        for row in result["results"]
        if row["rule"] == rule and row["correlation"] == correlation
    ]


def test_a_seed_reproduces_the_same_experiment() -> None:
    """A reviewer can rerun an asset without Monte Carlo drift."""
    kwargs = {
        "trials": 100,
        "seed": 41,
        "rates": (0.025, 0.05),
        "correlations": (0.0, 0.1),
    }

    assert simulate(**kwargs) == simulate(**kwargs)


def test_iid_boundary_behavior_is_inside_the_nominal_budget() -> None:
    """At p=epsilon, either directional claim is a false boundary call."""
    result = simulate(
        trials=20_000,
        seed=20260822,
        rates=(0.05,),
        correlations=(0.0,),
    )

    fixed = _rows(result, rule="fixed-wilson", correlation=0.0)[0]
    sequential = _rows(result, rule="predeclared-sequential", correlation=0.0)[0]
    exact_fixed = result["exact_boundary"]["fixed-wilson"]
    exact_sequential = result["exact_boundary"]["predeclared-sequential"]

    assert 0.035 < fixed["wrong_direction_rate"] < 0.065
    assert sequential["wrong_direction_rate"] < 0.05
    assert exact_fixed["calls"]["deterministic"] < 0.025
    assert exact_fixed["wrong_direction_rate"] > 0.05
    assert exact_sequential["calls"]["deterministic"] <= 0.025
    assert exact_sequential["wrong_direction_rate"] <= 0.05
    assert (
        abs(fixed["wrong_direction_rate"] - exact_fixed["wrong_direction_rate"])
        < 4 * fixed["wrong_direction_mc95_half_width"]
    )
    assert sum(fixed["calls"].values()) == pytest.approx(1.0)
    assert sum(sequential["calls"].values()) == pytest.approx(1.0)


def test_clustered_pairs_make_the_independence_caveat_visible() -> None:
    """The same marginal p is not the same evidence under dependence."""
    result = simulate(
        trials=5_000,
        seed=99,
        rates=(0.05,),
        correlations=(0.0, 0.1),
    )
    iid = _rows(result, rule="fixed-wilson", correlation=0.0)[0]
    clustered = _rows(result, rule="fixed-wilson", correlation=0.1)[0]

    assert clustered["wrong_direction_rate"] > 5 * iid["wrong_direction_rate"]


def test_the_cli_writes_versioned_machine_readable_evidence(tmp_path) -> None:
    """The command produces an auditable JSON artifact as well as a table."""
    output = tmp_path / "method.json"

    assert main(["--trials", "10", "--rates", "0.05", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["schema"] == SCHEMA
    assert payload["method"]["seed"] == 20_260_822
    assert payload["interpretation"]["simulation_is_not_a_proof"] is True


def test_the_committed_asset_and_document_record_the_boundary_finding() -> None:
    """The reproducible evidence and its candid interpretation travel together."""
    payload = json.loads(ASSET.read_text(encoding="utf-8"))
    documentation = (ROOT / "docs" / "method-validation.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert payload["schema"] == SCHEMA
    assert payload["method"]["trials_per_scenario"] == 100_000
    assert payload["method"]["correlations"] == [0.0, 0.02, 0.05, 0.1]
    assert payload["exact_boundary"]["fixed-wilson"][
        "wrong_direction_rate"
    ] == pytest.approx(0.052860564251125106)
    assert "nominal, not an exact finite-sample error" in documentation
    assert "35.816%" in documentation
    assert "52.431%" in documentation
    assert "docs/method-validation.md" in readme


def test_the_committed_asset_separates_rate_projection_from_best_case_continuation():
    """Evidence must preserve the distinction that exposed the planning defect."""
    payload = json.loads(ASSET.read_text(encoding="utf-8"))

    assert [
        row["fixed_count_best_case_pairs"] for row in payload["continuation_planning"]
    ] == [110, 173, 202, 311]
    assert [
        row["fixed_rate_projection_pairs"] for row in payload["continuation_planning"]
    ] == [139, 2302, None, None]
    assert (
        payload["interpretation"]["best_case_is_not_an_adaptive_stopping_rule"] is True
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"trials": 0}, "trials"),
        ({"epsilon": 0}, "epsilon"),
        ({"alpha": 1}, "alpha"),
        ({"rates": ()}, "rates"),
        ({"correlations": (1.0,)}, "correlations"),
    ],
)
def test_invalid_experiments_are_refused(kwargs, message) -> None:
    """A malformed validation run should fail before producing evidence."""
    with pytest.raises(ValueError, match=message):
        simulate(**kwargs)
