"""Evaluate a live payment router with DeepEval and AgentVerity.

Examples:

    python examples/production_stack/evaluate_stack.py --target local
    python examples/production_stack/evaluate_stack.py --target agentcore --otel
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cases import CASES
from payment_agent import build_isolated_router
from runtime_client import build_runtime_router

from agentverity import (
    PRECISION_LEVELS,
    RunConfig,
    SnapshotRefused,
    create_snapshot,
    plan_repeats,
    record_otel_run,
    run,
    save_snapshot,
    write_junit_xml,
)


def _quality_score(agent) -> tuple[int, int]:
    """Use DeepEval's deterministic exact-match metric for route labels."""
    try:
        from deepeval.metrics import ExactMatchMetric
        from deepeval.test_case import LLMTestCase
    except ImportError as exc:  # pragma: no cover - live integration
        raise RuntimeError(
            'Install the live stack with: pip install -e ".[showcase]"'
        ) from exc

    passed = 0
    for ticket, expected in CASES:
        actual = str(agent(ticket).verdict)
        case = LLMTestCase(
            input=ticket,
            actual_output=actual,
            expected_output=expected,
        )
        metric = ExactMatchMetric(threshold=1.0)
        metric.measure(case)
        passed += int(metric.is_successful())
    return passed, len(CASES)


def _build_target(name: str):
    if name == "local":
        return build_isolated_router()
    return build_runtime_router()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=("local", "agentcore"),
        default="local",
        help="Invoke Bedrock directly through Strands or a deployed runtime.",
    )
    parser.add_argument(
        "--precision",
        choices=tuple(PRECISION_LEVELS),
        default="cheap",
        help="Stability threshold. Cheap is appropriate for the first live run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write the AgentVerity JUnit report and optional snapshot.",
    )
    parser.add_argument(
        "--accept-reference",
        action="store_true",
        help="Explicitly approve and save a stable, non-blind reference.",
    )
    parser.add_argument(
        "--otel",
        action="store_true",
        help="Emit one aggregate span through the configured OTEL provider.",
    )
    args = parser.parse_args()
    if args.accept_reference and not args.output_dir:
        parser.error("--accept-reference requires --output-dir")

    epsilon = PRECISION_LEVELS[args.precision]
    repeats = plan_repeats(len(CASES), epsilon)
    quality_calls = len(CASES)
    preflight_calls = repeats * len(CASES)
    print("PAYMENT TRIAGE: LIVE EVALUATION STACK")
    print("=====================================")
    print(f"Target: {args.target}")
    print(
        f"Planned model calls: {quality_calls + preflight_calls} "
        f"({quality_calls} DeepEval + {preflight_calls} AgentVerity)"
    )
    print()

    agent = _build_target(args.target)
    correct, total = _quality_score(agent)
    print(f"DeepEval exact-match: {correct}/{total} labelled routes passed")

    result = run(
        agent,
        inputs=[ticket for ticket, _ in CASES],
        relations=[],
        config=RunConfig(precision=args.precision),
    )
    print(result.summary())

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_junit_xml(
            result,
            args.output_dir / "agentverity.xml",
            suite_name=f"payment-triage.{args.target}.agentverity",
        )

    if args.accept_reference:
        try:
            snapshot = create_snapshot(result, approved=True)
        except SnapshotRefused as exc:
            raise SystemExit(f"Baseline refused: {exc}") from exc
        assert args.output_dir is not None
        save_snapshot(snapshot, args.output_dir / "payment-triage-snapshot.json")
        print("Baseline admitted: payment-triage-snapshot.json")

    if args.otel:
        record_otel_run(
            result,
            span_name=f"agentverity.payment_triage.{args.target}",
        )


if __name__ == "__main__":
    main()
