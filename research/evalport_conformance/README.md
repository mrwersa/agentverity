# EvalPort repetition conformance review

Offline consumer review for [EvalPort issue #20](https://github.com/adhabnr-ux/evalport/issues/20)
and [Discussion #22](https://github.com/adhabnr-ux/evalport/discussions/22).
All decisions and identifiers in these fixtures are synthetic.
The upstream fixture contribution is [PR #132](https://github.com/adhabnr-ux/evalport/pull/132),
submitted for review.

The repetition contract landed in [PR #35](https://github.com/adhabnr-ux/evalport/pull/35)
on 1 September 2026. This review uses upstream commit
`af1cadcb359dad55e9590dd0cd603c8d7028b9e1` and released AgentVerity 0.25.5.
The SDK checkout contains later validator changes beyond its 1.3.1 release,
so the upstream commit, rather than that package version, identifies the
validator exercised here.

## Run

Use a checkout of EvalPort at that commit. In a separate virtual environment,
install AgentVerity 0.25.5 and the checkout's `sdk/python[test]` extra, which
supplies the validator and its dependencies. From the AgentVerity repository root:

```bash
python research/evalport_conformance/check.py --evalport-root /tmp/agentverity-evalport-review
```

The path selects EvalPort's real Python validator. It does not install a
package or contact a provider. The four proposed fixtures live in `fixtures/`.
The two original fixtures are read from the supplied upstream checkout.

Verified output:

```text
multi_attempt_resultset_valid.json: expected SDK validity True
duplicate_attempt_collision_rejected.json: expected SDK validity False
four_attempt_disagreement_valid.json: SDK valid; 1/2 pair flips; isolation=fresh-instance
interleaved_attempt_order_valid.json: SDK valid; 0/4 pair flips; isolation=fresh-session
repeated_runner_error_valid.json: SDK valid; consumer refuses incomplete evidence
repeated_shared_session_valid.json: SDK valid; 0/4 pair flips; isolation=shared-session
PASS: structural checks and the bounded consumer rehearsal agree
```

## What is checked

| Fixture | Document validity | Consumer check |
| --- | --- | --- |
| Four attempts with a disagreement | Valid | One flip in two complete pairs. A quality assertion failure still carries its observed decision. |
| Interleaved, out-of-order attempts | Valid | Sort attempts within each case/run. Pairing array positions instead would change the answer. |
| Shared-session repeats | Valid | Assessment succeeds; sufficient quiet evidence still cannot admit a shared-session reference. |
| Runner error on attempt 2 | Valid | Refuse the incomplete collection before pairing. Do not count the error as a decision or silently remove it. |

`check.py` contains a restricted projection for one synthetic suite, with
reviewed case IDs mapped to synthetic probe inputs. It exercises the actual
`EvidenceSet`, assessment and pair-counting code. It is a conformance rehearsal
outside the public import surface. It does not implement a general EvalPort
importer or verify an end-to-end LangSmith export.

The projection requires explicit, contiguous attempt indices and at least two
observations per case. It refuses aggregates, duplicate attempts, unknown case
identities and missing decisions. These are consumer requirements, not added
EvalPort validity rules. For example, a gapped schedule can be structurally
valid while failing this consumer's pairing requirements.

## Isolation mapping

| EvalPort declaration | Rehearsal mapping |
| --- | --- |
| `fresh-session`, `fresh-instance`, `shared-session` | Preserve the explicit declaration |
| `shared` | `shared-session` |
| Missing, `unknown`, generic `fresh`, or another open string | `unknown`, retaining the original value in provenance |

Generic `fresh` does not distinguish a fresh session from a fresh instance.
The rehearsal preserves that limitation instead of asserting one. None of
these declarations establishes independent provider trials. AgentVerity's
existing caveats and admission policy apply.

## Verification boundary

The four proposed fixtures pass both real reference SDKs and raw JSON Schema
validation. SDK conformance and JSON Schema agreement do not establish ordering
preservation by producers or consumers. In particular, the existing duplicate
attempt rule is a cross-item SDK rule that raw JSON Schema does not enforce.

The unit checks exercise case order, attempt order, a disagreeing pair, quality
failure versus harness failure, isolation, evidence round trips and refusals.
The intentionally loose `epsilon=0.5` in the shared-session unit check isolates
the admission-policy check. It is not an application tolerance recommendation.

The original valid upstream fixture contains three attempts. Its changed third
decision is unpaired under disjoint adjacent pairing. The four-attempt fixture
adds the missing complete disagreeing pair.

These results establish a synthetic consumer check, not an external adoption,
completed pilot, or production reliability claim. The workshop reproduction at
`research/fixed_budget_qualification/` and the paper's frozen link are separate.
