# Integrations

AgentVerity owns one step: checking whether repeated decisions are stable and
whether the test inputs exercise more than one decision. Together, those
deliberately selected inputs form the probe set. AgentVerity should sit beside
quality evaluators and observability platforms, not replace them.

```text
agent or workflow
       |
       +---- AgentVerity ----> JUnit XML to CI
       |         |
       |         +---- OTEL summary span
       |
       +---- DeepEval / promptfoo / AgentCore Evaluations
                            |
                            +---- quality scores

release decision = quality result + qualified evidence
```

## Agent interfaces

| Stack | Connection |
|---|---|
| Plain Python | Wrap `fn(str) -> str | dict | Observation` with `from_callable` |
| Strands Agents | Use `from_strands_factory` for isolated trials. Use `from_strands` only when one continuing session is the subject of the test |
| LangGraph | Wrap `graph.invoke` in a callable that returns an `Observation` |
| Remote agents | Wrap the SDK or HTTP invocation and extract the verdict or tool path |
| AgentCore Runtime | Wrap `invoke_agent_runtime`, then use the existing OTEL pipeline |

The adapter has one job: preserve the observation layer you care about.
`Observation.verdict` protects a routing or policy decision,
`Observation.tools` protects the ordered tool path, and `Observation.text`
protects the final response.

Strands agents retain conversation history between calls. AgentVerity's
identical reruns must begin from equivalent context, so the recommended adapter
accepts a factory:

```python
from agentverity.adapters.strands import from_strands_factory

agent = from_strands_factory(build_fresh_agent)
```

The factory may reuse a stateless model client, but it must return a new agent
session. Reusing one stateful instance can turn conversation accumulation into
apparent verdict instability.

## Multi-agent systems

Choose the scope that owns the decision you need to protect. This mirrors the
split enterprise platforms use between
[system and process evaluation](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators):

- **System level:** wrap the whole pipeline to measure its end-to-end decision.
- **Step level:** wrap one agent to measure that step independently.

Run both for critical paths. The bundled
[`bugfix_pipeline.py`](../examples/bugfix_pipeline.py) produces different
diagnoses at the two scopes. Its supervisor pipeline is verdict-stochastic,
while the triage step inside it is verdict-deterministic and blind. Measuring
only the pipeline exposes instability but misses the blind step. Measuring
only triage misses the stochastic supervisor.

Use `Observation.tools` or `layer="tools"` when the ordered handoff path is
the contract. A pipeline can preserve its final verdict while changing which
agent or tool acts along the way.

## CI reporting

Text is for a person, JSON is for code, and JUnit is for the test-report
surface your delivery platform already has:

```bash
agentverity run \
  --agent examples/support_router.py:build_agent \
  --inputs examples/support_tickets.txt \
  --format junit \
  --output agentverity.xml
```

AgentVerity maps poor probe coverage (`blind`) and violated relations to
failures, incomplete or undecided evidence to errors, and unexercised relations
to skipped tests. An unstable decision (`stochastic`) is guidance rather than a
failure because it changes the test strategy. It does not by itself prove a
defective agent.

The command's exit code carries the same interpretation:

| Code | Meaning |
|---:|---|
| 0 | Evidence is interpretable and no relation was violated |
| 1 | Poor probe coverage, a relation that tested nothing, a violated relation, or snapshot drift |
| 2 | Incomplete or undecided evidence, or unsupported snapshot admission |

## OpenTelemetry monitoring

Install the optional API bridge:

```bash
pip install "agentverity[otel]"
```

Then attach one aggregate diagnostic span to the host's configured tracer:

```python
from agentverity import record_otel_run

result = run(agent, inputs=canary_probes)
record_otel_run(result)
```

`record_otel_run` emits low-cardinality `agentverity.*` attributes. It excludes
raw prompts, outputs, fingerprints, relation names, and exception messages.
That keeps the summary suitable for dashboards and alerts without pretending
that telemetry is a secure store.

The same bridge works with:

- **Amazon Bedrock AgentCore Observability and CloudWatch**, through the AWS
  Distro for OpenTelemetry already used by AgentCore.
- **Phoenix**, which accepts OTLP traces and can run locally or as a service.
- **LangSmith**, which accepts traces from a standard OpenTelemetry client.
- **Any OTLP collector**, including collectors that fan out to more than one
  backend.

