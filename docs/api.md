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

The catalogue is yours to extend. A `Relation` is a transform and a check, and
a user relation is scored, tabled and counted towards route coverage exactly
like a built-in:

```python
from agentverity import Relation, builtin_relations, run

currency = Relation(
    name="currency-symbol-invariance",
    rtype="invariant",
    transform=lambda text: text.replace("GBP ", "£"),
    check=lambda source, followup: source.verdict == followup.verdict,
)
result = run(agent, inputs, relations=[*builtin_relations(), currency])
```

`rtype` is `invariant`, `monotone`, or `directional`, and the set is closed
because the report renders by type. A relation with an empty name, an unknown
type, or a transform that is not callable is refused when you construct it,
before any call is made. From the command line,
`agentverity run --relations module:func` loads a function returning your
relations. See [custom relations](custom-relations.md).

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

## Assessing evidence collected elsewhere

```python
from agentverity import assess_evidence, load_evidence, load_decision_suite

result = assess_evidence(
    load_evidence("runs.json"),
    load_decision_suite("suite.json"),
    epsilon=0.05,
)
print(result.summary())
```

`assess_evidence` returns the same `RunResult` a live run produces, so the
report, JSON, JUnit, OpenTelemetry, and snapshot paths work unchanged.
`relation_results` is empty, because a relation needs calls no imported file
contains. See [imported evidence](imported-evidence.md).

Sizing a run, and stopping it early:

```python
from agentverity import plan_sequential, decide_sequentially

plan = plan_sequential(epsilon=0.05)        # checkpoints, before any call
call, pairs = decide_sequentially(plan, flip_outcomes)
```

`plan_sequential(epsilon, alpha=0.05, looks=4, budget=None)` declares the
checkpoints up front. `decide_sequentially(plan, outcomes)` reads one boolean
per disjoint pair, in collection order, and returns the call and the pairs it
took.

The checkpoints have to be declared first because choosing where to look after
seeing the data is the peeking this avoids. A decision reads exactly the first
`n` pairs, so results that overshoot a checkpoint under concurrency are kept as
evidence and never change a call.

Certification is tested once, at the final checkpoint, so it carries no
multiplicity penalty: 72 pairs at a 5% tolerance against the fixed sample's 73.
The earlier looks test only the stochastic direction. See DESIGN.md ADR 7,
including why an even split was measured and rejected.

Writing an adapter?

```python
from agentverity import declare_isolation

def from_my_framework(build_client):
    def run(text: str) -> Observation:
        ...
    return declare_isolation(run, "fresh-instance")
```

`run` records what you said, and that value decides whether the evidence may
certify a baseline. State what happened rather than what you wanted: a shared
session declared honestly is refused a baseline, and a shared session declared
as fresh certifies one on a false claim.

Framework bridges translate records without calling the target:

```python
from agentverity import (
    evidence_from_deepeval,
    evidence_from_jsonl,
    evidence_from_promptfoo,
    load_jsonl,
)
```

`evidence_from_deepeval(test_cases, ...)` groups repeated precomputed
`LLMTestCase` objects by input. `evidence_from_promptfoo(payload, suite, ...)`
selects one provider/prompt cell from a Promptfoo JSON export and matches
rendered inputs back to the reviewed suite. The latter is also available
through `agentverity assess --promptfoo`.

`evidence_from_jsonl(lines, ...)` and `load_jsonl(path, ...)` understand no
tool at all. They read one JSON object per run, and `input_path` and
`decision_path` name the fields as dotted paths, so a harness with no bridge
and a production log go through the same door. Python callers can pass a
`provenance` mapping to retain the harness, model, and collection context.
Exposed as `agentverity assess --jsonl`.

The order of the lines is the order runs are paired, and an input appearing
once is refused rather than imported, because a single run carries no
comparison.
