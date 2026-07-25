"""Structural checks for the optional live production-stack example."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "production_stack"


def test_live_example_files_are_valid_python():
    for name in (
        "agentcore_app.py",
        "cases.py",
        "evaluate_stack.py",
        "payment_agent.py",
        "runtime_client.py",
    ):
        source = (EXAMPLE / name).read_text(encoding="utf-8")
        ast.parse(source, filename=name)


def test_live_example_documents_state_isolation():
    readme = (EXAMPLE / "README.md").read_text(encoding="utf-8")
    runtime = (EXAMPLE / "runtime_client.py").read_text(encoding="utf-8")

    assert "fresh `runtimeSessionId`" in readme
    assert "str(uuid.uuid4())" in runtime
    assert "build_route_callable" in (
        EXAMPLE / "agentcore_app.py"
    ).read_text(encoding="utf-8")


def test_showcase_validates_snapshot_destination_before_live_calls():
    source = (EXAMPLE / "evaluate_stack.py").read_text(encoding="utf-8")

    validation = source.index('parser.error("--accept-reference requires --output-dir")')
    target_build = source.index("agent = _build_target(args.target)")

    assert validation < target_build
