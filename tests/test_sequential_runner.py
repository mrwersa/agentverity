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


def _small_inputs() -> list[str]:
    """Few enough that a low budget is legal rather than refused outright."""
    return [f"input_{index}" for index in range(5)] + [
        f"secret_{index}" for index in range(5)
    ]


def _meter_only(**kwargs) -> RunConfig:
    """Blindness and relations off, so a call count is a meter call count."""
    return RunConfig(run_blindness=False, **kwargs)


@pytest.mark.parametrize("budget", [30, 50, 80])
def test_a_budget_caps_sequential_collection_as_it_caps_the_fixed_path(budget):
    """`budget` is documented as a cap on meter calls and was ignored here.

    Measured before the fix: `budget=50` spent 180 meter calls and returned
    `verdict-deterministic`, certifying on evidence the caller had explicitly
    sized as insufficient, while the fixed path spent 40 and said undecided.
    Overspending is bad; certifying because you overspent is worse.

    Threaded rather than refused, unlike declared route targets. A budget is a
    cap and a cap bounds early stopping happily. Targets are a second sizing
    rule, and two rules sizing one run is the conflict that gets refused.
    """
    fixed_agent, fixed_calls = _counted(_stable)
    fixed = run(fixed_agent, _small_inputs(), config=_meter_only(budget=budget),
                relations=[])
    seq_agent, seq_calls = _counted(_stable)
    sequential = run(seq_agent, _small_inputs(),
                     config=_meter_only(budget=budget, sequential=True),
                     relations=[])

    assert seq_calls["n"] <= budget, "the cap is a cap"
    assert seq_calls["n"] == fixed_calls["n"], "and both paths spend the same"
    assert "undecided" in sequential.meter.call
    assert "undecided" in fixed.meter.call, "the honest answer under a cap"


def test_a_capped_sequential_run_does_not_certify():
    """The direction that matters. A cap below what certification needs must
    not produce a certification, whichever path collected it."""
    agent, _ = _counted(_stable)
    result = run(agent, _small_inputs(),
                 config=_meter_only(budget=50, sequential=True), relations=[])

    assert result.meter.call != "verdict-deterministic"


def _suite() -> DecisionSuite:
    return DecisionSuite(
        contract=DecisionContract(
            allowed=frozenset({"allow", "block"}),
            required=frozenset({"allow", "block"}),
        ),
        cases=tuple(
            DecisionCase(input=text, expected="block" if "secret" in text else "allow")
            for text in _inputs()
        ),
    )


def test_a_suite_run_keeps_its_route_table_when_collection_stops_early():
    """Parity, because the route table is what a suite user came for.

    The sequential branch built the pooled meter and never called
    `stratify_runs`, so `route_stability` was None for every suite run in the
    new mode while the fixed path computed it.
    """
    fixed_agent, _ = _counted(_stable)
    fixed = run(fixed_agent, suite=_suite(), config=RunConfig())
    seq_agent, _ = _counted(_stable)
    sequential = run(seq_agent, suite=_suite(), config=RunConfig(sequential=True))

    assert fixed.route_stability is not None
    assert sequential.route_stability is not None
    named = {route.decision for route in sequential.route_stability.routes}
    assert named == {route.decision for route in fixed.route_stability.routes}
    assert named == {"allow", "block"}
