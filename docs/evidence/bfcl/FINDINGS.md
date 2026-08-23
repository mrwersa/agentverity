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

| Case | Flips | Values observed |
|---|---:|---|
| 7 | **29** | `"A": 10` (107) against `"A": 10.0` (39) |
| 8 | **24** | `Washington` (122), `Washington State` (13), `Washington state` (11) |

Flip counts, not value counts, are what the interval consumes. Case 7 is
lexical variation a canonicalising label would collapse. Case 8 is real output
variation, and it has three renderings rather than two, the third differing
only in capitalisation.

**The reduction granularity changes the release decision.** Collapsing integer
and float renderings of the same number, and nothing else, moves the run from
reject to admit:

| Labelling | Flips | Rate | Wilson interval | Call |
|---|---:|---:|---|---|
| As collected | 53/730 | 7.3% | [0.056, 0.094] | **REJECT** |
| Numerics canonicalised | 24/730 | 3.3% | [0.022, 0.048] | **ADMIT** |

That is the load-bearing result of this run. The recipe warns that exact string
labels overstate instability and that the granularity must be declared before
collection. Here that warning is worth a reversed verdict on the same
observations, so the declaration is not a formality. Argument-level stability
remains measurably worse than function-name stability under either labelling.

Isolation declared `unknown`; the report carries the independence caveat.
Correctness scoring against BFCL's own evaluator remains future work.
