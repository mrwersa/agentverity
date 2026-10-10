#!/usr/bin/env python3
"""Reproduce the disagreement-count and dependence results reported in the paper."""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Any

SCHEMA = "anonymous.method-validation/v2"
OUTCOMES = ("qualify", "exceeds_tolerance", "undecided")


def wilson_interval(disagreements: int, pairs: int, z: float) -> tuple[float, float]:
    if pairs < 1 or not 0 <= disagreements <= pairs:
        raise ValueError(
            "disagreements must lie between zero and the positive pair count"
        )
    rate = disagreements / pairs
    denominator = 1 + z * z / pairs
    centre = (rate + z * z / (2 * pairs)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / pairs + z * z / (4 * pairs * pairs))
    radius /= denominator
    return max(0.0, centre - radius), min(1.0, centre + radius)


def classify(disagreements: int, pairs: int, epsilon: float, z: float) -> str:
    low, high = wilson_interval(disagreements, pairs, z)
    if high < epsilon:
        return "qualify"
    if low > epsilon:
        return "exceeds_tolerance"
    return "undecided"


def maximum_qualifying_disagreements(
    pairs: int, epsilon: float, z: float
) -> int:
    """Largest disagreement count that qualifies at the stated pair budget."""
    if pairs < 1 or not 0 < epsilon < 1:
        raise ValueError("pairs must be positive and epsilon must lie in (0, 1)")
    boundary = pairs * epsilon - z * math.sqrt(
        pairs * epsilon * (1 - epsilon)
    )
    return math.ceil(boundary) - 1


def minimum_qualifying_budget(
    disagreements: int, epsilon: float, z: float
) -> int:
    """Smallest pair budget that qualifies ``disagreements`` disagreements."""
    if disagreements < 0 or not 0 < epsilon < 1:
        raise ValueError(
            "disagreements must be non-negative and epsilon must lie in (0, 1)"
        )
    root = (
        z * math.sqrt(epsilon * (1 - epsilon))
        + math.sqrt(
            z * z * epsilon * (1 - epsilon)
            + 4 * epsilon * disagreements
        )
    ) / (2 * epsilon)
    return math.floor(root * root) + 1


def draw_pairs(
    rng: random.Random, rate: float, pairs: int, correlation: float
) -> list[bool]:
    if rate in (0.0, 1.0):
        return [bool(rate)] * pairs
    effective_rate = rate
    if correlation:
        concentration = 1 / correlation - 1
        effective_rate = rng.betavariate(
            rate * concentration, (1 - rate) * concentration
        )
    return [rng.random() < effective_rate for _ in range(pairs)]


def binomial_probability(
    pairs: int, disagreements: int, rate: float
) -> float:
    return (
        math.comb(pairs, disagreements)
        * rate**disagreements
        * (1 - rate) ** (pairs - disagreements)
    )


def beta_binomial_probability(
    pairs: int, disagreements: int, rate: float, correlation: float
) -> float:
    concentration = 1 / correlation - 1
    alpha = rate * concentration
    beta = (1 - rate) * concentration
    log_probability = (
        math.lgamma(pairs + 1)
        - math.lgamma(disagreements + 1)
        - math.lgamma(pairs - disagreements + 1)
        + math.lgamma(disagreements + alpha)
        + math.lgamma(pairs - disagreements + beta)
        - math.lgamma(pairs + alpha + beta)
        + math.lgamma(alpha + beta)
        - math.lgamma(alpha)
        - math.lgamma(beta)
    )
    return math.exp(log_probability)


def exact_classification(
    pairs: int,
    rate: float,
    epsilon: float,
    z: float,
    correlation: float = 0.0,
) -> dict[str, Any]:
    outcomes = {name: 0.0 for name in OUTCOMES}
    for disagreements in range(pairs + 1):
        probability = (
            beta_binomial_probability(
                pairs, disagreements, rate, correlation
            )
            if correlation
            else binomial_probability(pairs, disagreements, rate)
        )
        outcomes[classify(disagreements, pairs, epsilon, z)] += probability
    return {
        "pairs": pairs,
        "rate": rate,
        "correlation": correlation,
        "outcomes": outcomes,
    }


def exact_boundary(
    pairs: int, epsilon: float, z: float, correlation: float = 0.0
) -> dict[str, Any]:
    result = exact_classification(pairs, epsilon, epsilon, z, correlation)
    result.update({
        "incorrect_directional_classification_probability": (
            result["outcomes"]["qualify"]
            + result["outcomes"]["exceeds_tolerance"]
        ),
    })
    return result


