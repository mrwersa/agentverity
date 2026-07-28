# AgentVerity

> **Conservative baseline admission for AI agents with bounded decisions.**

[![PyPI](https://img.shields.io/pypi/v/agentverity.svg)](https://pypi.org/project/agentverity/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20--%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml/badge.svg)](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml)
[![Coverage: 90%+](https://img.shields.io/badge/coverage-90%25%2B-brightgreen.svg)](#development)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/mrwersa/agentverity/blob/main/LICENSE)

## The 60-second problem

Consider a **routing workflow**: a model classifies each payment dispute and
hands it to one of six specialist queues.
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

The contract check passes, but the decision switches between `card_security`
and `merchant_dispute` in 8 of 13 paired reruns.

## Why you should care

- Those labels send work to different queues, controls, and owners.
- A moving reference makes later regression failures noisy and hard to trust.
- One pooled score hides which route is moving.
- Zero observed changes do not prove a quiet route is stable when the sample
  is too small.

AgentVerity names the unstable route and leaves the five underpowered routes
`undecided`. It will not freeze this run as a baseline.

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

The last command performs arithmetic over saved decisions. It makes no model
or provider calls.

Already using [DeepEval](https://deepeval.com/)? Pass the same precomputed
`LLMTestCase` objects to `evidence_from_deepeval`. Any harness can use the
[small neutral evidence format](https://github.com/mrwersa/agentverity/blob/main/docs/imported-evidence.md).

Keep your existing evaluator for correctness and trajectory quality.
AgentVerity qualifies whether its repeated decision evidence is suitable for a
regression baseline.

## Where to integrate it

AgentVerity is a test and release step, not serving-path middleware.

| Stage | Use it for |
|---|---|
| Local development | Diagnose a moving or one-route-only test set |
| Pull request | Qualify a candidate baseline and publish JUnit |
| Pre-release | Refuse unstable, incomplete, or underpowered evidence |
| Scheduled canary | Recheck reviewed synthetic cases and emit OpenTelemetry |

One real integration combines DeepEval quality, AgentVerity evidence, and
Amazon AgentCore health before admitting a baseline:

![A real AgentCore canary combines DeepEval quality, AgentVerity evidence, and cloud health before baseline admission](https://raw.githubusercontent.com/mrwersa/agentverity/main/docs/assets/agentcore-release-gate.svg)

Never repeat live customer requests. Use reviewed synthetic cases in CI,
before release, or on a schedule.

## The developer workflow

1. **Evaluate quality.** Keep Promptfoo, DeepEval, or your current assertions.
2. **Reuse the outputs.** Import repeated decisions into AgentVerity without
   calling the model again.
3. **Repair the evidence.** Fix moving routes, add missing cases, or collect
   the reruns needed for an honest conclusion.
4. **Freeze a baseline.** A human approves the reference only after the
   evidence gate admits it.
5. **Catch regressions.** `agentverity check` requalifies the current run
   before comparing it with that baseline.

The import command diagnoses decisions already collected by another
evaluator. The `snapshot` and `check` commands below provide the same
admission policy when AgentVerity calls your agent directly.

## What it checks

| Check | Developer question |
|---|---|
| Decision stability | Does the same case keep reaching the same decision? |
| Observed spread | Did all test inputs collapse onto one decision? |
| Declared coverage | Were all required decisions and critical routes represented and returned? |
| Route evidence | Which route moves, and which quiet routes still lack enough reruns? |
| Relation coverage | Did an input transformation genuinely exercise each route, or was it a no-op? |

It keeps three outcomes separate:

- **stable enough** for the declared tolerance
- **unstable** above that tolerance
- **undecided** because the run did not collect enough evidence

## Is it for my agent?

Use it when:

- the component chooses from named routes, approvals, policies, tools, or
  hand-offs
- repeated runs can start from equivalent isolated state
- you can write deliberately varied cases for the decisions that matter

It fits the agent patterns whose value is a named choice rather than open
prose:

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

AgentVerity sizes the run from your tolerance, uses non-overlapping pairs, and
keeps three answers: stable enough, unstable, or undecided. The default
`balanced` setting uses a 5% tolerance.

A small pytest loop can collect calls. The library packages the harder policy:
evidence sizing, route-specific targets, and one consistent decision across
text, JSON, JUnit, telemetry, and snapshots.

[Read the executable arithmetic and design](https://github.com/mrwersa/agentverity/blob/main/docs/decision-stability.md).

## The evidence gate

The evidence gate refuses to save a baseline until:

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

## Measured production example

The optional production example combines a Strands routing agent on Amazon
Bedrock, DeepEval route-quality checks, AgentVerity, AgentCore Runtime, and
CloudWatch.

At its declared 10% canary tolerance, the London run recorded 6/6 correct
routes, no changes across 36 repeat pairs, all six routes reached, and 78
successful cloud calls with no errors or throttles. An earlier run was stable
but only 5/6 correct. The release policy therefore requires both quality and
evidence rather than treating either tool as sufficient.

This is deployment proof, not an AWS requirement. The zero-dependency callable
works with any stack.

[Run the production example](https://github.com/mrwersa/agentverity/tree/main/examples/production_stack) ·
[Read the measured result](https://github.com/mrwersa/agentverity/blob/main/examples/production_stack/RESULTS.md)

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
- [Reuse Promptfoo, DeepEval, or generic evidence without duplicate calls](https://github.com/mrwersa/agentverity/blob/main/docs/imported-evidence.md)
- [Integrations and AgentCore validation](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md)
- [API guide](https://github.com/mrwersa/agentverity/blob/main/docs/api.md)
- [API stability and path to 1.0](https://github.com/mrwersa/agentverity/blob/main/STABILITY.md)
- [Security and data handling](https://github.com/mrwersa/agentverity/blob/main/SECURITY.md)

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
`agentverity~=0.12.0`. Patch releases preserve the public API.

Apache-2.0. Contributions are welcome through the pull-request workflow.