AgentVerity is not an online evaluator. Do not repeat each customer request 26
times. Run it in CI, before deployment, or as a scheduled canary over a
reviewed probe set, then monitor the resulting summary.

## Capture the evidence gate

The payment-dispute demo prepares the exact outputs needed for CI and
observability:

```bash
python examples/payment_dispute_gate.py \
  --output-dir /tmp/agentverity-payment-demo
```

Both probe sets score 6/6. The `narrow-*.xml` reports show a passing
exact-match evaluator beside a failed probe-coverage case, and no snapshot is
admitted. The `repaired-*.xml` reports are green, and
`repaired-snapshot.json` records the reviewed reference.

Inside a configured OTEL process, add `--otel` to emit:

- `agentverity.payment_dispute.narrow` with `agentverity.status=blind`
- `agentverity.payment_dispute.repaired` with
  `agentverity.status=deterministic`

This makes a useful before-and-after trace without inventing an AgentVerity
dashboard. The same spans can be viewed in CloudWatch, Phoenix, or another
OTLP-compatible interface.

For a CI view, run **Evidence gate demo** from the repository's Actions tab.
The manual workflow feeds both JUnit files into its Actions run summary.
Capture the expanded `Narrow probes - baseline refused` and
`Repaired probes - baseline admitted` reports side by side. The workflow pins
the third-party reporter to an immutable commit.

## Live production-stack example

[`examples/production_stack/`](../examples/production_stack/) implements the
validation path below rather than leaving it as an architecture sketch:

- Strands runs a structured-output payment-dispute routing agent on Bedrock.
- DeepEval's non-LLM exact-match metric checks the selected route against
  reviewed labels.
- AgentVerity measures route stability and decision coverage before admitting
  a snapshot.
- The same entry point deploys on AgentCore Runtime.
- A remote canary uses a fresh AgentCore session for every repeated trial and
  can emit one aggregate AgentVerity span into the configured OTEL pipeline.

The example deliberately keeps quality and evidence as separate results. A
quality score says whether the selected routes match their labels. AgentVerity
says whether repeated decisions and the chosen inputs support treating that
score as a reusable baseline.

## AgentCore validation result

The production-stack example was run through a real AgentCore Runtime in
London. DeepEval and AgentVerity remained outside the serving process, as they
would in CI or a scheduled canary:

```text
reviewed cases
      |
      +---- DeepEval: is each route correct?
      |
      +---- AgentVerity: is that result stable and non-blind?
                         |
                         v
                admit or refuse baseline
      |
      v
AgentCore Runtime ----> CloudWatch operational evidence
```

The final canary produced 6/6 correct routes, 0/36 verdict flips, six distinct
routes, 78 successful invocations, and no errors or throttles. Every repeat
used a fresh AgentCore session, which was stopped after the response.

The first live run was more informative. It was stable and non-blind but
scored only 5/6 on route quality. The example now blocks snapshot creation
unless both quality and evidence pass. This is the boundary between a quality
evaluator and AgentVerity in executable form.

See the [method and measured result](../examples/production_stack/RESULTS.md).
Account identifiers, runtime ARNs, prompts, outputs, sessions, and trace
identifiers are not committed.

AWS documents AgentCore telemetry as OpenTelemetry-compatible and exposes it
through CloudWatch:

- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
- [AgentCore observability setup](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html)

## Using AgentVerity with DeepEval

DeepEval answers whether outputs satisfy quality metrics. AgentVerity answers
whether the verdict layer and probe set make those scores interpretable.
Use both in sequence:

```python
preflight = run(agent, inputs=probes, relations=[])
if preflight.status not in {"deterministic", "stochastic"}:
    raise RuntimeError(preflight.headline)

# Run DeepEval, promptfoo, or AgentCore Evaluations here.
```

For a verdict-stochastic agent, retain repeated quality evaluation and compare
rates against measured noise. For a deterministic, non-blind verdict with
reviewed references, AgentVerity can admit a snapshot before the broader
quality suite runs.

Further connection points:

- [DeepEval CI/CD testing](https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd)
- [Phoenix OTLP tracing](https://arize.com/docs/phoenix/tracing/concepts-tracing/how-does-tracing-work)
- [LangSmith OpenTelemetry tracing](https://docs.langchain.com/langsmith/trace-with-opentelemetry)
