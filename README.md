# agentverity

> **Can you trust this green agent test?**

[![PyPI](https://img.shields.io/pypi/v/agentverity.svg)](https://pypi.org/project/agentverity/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20--%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml/badge.svg)](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/mrwersa/agentverity/blob/main/LICENSE)

AgentVerity is a pre-flight testing library for non-deterministic agents. It
checks whether the verdict is stable across identical reruns and whether the
probe set can move the decision at all. Then it tells you which test result is
safe to trust.

It does not replace DeepEval, promptfoo, AgentCore Evaluations, or your quality
metrics. It checks two conditions that can make those scores misleading before
you trust them.

![AgentVerity diagnoses a blind triage step and a stochastic supervisor pipeline](https://raw.githubusercontent.com/mrwersa/agentverity/main/docs/assets/diagnostic-report.svg)

*This report is regenerated from the executable
[`bugfix_pipeline.py`](https://github.com/mrwersa/agentverity/blob/main/examples/bugfix_pipeline.py)
example and tested against
its current results.*

## Try it

```bash
pip install agentverity
```

```python
from agentverity import from_callable, run

def route(ticket: str) -> dict:
    # Deliberate defect: the input is ignored.
    return {"text": "route: general", "verdict": "general"}

agent = from_callable(route)
result = run(agent, inputs=[
    "my card was charged twice",
    "the app crashes on login",
    "where is my refund",
    "the checkout button is the wrong colour",
])

print(result.headline)
```

```text
NOT TRUSTWORTHY - the agent answered 'general' on 100% of the probes,
so a pass says more about the probe set than about the agent.
```

The default `balanced` precision sizes the repeat count automatically. A
default run answers rather than leaving a deterministic function as
`undecided`.

From a repository checkout, the same example is directly runnable:

```bash
python examples/support_router.py

agentverity run \
  --agent examples/support_router.py:build_agent \
  --inputs examples/support_tickets.txt
```

## What it catches

| Condition | Why the green result is unsafe | AgentVerity's action |
|---|---|---|
| **Blind probes** | One verdict dominates, so relations can pass without crossing a decision boundary | Repair the probe set |
| **Stochastic verdict** | Identical reruns disagree, so zero-tolerance checks confuse noise with regressions | Use repeated rates against measured noise |
| **Stable, varied verdict** | The decision is suitable for a reviewed reference | Prefer an evidence-gated snapshot or targeted relations |
| **Unexercised relation** | The transform returned the original input, so no test happened | Report `n/a`, never a false pass |

The meter reports `deterministic`, `stochastic`, or `undecided` from a Wilson
interval over disjoint repeat pairs. The skew scan separately checks whether
varied inputs produce varied verdicts. Stability is not correctness, so
snapshots still require explicit human approval.

## The evidence gate

AgentVerity will not freeze a baseline it cannot justify. The
[`payment_dispute_gate.py`](https://github.com/mrwersa/agentverity/blob/main/examples/payment_dispute_gate.py)
example runs the same router against two probe sets:

```bash
python examples/payment_dispute_gate.py
```

| Probe set | Exact-match | Verdict stability | Probe coverage | Baseline |
|---|---|---|---|---|
| Narrow, 6 duplicate-charge cases | ✅ 6/6 | ✅ verdict-deterministic | ❌ blind, 1 route | ❌ REFUSED |
| Repaired, 6 dispute categories | ✅ 6/6 | ✅ verdict-deterministic | ✅ 6 routes | ✅ ADMITTED |

Both sets score 6/6 against their expected routes. The narrow set produces one
verdict, so snapshot creation is refused. The repaired set crosses six routing
categories and is admitted. The evaluator remains green while the evidence
gate distinguishes a focused unit test from a system-wide baseline.

<details>
<summary>See the exact terminal output</summary>

```text
PAYMENT-DISPUTE ROUTER: THE EVIDENCE GATE
==========================================

BEFORE: narrow probe set
------------------------
Exact-match evaluator: 6/6 correct
Verdict mix: duplicate_charge=6
AgentVerity: NOT TRUSTWORTHY - the agent answered 'duplicate_charge' on 100% of the probes, so a pass says more about the probe set than about the agent.
Baseline: REFUSED - probe set is blind; add inputs that cross a decision boundary

AFTER: repaired probe set
-------------------------
Exact-match evaluator: 6/6 correct
Verdict mix: duplicate_charge=1, refund_delay=1, card_security=1, merchant_dispute=1, cash_withdrawal=1, transfer_delay=1
AgentVerity: TRUSTWORTHY - the verdict held across every identical rerun and the probes cross a decision boundary.
Baseline: ADMITTED - evidence is complete, stable, and non-blind
```

</details>

The repository's manually triggered
[**Evidence gate demo**](https://github.com/mrwersa/agentverity/actions/workflows/evidence-gate-demo.yml)
workflow renders both JUnit reports in its GitHub Actions summary. No
AgentVerity account or dashboard is involved.

Create a reviewed reference through the CLI:

```bash
agentverity snapshot \
  --agent mymod:build_agent \
  --inputs seeds.txt \
  --output baseline.json \
  --accept-reference
```

Calls must complete, the verdict must be stable enough, the probes must cross a
decision boundary, and a person must approve the outputs. The same admission
checks run again before `agentverity check` reports differences as regressions.
Snapshot files retain SHA-256 input fingerprints rather than raw prompts.

## Where it fits

```text
agent or workflow
       |
       v
AgentVerity pre-flight ----> quality evaluator
       |                    DeepEval / promptfoo / AgentCore Evaluations
       |
       +---- text for people
       +---- JSON for code
       +---- JUnit XML for CI
       +---- OTEL span for CloudWatch / Phoenix / LangSmith
```

AgentVerity is deliberately small at this boundary. The core has no runtime
dependencies, no hosted account, and no dashboard to adopt.

### CI reporting

Write a report that Jenkins, GitLab, Azure DevOps, and JUnit collectors already
understand:

```bash
agentverity run \
  --agent examples/support_router.py:build_agent \
  --inputs examples/support_tickets.txt \
  --format junit \
  --output agentverity.xml
```

Exit codes and JUnit carry the same interpretation:

- `0`: interpretable evidence and no relation violation
- `1`: blind or vacuous probes, a relation violation, or snapshot drift
- `2`: incomplete, undecided, or unsupported evidence

### Monitoring

Use the host application's OpenTelemetry pipeline:

```bash
pip install "agentverity[otel]"
```

```python
from agentverity import record_otel_run

result = run(agent, inputs=canary_probes)
record_otel_run(result)
```

The summary span contains low-cardinality `agentverity.*` attributes. It
excludes prompts, outputs, fingerprints, relation names, and exception
messages. OTLP can carry the span into Amazon Bedrock AgentCore Observability
and CloudWatch, Phoenix, LangSmith, or another collector.

Run this in CI, before deployment, or as a scheduled canary. AgentVerity is not
an online evaluator and should not repeat every customer request.

[Integration examples and the AgentCore validation plan](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md)

## Observation layers

Every call becomes one `Observation`:

```python
from agentverity import Observation

Observation(
    text="Escalating this case",
    verdict="escalate",
    tools=("lookup_order", "create_case"),
)
```

Measure the layer the test protects:

- `verdict` for routing, policy, and categorical decisions
- `tools` for the ordered tool trajectory
- `text` when wording itself is the contract

Token variation does not have to become verdict instability, and a stable
answer can still hide a changed tool path.

## Configuration

Most runs need two knobs:

```python
from agentverity import RunConfig

config = RunConfig(
    precision="balanced",  # cheap=10%, balanced=5%, strict=1%
    budget=None,           # optional cap on meter calls
    max_workers=4,         # distinct inputs only
    error_policy="record",
)
```

`k=` and `epsilon=` remain exact overrides. Repeated calls for one input stay
sequential, while distinct inputs can run concurrently. Recorded provider
failures mark evidence incomplete and never become passing verdicts.

## Examples

- [`support_router.py`](https://github.com/mrwersa/agentverity/blob/main/examples/support_router.py): the smallest blind-agent example
- [`payment_dispute_gate.py`](https://github.com/mrwersa/agentverity/blob/main/examples/payment_dispute_gate.py): a green evaluator whose narrow baseline is refused, then admitted after probe repair
- [`bugfix_pipeline.py`](https://github.com/mrwersa/agentverity/blob/main/examples/bugfix_pipeline.py): blind triage plus a stochastic supervisor
- [`strands_example.py`](https://github.com/mrwersa/agentverity/blob/main/examples/strands_example.py): optional Strands adapter
- [`otel_monitoring.py`](https://github.com/mrwersa/agentverity/blob/main/examples/otel_monitoring.py): one diagnostic span through OTEL

For Strands:

```bash
pip install "agentverity[strands]"
```

Plain LangGraph, remote APIs, and other frameworks can use `from_callable` by
returning an `Observation` from their invocation wrapper.

## Scope

AgentVerity is:

- a pre-flight check for the evidence behind an agent test
- an evidence gate for reviewed snapshots
- a small CI and telemetry citizen

It is not:

- a correctness oracle or LLM judge
- a benchmark or leaderboard
- a trace store, dashboard, or production monitoring service
- a claim that metamorphic relations or Wilson intervals are new

The distinctive part is their ordering: measure verdict stability and probe
coverage before interpreting the ordinary test result.

## Documentation

- [Integrations and AgentCore validation](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md)
- [API guide](https://github.com/mrwersa/agentverity/blob/main/docs/api.md)
- [Design decisions](https://github.com/mrwersa/agentverity/blob/main/DESIGN.md)
- [Security and data handling](https://github.com/mrwersa/agentverity/blob/main/SECURITY.md)
- [Contributing](https://github.com/mrwersa/agentverity/blob/main/CONTRIBUTING.md)
- [Release process](https://github.com/mrwersa/agentverity/blob/main/RELEASING.md)

## Development

```bash
pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

CI covers Python 3.10 through 3.14, lint, package construction, and the
generated README diagnostic.

## Status and licence

Alpha. Public APIs may change before 1.0.

Apache-2.0. Contributions are welcome through the pull-request workflow.
