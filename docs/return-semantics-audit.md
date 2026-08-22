# Return Semantics Compatibility Audit

This preliminary audit records observable Python return behavior published by
AgentVerity 0.19.0. It complements the signature inventory and CLI exit
contract: a callable can keep the same signature and still break callers by
changing the type, status, or field relationship it returns.

## Executed Contract

`scripts/audit_return_semantics.py` runs only public APIs with deterministic,
offline agents and evidence. Its reviewed fixture pins:

- `plan_repeats` returning an integer repeat count;
- the `RunResult`, `MeterResult`, `BlindnessResult`, and
  `DecisionCoverageResult` types and their core values on an admitted run;
- one real execution path for every canonical `RunResult.status` value:
  `deterministic`, `stochastic`, `undecided`, `blind`, `contract`, `vacuous`,
  `target-failed`, `violations`, `incomplete`, and `unmeasured`;
- `assess_evidence` returning the same `RunResult` family without inventing
  relation results;
- evidence drift types, material-change fields, provenance changes, and
  serialized keys;
- snapshot admission plus clean and changed `SnapshotDiff` behavior; and
- JSON, JUnit, and OpenTelemetry return types, schemas, classifications, and
  field/attribute sets for a successful declared-contract run.

CI recollects those semantics and compares them with
`tests/fixtures/compatibility/v0.19.0/return-semantics.json`. A behavior change
therefore requires a readable fixture diff rather than passing unnoticed.

## Provenance and Reproduction

The committed fixture was written by the published 0.19.0 wheel. Run the
repository script from outside the checkout so local source cannot shadow it:

```bash
python -m venv /tmp/agentverity-v019-returns
/tmp/agentverity-v019-returns/bin/pip install agentverity==0.19.0
cd /tmp
/tmp/agentverity-v019-returns/bin/python \
  /path/to/agentverity/scripts/audit_return_semantics.py \
  /path/to/agentverity/tests/fixtures/compatibility/v0.19.0/return-semantics.json \
  --expected-version 0.19.0
```

The auditor refuses to write when the imported version differs from the named
producer. Collection omits durations, timestamps, and installed-version
attributes because they are not stable return semantics.

## Scope Boundary

This fixture does not freeze exact headlines, help prose, floating-point
confidence bounds, arbitrary provider values, class methods, or every field on
every result object. Existing focused tests still define more behavior than
this compatibility sample. Public class structure now has a separate
[member audit](class-member-audit.md); help/documentation parity, independent
adoption, and release security review keep the final 1.0 audit open.
