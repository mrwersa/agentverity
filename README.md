# AgentVerity

> **Your agent test passed. Would it pass again?**

[![PyPI](https://img.shields.io/pypi/v/agentverity.svg)](https://pypi.org/project/agentverity/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20--%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml/badge.svg)](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml)
[![Coverage: 90%+](https://img.shields.io/badge/coverage-90%25%2B-brightgreen.svg)](#development)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/mrwersa/agentverity/blob/main/LICENSE)

An agent can pass a test and choose a different route on its next run. That makes
one passing output a noisy regression reference for later releases.
AgentVerity is a local Python library and CLI that checks whether repeated
agent decisions are repeatable enough to save as a baseline. It also flags
missing routes and evidence too small to support a conclusion.

## The 60-second problem

A payment router sends disputes to six queues. Promptfoo repeats six reviewed
cases 26 times: **156/156 assertions pass**. One case accepts either of two
valid fraud queues. AgentVerity reads the same export and finds:

```text
route              cases  pairs  flips  95% CI            result
card_security          1     13      8  [0.355, 0.823]    stochastic
cash_withdrawal        1     13      0  [0.000, 0.228]    undecided
duplicate_charge       1     13      0  [0.000, 0.228]    undecided

flip pairs:
  card_security <-> merchant_dispute  x8
```

Every answer is allowed, but the changing queue would make a regression check
noisy. The five quiet routes need more evidence to qualify separately.
A **flip** is a pairwise disagreement: two reruns of the same case returned
different decisions. This evidence is refused as a regression reference.
Observations form non-overlapping pairs in collection order.

## Try it without model calls

```bash
git clone --depth 1 https://github.com/mrwersa/agentverity.git
cd agentverity
python -m venv .venv
. .venv/bin/activate
python -m pip install .
agentverity assess \
  --promptfoo examples/promptfoo_bridge/results.json \
  --suite examples/payment_decisions.json
```

This reads recorded decisions and makes no model or provider calls. Assessment
exit `0` means the report completed, not that a baseline was admitted.
See [imported evidence](https://github.com/mrwersa/agentverity/blob/main/docs/imported-evidence.md)
for Promptfoo, precomputed DeepEval cases, JSONL, and ordering requirements.

Plain Python callables need no extra dependency:

```python
from agentverity import from_callable, run


def route(text):
    return "billing" if "charge" in text.lower() else "cash_withdrawal"


agent = from_callable(lambda text: {"verdict": route(text)})
result = run(agent, inputs=["duplicate charge", "cash withdrawal"])
print(result.summary())
```

For stateful agents, use a fresh instance or session for each trial. The
[integration guide](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md)
covers Strands, LangGraph, remote agents, and isolation declarations. Optional
extras are `agentverity[strands]` and `agentverity[langgraph]`. The callable
example reports `unknown` isolation because the adapter does not
verify how the function manages state.

## Two gates, not one

A regression reference needs two separate yeses: AgentVerity qualifies
repeatability, while a human or quality evaluator checks whether the expected
behaviour is acceptable. A person then approves saving the reference.

The repeatability meter has three public machine outcomes:

- `deterministic`: repeatability qualified at the declared tolerance
- `stochastic`: repeatability rejected at that tolerance
- `undecided`: inconclusive, supporting neither direction

`deterministic` does not mean zero randomness. Missing coverage, failed calls,
and isolation caveats also matter to admission. A pooled qualification does
not certify every route separately.

The offline coverage example shows another reason to refuse a baseline:

```bash
python examples/payment_dispute_gate.py
```

| Probe set | Exact-match | Verdict repeatability | Declared coverage | Reference |
|---|---|---|---|---|
| Narrow, 6 duplicate-charge cases | ✅ 6/6 | ✅ verdict-deterministic | ❌ 1/6 required routes | ❌ REFUSED |
| Repaired, 6 dispute categories | ✅ 6/6 | ✅ verdict-deterministic | ✅ 6/6 required routes | ✅ ADMITTED |

Both sets score 6/6, and both pooled meters qualify. Missing coverage blocks
the narrow reference. The repaired reference is admitted at pooled level;
its individual route intervals remain inconclusive.

## Where it fits

| Layer | Question |
|---|---|
| Quality evaluator or reviewed assertions | Was the answer acceptable? |
| **AgentVerity** | **Is the repeated decision evidence strong enough to save as a regression reference?** |
| Tracing and monitoring | What happened during the run and in production? |

Use it for named routes, approvals, tool choices, handoffs, or a reviewed finite
tool path. Use another evaluator for open-ended chat, RAG quality, or generated
content. Choose the decision layer before collecting evidence: a tool-name
check cannot detect changed arguments.

| Command | Purpose |
|---|---|
| `agentverity plan` | Budget evidence before calling an agent |
| `agentverity run` | Collect and assess repeated decisions |
| `agentverity assess` | Assess recorded evidence without new target calls |
| `agentverity snapshot` | Collect live evidence and admit an approved regression reference when evidence permits |
| `agentverity inspect` | Read the stored reference without calling anything |
| `agentverity check` | Recheck admission and compare current decisions with the reference |
| `agentverity compare-evidence` | Compare repeatability structure and provenance across evidence windows |

`compare-evidence` can report NO CHANGE even when stable output labels differ.
Use `check` when the reviewed decisions themselves must match.
To save imported evidence, Python callers use
[`create_snapshot(result, approved=True)`](https://github.com/mrwersa/agentverity/blob/main/docs/imported-evidence.md#what-an-import-can-and-cannot-check);
CLI `snapshot` collects a new live run.

## Stop when more runs cannot help

Repeat-run variation is often called **flakiness**. With no flips, a fixed
95% Wilson interval needs 73 independent pairs to qualify below a 5%
tolerance. This is a best-case minimum, not a guarantee of qualification.

`plan` prices that evidence. Live `--curtail` stops when qualification becomes
impossible within the fixed budget and never admits early.
`assess --replay-curtailment` is post-hoc and counterfactual: it never changes
the observed endpoint classification. See the
[method guide](https://github.com/mrwersa/agentverity/blob/main/docs/decision-stability.md)
and [workshop calculations](https://github.com/mrwersa/agentverity/blob/main/research/fixed_budget_qualification/README.md)
for planning, stopping rules, and evidence.

Qualification concerns the supplied cases in one evaluation period. It does
not prove correctness, safety, independent provider calls, or reliability
across deployments and time. Never repeat live customer requests. Use reviewed
synthetic cases with equivalent starting state.

## Documentation and community

- [Applicability and limits](https://github.com/mrwersa/agentverity/blob/main/docs/applicability.md)
- [API guide](https://github.com/mrwersa/agentverity/blob/main/docs/api.md) and [runnable examples](https://github.com/mrwersa/agentverity/tree/main/examples)
- [Per-route evidence](https://github.com/mrwersa/agentverity/blob/main/docs/route-evidence.md) and [evaluator repeatability](https://github.com/mrwersa/agentverity/blob/main/docs/evaluator-stability.md)
- [Method validation](https://github.com/mrwersa/agentverity/blob/main/docs/method-validation.md) and the [AgentKit study: 4,380 calls](https://github.com/mrwersa/agentverity/tree/main/docs/evidence/agentkit)
- [Security](https://github.com/mrwersa/agentverity/blob/main/SECURITY.md), [API stability](https://github.com/mrwersa/agentverity/blob/main/STABILITY.md), and [roadmap](https://github.com/mrwersa/agentverity/blob/main/ROADMAP.md)
- [Contribute](https://github.com/mrwersa/agentverity/blob/main/CONTRIBUTING.md) or [join the design-partner pilot](https://github.com/mrwersa/agentverity/blob/main/docs/design-partners.md)

## Development

```bash
pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

Core runtime dependencies: none. CI covers Python 3.10–3.14 and at least 90%
statement coverage.

Alpha. Pin `agentverity~=0.25.0` for compatible patch updates. Apache-2.0.
