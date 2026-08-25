# Public Class-Member Audit

This preliminary compatibility audit records the caller-visible structure of
all 37 classes exported by the AgentVerity 0.23.0 candidate. It closes the gap
between a stable constructor signature and the methods, properties, or fields
callers use after construction.

## What CI Pins

`tests/fixtures/compatibility/v0.21.0/class-members.json` records the published
baseline. CI checks its explicit additive candidate delta, for a total of:

- all 190 fields across the 33 exported dataclasses, in declaration order;
- field annotations, constructor participation, keyword-only status, and
  whether defaults are required, literal values, or factories;
- frozen and ordering policy for each dataclass; and
- all 91 public methods, class methods, static methods, and properties declared
  by exported classes, including callable signatures and property writability.

The collector audits every class named by `agentverity.__all__`. A separate CI
check compares that set with the top-level public-surface fixture, so a class
cannot disappear between the two inventories. Private and generated dunder
methods, inherited `object`/exception machinery, docstrings, and method bodies
are deliberately excluded.

The reviewed delta is `CurtailmentReplayResult` and its two properties, plus
the optional `RunResult.curtailment_replay` field. The published 0.21.0
fixture remains unchanged rather than being relabelled as a candidate release.

## Provenance and Reproduction

The committed fixture was produced by the published 0.21.0 wheel. Run outside
the checkout so local source cannot shadow it:

```bash
python -m venv /tmp/agentverity-v021-members
/tmp/agentverity-v021-members/bin/pip install agentverity==0.21.0
cd /tmp
/tmp/agentverity-v021-members/bin/python \
  /path/to/agentverity/scripts/audit_class_members.py \
  /path/to/agentverity/tests/fixtures/compatibility/v0.21.0/class-members.json \
  --expected-version 0.21.0
```

The auditor refuses to write if the imported version differs from the named
producer. Intentional pre-1.0 changes remain allowed, but now require an
explicit fixture diff, the version treatment in `STABILITY.md`, and migration
notes where appropriate.

## Scope Boundary

This is a structural audit, not a claim that every method behaviour is frozen.
The return-semantics fixture and focused behavioural tests cover representative
meaning. Exact CLI help/documentation parity, exact report prose, independent
adoption, and the release security review remain open before 1.0.
