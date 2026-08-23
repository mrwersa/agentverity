# Recipe: qualifying Inspect AI epoch runs

[Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) reruns each
evaluation task a declared number of times through its `epochs` parameter.
Those repeated solves are ordered repeated trials of one task, which is the
input shape AgentVerity qualifies. This recipe maps an Inspect run with
`epochs=N` onto AgentVerity evidence.

> **Status: recipe, not integration.** Written against the documented Inspect
> API and not yet exercised end to end against a live Inspect installation.
> Verify scorer names and field paths against your Inspect version before use.

## The categorical reduction

Inspect scorers can return numeric or partial scores. AgentVerity pairs
categorical decisions, so the first step reduces each epoch of a task to one
label. The usual choice is pass or fail per the scorer's own threshold.

This is the step users get wrong. Averaging per-epoch scores and comparing the
average to tolerance answers a different question from certifying that the
epoch-to-epoch label stays stable, and averaging hides exactly the flips the
stability call exists to catch. Reduce first, then assess.

Each task also needs an intended decision when you want contract checking.
For pure stability assessment the expected value can be omitted.

## Mapping

| Inspect | AgentVerity |
|---|---|
| Task with `epochs=N` | One case |
| Epoch solve | One ordered observation |
| Reduced per-epoch label | The decision |
| Fresh solve per epoch | `isolation="fresh-instance"` |
| Task identifier | Case input identity |

Epochs rerun the task in isolation by default, which matches the strongest
isolation declaration. If your solver shares state across epochs, declare
`shared-session` instead: AgentVerity refuses such evidence for baseline
admission, because correlated trials make intervals overconfident.

## Assessing an exported run

Write one JSON object per epoch solve:

```jsonl
{"task_id":"capital_question","decision":"pass"}
{"task_id":"capital_question","decision":"fail"}
{"task_id":"second_task","decision":"pass"}
{"task_id":"second_task","decision":"pass"}
```

Then assess:

```bash
agentverity assess --jsonl inspect-run.jsonl \
  --input-path task_id --decision-path decision \
  --epsilon 0.05
```

File order is pairing order. Export the epochs of each task together and in
epoch order, or the pairs will not mean what you think. See
[imported evidence](../imported-evidence.md) for why aggregates are refused.

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
