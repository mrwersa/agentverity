"""Capture the reviewable top-level Python and command-line surface."""

from __future__ import annotations

import argparse
import inspect
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import agentverity
from agentverity.cli import _build_parser

AUDIT_SCHEMA = "agentverity.public-surface-audit/v1"


def _value(value: Any) -> Any:
    """Return a stable JSON representation for public defaults and constants."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _value(item) for key, item in sorted(value.items())}
    if isinstance(value, (set, frozenset)):
        return sorted(_value(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    if inspect.isclass(value):
        return f"{value.__module__}.{value.__qualname__}"
    return repr(value)


def _signature(value: Any) -> str | None:
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        return None


def python_surface() -> list[dict[str, Any]]:
    """Describe every explicitly exported top-level name."""
    surface = []
    for name in sorted(agentverity.__all__):
        value = getattr(agentverity, name)
        if inspect.isclass(value):
            entry = {
                "kind": "class",
                "module": value.__module__,
                "qualified_name": value.__qualname__,
                "signature": _signature(value),
            }
        elif inspect.isroutine(value):
            entry = {
                "kind": "function",
                "module": value.__module__,
                "qualified_name": value.__qualname__,
                "signature": _signature(value),
            }
        else:
            entry = {"kind": "constant", "value": _value(value)}
        surface.append({"name": name, **entry})
    return surface


def _argument(action: argparse.Action) -> dict[str, Any]:
    names = list(action.option_strings) or [action.dest]
    entry: dict[str, Any] = {
        "action": type(action).__name__,
        "dest": action.dest,
        "names": names,
        "required": action.required,
    }
    if action.nargs is not None:
        entry["nargs"] = action.nargs
    if action.type is not None:
        entry["type"] = _value(action.type)
    if action.choices is not None:
        entry["choices"] = sorted(_value(choice) for choice in action.choices)
    if action.default is not None and action.default != argparse.SUPPRESS:
        entry["default"] = _value(action.default)
    return entry


def _parser_arguments(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    return [
        _argument(action)
        for action in parser._actions
        if not isinstance(action, argparse._SubParsersAction)
    ]


def cli_surface() -> dict[str, Any]:
    """Describe commands and parser-enforced argument contracts."""
    parser = _build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return {
        "global_arguments": _parser_arguments(parser),
        "commands": {
            name: _parser_arguments(command)
            for name, command in sorted(subparsers.choices.items())
        },
    }


def collect_surface() -> dict[str, Any]:
    """Collect the current contract without embedding the package version."""
    return {
        "schema": AUDIT_SCHEMA,
        "python": python_surface(),
        "cli": cli_surface(),
    }


def main() -> None:
    """Write an audit fixture from the explicitly named installed release."""
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    if agentverity.__version__ != args.expected_version:
        raise SystemExit(
            f"expected agentverity {args.expected_version}, imported "
            f"{agentverity.__version__}; run outside the repository with the "
            "named wheel installed"
        )
    payload = {
        "producer": f"agentverity=={args.expected_version}",
        "surface": collect_surface(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
