"""The evaluator-stability example must preserve its narrow claim."""

from __future__ import annotations

import runpy
from pathlib import Path

from agentverity import assess_evidence

ROOT = Path(__file__).resolve().parents[1]


def _example_namespace() -> dict:
    return runpy.run_path(str(ROOT / "examples" / "evaluator_stability.py"))


def test_recorded_judge_verdicts_name_the_stochastic_human_label():
    namespace = _example_namespace()
    evidence = namespace["build_evidence"]()
    result = assess_evidence(
        evidence,
        namespace["build_contract"](),
        epsilon=0.05,
    )

    assert evidence.provenance["target_kind"] == "evaluator-verdict"
    assert result.route_stability is not None
    assert result.route_stability.stochastic == ("pass",)
    assert result.meter.pair_flips == 13


def test_example_states_that_repeatability_is_not_validity(capsys):
    namespace = _example_namespace()

    namespace["main"]()

    output = capsys.readouterr().out
    assert "NOT READY" in output
    assert "stochastic human-labelled classes: pass" in output
    assert "Validity still requires" in output
