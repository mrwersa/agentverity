"""Diagnose a toy Supervisor -> Triage -> Planner -> Implementor pipeline.

Two defects are planted deliberately:

1. Triage ignores the report and always emits ``medium``.
2. Planning uses a stochastic route decision.

Run with:

    python examples/bugfix_pipeline.py
    python examples/bugfix_pipeline.py --json result.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from agentverity import Observation, from_callable, run, run_result_to_dict

BUG_REPORTS = [
    "NullPointerException in checkout when cart is empty",
    "Login page 500s intermittently under load",
    "Typo in footer copyright year",
    "Payment webhook drops events during traffic spikes",
    "Button colour slightly off-brand on dark mode",
    "Race condition corrupts order totals under concurrent writes",
]


def triage(_: str) -> dict:
    """Classify severity. Deliberate defect: the report is ignored."""
    return {"severity": "medium", "auto_fixable": True}


def triage_agent(report: str) -> Observation:
    result = triage(report)
    return Observation(text=str(result), verdict=result["severity"])


def make_supervisor(*, seed: int = 1, escalation_bias: float = 0.35):
    """Return a reproducibly stochastic toy supervisor."""
    rng = random.Random(seed)

    def supervisor(report: str) -> Observation:
        triage_result = triage(report)
        route = "escalate" if rng.random() < escalation_bias else "auto_fix"
        tools = ["triage", "planner"]
        if route == "auto_fix":
            tools.append("implementor")
        verdict = "auto_fixed" if route == "auto_fix" else "escalated"
        return Observation(
            text=f"{report} -> {verdict}",
            verdict=verdict,
            tools=tuple(tools),
            raw=triage_result,
        )

    return supervisor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    triage_result = run(from_callable(triage_agent), inputs=BUG_REPORTS)
    pipeline_result = run(
        from_callable(make_supervisor(seed=args.seed)),
        inputs=BUG_REPORTS,
    )

    print("### Triage step\n")
    print(triage_result.summary())
    print("\n### Full supervisor pipeline\n")
    print(pipeline_result.summary())

    if args.json:
        payload = {
            "schema": "agentverity.example.bugfix-pipeline/v1",
            "seed": args.seed,
            "inputs": len(BUG_REPORTS),
            "triage": run_result_to_dict(triage_result),
            "pipeline": run_result_to_dict(pipeline_result),
        }
        args.json.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
