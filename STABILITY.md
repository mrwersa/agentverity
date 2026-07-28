# API stability and the path to 1.0

AgentVerity is alpha because its public interface has not completed a
compatibility audit or been validated by independent adopters. The label is a
scope statement, not a waiver for silent breakage.

## Guarantees before 1.0

- Patch releases preserve the public Python API and command-line contracts.
- Breaking Python or CLI changes require a new minor release and migration
  notes in `CHANGELOG.md`.
- Deprecated names remain available for at least one minor release where a
  compatibility alias is practical.
- JSON reports and snapshots carry explicit schema versions. The snapshot
  loader rejects an unsupported schema, while reports expose their version for
  downstream validation.
- Stored prompts and outputs remain excluded from default reports, snapshots,
  JUnit, and OpenTelemetry exports.

Production users should pin the current minor series:

```text
agentverity~=0.11.0
```

That accepts compatible `0.11.x` fixes without moving to a later pre-1.0 minor
series.

Version 0.11 writes `agentverity.run/v2`, `agentverity.telemetry/v2`, and
`agentverity.snapshot/v2`. The snapshot loader accepts v1 files and migrates
them in memory. JSON reports and telemetry exports are append-only artefacts,
so consumers must opt into their v2 schemas.

## What remains open

The relation API and convenience adapters are the likeliest surfaces to change.
The core decision model, `run`, report schemas, snapshot admission checks, and
the three exit-code classes are treated as the stabilising contract.

## Exit criteria for 1.0

AgentVerity reaches 1.0 after all of the following are true:

1. The exported Python API, CLI, report schema, and snapshot schema receive a
   final compatibility audit.
2. CI reads fixtures produced by at least one earlier minor series and checks
   every supported migration path.
3. At least one independent integration exercises a real agent or workflow and
   feeds its interface problems back into the project.
4. Security, data-retention, and failure-mode documentation receive a release
   review against the implementation.

Download count alone is not an exit criterion. The goal is evidence that the
contract works outside the examples that shaped it.
