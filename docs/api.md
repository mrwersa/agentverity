# API guide

Most runs without a declared decision contract need four names:

```python
from agentverity import Observation, RunConfig, from_callable, run
```

- `from_callable` adapts a Python function.
- `run` performs the decision-stability check, decision-coverage check, and
  optional relations.
- `Observation` separates text, verdict, and tool-path layers.
- `RunConfig` controls precision, call budget, concurrency, and failures.

## Declared decision coverage

Use three additional types when the application has a finite route inventory:

```python
from agentverity import DecisionCase, DecisionContract, DecisionSuite, run

suite = DecisionSuite(
    contract=DecisionContract(
        allowed={"approve", "review", "deny"},
        critical={"deny"},
    ),
    cases=(
        DecisionCase("routine request", "approve"),
        DecisionCase("ambiguous request", "review"),
        DecisionCase("prohibited request", "deny"),
    ),
)
result = run(agent, suite=suite)
```

- `DecisionContract` declares allowed, required, and critical labels.
  `required` defaults to every allowed label.
- `DecisionCase` pairs one raw input with the decision it is intended to
  exercise.
- `DecisionSuite` validates the contract and cases before any agent call.
- `RunResult.decision_coverage` reports intended, observed, missing, unknown,
  and missing-critical labels. Its `intended_counts` and `observed_counts`
  hold `DecisionCount` values, so that name is exported for annotations.
- `DecisionContract.stability_targets` sets a per-route tolerance. Declaring
  one also sizes that route's repeats, so the budget follows consequence.
- `RunResult.route_plans` holds the repeats and calls each route was given.
- `RunResult.route_stability` splits stability by each case's intended
  decision, using the calls the run already made. Each `RouteStability` carries
  cases, pairs, flips, a Wilson interval, and the same tri-state `call` as the
  pooled meter. `flip_pairs` records the unordered decision pairs behind those
  flips.

The contract path is available for the `verdict` layer. It checks coverage,
not per-case correctness. Keep labelled assertions or a quality evaluator
beside it.

The CLI accepts the same versioned structure with `--suite suite.json`.
`--suite` and `--inputs` are mutually exclusive.

## Results and reports

- `RunResult.headline` gives the plain-language interpretation.
- `RunResult.status` gives the canonical machine interpretation.
- `RunResult.summary()` returns the terminal report.
- `run_result_to_dict` and `write_run_json` produce versioned JSON.
- `run_result_to_junit_xml` and `write_junit_xml` produce CI test reports.
- `run_result_to_otel_attributes` returns privacy-minimised aggregate fields.
- `record_otel_run` emits those fields as one optional OpenTelemetry span.

JSON includes the complete route table. The route-stability checks in JUnit
and OpenTelemetry carry aggregate route counts. OpenTelemetry remains
label-free and low-cardinality, while JUnit may name decisions in actionable
failure guidance elsewhere in the report.

## Snapshots

A snapshot is a versioned file containing the reviewed expected decisions used
as a baseline for later runs. Contract-aware snapshots also preserve the
declared contract and each case's intended decision.

- `create_snapshot` admits a reviewed reference only when the evidence permits.
- `compare_snapshot` rechecks admission before comparing current outputs.
- `save_snapshot` and `load_snapshot` persist versioned snapshot JSON.

A route proven stochastic blocks snapshot admission even when the pooled meter
looks deterministic. An undecided route remains a diagnostic in this release,
not an independent route-level certification requirement. The pooled meter
still governs whether the overall run has enough stability evidence.

The CLI exposes the same path through `agentverity snapshot` and
`agentverity check`.

## Advanced measurement

- `measure` runs only the verdict-stochasticity meter, the underlying
  decision-stability check.
- `detect` runs only the constant-gate-blindness scan, the underlying
  decision-coverage check.
- `pairs_for_deterministic_call` budgets the minimum pair count.
- `plan_repeats` converts the input count and precision into `k`.
- `builtin_relations` returns the default metamorphic catalogue.
- `Relation` defines a custom invariant, monotone, or directional check.

See docstrings for the typed return objects and `DESIGN.md` for the statistical
and privacy decisions behind the API.
