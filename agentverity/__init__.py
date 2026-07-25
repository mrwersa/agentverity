"""agentverity — measure-first testing for non-deterministic LLM agents.

Before trusting any test suite, agentverity tells you whether your agent's
verdict is stable enough to test against, and whether a passing relation is
trivially satisfied by an indifferent agent. Two headline diagnostics:

  1. **Verdict-stochasticity meter** — does the agent's decision flip across
     identical reruns? If not, a frozen-output diff dominates and metamorphic
     relations add little.
  2. **Constant-gate-blindness detector** — does the agent return a near-constant
     verdict across a diverse input set? If so, every relation passes
     trivially and the suite is lying to you.

Metamorphic relations are the vehicle; the diagnostics are the product.
When those diagnostics support frozen-baseline testing, evidence-gated
snapshots refuse to freeze an incomplete, underpowered, blind, or unapproved
reference.

Quickstart::

    from agentverity import run, from_callable
    from agentverity.relations import builtin_relations

    agent = from_callable(my_agent_fn)
    result = run(agent, inputs=["hello", "world"], relations=builtin_relations())
    print(result.summary())
"""

from importlib.metadata import PackageNotFoundError, version

from agentverity.adapters import from_callable
from agentverity.blindness import BlindnessResult, detect
from agentverity.execution import ProgressEvent, RunError, input_fingerprint
from agentverity.meter import (
    PRECISION_LEVELS,
    MeterResult,
    measure,
    pairs_for_deterministic_call,
    plan_repeats,
)
from agentverity.observation import Observation
from agentverity.relations import Relation, builtin_relations
from agentverity.reporting import (
    JUNIT_SUITE_NAME,
    RUN_SCHEMA,
    run_result_to_dict,
    run_result_to_junit_xml,
    write_junit_xml,
    write_run_json,
)
from agentverity.runner import RelationResult, RunConfig, RunResult, run
from agentverity.snapshot import (
    SNAPSHOT_SCHEMA,
    Snapshot,
    SnapshotChange,
    SnapshotCompatibilityError,
    SnapshotDiff,
    SnapshotProbe,
    SnapshotRefused,
    compare_snapshot,
    create_snapshot,
    load_snapshot,
    save_snapshot,
)
from agentverity.telemetry import (
    TELEMETRY_SCHEMA,
    record_otel_run,
    run_result_to_otel_attributes,
)

__all__ = [
    "JUNIT_SUITE_NAME",
    "PRECISION_LEVELS",
    "RUN_SCHEMA",
    "SNAPSHOT_SCHEMA",
    "TELEMETRY_SCHEMA",
    "BlindnessResult",
    "MeterResult",
    "Observation",
    "ProgressEvent",
    "Relation",
    "RelationResult",
    "RunConfig",
    "RunError",
    "RunResult",
    "Snapshot",
    "SnapshotChange",
    "SnapshotCompatibilityError",
    "SnapshotDiff",
    "SnapshotProbe",
    "SnapshotRefused",
    "builtin_relations",
    "compare_snapshot",
    "create_snapshot",
    "detect",
    "from_callable",
    "input_fingerprint",
    "load_snapshot",
    "measure",
    "pairs_for_deterministic_call",
    "plan_repeats",
    "record_otel_run",
    "run",
    "run_result_to_dict",
    "run_result_to_junit_xml",
    "run_result_to_otel_attributes",
    "save_snapshot",
    "write_junit_xml",
    "write_run_json",
]

try:
    __version__ = version("agentverity")
except PackageNotFoundError:
    __version__ = "0+unknown"
