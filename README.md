# AgentVerity

> **Your agent test passed. Would it pass again?**

[![PyPI](https://img.shields.io/pypi/v/agentverity.svg)](https://pypi.org/project/agentverity/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20--%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml/badge.svg)](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml)
[![Coverage: 90%+](https://img.shields.io/badge/coverage-90%25%2B-brightgreen.svg)](#development)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/mrwersa/agentverity/blob/main/LICENSE)

AgentVerity is an offline Python library and CLI that qualifies repeated,
categorical AI-agent decisions before you save them as a **regression
baseline**—a reviewed reference for future releases. It finds unstable routes,
weak decision coverage, and runs too small to support a conclusion. It does
not judge whether an answer is correct.

## The 60-second problem

A payment router sends disputes to six specialist queues. Promptfoo runs six
reviewed cases 26 times, and all **156/156 assertions pass**. One
ambiguous case allows either of two valid fraud queues.

AgentVerity reads that same export and finds:

```text
route              cases  pairs  flips  95% CI            result
card_security          1     13      8  [0.355, 0.823]    stochastic
cash_withdrawal        1     13      0  [0.000, 0.228]    undecided
duplicate_charge       1     13      0  [0.000, 0.228]    undecided

flip pairs:
  card_security <-> merchant_dispute  x8
```

The quality policy accepts both answers, but a reference that switches queues
will make later regression checks noisy. The changing route is `stochastic`;
the five quiet routes are `undecided` because 13 pairs are too few to certify
them separately. A **flip** means the two observations in a paired rerun
differed. AgentVerity therefore refuses this run as a baseline.

## Try it without model calls

```bash
git clone --depth 1 https://github.com/mrwersa/agentverity.git
cd agentverity
python -m pip install .
agentverity assess \
  --promptfoo examples/promptfoo_bridge/results.json \
  --suite examples/payment_decisions.json
```

`assess` performs arithmetic over recorded decisions. It makes no model or
provider calls. You can also reuse precomputed DeepEval `LLMTestCase` objects
or any ordered JSONL log:

```bash
agentverity assess --jsonl runs.jsonl \
  --input-path probe.text --decision-path result.route
```

Order matters because observations are paired in collection order. See
[imported evidence](https://github.com/mrwersa/agentverity/blob/main/docs/imported-evidence.md)
before converting a log.

To call an agent directly, install only the framework adapter you need:

```bash
pip install "agentverity[strands]"
pip install "agentverity[langgraph]"
```

Plain Python callables need no extra dependency:

```python
from agentverity import from_callable, run


def route(text):
    return "billing" if "charge" in text.lower() else "cash_withdrawal"


agent = from_callable(lambda text: {"verdict": route(text)})
result = run(agent, inputs=["duplicate charge", "cash withdrawal"])
print(result.summary())
```

## What it decides

AgentVerity keeps three statistical outcomes separate:

- `deterministic`: enough evidence supports the declared tolerance
- `stochastic`: decision changes exceed that tolerance
- `undecided`: the run supports neither conclusion

It then checks whether the probe set collapsed onto one decision and, when a
decision contract is supplied, whether every required route was intended and
observed. Per-route results show where changes concentrate. Optional relations
check reviewed input transformations and report no-op transforms as untested,
not passed.

Once you have two evidence windows, `agentverity compare-evidence before.json
after.json` reports changed route conclusions, gained or lost decisions,
changed flip pairs, isolation, and provenance.

## Where it fits

| Layer | Question |
|---|---|
| Promptfoo, DeepEval, Ragas, or labelled assertions | Was the answer acceptable? |
| **AgentVerity** | **Is the repeated categorical evidence strong enough to freeze?** |
| LangSmith, Phoenix, AgentCore, or another trace system | What happened during the run and in production? |
| Security and authority tests | Was the agent allowed to take that action? |

AgentVerity is a local test and release step, not serving-path middleware. Use
it for named routes, approvals, policy outcomes, tool choices, hand-offs, or a
reviewed finite tool path. Use another evaluator for open-ended chat, RAG
quality, generated content, or coding-agent output. If those systems also emit
a bounded route or approval, AgentVerity can qualify that decision layer.

| Command | Purpose |
|---|---|
| `agentverity plan` | Price the best-case evidence budget without calling an agent |
| `agentverity run` | Collect and assess isolated repeated decisions |
| `agentverity assess` | Assess Promptfoo, DeepEval, JSONL, or native evidence |
| `agentverity snapshot` | Admit a human-reviewed reference when evidence permits |
| `agentverity check` | Re-run the admission policy and compare with a snapshot |
| `agentverity compare-evidence` | Compare two independently collected evidence windows |

## Why rerun counts are harder than they look

Three or five reruns by convention do not state what variation they can rule
out. With no observed changes:

- 36 independent pairs bound the change rate below about 9.6%
- a claim below 5% needs 73 pairs
- a short quiet run is therefore `undecided`, not proven stable

AgentVerity sizes calls from the tolerance, uses non-overlapping pairs, and
places a Wilson interval around the flip rate. Optional sequential collection
uses checkpoints declared before collection; it does not repeatedly inspect a
fixed-sample interval and stop when the result looks favourable.

For evidence already collected, `best_case_admission_pairs` tests whether an
all-agree continuation could admit within a predeclared pair budget. It may
justify stopping an impossible run early; it never creates an early admission.

Use `agentverity plan --suite examples/route_stability_plan.json` before
spending remote calls. The [method guide](https://github.com/mrwersa/agentverity/blob/main/docs/decision-stability.md)
explains the arithmetic, and the [validation artifact](https://github.com/mrwersa/agentverity/blob/main/docs/method-validation.md)
records exact-boundary checks and dependence stress tests.

## The evidence gate

`snapshot` refuses a baseline until calls complete, the evidence supports the
declared stability and coverage policy, and a person approves the reference as
correct. The bundled offline example shows why correctness alone is not enough:

```bash
python examples/payment_dispute_gate.py
```

| Probe set | Exact-match | Verdict stability | Declared coverage | Baseline |
|---|---|---|---|---|
| Narrow, 6 duplicate-charge cases | ✅ 6/6 | ✅ verdict-deterministic | ❌ 1/6 required routes | ❌ REFUSED |
| Repaired, 6 dispute categories | ✅ 6/6 | ✅ verdict-deterministic | ✅ 6/6 required routes | ✅ ADMITTED |

Both sets score 6/6. Only the repaired set reaches all six required routes.

Real-system evidence is also committed and reproducible without new calls:

- The [AgentCore canary](https://github.com/mrwersa/agentverity/blob/main/examples/production_stack/RESULTS.md) validates a
  production-shaped integration while explicitly stopping short of per-route
  certification.
- The [AgentKit study](https://github.com/mrwersa/agentverity/tree/main/docs/evidence/agentkit) records 4,380 calls across
  three models and shows that the most stable model can be less correct.

Never repeat live customer requests. Use reviewed synthetic cases in CI,
before release, or on a schedule.

## What it does not prove

`TRUSTWORTHY` means the supplied cases produced stable, non-collapsed evidence
at the declared tolerance and satisfied any declared decision contract. It
does not prove correctness, safety, semantic diversity, complete behavioural
coverage, provider independence, or production reliability. AgentVerity also
does not store traces, host a dashboard, monitor traffic, or score open-ended
answers.

## Documentation

- **Start:** [applicability and limits](https://github.com/mrwersa/agentverity/blob/main/docs/applicability.md),
  [runnable examples](https://github.com/mrwersa/agentverity/tree/main/examples),
  and the [API guide](https://github.com/mrwersa/agentverity/blob/main/docs/api.md)
- **Use existing tools:** [imported evidence](https://github.com/mrwersa/agentverity/blob/main/docs/imported-evidence.md),
  [integration placement](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md),
  and the [importer conformance contract](https://github.com/mrwersa/agentverity/blob/main/docs/integration-contract.md)
- **Framework recipes:** [qualifying Inspect AI epoch runs](https://github.com/mrwersa/agentverity/blob/main/docs/recipes/inspect-ai-epochs.md)
- **Understand the method:** [decision stability](https://github.com/mrwersa/agentverity/blob/main/docs/decision-stability.md),
  [per-route evidence](https://github.com/mrwersa/agentverity/blob/main/docs/route-evidence.md),
  and [categorical evaluator stability](https://github.com/mrwersa/agentverity/blob/main/docs/evaluator-stability.md)
- **Operate safely:** [security](https://github.com/mrwersa/agentverity/blob/main/SECURITY.md),
  [data-retention audit](https://github.com/mrwersa/agentverity/blob/main/docs/security-data-audit.md),
  and [API stability](https://github.com/mrwersa/agentverity/blob/main/STABILITY.md)
- **Project direction:** [design](https://github.com/mrwersa/agentverity/blob/main/DESIGN.md),
  [roadmap](https://github.com/mrwersa/agentverity/blob/main/ROADMAP.md), and the
  [agent-evaluation landscape](https://github.com/mrwersa/agentverity/blob/main/docs/agentic-ai-landscape.md)
- **Participate:** [contribute](https://github.com/mrwersa/agentverity/blob/main/CONTRIBUTING.md)
  or [join the design-partner pilot](https://github.com/mrwersa/agentverity/blob/main/docs/design-partners.md)

## Development

```bash
pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

CI covers Python 3.10–3.14, package construction, and at least 90% statement
coverage. See the contributing guide above before opening a pull request.

## Status and licence

Alpha. Pin the current minor series for production use:
`agentverity~=0.20.0`. Patch releases preserve the public API.

Apache-2.0.
