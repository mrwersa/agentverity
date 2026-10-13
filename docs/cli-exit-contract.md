# CLI exit behaviour contract

AgentVerity uses three process outcomes: `0` for interpretable completion, `1`
for a reviewable finding, and `2` for a refusal or evidence that cannot support
an answer. Not every command can produce every class.

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `run` | Interpretable diagnostics | Blindness, coverage, relation, target, or curtailment finding | Incomplete, undecided, invalid, or infeasible run |
| `plan` | Plan printed, including an unreachable endpoint | — | Invalid arguments, unreadable suite, or infeasible plan |
| `assess` | Interpretable imported evidence | Blindness, coverage, or target finding | Malformed, incomplete, unsupported, or undecided evidence |
| `compare-evidence` | No drift | Drift detected | Malformed or incompatible evidence |
| `snapshot` | Regression reference admitted | — | Approval absent or evidence refused |
| `check` | Snapshot clean | Snapshot drift | Invalid snapshot or current evidence refused |
| `inspect` | Stored reference rendered | — | Unreadable, malformed, or incompatible snapshot |

Interpretable stochastic evidence can exit `0` from `run` or `assess` while
remaining inadmissible as a snapshot. A failed targeted tolerance exits `1`;
an undecided target exits `2`. Read the report and use snapshot admission for
the baseline decision.

`tests/test_cli_exit_contract.py` executes the original command matrix using
synthetic, offline inputs. Later commands and refusal paths also have focused
tests in `tests/test_cli.py`. The versioned test contract lives at
`tests/fixtures/compatibility/v0.20.0/cli-exit-contract.json`. This pins process
classification, not exact output prose.

AgentVerity 0.21.0 extends that published baseline through focused execution
tests rather than relabelling the fixture: `run --curtail` exits `1` when
fixed-endpoint admission becomes unreachable, while `snapshot --curtail`
exits `2` because partial evidence has no final repeatability class to admit.

The read-only `agentverity inspect --snapshot` view is a later additive command
with only two outcomes: `0` when it reads a stored reference and `2` when the
file is not one. Its focused execution tests live in `tests/test_cli.py`, the
same way, rather than in the published fixture.

Argument-parser errors also exit `2` through `argparse`. Exceptions raised by a
user-supplied Python factory remain programming errors with tracebacks; they
are not converted into evidence refusals.
