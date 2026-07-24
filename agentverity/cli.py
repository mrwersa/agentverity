"""CLI entry point for agentverity.

Usage::

    agentverity run --agent mymod:build_agent --inputs seeds.txt
    agentverity run --agent mymod:build_agent --inputs seeds.txt --k 10 --epsilon 0.02

The ``--agent`` argument is a Python dotted path to a callable that returns
the agent function (``fn() -> (str) -> Observation``). The ``--inputs``
argument is a text file with one input per line.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable

from agentverity.adapters.callable_adapter import from_callable
from agentverity.observation import Observation
from agentverity.runner import RunConfig, run


def _load_agent(spec: str) -> Callable:
    """Load an agent factory from a ``module:func`` spec."""
    if ":" not in spec:
        raise ValueError(
            f"--agent must be 'module:func', got {spec!r}"
        )
    module_path, func_name = spec.split(":", 1)
    module = importlib.import_module(module_path)
    factory = getattr(module, func_name)
    if not callable(factory):
        raise TypeError(f"{spec!r} is not callable")
    return factory


def _load_inputs(path: str) -> list[str]:
    """Load inputs from a text file, one per line, skipping blanks."""
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """Run the agentverity CLI.

    Returns:
        0 if all relations hold and no blindness is detected, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        prog="agentverity",
        description="Measure-first testing for non-deterministic LLM agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Run the diagnostic suite on an agent.")
    run_parser.add_argument(
        "--agent", required=True,
        help="Python dotted path to an agent factory: 'module:func'. "
             "The factory is called with no args and must return a "
             "callable (str) -> Observation.",
    )
    run_parser.add_argument(
        "--inputs", required=True,
        help="Path to a text file with one input per line.",
    )
    run_parser.add_argument("--k", type=int, default=5, help="Meter repeats per input (default 5).")
    run_parser.add_argument("--epsilon", type=float, default=0.01, help="Meter epsilon (default 0.01).")
    run_parser.add_argument(
        "--blindness-threshold", type=float, default=0.9,
        help="Blindness skew threshold (default 0.9).",
    )
    run_parser.add_argument("--layer", default="verdict", help="Observation layer to measure (default 'verdict').")
    run_parser.add_argument(
        "--no-meter", action="store_true",
        help="Skip the verdict-stochasticity meter.",
    )
    run_parser.add_argument(
        "--no-blindness", action="store_true",
        help="Skip the constant-gate-blindness detector.",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        factory = _load_agent(args.agent)
        agent_fn = factory()
        # Auto-wrap: if the factory returns a raw callable (str) -> str|dict
        # rather than (str) -> Observation, wrap it with from_callable.
        probe = agent_fn("__agentverity_probe__")
        if not isinstance(probe, Observation):
            agent_fn = from_callable(agent_fn)
        inputs = _load_inputs(args.inputs)
        config = RunConfig(
            k=args.k,
            epsilon=args.epsilon,
            blindness_threshold=args.blindness_threshold,
            layer=args.layer,
            run_meter=not args.no_meter,
            run_blindness=not args.no_blindness,
        )
        result = run(agent_fn, inputs, config=config)
        print(result.summary())

        # Exit code: 1 if blind or any relation violated, 0 otherwise
        if result.is_blind:
            return 1
        if any(rr.violated > 0 for rr in result.relation_results):
            return 1
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
