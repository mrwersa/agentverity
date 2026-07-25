"""Command-line interface for diagnostics and evidence-gated snapshots."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

from agentverity.adapters.callable_adapter import from_callable
from agentverity.execution import ProgressEvent
from agentverity.reporting import run_result_to_dict, write_run_json
from agentverity.runner import RunConfig, RunResult, run
from agentverity.snapshot import (
    SnapshotCompatibilityError,
    SnapshotRefused,
    compare_snapshot,
    create_snapshot,
    load_snapshot,
    save_snapshot,
)


def _load_agent(spec: str) -> Callable:
    """Load an agent factory from a ``module:func`` spec."""
    if ":" not in spec:
        raise ValueError(f"--agent must be 'module:func', got {spec!r}")
    module_path, func_name = spec.split(":", 1)
    module = importlib.import_module(module_path)
    factory = getattr(module, func_name)
    if not callable(factory):
        raise TypeError(f"{spec!r} is not callable")
    return factory


def _load_inputs(path: str) -> list[str]:
    """Load inputs from a text file, one per line, skipping blanks."""
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def _add_agent_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--agent",
        required=True,
        help=(
            "Python dotted path to an agent factory: 'module:func'. The "
            "factory must return a callable (str) -> Observation."
        ),
    )
    parser.add_argument(
        "--inputs",
        required=True,
        help="Path to a UTF-8 text file with one input per line.",
    )


def _add_execution_options(
    parser: argparse.ArgumentParser,
    *,
    default_error_policy: str = "raise",
) -> None:
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help=(
            "Distinct inputs to process concurrently (default 1). Calls for "
            "one input remain sequential. Opt in only for thread-safe agents."
        ),
    )
    parser.add_argument(
        "--error-policy",
        choices=("raise", "record"),
        default=default_error_policy,
        help=(
            "Stop on the first failure or retain partial evidence as "
            f"incomplete (default {default_error_policy})."
        ),
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print non-plaintext phase progress to stderr.",
    )


def _add_meter_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Meter repeats per input (default 5).",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.01,
        help="Meter flip-rate threshold (default 0.01).",
    )
    parser.add_argument(
        "--blindness-threshold",
        type=float,
        default=0.9,
        help="Blindness skew threshold (default 0.9).",
    )
    parser.add_argument(
        "--layer",
        choices=("verdict", "text", "tools"),
        default="verdict",
        help="Observation layer to measure (default verdict).",
    )


def _progress(event: ProgressEvent) -> None:
    short = event.input_fingerprint[:10]
    print(
        f"[{event.phase}] {event.completed}/{event.total} "
        f"input={event.input_index} sha256={short} status={event.status}",
        file=sys.stderr,
    )


def _agent_and_inputs(args: argparse.Namespace) -> tuple[Callable, list[str]]:
    factory = _load_agent(args.agent)
    return from_callable(factory()), _load_inputs(args.inputs)


def _exit_code(result: RunResult) -> int:
    if not result.complete:
        return 2
    if result.is_blind or any(
        relation.violated > 0 for relation in result.relation_results
    ):
        return 1
    return 0


def _run_command(args: argparse.Namespace) -> int:
    agent, inputs = _agent_and_inputs(args)
    config = RunConfig(
        k=args.k,
        epsilon=args.epsilon,
        blindness_threshold=args.blindness_threshold,
        layer=args.layer,
        run_meter=not args.no_meter,
        run_blindness=not args.no_blindness,
        max_workers=args.max_workers,
        error_policy=args.error_policy,
    )
    result = run(
        agent,
        inputs,
        relations=[] if args.no_relations else None,
        config=config,
        on_progress=_progress if args.progress else None,
    )
    if args.format == "json":
        if args.output:
            write_run_json(result, args.output)
        else:
            print(json.dumps(run_result_to_dict(result), indent=2, sort_keys=True))
    else:
        report = result.summary()
        if args.output:
            Path(args.output).write_text(report + "\n", encoding="utf-8")
        else:
            print(report)
    return _exit_code(result)


def _snapshot_command(args: argparse.Namespace) -> int:
    if not args.accept_reference:
        print(
            "snapshot refused: reference outputs require explicit approval; "
            "stability is not correctness",
            file=sys.stderr,
        )
        return 2
    agent, inputs = _agent_and_inputs(args)
    result = run(
        agent,
        inputs,
        relations=[],
        config=RunConfig(
            k=args.k,
            epsilon=args.epsilon,
            blindness_threshold=args.blindness_threshold,
            layer=args.layer,
            max_workers=args.max_workers,
            error_policy=args.error_policy,
        ),
        on_progress=_progress if args.progress else None,
    )
    try:
        snapshot = create_snapshot(result, approved=True)
    except SnapshotRefused as exc:
        print(f"snapshot refused: {exc}", file=sys.stderr)
        return 2
    save_snapshot(snapshot, args.output)
    print(
        f"snapshot admitted: {len(snapshot.probes)} approved "
        f"{snapshot.layer} references -> {args.output}"
    )
    return 0


def _check_command(args: argparse.Namespace) -> int:
    try:
        snapshot = load_snapshot(args.snapshot)
    except SnapshotCompatibilityError as exc:
        print(f"snapshot check refused: {exc}", file=sys.stderr)
        return 2
    agent, inputs = _agent_and_inputs(args)
    result = run(
        agent,
        inputs,
        relations=[],
        config=RunConfig(
            k=snapshot.k,
            epsilon=snapshot.epsilon,
            blindness_threshold=snapshot.blindness_threshold,
            layer=snapshot.layer,
            max_workers=args.max_workers,
            error_policy=args.error_policy,
        ),
        on_progress=_progress if args.progress else None,
    )
    try:
        diff = compare_snapshot(snapshot, result)
    except (SnapshotRefused, SnapshotCompatibilityError) as exc:
        print(f"snapshot check refused: {exc}", file=sys.stderr)
        return 2
    if diff.clean:
        print(f"snapshot clean: {diff.checked}/{diff.checked} references matched")
        return 0
    print(f"snapshot drift: {len(diff.changes)}/{diff.checked} references changed")
    for change in diff.changes:
        print(
            f"  sha256={change.input_fingerprint[:12]} "
            f"expected={change.expected!r} actual={change.actual!r}"
        )
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentverity",
        description="Measure-first testing for non-deterministic LLM agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser(
        "run",
        help="Run diagnostics and optional metamorphic relations.",
    )
    _add_agent_inputs(run_parser)
    _add_meter_options(run_parser)
    _add_execution_options(run_parser)
    run_parser.add_argument(
        "--no-meter",
        action="store_true",
        help="Skip the verdict-stochasticity meter.",
    )
    run_parser.add_argument(
        "--no-blindness",
        action="store_true",
        help="Skip the constant-gate-blindness detector.",
    )
    run_parser.add_argument(
        "--no-relations",
        action="store_true",
        help="Run diagnostics only, without metamorphic relations.",
    )
    run_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Report format (default text).",
    )
    run_parser.add_argument(
        "--output",
        help="Write the report to this path instead of stdout.",
    )

    snapshot_parser = sub.add_parser(
        "snapshot",
        help="Create an approved baseline when the evidence supports one.",
    )
    _add_agent_inputs(snapshot_parser)
    _add_meter_options(snapshot_parser)
    _add_execution_options(snapshot_parser, default_error_policy="record")
    snapshot_parser.add_argument(
        "--output",
        required=True,
        help="Path for the versioned snapshot JSON.",
    )
    snapshot_parser.add_argument(
        "--accept-reference",
        action="store_true",
        help=(
            "Confirm that a human reviewed the outputs as correct. Stability "
            "alone cannot approve a reference."
        ),
    )

    check_parser = sub.add_parser(
        "check",
        help="Re-admit current evidence, then compare it with a snapshot.",
    )
    _add_agent_inputs(check_parser)
    _add_execution_options(check_parser, default_error_policy="record")
    check_parser.add_argument(
        "--snapshot",
        required=True,
        help="Path to a snapshot created by 'agentverity snapshot'.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the AgentVerity CLI."""
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return _run_command(args)
    if args.command == "snapshot":
        return _snapshot_command(args)
    if args.command == "check":
        return _check_command(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
