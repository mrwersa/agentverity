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
the baseline. Eight of ten cases were perfectly stable; the instability is
concentrated in two cases:

- one flipped between integer and float renderings of the same numeric value
  (`"A": 10` versus `"A": 10.0`, 107 versus 39), which is lexical variation
  that a canonicalising label would collapse;
- one genuinely varied a location string (`Washington` versus
  `Washington State`, 122 versus 13).

So of the 53 observed flips, roughly 39 are canonicalisation artefacts and 13
are real output variation. The honest reading: the true flip rate is near but
not obviously below the tolerance on this case set, and argument-level
stability is measurably worse than function-name stability. This is exactly
why the reduction granularity must be declared before collection, as the
recipe says.

Isolation declared `unknown`; the report carries the independence caveat.
Correctness scoring against BFCL's own evaluator remains future work.
