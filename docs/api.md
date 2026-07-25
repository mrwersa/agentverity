# API guide

Most users need four names:

```python
from agentverity import Observation, RunConfig, from_callable, run
```

- `from_callable` adapts a Python function.
- `run` performs the decision-stability check, decision-coverage check, and
  optional relations.
- `Observation` separates text, verdict, and tool-path layers.
- `RunConfig` controls precision, call budget, concurrency, and failures.

## Results and reports

- `RunResult.headline` gives the plain-language interpretation.
- `RunResult.status` gives the canonical machine interpretation.
- `RunResult.summary()` returns the terminal report.
- `run_result_to_dict` and `write_run_json` produce versioned JSON.
- `run_result_to_junit_xml` and `write_junit_xml` produce CI test reports.
- `run_result_to_otel_attributes` returns privacy-minimised aggregate fields.
- `record_otel_run` emits those fields as one optional OpenTelemetry span.

## Snapshots

- `create_snapshot` admits a reviewed reference only when the evidence permits.
- `compare_snapshot` rechecks admission before comparing current outputs.
- `save_snapshot` and `load_snapshot` persist versioned snapshot JSON.

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
