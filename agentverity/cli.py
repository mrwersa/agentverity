"""Command-line interface for diagnostics and evidence-gated snapshots."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path

from agentverity import __version__
from agentverity.adapters.callable_adapter import from_callable
from agentverity.decision_contract import DecisionSuite, load_decision_suite
from agentverity.drift import compare_evidence
from agentverity.evidence import EvidenceError, assess_evidence, load_evidence
from agentverity.execution import ProgressEvent
from agentverity.integrations.jsonl import load_jsonl
from agentverity.integrations.promptfoo import load_promptfoo
from agentverity.meter import (
    PRECISION_LEVELS,
    pairs_for_deterministic_call,
    resolve_epsilon,
)
from agentverity.reporting import (
    run_result_to_dict,
    run_result_to_junit_xml,
    write_junit_xml,
    write_run_json,
)
from agentverity.runner import RunConfig, RunResult, run
from agentverity.snapshot import (
    SnapshotCompatibilityError,
    SnapshotRefused,
    compare_snapshot,
    create_snapshot,
    load_snapshot,
    save_snapshot,
)
from agentverity.stratified import plan_route_repeats, render_plan


class CliRefusal(Exception):
    """A caller-input problem the CLI reports as a refusal rather than a crash."""


def _load_agent(spec: str) -> Callable:
    """Load an agent factory from ``module:func`` or ``file.py:func``."""
    if ":" not in spec:
        raise ValueError(
            f"--agent must be 'module:func' or 'file.py:func', got {spec!r}"
        )
    module_path, func_name = spec.rsplit(":", 1)
    if module_path.endswith(".py"):
        source = Path(module_path).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"agent module not found: {source}")
        module_spec = importlib.util.spec_from_file_location(
            "_agentverity_user_agent",
            source,
        )
        if module_spec is None or module_spec.loader is None:
            raise ImportError(f"cannot load agent module: {source}")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
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
            "Python module or file path to an agent factory: 'module:func' or "
            "'file.py:func'. The factory must return a callable "
            "(str) -> Observation."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--inputs",
        help="Path to a UTF-8 text file with one input per line.",
    )
    source.add_argument(
        "--suite",
        help=(
            "Path to a versioned decision-suite JSON file containing the "
            "declared contract and reviewed cases."
        ),
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
        "--precision",
        choices=sorted(PRECISION_LEVELS),
        default="balanced",
        help=(
            "How tight a flip rate to care about: cheap (10%%), balanced (5%%, "
            "the default), or strict (1%%). Overridden by --epsilon."
        ),
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=None,
        help=(
            "Cap on meter agent calls. Defaults to spending what the chosen "
            "precision needs. Overridden by --k."
        ),
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help=(
            "Minimum meter repeats per input. Defaults to sizing from "
            "--budget; declared route targets may raise it per route."
        ),
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=None,
        help="Exact meter flip-rate threshold, overriding --precision.",
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


def _agent_and_inputs(
    args: argparse.Namespace,
) -> tuple[Callable, list[str] | None, DecisionSuite | None]:
    try:
        factory = _load_agent(args.agent)
        suite = load_decision_suite(args.suite) if args.suite else None
        inputs = None if args.suite else _load_inputs(args.inputs)
    except (
        AttributeError,
        FileNotFoundError,
        ImportError,
        TypeError,
        ValueError,
    ) as exc:
        raise CliRefusal(str(exc)) from exc
    return from_callable(factory()), inputs, suite


def _exit_code(result: RunResult) -> int:
    if result.status == "incomplete":
        return 2
    if result.status == "undecided":
        return 2
    if result.status in {
        "blind",
        "contract",
        "target-failed",
        "vacuous",
        "violations",
    }:
        return 1
    return 0


def _run_command(args: argparse.Namespace) -> int:
    try:
        agent, inputs, suite = _agent_and_inputs(args)
    except CliRefusal as exc:
        print(f"run refused: {exc}", file=sys.stderr)
        return 2
    config = RunConfig(
        budget=args.budget,
        precision=args.precision,
        k=args.k,
        epsilon=args.epsilon,
        blindness_threshold=args.blindness_threshold,
        layer=args.layer,
        run_meter=not args.no_meter,
        run_blindness=not args.no_blindness,
        max_workers=args.max_workers,
        error_policy=args.error_policy,
    )
    try:
        result = run(
            agent,
            inputs,
            suite=suite,
            relations=[] if args.no_relations else None,
            config=config,
            on_progress=_progress if args.progress else None,
        )
    except ValueError as exc:
        print(f"run refused: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        if args.output:
            write_run_json(result, args.output)
        else:
            print(json.dumps(run_result_to_dict(result), indent=2, sort_keys=True))
    elif args.format == "junit":
        if args.output:
            write_junit_xml(result, args.output)
        else:
            print(run_result_to_junit_xml(result), end="")
    else:
        report = result.summary()
        if args.output:
            Path(args.output).write_text(report + "\n", encoding="utf-8")
        else:
            print(report)
    return _exit_code(result)


def _infeasible_reason(inputs: int, k: int | None, epsilon: float) -> str | None:
    """Reject a configuration that cannot certify determinism, before running.

    Each input contributes ``floor(k / 2)`` disjoint pairs, so the ceiling on
    evidence is fixed the moment the probe set and ``k`` are chosen. If that
    ceiling sits below the pairs needed even in the best case of zero flips, no
    execution can succeed and the calls are wasted.
    """
    if k is None:
        # Auto-sizing already picks a k that can reach the bound, so there is
        # nothing to rule out ahead of the run.
        return None
    best_case = pairs_for_deterministic_call(epsilon)
    if best_case is None:
        return None
    available = inputs * (k // 2)
    if available >= best_case:
        return None
    per_input = -(-best_case // inputs)
    return (
        f"this configuration cannot certify determinism at epsilon={epsilon}. "
        f"{inputs} inputs at k={k} yield {available} disjoint pairs, and "
        f"{best_case} are needed even with zero flips. Raise --k to at least "
        f"{per_input * 2}, add inputs, or set a deployment-relevant --epsilon. "
        "Refused before running so the calls are not spent."
    )


def _snapshot_command(args: argparse.Namespace) -> int:
    if not args.accept_reference:
        print(
            "snapshot refused: reference outputs require explicit approval; "
            "stability is not correctness",
            file=sys.stderr,
        )
        return 2
    try:
        agent, inputs, suite = _agent_and_inputs(args)
    except CliRefusal as exc:
        print(f"snapshot refused: {exc}", file=sys.stderr)
        return 2
    input_count = len(suite.cases) if suite is not None else len(inputs or ())
    infeasible = _infeasible_reason(
        input_count,
        args.k,
        resolve_epsilon(args.precision, args.epsilon),
    )
    if infeasible is not None:
        # Refusing after the run would be honest but expensive: on a paid model
        # every one of those calls is spent proving something the arithmetic
        # already ruled out.
        print(f"snapshot refused: {infeasible}", file=sys.stderr)
        return 2
    try:
        result = run(
            agent,
            inputs,
            suite=suite,
            relations=[],
            config=RunConfig(
                budget=args.budget,
                precision=args.precision,
                k=args.k,
                epsilon=args.epsilon,
                blindness_threshold=args.blindness_threshold,
                layer=args.layer,
                max_workers=args.max_workers,
                error_policy=args.error_policy,
            ),
            on_progress=_progress if args.progress else None,
        )
    except ValueError as exc:
        print(f"snapshot refused: {exc}", file=sys.stderr)
        return 2
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
    try:
        agent, inputs, suite = _agent_and_inputs(args)
    except CliRefusal as exc:
        print(f"snapshot check refused: {exc}", file=sys.stderr)
        return 2
    if (snapshot.decision_contract is None) != (suite is None):
        print(
            "snapshot check refused: current decision-suite mode does not "
            "match the snapshot",
            file=sys.stderr,
        )
        return 2
    result = run(
        agent,
        inputs,
        suite=suite,
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
        description=(
            "Evidence checks for regression baselines on AI agents with "
            "bounded decisions."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show the installed version and exit.",
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
        choices=("text", "json", "junit"),
        default="text",
        help="Report format (default text).",
    )
    run_parser.add_argument(
        "--output",
        help="Write the report to this path instead of stdout.",
    )

    plan_parser = sub.add_parser(
        "plan",
        help=(
            "show the zero-change call plan for a declared suite, without "
            "calling the agent"
        ),
    )
    plan_parser.add_argument("--suite", required=True, help="decision suite JSON")
    plan_parser.add_argument(
        "--precision",
        choices=sorted(PRECISION_LEVELS),
        default="balanced",
        help=(
            "Default route tolerance: cheap (10%%), balanced (5%%), or "
            "strict (1%%). Overridden by --epsilon."
        ),
    )
    plan_parser.add_argument(
        "--epsilon",
        type=float,
        default=None,
        help="exact default tolerance for routes with no declared target",
    )

    assess_parser = sub.add_parser(
        "assess",
        help="assess repeated runs collected elsewhere, making no calls",
    )
    assess_source = assess_parser.add_mutually_exclusive_group(required=True)
    assess_source.add_argument(
        "--evidence", help="evidence JSON (agentverity.evidence/v2)"
    )
    assess_source.add_argument(
        "--promptfoo", help="Promptfoo JSON export containing repeated outputs"
    )
    assess_source.add_argument(
        "--jsonl",
        help=(
            "JSONL from any harness: one JSON object per run, in the order "
            "produced. Name the fields with --input-path and --decision-path."
        ),
    )
    assess_parser.add_argument(
        "--suite", default=None, help="optional decision suite to check against"
    )
    assess_parser.add_argument("--epsilon", type=float, default=0.05)
    assess_parser.add_argument(
        "--decision-path",
        default=None,
        help=(
            "dot path to the decision in each row. Defaults to the source's "
            "own convention: a Promptfoo structured output, or 'decision' "
            "for --jsonl"
        ),
    )
    assess_parser.add_argument(
        "--input-path",
        default=None,
        help=(
            "dot path to the reviewed input in each row. Defaults to "
            "'prompt.raw' for --promptfoo and 'input' for --jsonl"
        ),
    )
    assess_parser.add_argument(
        "--provider",
        default=None,
        help="Promptfoo provider id when the export contains a matrix",
    )
    assess_parser.add_argument(
        "--prompt-id",
        default=None,
        help="Promptfoo prompt id when the export contains a matrix",
    )
    assess_parser.add_argument(
        "--isolation",
        choices=("fresh-session", "fresh-instance", "shared-session", "unknown"),
        default="unknown",
        help="how Promptfoo repetitions were separated",
    )
    assess_parser.add_argument(
        "--json", dest="json_path", default=None, help="write the JSON report here"
    )

    drift_parser = sub.add_parser(
        "compare-evidence",
        help="compare two evidence windows collected at different times",
    )
    drift_parser.add_argument("before", help="the earlier evidence file")
    drift_parser.add_argument("after", help="the later evidence file")
    drift_parser.add_argument("--epsilon", type=float, default=0.05)
    drift_parser.add_argument(
        "--json", dest="json_path", default=None, help="write the drift JSON here"
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


def _compare_evidence_command(args: argparse.Namespace) -> int:
    """Report how two independently collected windows differ."""
    try:
        drift = compare_evidence(
            load_evidence(args.before),
            load_evidence(args.after),
            epsilon=args.epsilon,
        )
    except (EvidenceError, ValueError) as exc:
        # A malformed file or an incompatible pair is the caller's input
        # problem, and a traceback tells them less than the sentence does.
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(drift.render())
    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(drift.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    # Drift is a finding to review, not a failure to block on. Whether a moved
    # route is a regression, an improvement, or a relabelled taxonomy is a
    # judgement this package does not make.
    return 1 if drift.drifted else 0


def _assess_command(args: argparse.Namespace) -> int:
    """Assess evidence a run collected elsewhere, without calling anything."""
    try:
        suite = load_decision_suite(args.suite) if args.suite else None
        # Each importer carries its own field-name defaults, so the CLI
        # forwards a path only when one was named. Defaulting here instead
        # would make one flag mean two conventions, and passing
        # `--input-path prompt.raw` to --jsonl would then be silently ignored.
        paths = {
            name: value
            for name, value in (
                ("input_path", args.input_path),
                ("decision_path", args.decision_path),
            )
            if value is not None
        }
        if args.promptfoo:
            if suite is None:
                raise ValueError(
                    "--promptfoo requires --suite so exported inputs map to "
                    "reviewed cases"
                )
            evidence = load_promptfoo(
                args.promptfoo,
                suite,
                provider=args.provider,
                prompt_id=args.prompt_id,
                isolation=args.isolation,
                **paths,
            )
        elif args.jsonl:
            evidence = load_jsonl(
                args.jsonl,
                suite=suite,
                isolation=args.isolation,
                **paths,
            )
        else:
            evidence = load_evidence(args.evidence)
        result = assess_evidence(evidence, suite, epsilon=args.epsilon)
    except (TypeError, ValueError) as exc:
        print(f"assessment refused: {exc}", file=sys.stderr)
        return 2
    print(result.summary())
    if args.json_path:
        write_run_json(result, args.json_path)
    # The same precedence a live run uses, so a gate behaves identically
    # whether the calls were made here or imported.
    return _exit_code(result)


def _plan_command(args: argparse.Namespace) -> int:
    """Print what a suite would cost before any agent call is made.

    Knowing the bill in advance is the difference between adopting a tighter
    tolerance and discovering it after a provider invoice.
    """
    suite = load_decision_suite(args.suite)
    plans = plan_route_repeats(
        suite.expected,
        epsilon=resolve_epsilon(args.precision, args.epsilon),
        targets=suite.contract.stability_targets,
    )
    print("agentverity — zero-flip call plan")
    print(render_plan(plans, compare_uniform=True))
    print(
        "\nThis is the minimum needed to certify quiet routes. "
        "Observed decision changes can leave a route undecided or prove it "
        "stochastic."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the AgentVerity CLI."""
    args = _build_parser().parse_args(argv)
    if args.command == "compare-evidence":
        return _compare_evidence_command(args)
    if args.command == "assess":
        return _assess_command(args)
    if args.command == "plan":
        return _plan_command(args)
    if args.command == "run":
        return _run_command(args)
    if args.command == "snapshot":
        return _snapshot_command(args)
    if args.command == "check":
        return _check_command(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
