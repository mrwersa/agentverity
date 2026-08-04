# Promptfoo bridge

Promptfoo owns case-level quality assertions. AgentVerity reuses its repeated
outputs to decide whether those results are stable and cover the reviewed
decision contract. The ambiguous card-security case accepts either fraud queue
as a valid quality result, so all 156 configured assertions pass.

From this directory, regenerate the sample with Promptfoo:

```bash
npx promptfoo@latest eval \
  --repeat 26 \
  --max-concurrency 1 \
  --no-cache \
  --output results.json \
  --no-share

agentverity assess \
  --promptfoo results.json \
  --suite ../payment_decisions.json \
  --isolation unknown
```

The first command calls the included local Python provider. The second command
makes no model or provider calls. Failed assertions remain decision
observations because Promptfoo owns correctness. Provider or runtime errors
make the AgentVerity result incomplete.

This 26-repeat example classifies the pooled decision-change rate above the 5%
tolerance. It deliberately leaves each quiet one-case route undecided because
13 pairs do not support a separate stability claim. `agentverity plan --suite
../payment_decisions.json` shows the larger zero-change budget before you
spend it.

The fixture uses a single global repeat count. Promptfoo has also allowed a
per-test count since 0.121.18 (`tests[].options.repeat`), and the importer
handles that the same way: each rendered input is matched back to a reviewed
suite case, so a case with its own count simply contributes its own pairs.

An export containing several providers or prompts is refused. Select one
configuration with `--provider` and `--prompt-id` so differences between
models or prompts are not misreported as stochasticity.

## Try it without installing Promptfoo

`results.json` is a recorded Promptfoo JSON export produced by the included
local provider: 6 reviewed cases, 26 repeats each, with one deliberately
varying route.

```console
$ agentverity assess \
    --promptfoo results.json \
    --suite ../payment_decisions.json \
    --isolation unknown
```

The contract check passes and the pooled decision-change rate is 10.3%. For
the ambiguous case, the decision switches between `card_security` and
`merchant_dispute` in 8 of its 13 paired reruns. The other five routes did not
change, but remain `undecided`: 13 pairs bound their change rate at 22.8%,
while 73 zero-change pairs are needed to certify the declared 5% tolerance.

The fixed pseudo-random seed, serial collection, and disabled cache make the
committed fixture reproducible. The provider still returns different
decisions across repeated calls to the `card_security` case. Promptfoo accepts
both labels under the configured quality policy. AgentVerity catches the
separate operational problem: a moving route is not a stable regression
reference even when each answer is allowed.
