#!/usr/bin/env python3
"""Reproduce AgentVerity's fixed and sequential operating characteristics.

The exact guarantees live in the implementation and DESIGN.md. This simulation
is an empirical cross-check and a dependence sensitivity analysis, not a proof.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Any

from agentverity.meter import (
    best_case_admission_pairs,
    classify_call,
    pairs_for_deterministic_call,
    wilson_ci,
)
from agentverity.sequential import decide_sequentially, plan_sequential

SCHEMA = "agentverity.method-validation/v2"
DETERMINISTIC = "deterministic"
STOCHASTIC = "stochastic"
UNDECIDED = "undecided"


def _call_name(call: str) -> str:
    if call == "verdict-deterministic":
        return DETERMINISTIC
    if call == "verdict-stochastic":
        return STOCHASTIC
    return UNDECIDED


def _outcomes(
    rng: random.Random,
    *,
    rate: float,
    pairs: int,
    correlation: float,
) -> list[bool]:
    """Draw one qualification run under an iid or beta-binomial model."""
    if rate in (0.0, 1.0):
        return [bool(rate)] * pairs
    if correlation == 0.0:
        effective_rate = rate
    else:
        concentration = 1 / correlation - 1
        effective_rate = rng.betavariate(
            rate * concentration,
            (1 - rate) * concentration,
        )
    return [rng.random() < effective_rate for _ in range(pairs)]


def _wrong_direction(calls: Counter[str], rate: float, epsilon: float) -> int:
    if rate < epsilon:
        return calls[STOCHASTIC]
    if rate > epsilon:
        return calls[DETERMINISTIC]
    return calls[DETERMINISTIC] + calls[STOCHASTIC]


def _binomial_probability(pairs: int, flips: int, rate: float) -> float:
    return math.comb(pairs, flips) * rate**flips * (1 - rate) ** (pairs - flips)


def _exact_fixed_calls(
    *, pairs: int, rate: float, epsilon: float, z: float
) -> dict[str, float]:
    calls = {DETERMINISTIC: 0.0, STOCHASTIC: 0.0, UNDECIDED: 0.0}
    for flips in range(pairs + 1):
        low, high = wilson_ci(flips, pairs, z)
        call = _call_name(classify_call(low, high, epsilon))
        calls[call] += _binomial_probability(pairs, flips, rate)
    return calls


def _exact_sequential_calls(plan, *, rate: float) -> dict[str, float]:
    calls = {DETERMINISTIC: 0.0, STOCHASTIC: 0.0, UNDECIDED: 0.0}
    live = {0: 1.0}
    previous = 0
    for checkpoint in plan.checkpoints:
        increment = checkpoint - previous
        next_live: dict[int, float] = {}
        for prior_flips, prior_probability in live.items():
            for new_flips in range(increment + 1):
                flips = prior_flips + new_flips
                probability = prior_probability * _binomial_probability(
                    increment, new_flips, rate
                )
                call = plan.call_at(checkpoint, flips)
                if call is None:
                    next_live[flips] = next_live.get(flips, 0.0) + probability
                else:
                    calls[_call_name(call)] += probability
        live = next_live
        previous = checkpoint
    assert not live
    return calls


def _continuation_planning(epsilon: float, z: float) -> list[dict[str, Any]]:
    """Cross-check the two distinct planning questions on canonical counts."""
    rows = []
    for flips in (1, 3, 4, 8):
        pairs = 73
        rows.append(
            {
                "observed_flips": flips,
                "observed_pairs": pairs,
                "fixed_rate_projection_pairs": pairs_for_deterministic_call(
                    epsilon, z, flip_rate=flips / pairs
                ),
                "fixed_count_best_case_pairs": best_case_admission_pairs(
                    epsilon, flips=flips, pairs=pairs, z=z
                ),
            }
        )
    return rows


def _row(
    *,
    rule: str,
    rate: float,
    correlation: float,
    calls: Counter[str],
    pairs_spent: int,
    trials: int,
    epsilon: float,
) -> dict[str, Any]:
    shares = {
        name: calls[name] / trials for name in (DETERMINISTIC, STOCHASTIC, UNDECIDED)
    }
    wrong = _wrong_direction(calls, rate, epsilon) / trials
    half_width = 1.96 * math.sqrt(wrong * (1 - wrong) / trials)

    return {
        "rule": rule,
        "assumption": "iid" if correlation == 0 else "beta-binomial",
        "correlation": correlation,
        "true_flip_rate": rate,
        "trials": trials,
        "calls": shares,
        "wrong_direction_rate": wrong,
        "wrong_direction_mc95_half_width": half_width,
        "mean_pairs": pairs_spent / trials,
    }


def simulate(
    *,
    trials: int = 20_000,
    seed: int = 20_260_822,
    epsilon: float = 0.05,
    alpha: float = 0.05,
    rates: tuple[float, ...] | None = None,
    correlations: tuple[float, ...] = (0.0, 0.02, 0.05, 0.1),
) -> dict[str, Any]:
    """Return deterministic Monte Carlo results for both admission rules.

    ``correlation`` is the intraclass correlation between pairs within one
    simulated qualification run. Zero produces the independent Bernoulli model
    assumed by the methods. Positive values draw one latent run-level flip rate
    from a beta distribution, preserving the marginal rate while clustering
    outcomes.
    """
    if trials < 1:
        raise ValueError("trials must be at least 1")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    if rates is None:
        rates = tuple(
            dict.fromkeys(
                (
                    0.0,
                    epsilon / 2,
                    epsilon,
                    min(2 * epsilon, 1.0),
                    round(min(6 * epsilon, 1.0), 12),
                )
            )
        )
    if not rates or any(not 0 <= rate <= 1 for rate in rates):
        raise ValueError("rates must contain values between 0 and 1")
    if not correlations or any(not 0 <= value < 1 for value in correlations):
        raise ValueError(
            "correlations must contain values from 0 up to but not including 1"
        )

    z = NormalDist().inv_cdf(1 - alpha / 2)
    fixed_pairs = pairs_for_deterministic_call(epsilon, z)
    assert fixed_pairs is not None
    sequential = plan_sequential(epsilon, alpha=alpha)
    maximum_pairs = max(fixed_pairs, sequential.budget)
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []

    for correlation in correlations:
        for rate in rates:
            fixed_calls: Counter[str] = Counter()
            sequential_calls: Counter[str] = Counter()
            sequential_spent = 0
            for _ in range(trials):
                outcomes = _outcomes(
                    rng,
                    rate=rate,
                    pairs=maximum_pairs,
                    correlation=correlation,
                )
                flips = sum(outcomes[:fixed_pairs])
                low, high = wilson_ci(flips, fixed_pairs, z)
                fixed_calls[_call_name(classify_call(low, high, epsilon))] += 1

                call, spent = decide_sequentially(
                    sequential, outcomes[: sequential.budget]
                )
                sequential_calls[_call_name(call)] += 1
                sequential_spent += spent

            rows.append(
                _row(
                    rule="fixed-wilson",
                    rate=rate,
                    correlation=correlation,
                    calls=fixed_calls,
                    pairs_spent=fixed_pairs * trials,
                    trials=trials,
                    epsilon=epsilon,
                )
            )
            rows.append(
                _row(
                    rule="predeclared-sequential",
                    rate=rate,
                    correlation=correlation,
                    calls=sequential_calls,
                    pairs_spent=sequential_spent,
                    trials=trials,
                    epsilon=epsilon,
                )
            )

    fixed_boundary = _exact_fixed_calls(
        pairs=fixed_pairs,
        rate=epsilon,
        epsilon=epsilon,
        z=z,
    )
    sequential_boundary = _exact_sequential_calls(sequential, rate=epsilon)

    return {
        "schema": SCHEMA,
        "method": {
            "trials_per_scenario": trials,
            "seed": seed,
            "epsilon": epsilon,
            "alpha": alpha,
            "rates": list(rates),
            "correlations": list(correlations),
            "fixed": {"pairs": fixed_pairs, "z": z},
            "sequential": {
                "pairs": sequential.budget,
                "checkpoints": list(sequential.checkpoints),
                "certify_at_most": sequential.certify_at_most,
                "stochastic_at_least": sequential.stochastic_at_least,
            },
        },
        "exact_boundary": {
            "fixed-wilson": {
                "calls": fixed_boundary,
                "wrong_direction_rate": fixed_boundary[DETERMINISTIC]
                + fixed_boundary[STOCHASTIC],
            },
            "predeclared-sequential": {
                "calls": sequential_boundary,
                "wrong_direction_rate": sequential_boundary[DETERMINISTIC]
                + sequential_boundary[STOCHASTIC],
            },
        },
        "continuation_planning": _continuation_planning(epsilon, z),
        "interpretation": {
            "best_case_is_not_an_adaptive_stopping_rule": True,
            "iid_is_the_claimed_model": True,
            "positive_correlation_is_sensitivity_only": True,
            "simulation_is_not_a_proof": True,
        },
        "results": rows,
    }


def render(result: dict[str, Any]) -> str:
    """Render a compact Markdown table for human inspection."""
    lines = [
        "| assumption | rho | true p | rule | deterministic | stochastic | undecided | wrong direction | mean pairs |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in result["results"]:
        calls = row["calls"]
        lines.append(
            "| {assumption} | {correlation:.2f} | {true_flip_rate:.3f} | {rule} | "
            "{deterministic:.3%} | {stochastic:.3%} | {undecided:.3%} | "
            "{wrong_direction_rate:.3%} ± {wrong_direction_mc95_half_width:.3%} | "
            "{mean_pairs:.1f} |".format(**row, **calls)
        )
    return "\n".join(lines)


def _comma_floats(value: str) -> tuple[float, ...]:
    try:
        return tuple(float(item) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20_260_822)
    parser.add_argument("--epsilon", type=float, default=0.05)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--rates", type=_comma_floats)
    parser.add_argument(
        "--correlations", type=_comma_floats, default=(0.0, 0.02, 0.05, 0.1)
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        result = simulate(
            trials=args.trials,
            seed=args.seed,
            epsilon=args.epsilon,
            alpha=args.alpha,
            rates=args.rates,
            correlations=args.correlations,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(render(result))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