def simulate(
    *,
    trials: int = 100_000,
    seed: int = 20_260_822,
    epsilon: float = 0.05,
    alpha: float = 0.05,
    rates: tuple[float, ...] = (0.0, 0.025, 0.05, 0.1, 0.3),
    correlations: tuple[float, ...] = (0.0, 0.02, 0.05, 0.1),
) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials must be positive")
    if not 0 < epsilon < 1 or not 0 < alpha < 1:
        raise ValueError("epsilon and alpha must lie strictly between zero and one")
    if not rates or any(not 0 <= rate <= 1 for rate in rates):
        raise ValueError("rates must lie between zero and one")
    if not correlations or any(not 0 <= rho < 1 for rho in correlations):
        raise ValueError("correlations must lie from zero up to but excluding one")

    z = NormalDist().inv_cdf(1 - alpha / 2)
    pairs = minimum_qualifying_budget(0, epsilon, z)
    rng = random.Random(seed)
    rows = []

    for correlation in correlations:
        for rate in rates:
            outcomes: Counter[str] = Counter()
            for _ in range(trials):
                disagreements = sum(draw_pairs(rng, rate, pairs, correlation))
                outcomes[classify(disagreements, pairs, epsilon, z)] += 1
            wrong = (
                outcomes["exceeds_tolerance"]
                if rate < epsilon
                else outcomes["qualify"]
                if rate > epsilon
                else outcomes["qualify"] + outcomes["exceeds_tolerance"]
            ) / trials
            rows.append(
                {
                    "assumption": "iid" if correlation == 0 else "beta-binomial",
                    "correlation": correlation,
                    "true_disagreement_probability": rate,
                    "trials": trials,
                    "outcomes": {
                        name: outcomes[name] / trials for name in OUTCOMES
                    },
                    "incorrect_directional_classification_probability": wrong,
                    "incorrect_direction_mc95_half_width": 1.96
                    * math.sqrt(wrong * (1 - wrong) / trials),
                }
            )

    return {
        "schema": SCHEMA,
        "method": {
            "trials_per_scenario": trials,
            "seed": seed,
            "epsilon": epsilon,
            "alpha": alpha,
            "pairs": pairs,
            "rates": list(rates),
            "correlations": list(correlations),
        },
        "exact_boundary": exact_boundary(pairs, epsilon, z),
        "exact_boundary_sensitivity": [
            exact_boundary(budget, epsilon, z, correlation)
            for budget in (pairs, 146)
            for correlation in correlations
        ],
        "exact_off_boundary_sensitivity": [
            exact_classification(budget, 0.03, epsilon, z, 0.10)
            for budget in (146, 2_000)
        ],
        "results": rows,
        "interpretation": {
            "iid_is_the_claimed_model": True,
            "positive_correlation_is_sensitivity_only": True,
            "simulation_is_not_a_proof": True,
        },
    }


def render(result: dict[str, Any]) -> str:
    lines = [
        "assumption       rho      p    qualify    exceeds  undecided  incorrect"
    ]
    for row in result["results"]:
        outcomes = row["outcomes"]
        lines.append(
            f"{row['assumption']:<15} {row['correlation']:>4.2f}  "
            f"{row['true_disagreement_probability']:>5.3f}  "
            f"{outcomes['qualify']:>8.3%}  "
            f"{outcomes['exceeds_tolerance']:>8.3%}  "
            f"{outcomes['undecided']:>9.3%}  "
            f"{row['incorrect_directional_classification_probability']:>9.3%}"
        )
    exact = result["exact_boundary"]
    outcomes = exact["outcomes"]
    lines.extend([
        "",
        "exact iid boundary (p = epsilon)",
        (
            f"qualify {outcomes['qualify']:.3%}  "
            f"exceeds {outcomes['exceeds_tolerance']:.3%}  "
            f"undecided {outcomes['undecided']:.3%}  "
            "incorrect "
            f"{exact['incorrect_directional_classification_probability']:.3%}"
        ),
        "",
        "exact boundary sensitivity (p = epsilon)",
        "pairs   rho    qualify    exceeds  undecided  incorrect",
    ])
    for row in result["exact_boundary_sensitivity"]:
        outcomes = row["outcomes"]
        lines.append(
            f"{row['pairs']:>5}  {row['correlation']:>4.2f}  "
            f"{outcomes['qualify']:>8.3%}  "
            f"{outcomes['exceeds_tolerance']:>8.3%}  "
            f"{outcomes['undecided']:>9.3%}  "
            f"{row['incorrect_directional_classification_probability']:>9.3%}"
        )
    lines.extend([
        "",
        "exact off-boundary sensitivity (p = 0.03, rho = 0.10)",
        "pairs   qualify    exceeds  undecided",
    ])
    for row in result["exact_off_boundary_sensitivity"]:
        outcomes = row["outcomes"]
        lines.append(
            f"{row['pairs']:>5}  {outcomes['qualify']:>8.3%}  "
            f"{outcomes['exceeds_tolerance']:>8.3%}  "
            f"{outcomes['undecided']:>9.3%}"
        )
    return "\n".join(lines)


