# AgentVerity

> **Decision stability and coverage checks for AI agent tests.**

[![PyPI](https://img.shields.io/pypi/v/agentverity.svg)](https://pypi.org/project/agentverity/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20--%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml/badge.svg)](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml)
[![Coverage: 90%+](https://img.shields.io/badge/coverage-90%25%2B-brightgreen.svg)](#development)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/mrwersa/agentverity/blob/main/LICENSE)

AgentVerity qualifies tests for model-backed components that choose from a
finite, reviewed set of decisions. Examples include routers, approval or
policy gates, and supervisors that select the next agent or tool. It compares
the named decision, exposed as `verdict`, rather than harmless changes in
explanation text.

Use another evaluator for open-ended chat with no reviewed decision or ordered
tool-path contract. AgentVerity is alpha, with
[documented pre-1.0 guarantees](https://github.com/mrwersa/agentverity/blob/main/STABILITY.md).

Read the design story:
[Introducing AgentVerity: What Does a Green Agent Test Prove?](https://mrwersa.medium.com/introducing-agentverity-what-does-a-green-agent-test-prove-fa6ebbfda2d3)

## Is it a fit?

AgentVerity fits when all three conditions hold:

- each run exposes a named decision or a reviewed tool or handoff path
- repeated trials can start from equivalent state in isolated sessions
- you can supply deliberately varied test inputs that should reach different
  valid decisions

Good targets include support and payment routers, fraud triage, approval and
policy gates, incident routing, multi-agent supervisors, and bounded tool
selectors. In a larger agent, test the step that owns the decision or the
final pipeline decision. Test both when each is a release contract.

It is not an end-to-end quality evaluator for chat, RAG answers, generated
content, coding agents, or research agents. If one of those systems also emits
a reviewed route, approval, escalation, or tool path, AgentVerity can qualify
that decision layer, not the open-ended work around it.

[See the applicability checklist and exact limits](https://github.com/mrwersa/agentverity/blob/main/docs/applicability.md).

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
- **Declared coverage:** when you supply a decision contract, did the suite
  include every required decision, did the agent return them, and did it emit
  an unknown decision?

A green quality score answers a different question: whether the selected
answers were right. AgentVerity checks how much evidence that score rests on.
It complements DeepEval, promptfoo, AgentCore Evaluations, and ordinary
assertions rather than replacing them.

Together, the checks guard against two failure modes:

- **Vacuous green:** every supplied assertion passes, but the test inputs reach
  only one decision.
- **Regression trap:** that narrow run becomes the baseline, so later changes
  to untested decisions remain invisible.

AgentVerity qualifies the evidence from this run. It does not certify the
agent as correct, safe, or fully covered.

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

| Probe set | Exact-match | Verdict stability | Declared coverage | Baseline |
|---|---|---|---|---|
| Narrow, 6 duplicate-charge cases | ✅ 6/6 | ✅ verdict-deterministic | ❌ 1/6 required routes | ❌ REFUSED |
| Repaired, 6 dispute categories | ✅ 6/6 | ✅ verdict-deterministic | ✅ 6/6 required routes | ✅ ADMITTED |

Both score 6/6. The narrow set correctly tests one route, but it covers only
one of the six routes declared as required. The repaired set reaches all six
and can be saved as a versioned snapshot.

Declare that test contract in Python:

```python
from agentverity import DecisionCase, DecisionContract, DecisionSuite, run

suite = DecisionSuite(
    contract=DecisionContract(
        allowed={"duplicate_charge", "refund_delay", "card_security"},
        critical={"card_security"},
    ),
    cases=(
        DecisionCase("I was charged twice", "duplicate_charge"),
        DecisionCase("My refund is late", "refund_delay"),
        DecisionCase("I do not recognise this card payment", "card_security"),
    ),
)

result = run(agent, suite=suite)
```

`expected` records the route each case is intended to exercise. AgentVerity
checks intended and observed route coverage separately. Your assertions or
quality evaluator still decide whether each returned route was correct.

Declaring a suite also splits stability by route, from the calls the run
already made:

```text
4. STABILITY BY ROUTE
   route              cases  pairs  flips  95% CI            result
   approve                2     26      0  [0.000, 0.129]    undecided
   deny                   2     26      0  [0.000, 0.129]    undecided
   review                 2     26     10  [0.224, 0.575]    stochastic
   flip pairs:
     deny <-> review  x10
```

The pooled meter said 12.8% across the whole set. One route is the reason. The
other two are not clean, they are unmeasured: 26 pairs bounds them at 12.9%,
and 73 pairs are needed to certify at 5%.

A route proven stochastic blocks snapshot admission even when the pooled meter
looks deterministic. Undecided route rows remain visible limits in this
release. They do not silently trigger the much larger call budget needed to
certify every route independently.

Create one through the CLI:

```bash
agentverity snapshot \
  --agent examples/payment_dispute_gate.py:build_agent \
  --suite examples/payment_decisions.json \
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

[Read how per-route evidence works, with worked examples](https://github.com/mrwersa/agentverity/blob/main/docs/route-evidence.md).

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

The v0.9 contract path was then rerun directly through Bedrock after the old
runtime was removed. It again scored 6/6 with 0/36 route changes, and reported
all six required routes intended and observed with no unknown decision.

This is deployment proof, not an AWS requirement. The zero-dependency callable
works with any stack.

[Run the production example](https://github.com/mrwersa/agentverity/tree/main/examples/production_stack) ·
[Read the measured result](https://github.com/mrwersa/agentverity/blob/main/examples/production_stack/RESULTS.md)

## Scope

A trustworthy AgentVerity result means that, for the supplied probe set,
optional decision contract, and chosen tolerance:

- repeated isolated calls provided enough evidence about decision stability
- observed decisions did not collapse onto one highly dominant route
- every required decision was intended and observed when a contract was given
- no observed decision fell outside that contract
- execution completed and any requested relation checks were meaningful

That is a minimum dynamic adequacy check, not exhaustive branch coverage.
Without a decision contract, AgentVerity only checks observed diversity. With
one, it reports required, intended, observed, missing, and unknown decisions.
It still does not establish that every boundary was tested or that critical
routes meet their own stability target. Keep labelled correctness cases and
run critical groups separately when their risk warrants a tighter tolerance.

It also does not judge answer correctness, prove safety, store traces, host a
dashboard, or monitor production traffic. Static tools remain useful for
declared branches, route schemas, and expected labels. AgentVerity measures
the decisions a model-backed or black-box target actually returns.

## Documentation

- [Which agents fit, and what the result does not prove](https://github.com/mrwersa/agentverity/blob/main/docs/applicability.md)
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
`agentverity~=0.9.0`. Patch releases preserve the public API.

Apache-2.0. Contributions are welcome through the pull-request workflow.
