# EvalPort repetition contract: independent consumer review

Reviewed 15 October 2026 against upstream commit
`af1cadcb359dad55e9590dd0cd603c8d7028b9e1` and AgentVerity 0.25.5.
The [executable review](../../research/evalport_conformance/README.md) uses
synthetic observations only and makes no model calls.

## Shipped upstream behaviour

[PR #35](https://github.com/adhabnr-ux/evalport/pull/35) merged on 1 September.
`Result.attempt` is a positive integer whose ascending order defines observation
order within a case/run. `ResultSet.isolation` is declared once per collection
and accepts open string values. The reference SDKs reject duplicate
`(test_case_id, run_id, attempt)` keys.

The two original conformance fixtures behave as described: repeated attempts
validate, while a duplicate attempt is refused. Four additional synthetic
fixtures exercise a complete disagreeing pair, interleaved storage order,
shared-session evidence and a retained runner error. Both reference SDKs and
raw JSON Schema accept these four documents. The downstream rehearsal checks
their statistical meaning separately.

## Findings

- The original three-attempt fixture does not exercise a disagreeing pair:
  its changed final observation is unpaired. The four-attempt fixture gives
  one flip in two pairs, including an observed decision whose quality assertion
  failed.
- Attempt order matters. The interleaved fixture yields zero flips in four
  pairs after per-case attempt ordering. Reading its array order would create
  flips that were not in the declared observation order.
- Structural validity does not confer admission. Shared-session evidence is
  assessed, and snapshot admission still refuses it.
- A runner error without an output is missing decision evidence. The rehearsal
  refuses the collection before pairing instead of counting or dropping that
  row. A numeric quality failure with an actual decision remains usable.
- An open isolation string needs an explicit consumer mapping. Generic `fresh`
  retains its source value but maps conservatively to `unknown` in this review.
- Missing attempts, duplicate attempts, gapped schedules, one-observation cases
  and aggregate-only evidence are refused by the restricted consumer profile.
  These refusals do not add requirements to the EvalPort specification.

## Remaining interoperability boundary

AgentVerity has no public EvalPort importer. The standalone upstream LangSmith
adapter at the reviewed commit exports suites, with one test case per run.
A two-run synthetic probe with a shared `reference_example_id` produced two
different case IDs and no attempt or isolation fields. It does not yet provide
the repetition-preserving ResultSet path needed for this workflow.

The [native LangSmith feature request](https://github.com/langchain-ai/langsmith-sdk/issues/3428)
remains open. A future bridge must bind case identity, preserve observation
order and errors, carry provenance and isolation, and pass an actual producer
round trip. The fixture rehearsal is not evidence that such a bridge already
exists or that an independent user adopted AgentVerity.

## Verification

- EvalPort conformance runner: 33 fixtures passed, including the four additions.
- EvalPort Python SDK: 572 passed, 2 skipped.
- EvalPort TypeScript SDK: 532 passed.
- Raw JSON Schema: all four additional documents accepted.
- AgentVerity: 1,102 passed, 5 skipped; 96.88% coverage; Ruff clean.

The executable review also passed against the released AgentVerity 0.25.5 wheel
in a separate virtual environment, with its import resolving to `site-packages`.
The proposed upstream changes are fixtures and their documentation only; they
change no schema, SDK behaviour or specification. The checked-in copies and
consumer checks remain usable independently of upstream acceptance.
