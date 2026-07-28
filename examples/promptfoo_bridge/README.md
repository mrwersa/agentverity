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

## Try it without installing Promptfoo

`results.json` in this directory is a recorded export in the real Promptfoo
shape: 6 reviewed cases, 26 repeats each, one route deliberately unstable.

```console
$ agentverity assess \
    --promptfoo results.json \
    --suite ../payment_decisions.json \
    --isolation unknown
```

The contract check passes and the pooled flip rate is 11.5%. Per route,
`card_security` changes decision on 9 of its 13 comparisons and confuses with
`merchant_dispute`. The other five routes are not clean, they are unmeasured:
13 pairs bounds them at 22.8%, and 73 are needed to certify at 5%.

Regenerate it against a live Promptfoo run with the config in this directory.
