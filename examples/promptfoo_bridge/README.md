# Promptfoo bridge

Promptfoo owns case-level quality assertions. AgentVerity reuses its repeated
outputs to decide whether those results are stable and cover the reviewed
decision contract.

From this directory:

```bash
npx promptfoo@latest eval \
  --repeat 26 \
  --output results.json \
  --no-share

agentverity assess \
  --promptfoo results.json \
  --suite ../payment_decisions.json \
  --isolation fresh-session
```

The second command makes no model or provider calls. Assertion failures remain
observations because Promptfoo owns correctness. Provider errors make the
AgentVerity result incomplete.

This 26-repeat example certifies the pooled 5% check. It deliberately leaves
each one-case route undecided because 13 pairs do not support the same claim
route by route. `agentverity plan --suite ../payment_decisions.json` shows the
larger zero-change budget before you spend it.

An export containing several providers or prompts is refused. Select one
configuration with `--provider` and `--prompt-id` so differences between
models or prompts are not misreported as stochasticity.
