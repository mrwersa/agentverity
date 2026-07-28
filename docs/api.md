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
  one also sizes route repeats when the meter is enabled. Targets must name
  required decisions. They are separate from the `critical` reporting label.
- `DecisionContract.minimum_cases` declares the minimum number of reviewed
  cases a required route must carry. It counts cases, not reruns, and does not
  infer whether those cases are semantically different.
- `RunResult.route_plans` holds the zero-change pair requirement and the actual
  repeats and calls allocated to each route.
- `RunResult.route_stability` splits stability by each case's intended
  decision, using the calls the run already made. Each `RouteStability` carries
  cases, pairs, flips, a Wilson interval, and the same tri-state `call` as the
  pooled meter. `flip_pairs` records the unordered decision pairs behind those
  flips.
- `RunResult.relation_coverage` reports which intended routes were genuinely
  changed by at least one requested relation. `RelationCoverage` contains one
  `RouteRelationCoverage` per route. An untouched route has no violation rate,
  rather than a misleading rate of zero.

Partial relation coverage is diagnostic. It does not block snapshot admission
because the contract does not declare which relations should apply to which
routes. A requested catalogue that changes no input at all remains vacuous and
fails.

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

JSON includes the complete stability and relation-coverage route tables. The
route checks in JUnit and OpenTelemetry carry aggregate counts. OpenTelemetry
remains label-free and low-cardinality, while JUnit may name decisions in
actionable failure guidance elsewhere in the report. JSON also includes
`route_plans`, and the meter reports both minimum and maximum repeats when
allocation differs by route.

## Snapshots

A snapshot is a versioned file containing the reviewed expected decisions used
as a baseline for later runs. Contract-aware snapshots also preserve the
declared contract and each case's intended decision.

- `create_snapshot` admits a reviewed reference only when the evidence permits.
- `compare_snapshot` rechecks admission before comparing current outputs.
- `save_snapshot` and `load_snapshot` persist versioned snapshot JSON.

A route proven stochastic blocks snapshot admission even when the pooled meter
looks deterministic. An untargeted undecided route remains a diagnostic. A
route named in `stability_targets` is an explicit release condition, so an
undecided target blocks admission and an exceeded target fails the release
policy.

The CLI exposes the same path through `agentverity snapshot` and
`agentverity check`.

## Planning route targets

`agentverity plan --suite suite.json` prints the best-case call plan without
calling the agent. The plan assumes zero decision changes. A changing route
can remain undecided or resolve as stochastic.

Programmatic callers can import `RoutePlan` and `plan_route_repeats`.
`RunConfig.k` is a minimum when route targets are declared, and the route plan
records any larger per-route allocation. `RunConfig.budget` remains a hard cap
unless the caller explicitly supplies `k`.

## Advanced measurement

- `measure` runs only the verdict-stochasticity meter, the underlying
  decision-stability check.
- `detect` runs only the constant-gate-blindness scan, the underlying
  decision-coverage check.
- `pairs_for_deterministic_call` budgets the minimum pair count.
- `plan_repeats` converts the input count and precision into `k`.
- `plan_route_repeats` produces a zero-change budget for a declared suite.
- `stratify_relations` groups already-collected relation outcomes by intended
  decision. Normal runs populate the same result automatically.
- `builtin_relations` returns the default metamorphic catalogue.
- `Relation` defines a custom invariant, monotone, or directional check.

See docstrings for the typed return objects and `DESIGN.md` for the statistical
and privacy decisions behind the API.
