#!/usr/bin/env python3
"""Analyse finite-budget savings from anonymised derived evaluation summaries."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Any

SCHEMA = "anonymous.maintenance-audit/v2"
RESULT_SCHEMA = "anonymous.maintenance-audit-result/v2"
HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "maintenance_input.json"
DEFAULT_OUTPUT = HERE / "maintenance_results.json"


def load_input(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"expected schema {SCHEMA!r}")
    budget = payload.get("budget_pairs")
    epsilon = payload.get("epsilon")
    confidence = payload.get("confidence")
    cells = payload.get("cells")
    if not isinstance(budget, int) or budget < 1:
        raise ValueError("budget_pairs must be a positive integer")
    if not isinstance(cells, list) or not cells:
        raise ValueError("cells must be a non-empty list")
    if not isinstance(epsilon, (int, float)) or isinstance(epsilon, bool):
        raise TypeError("epsilon must be numeric")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must lie strictly between zero and one")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise TypeError("confidence must be numeric")
    if not 0 < confidence < 1:
        raise ValueError("confidence must lie strictly between zero and one")
    return payload


def endpoint_qualifies(
    disagreements: int, budget: int, epsilon: float, z: float
) -> bool:
    """Whether the Wilson upper bound qualifies at the declared endpoint."""
    observed = disagreements / budget
    score = (budget * epsilon - disagreements) / math.sqrt(
        budget * epsilon * (1 - epsilon)
    )
    return observed < epsilon and score > z


def wilson_interval(disagreements: int, pairs: int, z: float) -> tuple[float, float]:
    rate = disagreements / pairs
    denominator = 1 + z * z / pairs
    centre = (rate + z * z / (2 * pairs)) / denominator
    radius = z * math.sqrt(
        rate * (1 - rate) / pairs + z * z / (4 * pairs * pairs)
    ) / denominator
    return max(0.0, centre - radius), min(1.0, centre + radius)


def classify(disagreements: int, pairs: int, epsilon: float, z: float) -> str:
    low, high = wilson_interval(disagreements, pairs, z)
    if high < epsilon:
        return "qualify"
    if low > epsilon:
        return "exceeds_tolerance"
    return "undecided"


def analyse(payload: dict[str, Any]) -> dict[str, Any]:
    budget = payload["budget_pairs"]
    epsilon = payload["epsilon"]
    confidence = payload["confidence"]
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for cell in payload["cells"]:
        configuration = cell.get("configuration")
        request = cell.get("request")
        stop_pair = cell.get("stop_pair")
        final_classification = cell.get("final_classification")
        final_disagreements = cell.get("final_disagreements")
        disagreements_at_stop = cell.get("disagreements_at_stop")
        if not isinstance(configuration, str) or not isinstance(request, str):
            raise TypeError(
                "every cell needs anonymised configuration and request labels"
            )
        if final_classification not in {"qualify", "exceeds_tolerance", "undecided"}:
            raise ValueError(
                f"{configuration}/{request}: invalid final classification"
            )
        if (
            not isinstance(final_disagreements, int)
            or isinstance(final_disagreements, bool)
            or not 0 <= final_disagreements <= budget
        ):
            raise ValueError(
                f"{configuration}/{request}: final_disagreements must lie within the budget"
            )
        computed_classification = classify(final_disagreements, budget, epsilon, z)
        if final_classification != computed_classification:
            raise ValueError(
                f"{configuration}/{request}: final classification conflicts with "
                "final disagreement count"
            )
        if stop_pair is not None and (
            not isinstance(stop_pair, int)
            or isinstance(stop_pair, bool)
            or not 1 <= stop_pair <= budget
        ):
            raise ValueError(
                f"{configuration}/{request}: stop_pair must lie within the budget"
            )
        if stop_pair is None and disagreements_at_stop is not None:
            raise ValueError(
                f"{configuration}/{request}: disagreements_at_stop requires a stop"
            )
        if stop_pair is not None and (
            not isinstance(disagreements_at_stop, int)
            or isinstance(disagreements_at_stop, bool)
            or disagreements_at_stop < 1
        ):
            raise ValueError(
                f"{configuration}/{request}: stopped cells need a positive "
                "disagreements_at_stop"
            )
        if stop_pair is not None and final_disagreements < disagreements_at_stop:
            raise ValueError(
                f"{configuration}/{request}: final disagreement count precedes "
                "stopping count"
            )
        if stop_pair is not None and (
            endpoint_qualifies(disagreements_at_stop, budget, epsilon, z)
            or not endpoint_qualifies(
                disagreements_at_stop - 1, budget, epsilon, z
            )
        ):
            raise ValueError(
                f"{configuration}/{request}: stopping disagreement count does not "
                "cross the declared endpoint boundary"
            )

        final_qualifies = computed_classification == "qualify"
        summary_qualifies = stop_pair is None
        if summary_qualifies != final_qualifies:
            raise ValueError(
                f"{configuration}/{request}: stopping summary conflicts with final "
                "qualification"
            )
        grouped[configuration].append(
            {
                "request": request,
                "stopped": not summary_qualifies,
                "final_classification": final_classification,
                "multi_disagreement_stop": (
                    disagreements_at_stop is not None and disagreements_at_stop > 1
                ),
                "pairs_spent": budget if stop_pair is None else stop_pair,
                "pairs_saved": 0 if stop_pair is None else budget - stop_pair,
            }
        )

    def summarise(cells: list[dict[str, Any]]) -> dict[str, Any]:
        planned = budget * len(cells)
        saved = sum(cell["pairs_saved"] for cell in cells)
        stopped = [cell for cell in cells if cell["stopped"]]
        stopped_planned = budget * len(stopped)
        return {
            "cells": len(cells),
            "final_classifications": dict(
                sorted(
                    Counter(cell["final_classification"] for cell in cells).items()
                )
            ),
            "stops": len(stopped),
            "multi_disagreement_stops": sum(
                cell["multi_disagreement_stop"] for cell in stopped
            ),
            "pairs_planned": planned,
            "pairs_spent": planned - saved,
            "pairs_saved": saved,
            "saved_share": saved / planned,
            "stopped_pairs_planned": stopped_planned,
            "saved_share_when_stopped": (
                saved / stopped_planned if stopped_planned else None
            ),
            "mean_stop_pair": (
                sum(cell["pairs_spent"] for cell in stopped) / len(stopped)
                if stopped
                else None
            ),
        }

    all_cells = [cell for cells in grouped.values() for cell in cells]
    return {
        "schema": RESULT_SCHEMA,
        "budget_pairs": budget,
        "epsilon": epsilon,
        "confidence": confidence,
        "derived_input_inconsistencies": 0,
        "by_configuration": {
            configuration: summarise(cells)
            for configuration, cells in sorted(grouped.items())
        },
        "overall": summarise(all_cells),
    }


def render(result: dict[str, Any]) -> str:
    lines = [
        "configuration  cells  stops  pairs saved  saved share  stop saving  mean stop pair",
    ]
    for configuration, row in result["by_configuration"].items():
        mean = row["mean_stop_pair"]
        conditional = row["saved_share_when_stopped"]
        conditional_text = f"{conditional:.1%}" if conditional is not None else "n/a"
        lines.append(
            f"{configuration:>13}  {row['cells']:>5}  {row['stops']:>5}  "
            f"{row['pairs_saved']:>11}  {row['saved_share']:>10.1%}  "
            f"{conditional_text:>11}  "
            f"{mean if mean is not None else 'n/a':>17}"
        )
    row = result["overall"]
    lines.append(
        f"      ALL  {row['cells']:>5}  {row['stops']:>5}  "
        f"{row['pairs_saved']:>11}  {row['saved_share']:>10.1%}  "
        f"{row['saved_share_when_stopped']:>11.1%}  "
        f"{row['mean_stop_pair']:>17}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    result = analyse(load_input(args.input))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != encoded:
            print(f"FAIL  {args.output.name} is missing or stale")
            return 1
        print(f"PASS  {args.output.name} matches the anonymised analysis input")
    else:
        args.output.write_text(encoded, encoding="utf-8")
        print(render(result))
        print(f"wrote {args.output.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
