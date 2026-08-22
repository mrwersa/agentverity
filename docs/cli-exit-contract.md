# CLI exit behavior contract

AgentVerity uses three process outcomes: `0` for interpretable completion, `1`
for a reviewable finding, and `2` for a refusal or evidence that cannot support
an answer. Not every command can produce every class.

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `run` | Interpretable diagnostics | Coverage, relation, or target finding | Incomplete, undecided, invalid, or infeasible run |
| `plan` | Plan printed | — | CLI usage error |
| `assess` | Interpretable imported evidence | Coverage or target finding | Malformed, incomplete, or undecided evidence |
| `compare-evidence` | No drift | Drift detected | Malformed or incompatible evidence |
| `snapshot` | Baseline admitted | — | Approval absent or evidence refused |
| `check` | Snapshot clean | Snapshot drift | Invalid snapshot or current evidence refused |

`tests/test_cli_exit_contract.py` executes every populated cell using synthetic,
offline inputs. The versioned test contract lives at
`tests/fixtures/compatibility/v0.19.0/cli-exit-contract.json`. This pins process
classification, not exact output prose.

Argument-parser errors also exit `2` through `argparse`. Exceptions raised by a
user-supplied Python factory remain programming errors with tracebacks; they
are not converted into evidence refusals.
