# BFCL findings

## Run 1 — invocation-consistency smoke test (2026-08-23)

Ten consecutive simple-python cases, gpt-4o-mini via OpenRouter at default
sampling, 146 trials per case, 1,460 observations, zero recorded errors.

Result: every trial of every case emitted the case's single available
function name. Flip rate 0/730 pairs; Wilson upper bound 0.0052; all nine
distinct ground-truth functions observed under contract check.

**Scope, stated plainly after audit.** Each of these cases exposes exactly one
function, the collector forces `tool_choice: required`, and arguments were not
retained in this run. So this measures consistent *emission* of one available
function name, not tool-selection stability, argument stability, or
correctness. It also predates the collector fixes that preserve submission
order, retain arguments, and accumulate cost. Kept as a smoke test only; the
selection-stability run is the load-bearing artifact.

## Run 2 — selection stability over multi-function cases (2026-08-23)

Ten consecutive multiple-category cases (two to several candidate functions
per case), gpt-4o-mini via OpenRouter at default sampling, 146 trials per
case, 1,460 observations with schema normalisation (dict to object,
float to number, tuple to array), submission order preserved, canonicalised
arguments retained per trial.

Result: **verdict-stochastic.** Flip rate 7.3% (53/730 pairs), Wilson interval
[0.056, 0.094], which exceeds the 5 per cent tolerance, so the rule rejects
the baseline. Eight of ten cases were perfectly stable and the instability is
concentrated in two:

| Case | Entry | Flips | Values observed |
|---|---|---:|---|
| 7 | `multiple_6` | **29** | `"A": 10` (107) against `"A": 10.0` (39) |
| 8 | `multiple_7` | **24** | `Washington` (122), `Washington State` (13), `Washington state` (11) |

Cases are numbered from one in this note and the entries are identified from
zero in the evidence file, so the entry column is given to stop the two being
confused.

Flip counts, not value counts, are what the interval consumes. Case 7 is
lexical variation a canonicalising label would collapse. Case 8 is real output
variation, and it has three renderings rather than two, the third differing
only in capitalisation.

**The reduction granularity changes a qualification call.** Each entry is
qualified on its own, so the result is stated per entry. Collapsing integer and
float renderings of the same number, and nothing else, moves one entry from
reject to admit on the same 73 pairs:

| Entry | Exact labels | Numerics canonicalised |
|---|---|---|
| `multiple_6` | 29 flips, [0.293, 0.512], **REJECT** | 0 flips, [0.000, 0.050], **ADMIT** |
| `multiple_7` | 24 flips, [0.232, 0.443], **REJECT** | 24 flips, [0.232, 0.443], **REJECT** |
| other eight | 0 flips, ADMIT | 0 flips, ADMIT |

That is the load-bearing result of this run. The recipe warns that exact string
labels overstate instability and that the granularity must be declared before
collection. Here that warning is worth a reversed call on identical
observations, so the declaration is not a formality.

**Canonicalising is not a way to admit anything.** `multiple_7` rejects under
both labellings, because three surface renderings of one place name are real
output variation rather than a labelling artefact. The relation earns the
reversal on one entry and refuses it on the other, which is the argument for
declaring it rather than a licence to relabel until something admits.

**Pooling is not a call this rule licenses.** Summing every entry gives 53 of
730 pairs as collected and 24 of 730 canonicalised, which would read as reject
then admit. The pooled admit conceals `multiple_7`, which rejects either way, so
a release gate built on per-entry calls would still reject. The pooled figures
are recorded in [reduction-report.json](reduction-report.json) under
`pooled_not_a_call` for completeness and are not a verdict.

Argument-level stability remains measurably worse than function-name stability
under either labelling.

**Reproducing the counterfactual.** [reduce.py](reduce.py) declares both
reductions, applies them pointwise to the committed observations in collection
order, and writes [reduction-report.json](reduction-report.json). Run
`python3 reduce.py --check` to prove the committed report still matches the
evidence. `tests/test_bfcl_reduction.py` pins the numbers quoted above and
asserts that the reduction neither drops nor reorders an observation.

Isolation declared `unknown`; the report carries the independence caveat.
Correctness scoring against BFCL's own evaluator remains future work.
