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
    assert "stop_runtime_session" in runtime
    assert "build_route_callable" in (
        EXAMPLE / "agentcore_app.py"
    ).read_text(encoding="utf-8")


def test_showcase_validates_snapshot_destination_before_live_calls():
    source = (EXAMPLE / "evaluate_stack.py").read_text(encoding="utf-8")

    validation = source.index('parser.error("--accept-reference requires --output-dir")')
    target_build = source.index("TimedAgent(_build_target(args.target))")

    assert validation < target_build


def test_showcase_defaults_to_low_cost_model_and_current_cli():
    payment_agent = (EXAMPLE / "payment_agent.py").read_text(encoding="utf-8")
    readme = (EXAMPLE / "README.md").read_text(encoding="utf-8")

    assert 'DEFAULT_MODEL_ID = "amazon.nova-micro-v1:0"' in payment_agent
    assert "agentcore deploy --dry-run" in readme
    assert "agentcore deploy --plan" not in readme


def test_showcase_separates_runtime_dependencies():
    requirements = (
        EXAMPLE / "runtime-requirements.txt"
    ).read_text(encoding="utf-8")

    assert "bedrock-agentcore" in requirements
    assert "aws-opentelemetry-distro" in requirements
    assert "strands-agents" in requirements
    assert "deepeval" not in requirements
    assert "agentverity" not in requirements


def test_showcase_never_uses_stability_to_override_quality():
    source = (EXAMPLE / "evaluate_stack.py").read_text(encoding="utf-8")

    quality_guard = source.index("Stability cannot override correctness.")
    stability_run = source.index("result = run(")
    snapshot = source.index("snapshot = create_snapshot(result, approved=True)")

    assert quality_guard < stability_run
    assert quality_guard < snapshot
