# Security and Data-Retention Audit

This maintainer audit records what AgentVerity 0.20.0 retains on each data
surface. It is an implementation baseline, not an independent security review
or a claim that an artifact is anonymous.

## Method

The executable contract uses unique synthetic sentinels for a probe input,
model output, provider error, decision label, and relation name. It runs the
real library paths and checks the resulting objects or serializations. The
reviewed matrix lives in
`tests/fixtures/compatibility/v0.20.0/data-retention-contract.json`; CI executes
it through `tests/test_security_data_contract.py`.

“Excluded” means AgentVerity does not populate that category on the tested
surface. “Conditionally retained” means a documented diagnostic or
caller-controlled field can contain it. “Raw input” below means the direct
probe-input field: an agent output or exception can echo the same text and
must be treated according to its own column.

## Retention Matrix

| Surface | Raw input | Observation value | Input fingerprint | Exception message | Decision label | Relation name |
|---|---|---|---|---|---|---|
| Decision-suite JSON | Retained | n/a | Excluded | n/a | Retained | n/a |
| Imported evidence | Retained | Retained | Conditional | Conditional | Retained | Conditional |
| JSON run report | Excluded | Conditional | Retained | Retained | Retained | Retained |
| JUnit report | Excluded | Conditional | Excluded | Excluded | Conditional | Retained |
| Terminal summary | Excluded | Conditional | Excluded | Retained | Conditional | Retained |
| Progress event | Excluded | Excluded | Retained | Excluded | Excluded | Excluded |
| Snapshot | Excluded | Retained | Retained | Excluded | Retained | Excluded |
| OpenTelemetry | Excluded | Excluded | Excluded | Excluded | Excluded | Excluded |

Imported-evidence `provenance` is an unfiltered, caller-supplied mapping. It can
therefore retain identifiers, errors, or names even though the dedicated
evidence fields do not. Progress callbacks receive the full SHA-256
fingerprint; the CLI prints its first 10 characters.

JSON reports do not contain per-call output records, but diagnostic fields such
as `majority_verdict` can contain an observation value. JUnit and terminal
headlines can echo the same value on finding paths. JSON reports and terminal
summaries retain recorded exception messages; JUnit reports retain only
failure counts and AgentVerity-generated explanations. Snapshots necessarily
retain the approved reference observation they later compare.

OpenTelemetry is the narrowest surface: only aggregate counts, configuration,
rates, and AgentVerity status values are emitted. Exporter configuration,
resource attributes, surrounding spans, and backend retention are outside this
contract.

The 0.21.0 curtailment extension adds only generated status text and aggregate
pair, flip, endpoint, and avoided-call counts to terminal, JSON, JUnit, and
OpenTelemetry output. It does not add partial observations or raw inputs to
those surfaces; the published 0.20.0 retention fixture remains the baseline.

## Operator Controls and Failure Modes

- Treat suites, imported evidence, snapshots, JSON reports, and terminal logs
  as sensitive unless their contents have been inspected.
- Treat SHA-256 fingerprints as stable identifiers, not anonymisation; guessed
  inputs can be checked offline.
- Assume provider exceptions may contain request or response data. Prefer
  provider-side redaction before using `error_policy="record"` in shared logs.
- Keep generated artifacts out of source control unless they are synthetic and
  reviewed. Apply repository, CI-artifact, and telemetry-backend retention
  policies independently.
- Adapter and provider logging occurs outside AgentVerity's serializers. This
  audit does not establish their behaviour.

## Remaining Review Gate

This audit makes current behaviour explicit and regression-tested. It does not
cover dependency vulnerabilities, hostile file-size/resource-exhaustion tests,
filesystem permissions, CI secret handling, or an independent review of the
threat model. Those checks remain required before the 1.0 security criterion
is complete.
