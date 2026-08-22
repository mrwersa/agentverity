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
- Raw probe-input fields remain excluded from generated reports, snapshots,
  JUnit, progress, and OpenTelemetry exports. Snapshots intentionally retain
  approved observations, and diagnostic paths can retain values described in
  the [security and data-retention audit](docs/security-data-audit.md).

Production users should pin the current minor series:

```text
agentverity~=0.19.0
```

That accepts compatible `0.19.x` fixes without moving to a later pre-1.0 minor
series.

Version 0.19 reads and writes one version of each schema:
`agentverity.run/v2`, `agentverity.telemetry/v2`, `agentverity.snapshot/v4`,
`agentverity.evidence/v2` and `agentverity.decision-suite/v1`. The numbers
differ because each records its own format history, not a release. Evidence is
at v2 because the shape of a stored outcome changed. Snapshots are at v4 for
that and again for recording the isolation a baseline was admitted under, so a
v3 file is refused rather than read: it cannot say how its trials were
separated, and guessing would invent the provenance the check establishes. The decision suite is still at v1 because `allowed_no_decisions` is
optional and a suite written without it parses correctly. JSON reports and
telemetry exports are append-only artefacts, so consumers must opt into their
schemas. The evidence loader rejects unknown versions and aggregate-only
inputs rather than guessing. Promptfoo and DeepEval bridges translate into
that contract while keeping framework packages optional.

## Schema versions, and when one changes

Every artefact this package writes carries a schema version, and the loader
refuses a version it does not recognise rather than guessing at the contents.

**A version changes only when a reader cannot correctly interpret a file
written at the previous version.** Adding an optional field is not a version
change, because an older reader parses such a file correctly and simply does
not use the new field. Changing what an existing field means is a version
change, and so is removing one, and so is altering the type of a value already
in use.

The corollary is that different schemas sit at different numbers, and that is
normal. A version records what happened to one format. Levelling them for
visual uniformity states something false about the ones that did not change,
and hides the change in the one that did.

That rule exists because a version is an obligation. Every one declared is a
number somebody later feels obliged to bump, and every bump invites a
compatibility branch for files nobody holds. A version that sits still for a
long time is evidence the format is stable, not evidence the versioning is
unused.

Before 1.0 this package reads exactly one version of each schema. There is no
compatibility layer, because there are no known external consumers and a
dual-read path costs more than it is worth while the format is still moving.
An unrecognised version is refused by name and never silently reinterpreted,
because guessing at an old file's meaning is how a stored decision quietly
changes what it meant.

The [cross-version compatibility audit](docs/compatibility-audit.md) checks
the three durable reader paths against files written by 0.16.0, the earliest
minor that produced every currently supported schema. There are no migration
paths to test: older evidence and snapshot schemas are deliberately refused.

The preliminary [public surface audit](docs/public-surface-audit.md) also pins
top-level exports, signatures, public constants, commands, flags, and parser
defaults from 0.19.0. It does not yet cover class internals, help prose,
return-object semantics, or exit behavior, so the final compatibility audit
remains open.

The [CLI exit contract](docs/cli-exit-contract.md) exercises representative
offline paths for every command and each process class it supports. Exact help
and report prose remain outside that contract.

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

Criterion 2 is now exercised for the current reader schemas. The remaining
criteria, and any future migration introduced before 1.0, remain open.

The preliminary data-retention audit now has a versioned matrix and executable
sentinel checks across every in-tree output surface. It corrects the earlier
overbroad snapshot guarantee, but does not replace the independent release
security review required by criterion 4.

Download count alone is not an exit criterion. The goal is evidence that the
contract works outside the examples that shaped it.
