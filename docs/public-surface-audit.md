# Public surface compatibility audit

This preliminary audit records the top-level Python and command-line surface
published in AgentVerity 0.19.0. It makes accidental drift visible without
claiming the API is frozen before 1.0.

## What CI pins

`tests/fixtures/compatibility/v0.19.0/public-surface.json` records:

- every name in `agentverity.__all__`, classified as a function, class, or
  constant;
- function and constructor call signatures;
- public constant values, including schema names and closed vocabularies; and
- CLI commands plus parser-enforced option names, positionals, action types,
  defaults, choices, required flags, argument types, and cardinality.

CI recollects the surface and compares it with the reviewed fixture. An
intentional pre-1.0 break is still permitted, but it must now update one
readable artifact alongside the required minor version and migration notes.

Help prose, class methods and properties, return-object field semantics, and
serialized report meaning are not established by this fixture. Process exit
classification has a separate [executable contract](cli-exit-contract.md), and
the main Python boundaries now have a preliminary
[return-semantics audit](return-semantics-audit.md). Exact prose and exhaustive
report semantics still require a final audit before 1.0. The exported classes
now also have a structural
[class-member audit](class-member-audit.md); method behaviour remains governed
by focused tests and the return audit rather than this signature inventory.

## Provenance and reproduction

The committed inventory is generated from the published 0.19.0 wheel. Run
outside the checkout so local source cannot shadow it:

```bash
python -m venv /tmp/agentverity-v019
/tmp/agentverity-v019/bin/pip install agentverity==0.19.0
cd /tmp
/tmp/agentverity-v019/bin/python \
  /path/to/agentverity/scripts/audit_public_surface.py \
  /path/to/agentverity/tests/fixtures/compatibility/v0.19.0/public-surface.json \
  --expected-version 0.19.0
```

The auditor refuses to write when the imported version differs from the named
producer. Review fixture changes as contracts, not generated-file noise.
