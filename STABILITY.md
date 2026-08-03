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
agentverity~=0.14.0
```

That accepts compatible `0.14.x` fixes without moving to a later pre-1.0 minor
series.

Version 0.14 writes `agentverity.run/v2`, `agentverity.telemetry/v2` and
`agentverity.snapshot/v2`. Evidence and decision suites are written at the
**minimum version that can describe them**: `agentverity.evidence/v2` only when
a file carries a typed outcome, and `agentverity.decision-suite/v2` only when a
contract declares a no-decision outcome. Everything else stays v1 and readable
by an older build. The snapshot loader accepts v1 files and migrates them in
memory. JSON reports and telemetry
exports are append-only artefacts, so consumers must opt into their v2
schemas. The evidence loader rejects unknown versions and aggregate-only
inputs rather than guessing. Promptfoo and DeepEval bridges translate into
that contract while keeping framework packages optional.

## Sunsetting a legacy schema

Reading a legacy schema is a promise with a cost, so it gets an end rather than
drifting. The policy, applied to every schema this package reads:

1. A legacy version stays readable for **at least two minor releases** after
   the version that replaced it ships.
2. The release that stops reading it says so in `CHANGELOG.md` under
   **Removed**, names the last version that could read it, and gives the
   command to migrate.
3. A file at a sunset version is refused with a message naming its version and
   the current one. It is never silently reinterpreted, because guessing at an
   old file's meaning is how a stored decision quietly changes what it meant.

| Legacy schema | Readable since | Earliest removal |
|---|---|---|
| `agentverity.snapshot/v1` | superseded in 0.11 | 0.15 |
| `agentverity.evidence/v1` | superseded in 0.15 | 0.17 |
| `agentverity.decision-suite/v1` | superseded in 0.15 | 0.17 |

Migration is `load` then `save` with the current build, which rewrites a file
at the minimum version that describes it.

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
