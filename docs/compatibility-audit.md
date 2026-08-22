# Cross-version compatibility audit

This audit records what AgentVerity 0.19.0 can safely read from an earlier
minor release. It covers durable files with public loaders, not every JSON
object the package can emit.

## Result

AgentVerity 0.16.0 is the earliest minor that wrote all three schema versions
the current package reads:

| Durable file | Current schema | 0.19.0 result |
|---|---|---|
| Decision suite | `agentverity.decision-suite/v1` | Loads and rewrites without semantic change |
| Imported evidence | `agentverity.evidence/v2` | Loads ordered decisions, typed refusals, isolation, and provenance |
| Snapshot | `agentverity.snapshot/v4` | Loads approved outcomes, contract, admission evidence, and isolation |

The synthetic fixtures under `tests/fixtures/compatibility/v0.16.0/` were
written by the published 0.16.0 wheel. CI loads them with the current package
and compares their parsed-and-rewritten JSON with the original files.

There are no supported migration paths today. Evidence v1 changed the stored
outcome shape, and snapshot v3 cannot establish trial isolation. Current
loaders therefore refuse them instead of guessing. An old evidence collection
must be exported again as ordered v2 observations; an old snapshot must be
re-admitted from a newly isolated run.

## Reproduce the fixtures

Run outside the repository root so the checkout cannot shadow the historical
wheel:

```bash
python -m venv /tmp/agentverity-v016
/tmp/agentverity-v016/bin/pip install agentverity==0.16.0
cd /tmp
/tmp/agentverity-v016/bin/python \
  /path/to/agentverity/scripts/generate_compatibility_fixtures.py \
  /path/to/agentverity/tests/fixtures/compatibility/v0.16.0 \
  --expected-version 0.16.0
```

The generator refuses to write when the imported package version differs from
the named producer.

## Audit boundary

Run reports and OpenTelemetry attributes expose versioned, append-only schemas
but have no package loaders; downstream consumers must opt into and validate
those versions. The exported Python API and CLI still require a final 1.0
audit, and independent integration plus security review remain open. These
fixtures satisfy the earlier-minor reader check without claiming 1.0 readiness.
