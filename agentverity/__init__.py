"""Qualify repeated categorical AI-agent evidence for a regression reference.

Before trusting a green run, AgentVerity checks whether the agent's named
decision is repeatable across reruns and whether the test inputs reach more than
one decision. Two headline diagnostics:

  1. **Verdict-stochasticity meter** — does the agent's decision flip across
     identical reruns? A repeatable decision can support a reviewed reference.
  2. **Constant-gate-blindness detector** — does the agent return a near-constant
     verdict across a diverse input set? If so, a green result supports that
     path rather than the wider decision contract.

Metamorphic relations are an optional strategy, not the product. Evidence-gated
snapshots refuse to freeze an incomplete, underpowered, blind, or unapproved
reference.

Quickstart::

    from agentverity import from_callable, run

    agent = from_callable(my_agent_fn)
    result = run(agent, inputs=["hello", "world"])
    print(result.headline)
"""

from importlib.metadata import PackageNotFoundError, version

from agentverity.adapters import from_callable
from agentverity.blindness import BlindnessResult, detect
from agentverity.decision import (
    DECLARABLE_REASONS,
    INCOMPLETE_REASONS,
    NO_DECISION_REASONS,
    Decision,
    NoDecision,
    Outcome,
    OutcomeNotScorable,
    as_outcome,
)
from agentverity.decision_contract import (
    DECISION_SUITE_SCHEMA,
    DecisionCase,
    DecisionContract,
    DecisionCount,
    DecisionCoverageResult,
    DecisionSuite,
    load_decision_suite,
    save_decision_suite,
)
from agentverity.drift import EvidenceDrift, RouteDrift, compare_evidence
from agentverity.evidence import (
    EVIDENCE_SCHEMA,
    EvidenceCase,
    EvidenceError,
    EvidenceSet,
    assess_evidence,
    load_evidence,
    save_evidence,
)
from agentverity.execution import ProgressEvent, RunError, input_fingerprint
from agentverity.integrations import (
    evidence_from_deepeval,
    evidence_from_jsonl,
    evidence_from_promptfoo,
    load_jsonl,
    load_promptfoo,
)
from agentverity.isolation import declare_isolation, isolation_of
from agentverity.meter import (
    PRECISION_LEVELS,
    MeterResult,
    best_case_admission_pairs,
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
from agentverity.sequential import (
    SequentialPlan,
    decide_sequentially,
    plan_sequential,
)
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
from agentverity.stratified import (
    FlipPair,
    RelationCoverage,
    RoutePlan,
    RouteRelationCoverage,
    RouteStability,
    StratifiedStability,
    plan_route_repeats,
    stratify_relations,
    stratify_runs,
)
from agentverity.telemetry import (
    TELEMETRY_SCHEMA,
    record_otel_run,
    run_result_to_otel_attributes,
)

__all__ = [
    "DECISION_SUITE_SCHEMA",
    "DECLARABLE_REASONS",
    "EVIDENCE_SCHEMA",
    "INCOMPLETE_REASONS",
    "JUNIT_SUITE_NAME",
    "NO_DECISION_REASONS",
    "PRECISION_LEVELS",
    "RUN_SCHEMA",
    "SNAPSHOT_SCHEMA",
    "TELEMETRY_SCHEMA",
    "BlindnessResult",
    "Decision",
    "DecisionCase",
    "DecisionContract",
    "DecisionCount",
    "DecisionCoverageResult",
    "DecisionSuite",
    "EvidenceCase",
    "EvidenceDrift",
    "EvidenceError",
    "EvidenceSet",
    "FlipPair",
    "MeterResult",
    "NoDecision",
    "Observation",
    "Outcome",
    "OutcomeNotScorable",
    "ProgressEvent",
    "Relation",
    "RelationCoverage",
    "RelationResult",
    "RouteDrift",
    "RoutePlan",
    "RouteRelationCoverage",
    "RouteStability",
    "RunConfig",
    "RunError",
    "RunResult",
    "SequentialPlan",
    "Snapshot",
    "SnapshotChange",
    "SnapshotCompatibilityError",
    "SnapshotDiff",
    "SnapshotProbe",
    "SnapshotRefused",
    "StratifiedStability",
    "as_outcome",
    "assess_evidence",
    "best_case_admission_pairs",
    "builtin_relations",
    "compare_evidence",
    "compare_snapshot",
    "create_snapshot",
    "decide_sequentially",
    "declare_isolation",
    "detect",
    "evidence_from_deepeval",
    "evidence_from_jsonl",
    "evidence_from_promptfoo",
    "from_callable",
    "input_fingerprint",
    "isolation_of",
    "load_decision_suite",
    "load_evidence",
    "load_jsonl",
    "load_promptfoo",
    "load_snapshot",
    "measure",
    "pairs_for_deterministic_call",
    "plan_repeats",
    "plan_route_repeats",
    "plan_sequential",
    "record_otel_run",
    "run",
    "run_result_to_dict",
    "run_result_to_junit_xml",
    "run_result_to_otel_attributes",
    "save_decision_suite",
    "save_evidence",
    "save_snapshot",
    "stratify_relations",
    "stratify_runs",
    "write_junit_xml",
    "write_run_json",
]

try:
    __version__ = version("agentverity")
except PackageNotFoundError:
    __version__ = "0+unknown"
