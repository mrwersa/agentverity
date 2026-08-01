# AgentKit evidence: tool selection across three models

4,380 real model calls against the tool set a published agent exposes, to ask
one question: given the same request twice, does a model pick the same tool?

Everything here re-runs. The evidence files hold the individual observations,
so `summarise.py` and `agentverity assess` cost nothing.

## What was measured, and what was not

The target is the tool set of the
[Coinbase AgentKit](https://github.com/coinbase/agentkit) Strands example
chatbot: the twenty tools its seven wired providers declare, taken from
`coinbase-agentkit` 0.7.4 source. `agentkit_tools.json` holds the names and
descriptions exactly as AgentKit declares them.

**This is not AgentKit's chatbot end to end.** Constructing that needs CDP
credentials and a funded wallet, and executing the tools would move money. The
decision under test is tool *selection*, so the tools are declared to each
model exactly as AgentKit declares them and nothing is executed. The model
still makes the entire choice.

One turn, `tool_choice="required"`, temperature left at each provider's
default. Pinning it to zero would measure a configuration nobody deploys.

## The result

```
model                                           correct  always the same
amazon/nova-micro-v1                               4/10             1/10
openai/gpt-4o-mini                                 7/10             8/10
mistralai/mistral-small-3.2-24b-instruct           5/10            10/10
```

Read the two columns against each other. `mistral-small` returned the same
tool on every one of ten probes, 146 times each, and was correct on half of
them. It would pass a stability gate perfectly while being worse at the task
than `gpt-4o-mini`, which is unstable on two routes.

Repeatability is not correctness. This is that sentence with numbers behind
it.

## Where gpt-4o-mini is unstable, and why it matters

```
route              cases  pairs  flips  95% CI            result
approve                1     73     34  [0.356, 0.579]    stochastic
transfer               1     73     28  [0.281, 0.498]    stochastic
  approve <-> get_erc20_token_address  x34
  get_erc20_token_address <-> transfer x28
```

Eight routes settle as deterministic at a 5% tolerance. The two that do not
are `transfer` and `approve`, which are two of the three the suite marks
**critical** because they move value or grant the right to move it.

Neither alternative is silly. Asked to send USDC, the model sometimes calls
`transfer` and sometimes resolves the token address first. Both are reasonable
opening moves. What a release needs to know is that the first action on a
value-moving request is close to a coin flip, and a pooled figure of 8.5%
across all ten routes does not say which routes carry it.

## About the `correct` column

`expected` in `suite.json` is a reviewed judgement, and it assumes the right
first tool is the one that does the job. Several models instead resolve an
identifier first, which is a defensible plan rather than a mistake, and this
single-turn setup cannot express it. Read that column as agreement with one
reviewer's labels, not as ground truth.

The stability column does not depend on those labels at all. A model that
answers `get_erc20_token_address` 146 times out of 146 is stable whatever
anybody thinks the right answer was.

## Two things the collection itself found

`tool_choice="required"` did not always produce a tool call. Nova Micro
answered with prose on two probes, which the adapter records as
`no_tool_selected` rather than leaving the verdict unset. Leaving it unset
makes the meter fall back to comparing raw text, so two differently worded
refusals count as a changed decision. That measures wording, not choice.

Two providers declare `get_balance`: `ERC20ActionProvider` and
`WalletActionProvider`. A tool-calling API cannot carry the same name twice,
so the first declaration wins here and the collision is recorded rather than
silently resolved.

## Re-running

Free, from the committed evidence:

```bash
python docs/evidence/agentkit/summarise.py
agentverity assess --evidence docs/evidence/agentkit/evidence-gpt4o_mini.json \
                   --suite docs/evidence/agentkit/suite.json
```

Collecting again costs about 0.70 USD and 25 minutes, and needs an
`OPENROUTER_API_KEY`:

```bash
agentverity plan --suite suite.json          # price it first: 1460 calls per model
python collect.py --factory gpt4o_mini --model openai/gpt-4o-mini \
                  --repeats 146 --workers 6 --out evidence-gpt4o_mini.json
```

Collected 2026-08-01 through OpenRouter. Model behaviour changes without
notice, so a later run reproducing the method is expected; a later run
reproducing these exact numbers is not.
