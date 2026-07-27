# AgentVerity

> **Decision stability and coverage checks for AI agent tests.**

[![PyPI](https://img.shields.io/pypi/v/agentverity.svg)](https://pypi.org/project/agentverity/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20--%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml/badge.svg)](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml)
[![Coverage: 90%+](https://img.shields.io/badge/coverage-90%25%2B-brightgreen.svg)](#development)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/mrwersa/agentverity/blob/main/LICENSE)

AgentVerity tests agents that choose from a known set of decisions: routers,
approval or policy gates, and supervisors that select the next agent or tool.
It compares the named decision, exposed as `verdict`, rather than harmless
changes in explanation text.

Use another evaluator for open-ended chat with no reviewed decision or ordered
tool-path contract. AgentVerity is alpha, with
[documented pre-1.0 guarantees](https://github.com/mrwersa/agentverity/blob/main/STABILITY.md).

## Try it

```bash
pip install agentverity
```

```python
from agentverity import from_callable, run

def route(ticket: str) -> dict[str, str]:
    # Deliberate defect: every ticket takes the same route.
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

Those deliberately varied test inputs form the **probe set**. AgentVerity asks:

- **Decision stability:** does one case reach the same decision across
  isolated reruns?
- **Decision coverage:** do the cases reach more than one decision?

A green quality score answers a different question: whether the selected
answers were right. AgentVerity checks how much evidence that score rests on.
It complements DeepEval, promptfoo, AgentCore Evaluations, and ordinary
assertions rather than replacing them.

Together, the checks guard against two failure modes:

- **Vacuous green:** every supplied assertion passes, but the test inputs reach
  only one decision.
- **Regression trap:** that narrow run becomes the baseline, so later changes
  to untested decisions remain invisible.

## Why rerun counts are harder than they look

Three or five reruns chosen by convention can support the wrong conclusion.
In one deterministic example, 36 non-overlapping rerun comparisons produced no
decision changes. That was still too little evidence to certify a change rate
below 5%. The honest result was **undecided**, not unstable. Certifying that
threshold with no observed changes needed 73 comparisons.

The decision rule is:

- pair reruns without reusing an output
- calculate a 95% Wilson interval around the observed decision-change rate
- report `deterministic` when the upper bound is below the tolerated rate
- report `stochastic` when the lower bound is above the tolerated rate
- report `undecided` when the interval spans that tolerance

Wilson intervals are established statistics. AgentVerity's design choice is
to use one as a three-outcome release rule rather than force an underpowered
run into stable or unstable. Non-overlapping pairs avoid making the sample
look larger than the target calls justify, while the requested tolerance
determines the call budget before execution.

The default `balanced` precision calculates that budget automatically.

[See the executable helper, arithmetic, and exact API mapping](https://github.com/mrwersa/agentverity/blob/main/docs/decision-stability.md).

## The evidence gate

A **baseline** is a reviewed set of expected decisions for later versions.
AgentVerity refuses to save one until calls complete, decisions are stable
enough, the probe set crosses a decision boundary, and a person approves the
reference outputs.

The bundled payment-dispute example runs two test sets:

```bash
python examples/payment_dispute_gate.py
```

| Probe set | Exact-match | Verdict stability | Probe coverage | Baseline |
|---|---|---|---|---|
| Narrow, 6 duplicate-charge cases | ✅ 6/6 | ✅ verdict-deterministic | ❌ blind, 1 route | ❌ REFUSED |
| Repaired, 6 dispute categories | ✅ 6/6 | ✅ verdict-deterministic | ✅ 6 routes | ✅ ADMITTED |

Both score 6/6. The narrow set correctly tests one route, but it cannot justify
a system-wide baseline. The repaired set reaches all six routes and can be
saved as a versioned snapshot.

Create one through the CLI:

```bash
agentverity snapshot \
  --agent mymod:build_agent \
  --inputs seeds.txt \
  --output baseline.json \
  --accept-reference
```

The same checks run before `agentverity check` reports differences as
regressions. Snapshot files retain SHA-256 input fingerprints rather than raw
prompts.

## Where it fits

AgentVerity is an evaluation runner, not serving-path middleware. It makes
controlled calls with reviewed test inputs:

```text
reviewed cases ---> agent ---> quality evaluator: "Was it right?"
             +---> agent ---> AgentVerity: "Can I trust this test?"
                                      |
                           snapshot or release decision
```

Use it while developing, on a pull request, before release, or as a scheduled
synthetic canary. Do not repeat live customer requests. Results can leave as
text, JSON, JUnit XML, or one privacy-minimised OpenTelemetry span.

[See CI, telemetry, lifecycle, and multi-agent integration](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md).

### Measured AgentCore canary

The optional production example combines a Strands payment router on Amazon
Bedrock, DeepEval route-quality checks, AgentVerity, AgentCore Runtime, and
CloudWatch.

![A real AgentCore canary passes DeepEval quality, AgentVerity evidence, and cloud health checks before its baseline is admitted](https://raw.githubusercontent.com/mrwersa/agentverity/main/docs/assets/agentcore-release-gate.svg)

The London canary recorded 6/6 correct routes, no changes across 36 repeat
pairs, all six routes reached, and 78 successful cloud calls with no errors or
throttles. Its first run was stable but only 5/6 correct, so the example now
requires both quality and evidence before snapshot admission.

This is deployment proof, not an AWS requirement. The zero-dependency callable
works with any stack.

[Run the production example](https://github.com/mrwersa/agentverity/tree/main/examples/production_stack) ·
[Read the measured result](https://github.com/mrwersa/agentverity/blob/main/examples/production_stack/RESULTS.md)

## Scope

AgentVerity provides:

- pre-flight stability and decision-coverage checks
- evidence-gated snapshots for reviewed decisions
- JSON, JUnit, and optional OpenTelemetry handoffs
- optional metamorphic relations for controlled input changes

It does not judge answer correctness, store traces, host a dashboard, or
monitor production traffic. Static tools remain useful for declared branches,
route schemas, and expected labels. AgentVerity measures the decisions a
model-backed or black-box target actually returns.

## Documentation

- [Why arbitrary rerun counts fail](https://github.com/mrwersa/agentverity/blob/main/docs/decision-stability.md)
- [Integrations and AgentCore validation](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md)
- [API guide](https://github.com/mrwersa/agentverity/blob/main/docs/api.md)
- [Design decisions](https://github.com/mrwersa/agentverity/blob/main/DESIGN.md)
- [ADR: compare named decisions, not generated text](https://github.com/mrwersa/agentverity/blob/main/docs/adr/0001-compare-named-decisions.md)
- [API stability and path to 1.0](https://github.com/mrwersa/agentverity/blob/main/STABILITY.md)
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
generated README evidence. A coverage job enforces at least 90% statement
coverage, and the branch-protection `CI gate` requires that job to pass.

## Status and licence

Alpha. Pin a minor series for production use, for example
`agentverity~=0.8.0`. Patch releases preserve the public API.

Apache-2.0. Contributions are welcome through the pull-request workflow.