def comma_floats(value: str) -> tuple[float, ...]:
    return tuple(float(item) for item in value.split(","))


def validate_reported(result: dict[str, Any]) -> None:
    """Check the rounded claims without embedding attributable exact outputs."""
    if result["method"]["pairs"] != 73:
        raise ValueError("the zero-disagreement minimum is not 73 pairs")
    z = NormalDist().inv_cdf(0.975)
    if maximum_qualifying_disagreements(146, 0.05, z) != 2:
        raise ValueError("the 146-pair disagreement limit is not two")
    if tuple(minimum_qualifying_budget(f, 0.05, z) for f in range(4)) != (
        73,
        110,
        142,
        173,
    ):
        raise ValueError("the reported minimum qualifying budgets do not match")
    boundary = result["exact_boundary"][
        "incorrect_directional_classification_probability"
    ]
    if not 0.0528 < boundary < 0.0529:
        raise ValueError("the exact boundary rate is outside its reported range")

    ranges = {
        0.02: (0.19, 0.22),
        0.05: (0.34, 0.38),
        0.10: (0.50, 0.55),
    }
    rows = {
        (row["correlation"], row["true_disagreement_probability"]): row
        for row in result["results"]
    }
    for correlation, (low, high) in ranges.items():
        try:
            rate = rows[(correlation, 0.05)][
                "incorrect_directional_classification_probability"
            ]
        except KeyError as error:
            raise ValueError(
                f"missing boundary sensitivity row for correlation {correlation}"
            ) from error
        if not low < rate < high:
            raise ValueError(
                f"boundary sensitivity for correlation {correlation} is outside "
                "its reported Monte Carlo range"
            )

    exact_rows = {
        (row["pairs"], row["correlation"]): row
        for row in result["exact_boundary_sensitivity"]
    }
    maintenance_ranges = {
        0.02: (0.31, 0.33),
        0.05: (0.50, 0.52),
        0.10: (0.65, 0.67),
    }
    for correlation, (low, high) in maintenance_ranges.items():
        try:
            rate = exact_rows[(146, correlation)][
                "incorrect_directional_classification_probability"
            ]
        except KeyError as error:
            raise ValueError(
                f"missing 146-pair boundary row for correlation {correlation}"
            ) from error
        if not low < rate < high:
            raise ValueError(
                f"146-pair boundary sensitivity for correlation {correlation} "
                "is outside its reported exact range"
            )

    off_boundary = {
        row["pairs"]: row["outcomes"]["exceeds_tolerance"]
        for row in result["exact_off_boundary_sensitivity"]
    }
    if not 0.111 < off_boundary.get(146, 0.0) < 0.113:
        raise ValueError("146-pair off-boundary sensitivity is outside its reported range")
    if not 0.161 < off_boundary.get(2_000, 0.0) < 0.163:
        raise ValueError("2000-pair off-boundary sensitivity is outside its reported range")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20_260_822)
    parser.add_argument("--rates", type=comma_floats, default=(0.0, 0.025, 0.05, 0.1, 0.3))
    parser.add_argument("--correlations", type=comma_floats, default=(0.0, 0.02, 0.05, 0.1))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    result = simulate(
        trials=args.trials,
        seed=args.seed,
        rates=args.rates,
        correlations=args.correlations,
    )
    if args.check:
        try:
            validate_reported(result)
        except ValueError as error:
            print(f"FAIL  {error}")
            return 1
        print("PASS  fixed-seed experiment matches the reported ranges")
    else:
        print(render(result))
        if args.output is not None:
            encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
            args.output.write_text(encoded, encoding="utf-8")
            print(f"wrote {args.output.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
