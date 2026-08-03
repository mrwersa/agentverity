"""`run` can stop at a checkpoint instead of spending the whole budget.

The statistical core shipped without this, so the saving was available to a
caller driving collection and not from `run` or the command line. That is the
same shape the isolation policy had before its second PR: correct, and inert
on the path most callers use.
"""

from __future__ import annotations

import json
import random

import pytest

from agentverity import RunConfig, run
from agentverity.adapters.callable_adapter import from_callable
from agentverity.decision_contract import DecisionCase, DecisionContract, DecisionSuite
from agentverity.reporting import run_result_to_dict
from agentverity.sequential import plan_sequential


def _inputs() -> list[str]:
    return [f"input_{index}" for index in range(25)] + [
        f"secret_{index}" for index in range(25)
    ]


def _counted(fn):
    """Wrap an agent so the test can assert on calls rather than on trust."""
    calls = {"n": 0}

    def counted(text: str):
        calls["n"] += 1
        return fn(text)

    return from_callable(counted), calls


def _stable(text: str) -> dict:
    return {"verdict": "block" if "secret" in text else "allow"}


def _flaky(rate: float, seed: int):
    rng = random.Random(seed)

    def agent(text: str) -> dict:
        base = "block" if "secret" in text else "allow"
        return {"verdict": "other" if rng.random() < rate else base}

    return agent


def test_a_stable_agent_reaches_the_same_call_for_far_fewer_calls():
    fixed_agent, fixed_calls = _counted(_stable)
    fixed = run(fixed_agent, _inputs(), config=RunConfig(k=24))
    seq_agent, seq_calls = _counted(_stable)
    sequential = run(seq_agent, _inputs(), config=RunConfig(sequential=True))

    assert fixed.meter.call == sequential.meter.call == "verdict-deterministic"
    assert seq_calls["n"] < fixed_calls["n"] / 3


def test_an_unstable_agent_stops_sooner_still():
    stable_agent, stable_calls = _counted(_stable)
    run(stable_agent, _inputs(), config=RunConfig(sequential=True))
    flaky_agent, flaky_calls = _counted(_flaky(0.30, seed=3))
    result = run(flaky_agent, _inputs(), config=RunConfig(sequential=True))

    assert result.meter.call == "verdict-stochastic"
    assert flaky_calls["n"] < stable_calls["n"]


def test_the_checkpoint_decides_and_the_interval_does_not():
    """The whole point. Reading the interval at a stopping point it did not
    choose is the optional stopping this design avoids."""
    agent, _ = _counted(_stable)
    result = run(agent, _inputs(), config=RunConfig(sequential=True))
    meter = result.meter

    assert meter.sequential_call == "verdict-deterministic"
    assert meter.sequential_pairs == plan_sequential(meter.epsilon).budget
    assert meter.call is meter.sequential_call
    # More pairs were collected than the decision read, because a round adds
    # one pair per input and cannot land exactly on a checkpoint.
    assert meter.pair_trials > meter.sequential_pairs


def test_both_output_surfaces_say_which_count_decided():
    """A change that moves the terminal report and not the JSON one is the
    two-readings-that-disagree defect ADR 1 exists to remove."""
    agent, _ = _counted(_stable)
    result = run(agent, _inputs(), config=RunConfig(sequential=True))

    printed = result.summary()
    payload = json.loads(json.dumps(run_result_to_dict(result)))

    assert "decided by:  a declared checkpoint" in printed
    assert payload["meter"]["decided_by"] == {
        "rule": "declared-checkpoint",
        "pairs": result.meter.sequential_pairs,
    }


def test_the_fixed_sample_path_is_untouched():
    """Off by default, and the report says nothing about checkpoints."""
    agent, _ = _counted(_stable)
    result = run(agent, _inputs(), config=RunConfig(k=24))

    assert RunConfig().sequential is False
    assert result.meter.sequential_call is None
    assert "decided by" not in result.summary()
    assert "decided_by" not in run_result_to_dict(result)["meter"]


def test_sequential_and_declared_route_targets_are_refused_together():
    """Two rules sizing one run. Refused rather than one quietly winning."""
    suite = DecisionSuite(
        contract=DecisionContract(
            allowed=frozenset({"allow", "block"}),
            required=frozenset({"allow", "block"}),
            stability_targets={"block": 0.01},
        ),
        cases=tuple(
            DecisionCase(input=text, expected="block" if "secret" in text else "allow")
            for text in _inputs()
        ),
    )
    agent, calls = _counted(_stable)

    with pytest.raises(ValueError, match="two different ways"):
        run(agent, suite=suite, config=RunConfig(sequential=True))

    assert calls["n"] == 0, "refused before spending anything"


def test_a_failing_agent_does_not_spin_forever():
    """Every input failing ends the collection rather than looping on an
    empty live set."""
    def broken(text: str):
        raise RuntimeError("provider down")

    result = run(
        from_callable(broken),
        _inputs(),
        config=RunConfig(sequential=True, error_policy="record"),
    )

    assert not result.complete
    assert result.meter is None
