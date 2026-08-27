# BFCL repeated-evaluation protocol

Status: frozen before the first confirmatory provider call on 27 August 2026.
The machine-readable specification is
[`single-evaluation-protocol.json`](single-evaluation-protocol.json).

## Question and terminology

This is one evaluation of whether repeated categorical function-call decisions
are repeatable enough to qualify as regression references. It uses the paper's
three outcomes throughout: `qualify`, `exceeds_tolerance`, and `undecided`.
An early stop is reported as `qualification_impossible`, not as an endpoint
classification.

The evaluation fixes three declarations:

1. the mapping $g$ that determines when two observed calls count as the same
   categorical decision
2. the fixed-budget qualification rule $(B, \epsilon, \alpha)$
3. the evaluation period represented by the collected pairs

The primary mapping parses each argument object as JSON, collapses
integer-valued numbers such as `10.0` to `10`, and serialises keys in sorted
order. Function names, strings, non-integral numbers, lists, and call order are
otherwise unchanged. Exact serialisation is the comparison mapping.

## Corpus and models

The confirmatory corpus is BFCL v4 `multiple_10` through `multiple_59` at
upstream revision `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`. The exploratory
cases `multiple_0` through `multiple_9` are excluded from confirmatory
prevalence statements.

The three model endpoints are:

- `openai/gpt-4o-mini`
- `mistralai/mistral-small-3.2-24b-instruct`
- `amazon/nova-micro-v1`

Each model-case cell has a fixed endpoint of 73 disjoint pairs, or 146 calls,
with $\epsilon=0.05$, $\alpha=0.05$, and $z=1.96$.

## One evaluation, two collection paths

All 50 cases belong to one protocol and one analysis. The difference below is
predeclared because prospective stopping and fixed-budget mapping comparisons
need different observation lengths.

For the prospective collection, the runner evaluates the primary mapping after
each complete pair. A non-validation cell stops only when an all-agreement
continuation cannot qualify by pair 73. A stopped cell has no endpoint
classification. The runner records its stopping pair and avoided pairs.

Ten cases form the full-budget validation subset. They are the ten lowest
SHA-256 ranks of the 50 case identifiers, fixed without observing outcomes:

`multiple_21`, `multiple_23`, `multiple_24`, `multiple_26`, `multiple_39`,
`multiple_40`, `multiple_41`, `multiple_42`, `multiple_53`, and `multiple_56`.

Those cells continue to pair 73 even if qualification becomes impossible.
Only this subset supports fixed-budget comparisons between the primary and
exact mappings. It is not a separate experiment and is not pooled into one
qualification outcome.

## Evaluation periods

Period 1 may begin on 27 August 2026. Period 2 may begin on 17 September 2026,
which fixes a 21-day minimum gap. The second period is a matched replication.
Two periods do not estimate stationarity or an across-period disagreement rate.

## Receipts and integrity

Every provider response, parsed call, trial index, timestamp, latency, cost,
error, case, model, period, and protocol hash is written immediately to a
private JSONL receipt. One file is used per model-case cell. Completed cells
are sealed by summaries, and a model-period manifest records the byte length
and SHA-256 digest of every receipt and summary. A changed sealed file is
refused.

The private directory is ignored by Git. It must be copied to durable private
storage after each model-period run. Public or anonymous derivatives are built
from the sealed receipts and never replace them.

## Commands

Validate the protocol without provider calls:

```bash
.venv/bin/python docs/evidence/bfcl/collect_study.py \
  --model-key gpt4o_mini --period period-1 --dry-run
```

Collect one model-period after loading `OPENROUTER_API_KEY`:

```bash
.venv/bin/python docs/evidence/bfcl/collect_study.py \
  --model-key gpt4o_mini --period period-1
```

Use `mistral_small` and `nova` for the other model keys. Repeating an
interrupted command resumes unsealed cells. Repeating a completed command
verifies the sealed receipts and does not issue provider calls.