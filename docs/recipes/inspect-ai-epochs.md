# Recipe: qualifying Inspect AI epoch runs

[Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) reruns each
dataset sample a declared number of times through its `epochs` parameter:
`total_samples = len(dataset) * epochs`, keyed by `(sample_id, epoch)`. Those
repeated solves are ordered repeated trials of one sample, which is the input
shape AgentVerity qualifies. This recipe maps an Inspect run with `epochs=N`
onto AgentVerity evidence.

> **Status: recipe, not integration.** Written against the documented Inspect
> API and the execution source, and not yet exercised end to end against a
> live Inspect installation. A small exporter with a committed fixture is the
> planned follow-up. Verify scorer names and field paths against your Inspect
> version before use.

## What maps to what

| Inspect | AgentVerity |
|---|---|
| Dataset `Sample.id` | One case |
| One `(sample_id, epoch)` solve | One ordered observation |
| Reduced per-epoch label | The decision |
| Isolation of that solve | Declared isolation |

A Task is not one case. Its dataset may hold many samples, and epochs apply to
every one of them, so the case boundary follows the sample, not the task.
Pooling a whole run into one case would pair decisions from different inputs.

## The categorical reduction

Inspect scorers can return numeric or partial scores. AgentVerity pairs
categorical decisions, so each epoch must reduce to one label before
assessment. The usual choice is pass or fail per the scorer's own threshold.

This is the step users get wrong, in two directions. Averaging per-epoch scores
and comparing the average to tolerance answers a different question from
certifying that the epoch-to-epoch label stays stable. And reducing to
pass/fail measures evaluator or outcome-verdict stability: if you want agent
decision stability instead, extract the categorical route, tool choice, or
decision the agent actually produced on each epoch, not the grader's verdict.

Each sample also needs an intended decision when you want contract checking.
For pure stability assessment the expected value can be omitted.

## Isolation must be declared honestly

Epochs create fresh sample state, but that is not the same as a fresh
instance of the agent under test. Inspect resolves the solver plan once per
eval and reuses it across executions, and a sandbox persists across samples
unless configured otherwise. Whether two epochs of one sample share sessions,
caches, or mutable state depends on the task and solver, not on `epochs`.

So declare what actually happened:

- `unknown`: the default when you have not verified instance behaviour.
  AgentVerity will admit with an explicit caveat rather than assume
  independence.
- `fresh-instance`: only when task construction genuinely creates a new
  target or agent instance per epoch.
- `shared-session`: when mutable state persists across epochs. AgentVerity
  refuses such evidence for baseline admission, because correlated trials
  make intervals overconfident.

## Assessing an exported run

Write one JSON object per epoch solve, preserving epoch order within each
sample:

```jsonl
{"sample_id":"capital_question","epoch":1,"decision":"pass"}
{"sample_id":"capital_question","epoch":2,"decision":"fail"}
{"sample_id":"second_task","epoch":1,"decision":"pass"}
{"sample_id":"second_task","epoch":2,"decision":"pass"}
```

Then assess:

```bash
agentverity assess --jsonl inspect-run.jsonl \
  --input-path sample_id --decision-path decision \
  --epsilon 0.05 --isolation unknown
```

Interleaved samples are fine: pairing happens within identical inputs.
Preserving epoch order inside each sample is not negotiable. File order is
pairing order, so a log sorted by anything other than epoch reports a
stability the run never had. See
[imported evidence](../imported-evidence.md) for why aggregates are refused.

Omitting `--isolation` is equivalent to `--isolation unknown`: the report
gains a caveat saying independence is assumed rather than established. That
caveat is the honest output until someone verifies instance behaviour.

## Budget expectations

At a 5% tolerance, certifying stability with zero observed flips takes 73
disjoint pairs, so `epochs=2` across ten tasks cannot certify anything on its
own. It can still reject: a route flipping on half its pairs is visible almost
immediately. Size the run with `agentverity plan` before spending model calls.

## Non-guarantees

Reducing epochs to pass/fail discards partial credit. A stable wrong answer
qualifies as stable, and stability says nothing about correctness, safety, or
whether the tasks represent your workload. See
[applicability](../applicability.md).
