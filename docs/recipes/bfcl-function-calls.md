# Recipe: qualifying repeated runs on BFCL cases

The [Berkeley Function Calling Leaderboard](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)
ships a community-maintained set of function-calling cases with ground-truth
calls, across single-turn, multi-turn, memory, and web-search categories. The
leaderboard itself scores one run per case. This recipe covers the complementary
question: run your own model over those cases repeatedly and qualify whether
the chosen calls are stable enough to freeze as a regression baseline.

> **Status: recipe, not integration.** Written against the documented BFCL
> category and data layout, and not yet exercised end to end against a live
> BFCL installation. Verify field paths against your harness version before
> use.

## What maps to what

| BFCL | AgentVerity |
|---|---|
| One test entry (single-turn) | One case |
| One turn of one entry (multi-turn) | One case, if qualified per turn |
| One trial's decoded call on that entry | One ordered observation |
| Reduced call label per trial | The decision |
| The dataset's ground-truth call | Intended decision, enabling contract checking |

Run each entry or turn as its own case. Do not pool an entire category into
one case: pooling would pair decisions from different questions.

## The categorical reduction

BFCL's own evaluation checks an abstract-syntax-tree match between the decoded
call and the ground truth. For stability assessment you need something simpler:
one categorical label per trial. The natural choice is the called function
name, optionally with a canonicalised argument signature.

Two cautions. First, exact string labels will count semantically equivalent
calls as flips when argument order differs, which overstates instability.
Canonicalise before labelling. Second, reducing a whole call to its function
name discards argument drift: a model that always calls `transfer` but varies
the amount is stable at the function level and unstable at the parameter level.
Pick the granularity that matches the decision your release gate governs, and
say which one you chose.

## Isolation must be declared honestly

How you run the repeats determines the declaration:

- Re-invoking the model API per trial through the BFCL harness is most plausibly
  `unknown` unless you have verified no shared caching or session state.
- A hosted endpoint with server-side caching can correlate trials in ways that
  are invisible from the outside.
- Only declare `fresh-instance` when you have verified each trial starts a new
  conversation context with no carried state.

AgentVerity admits `unknown` evidence with an explicit caveat rather than
assuming independence, and refuses `shared-session` evidence outright.

## Assessing an exported run

Write one JSON object per trial, preserving trial order within each entry:

```jsonl
{"entry_id":"simple_0","decision":"get_weather"}
{"entry_id":"simple_0","decision":"get_weather"}
{"entry_id":"irrelevance_3","decision":"no_call"}
{"entry_id":"irrelevance_3","decision":"check_stock"}
```

Then assess:

```bash
agentverity assess --jsonl bfcl-run.jsonl \
  --input-path entry_id --decision-path decision \
  --epsilon 0.05 --isolation unknown
```

For contract checking against the dataset's ground truth, build a decision
suite whose allowed and required decisions come from the BFCL expected calls,
and pass it with `--suite`. That turns the report into a completeness verdict
as well as a stability one.

File order is pairing order within identical entries. Preserve trial order per
entry when exporting. See [imported evidence](../imported-evidence.md) for why
aggregate pass rates are refused.

## Budget expectations

At a 5% tolerance, certifying stability with zero observed flips takes 73
disjoint pairs per case. Fifty cases across three models at 146 repeats each
is about 21,900 calls, so price the run with `agentverity plan` first. Short
runs still reject: a model flipping between competing functions on half its
trials is visible almost immediately.

## Non-guarantees

A stable wrong call qualifies as stable. Stability says nothing about
correctness, safety, argument validity beyond the chosen reduction, or whether
BFCL cases represent your production traffic. See
[applicability](../applicability.md).
