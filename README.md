# AgentVerity

> **Your agent test passed. Would it pass again?**

[![PyPI](https://img.shields.io/pypi/v/agentverity.svg)](https://pypi.org/project/agentverity/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20--%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml/badge.svg)](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml)
[![Coverage: 90%+](https://img.shields.io/badge/coverage-90%25%2B-brightgreen.svg)](#development)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/mrwersa/agentverity/blob/main/LICENSE)

A Python library and CLI that reruns the decisions your agent makes and reports
whether they are repeatable enough, and varied enough, to trust as a
**regression baseline**: the reviewed run you save as expected behaviour and
compare future releases against. It can read runs another evaluator already
collected, so you do not pay for the same calls twice.

## The 60-second problem

Consider a [**routing workflow**](https://www.anthropic.com/engineering/building-effective-agents):
a model classifies each payment dispute and directs it to one of six specialist
queues.
[Promptfoo](https://www.promptfoo.dev/) runs six cases 26 times. Its configured
quality checks accept either fraud queue for one ambiguous card-security case.
All **156/156 assertions pass**.

Would you save that run as the expected behaviour for future releases?

AgentVerity reuses the same Promptfoo export and finds this:

```text
4. STABILITY BY ROUTE
   route              cases  pairs  flips  95% CI            result
   card_security          1     13      8  [0.355, 0.823]    stochastic
   cash_withdrawal        1     13      0  [0.000, 0.228]    undecided
   duplicate_charge       1     13      0  [0.000, 0.228]    undecided
   ...
   flip pairs:
     card_security <-> merchant_dispute  x8
```

Three words there are the tool's own. A **flip** is a decision that changed
between two runs of the same case, **stochastic** means the route moves more
than your tolerance allows, and **undecided** means the run did not collect
enough evidence to say either way.

The contract check passes, but the decision switches between `card_security`
and `merchant_dispute` in 8 of 13 paired reruns. Those labels send work to
different queues, controls, and owners, and a moving reference makes every
later regression failure noisy. One pooled score would have hidden which route
was moving, and the five quiet routes have too few reruns to call stable.

So AgentVerity names the unstable route, leaves the five underpowered routes
`undecided`, and refuses to freeze this run as a baseline.

## Try it without model calls

The repository includes that recorded Promptfoo run:

```bash
git clone --depth 1 https://github.com/mrwersa/agentverity.git
cd agentverity
python -m pip install agentverity
agentverity assess \
  --promptfoo examples/promptfoo_bridge/results.json \
  --suite examples/payment_decisions.json
```

That last command performs arithmetic over saved decisions. It makes no model
or provider calls.

Already using [DeepEval](https://deepeval.com/)? Pass the same precomputed
`LLMTestCase` objects to `evidence_from_deepeval`. Using neither, but holding a
log with one line per run? Name the two fields and import it:

```bash
agentverity assess --jsonl runs.jsonl \
  --input-path probe.text --decision-path result.route
```

Order matters there, and the
[small neutral evidence format](https://github.com/mrwersa/agentverity/blob/main/docs/imported-evidence.md)
says why: runs are paired in the order the file gives them, so a log sorted by
decision reports a stability the run never had.

If you would rather AgentVerity make the calls itself, install the adapter for
your framework. The core has no agent library as a dependency, so this is the
only place one is needed:

```bash
pip install "agentverity[strands]"     # Strands Agents
pip install "agentverity[langgraph]"   # LangGraph
```

## What it checks

| Check | Developer question |
|---|---|
| Decision stability | Does the same case keep reaching the same decision? |
| Observed spread | Did all test inputs collapse onto one decision? |
| Declared coverage | Were all required decisions and critical routes represented and returned? |
| Route evidence | Which route moves, and which quiet routes still lack enough reruns? |
| Relation coverage | Did an input transformation genuinely exercise each route, or was it a no-op? |

It keeps three outcomes separate:

- `deterministic`, stable enough for the declared tolerance
- `stochastic`, moving more than that tolerance allows
- `undecided`, because the run did not collect enough evidence either way

Once you have two runs, `agentverity compare-evidence before.json after.json`
answers the question a single report cannot: **what moved?** It reports which
per-route intervals shifted, which decisions appeared or disappeared, and how
the flip pairs changed, so a release that is still green for a different reason
than last week does not pass unnoticed.

## Measured on real systems

Two runs, answering different questions. The first shows the analysis survives
a real deployment. The second shows what the analysis is actually for, and it
exists because of a limitation the first one had.

### Does it work in a real pipeline?

A Strands routing agent on Amazon Bedrock, with DeepEval route-quality checks,
AgentVerity, AgentCore Runtime, and CloudWatch. The London run recorded 6/6
correct routes, no changes across 36 repeat pairs, all six routes reached, and
78 successful cloud calls with no errors or throttles.

Read the caveat, because it is the honest part. Those 36 pairs are six routes
at six pairs each, and six pairs bound a route at about 39%. **That run is
systems-integration evidence, not per-route certification.** An earlier
attempt was repeatable but only 5/6 correct, which is why the release policy
needs both quality and evidence rather than treating either as sufficient.

![A real AgentCore canary combines DeepEval quality, a pooled AgentVerity evidence rule, and cloud health](https://raw.githubusercontent.com/mrwersa/agentverity/main/docs/assets/agentcore-release-gate.svg)

That gate is pooled on purpose. Declare route-specific targets when admission
needs a per-route claim.

[Run it](https://github.com/mrwersa/agentverity/tree/main/examples/production_stack) ·
[the measured result](https://github.com/mrwersa/agentverity/blob/main/examples/production_stack/RESULTS.md)

### What does per-route analysis actually find?

4,380 real calls against the twenty tools a published agent exposes, across
three models, for 0.70 USD. Enough repeats this time to certify a route rather
than only reach it.

```
model                                           correct  always the same
amazon/nova-micro-v1                               4/10             1/10
openai/gpt-4o-mini                                 7/10             8/10
mistralai/mistral-small-3.2-24b-instruct           5/10            10/10
```

`mistral-small` returned the same tool on every probe and was correct on half
of them. `gpt-4o-mini` is unstable on two routes and correct on seven. **Rank
on stability alone and the worse agent wins**, which is why this library says
repeatability is not correctness and why that sentence needs numbers.

The two unstable routes are `transfer` and `approve`, two of the three the
suite marks critical. Pooled, the same evidence reads 8.5% and does not say
which routes carry it.

Running `assess` on that evidence still returns **NOT TRUSTWORTHY**, and the
reason changed for the better. It used to be a disagreement inside the report:
the contract counted the first answer per case while the route table counted
every repeat, so `approve` came back 98 times and was reported as never
reached. Coverage now counts the distinct cases that reached a decision on any
repeat, so `approve` is observed. Three routes remain genuinely unreached, and
the refusal is about them rather than about an inconsistency.

[The evidence, and the commands to re-run it for nothing](https://github.com/mrwersa/agentverity/tree/main/docs/evidence/agentkit)

Never repeat live customer requests. Reviewed synthetic cases only, in CI,
before release, or on a schedule.

## Where it sits beside your evaluator

Keep [Promptfoo](https://www.promptfoo.dev/), DeepEval, or your own assertions
to decide whether each answer is *correct*. AgentVerity reuses those same
results to find unstable routes, missing decisions, and runs too small to
support a reliable baseline.

| What you run | Question it answers |
|---|---|
| Promptfoo, DeepEval, your assertions | Was this answer acceptable? |
| **AgentVerity** | **Are the repeated answers stable and covered enough to save as expected behaviour?** |
| LangSmith, AgentCore, your observability | What happened during this run, and in production? |
| [AgentMandate](https://github.com/mrwersa/agentmandate) | What is this agent permitted to do, and did this release widen it? |

Those are different layers of evidence, and one does not substitute for
another:

| Layer | Example question |
|---|---|
| Outcome | Was the refund recorded in the case system? |
| Trajectory | Which tools or agents acted, and in what order? |
| Decision | Did the workflow choose refund, review, or deny? |

An evaluation framework can grade the first two. AgentVerity qualifies the
repeatability and declared coverage of the bounded decision, in the step
between a green quality run and saving that run as a reference.

It is a test and release step, not serving-path middleware:

| Stage | Use it for |
|---|---|
| Local development | Diagnose a moving or one-route-only test set |
| Pull request | Qualify a candidate baseline and publish JUnit |
| Pre-release | Refuse unstable, incomplete, or underpowered evidence |
| Scheduled canary | Recheck reviewed synthetic cases and emit OpenTelemetry |

[Where it belongs in the full test and release pipeline](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md),
including the layers it does not own, and
[**agent-release-gate**](https://github.com/mrwersa/agent-release-gate), which
runs AgentVerity beside authority analysis on one agent, offline.

## Is it for my agent?

Use it when:

- the component chooses from named routes, approvals, policies, tools, or
  hand-offs
- repeated runs can start from equivalent isolated state
- you can write deliberately varied cases for the decisions that matter

It fits the [agent workflow patterns](https://www.anthropic.com/engineering/building-effective-agents)
whose value is a named choice rather than open prose:

| Pattern | The decision under test |
|---|---|
| **Routing** | Which specialist path or queue an input is classified into |
| **Orchestrator-workers** | Which worker the orchestrator dispatches to next |
| **Evaluator-optimiser** | Whether the evaluator accepts, revises, or rejects |
| **Tool use** | Which tool is selected, and the ordered tool path taken |
| **Multi-agent supervisor** | Which agent receives the handoff |
| **Guardrail or policy gate** | Approve, review, escalate, or deny |

Concrete examples: support and payment routing, fraud triage, incident
dispatch, approval flows, and bounded tool selection.

Use another evaluator for open-ended chat, RAG quality, generated content, or
coding-agent output. If such a system also emits a reviewed route or approval,
AgentVerity can qualify that decision layer.

[Check applicability and exact limits](https://github.com/mrwersa/agentverity/blob/main/docs/applicability.md).

## Why rerun counts are harder than they look

Picking three or five reruns by convention is guesswork:

- 36 paired reruns with no changes only bound the change rate below 9.6%.
- A claim below 5% needs 73 zero-change pairs.
- A short quiet run is therefore `undecided`, not proven stable.

Promptfoo and DeepEval both let you choose the count, and promptfoo has
allowed a per-test count since 0.121.18. A knob is still a knob: choosing
five is guesswork until a tolerance sizes it.

AgentVerity sizes the run from your tolerance, uses non-overlapping pairs, and
keeps three answers: `deterministic`, `stochastic`, or `undecided`. The default
`balanced` setting uses a 5% tolerance.

You can also stop early without spoiling the answer. `agentverity run
--sequential` fixes the checkpoints before collection starts and stops at the
first one that decides. An agent flipping on a third of its pairs finishes in
33% to 60% fewer calls; a stable one saves little, because the planner already
sizes the ordinary path well. It is for not paying to confirm what a run has
already shown.

Recomputing the interval after every pair and stopping when it looks good is
optional stopping, and the interval stops meaning what it says. So the call
comes from the checkpoint and the report says which count decided.

A small pytest loop can collect calls. The library packages the harder policy:
evidence sizing, route-specific targets, and one consistent decision across
text, JSON, JUnit, telemetry, and snapshots.

[Read the executable arithmetic and design](https://github.com/mrwersa/agentverity/blob/main/docs/decision-stability.md).

## The evidence gate

`assess` diagnoses decisions another evaluator already collected. `snapshot`
and `check` apply the same admission policy when AgentVerity calls your agent
itself. Either way the gate refuses to save a baseline until:

- calls complete
- decisions are stable enough
- the cases reach the required decisions
- a person approves the reference outputs as correct

The bundled payment-dispute example runs two test sets:

```bash
python examples/payment_dispute_gate.py
```

| Probe set | Exact-match | Verdict stability | Declared coverage | Baseline |
|---|---|---|---|---|
| Narrow, 6 duplicate-charge cases | ✅ 6/6 | ✅ verdict-deterministic | ❌ 1/6 required routes | ❌ REFUSED |
| Repaired, 6 dispute categories | ✅ 6/6 | ✅ verdict-deterministic | ✅ 6/6 required routes | ✅ ADMITTED |

Both score 6/6. The narrow set is a valid unit test for one route, but it is
not a system-wide baseline. The repaired set reaches all six required routes
and can be admitted.

Before spending model calls, inspect the zero-change evidence budget:

```bash
agentverity plan --suite examples/route_stability_plan.json
```

Then create the reviewed baseline:

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

The contract can also declare stricter stability targets for critical routes
and minimum case counts. Repeats support a stability claim. Distinct reviewed
cases support breadth. AgentVerity keeps those two claims separate.

## What it does not prove

`TRUSTWORTHY` means the supplied cases produced stable, non-collapsed evidence
at the declared tolerance and satisfied any declared decision contract.

It does **not** prove:

- that each decision was correct or safe
- that every code branch or behavioural boundary was tested
- that several cases are semantically diverse
- that an open-ended answer is high quality

It also does not store traces, host a dashboard, or monitor production
traffic. Static coverage, Promptfoo or DeepEval quality checks, and production
observability remain separate parts of the stack.

## Go deeper

- [Which agents fit, and what the result does not prove](https://github.com/mrwersa/agentverity/blob/main/docs/applicability.md)
- [Why arbitrary rerun counts fail](https://github.com/mrwersa/agentverity/blob/main/docs/decision-stability.md)
- [How to read and budget per-route evidence](https://github.com/mrwersa/agentverity/blob/main/docs/route-evidence.md)
- [Write a relation the built-in catalogue cannot express](https://github.com/mrwersa/agentverity/blob/main/docs/custom-relations.md)
- [Reuse Promptfoo, DeepEval, or generic evidence without duplicate calls](https://github.com/mrwersa/agentverity/blob/main/docs/imported-evidence.md)
- [Qualify a categorical LLM judge without confusing stability with validity](https://github.com/mrwersa/agentverity/blob/main/docs/evaluator-stability.md)
- [Integrations and AgentCore validation](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md)
- [Cross-version compatibility audit](https://github.com/mrwersa/agentverity/blob/main/docs/compatibility-audit.md)
- [Runnable examples, and what each one shows](https://github.com/mrwersa/agentverity/blob/main/examples/README.md)
- [API guide](https://github.com/mrwersa/agentverity/blob/main/docs/api.md)
- [API stability and path to 1.0](https://github.com/mrwersa/agentverity/blob/main/STABILITY.md)
- [Security and data handling](https://github.com/mrwersa/agentverity/blob/main/SECURITY.md)
- [Agentic-AI evaluation landscape, positioning, and 12-month strategy](https://github.com/mrwersa/agentverity/blob/main/docs/agentic-ai-landscape.md)
- [Join the design-partner pilot](https://github.com/mrwersa/agentverity/blob/main/docs/design-partners.md)
- [Reproduce the statistical method validation and dependence stress test](https://github.com/mrwersa/agentverity/blob/main/docs/method-validation.md)

Read the design story:
[Introducing AgentVerity: What Does a Green Agent Test Prove?](https://mrwersa.medium.com/introducing-agentverity-what-does-a-green-agent-test-prove-fa6ebbfda2d3)

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
`agentverity~=0.19.0`. Patch releases preserve the public API.

Apache-2.0. Contributions are welcome through the pull-request workflow.
