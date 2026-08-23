# BFCL first-pass findings

First qualification run over Berkeley Function Calling Leaderboard v4 cases,
stored here. Model: `openai/gpt-4o-mini` via OpenRouter at default sampling.
Ten consecutive cases from `BFCL_v4_simple_python`, 146 trials per case,
1,460 observations, zero collection errors, collected 2026-08-23.

## Result

**verdict-deterministic, contract satisfied.**

- Flip rate 0/730 pairs; Wilson upper bound [0.000, 0.005] at epsilon 0.05.
- All nine distinct ground-truth functions across the ten cases were observed;
  the declared decision contract reports 100% intended and 100% observed.
- Isolation declared `unknown` (OpenRouter routes across providers and
  instances), so the report carries an independence caveat rather than an
  assumption.

## What was measured, precisely

The categorical label per trial is the called **function name**, canonicalised
to provider-safe characters (BFCL uses namespaced names such as
`math.factorial`). Parameter values were recorded in raw output but are not
part of this stability claim. See the recipe's reduction cautions.

## Reproduce

```bash
agentverity assess --evidence evidence-bfcl-gpt4o_mini.json \
  --suite suite-bfcl-simple-python.json --epsilon 0.05
```

Collection command and parameters are in `collect.py`. Ground truth comes
from the BFCL `possible_answer` file, so no label here was written by this
project.
