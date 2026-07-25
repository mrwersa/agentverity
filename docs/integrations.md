# Integrations

AgentVerity owns one step: checking whether an agent and its probe set produce
interpretable test evidence. It should sit beside quality evaluators and
observability platforms, not replace them.

```text
agent or workflow
       |
       v
AgentVerity pre-flight ----> DeepEval / promptfoo / AgentCore Evaluations
       |                                  |
       +---- JUnit XML to CI               +---- quality scores
       |
       +---- OTEL summary span to CloudWatch / Phoenix / LangSmith
```

## Agent interfaces

| Stack | Connection |
|---|---|
| Plain Python | Wrap `fn(str) -> str | dict | Observation` with `from_callable` |
| Strands Agents | Install `agentverity[strands]` and use `from_strands` |
| LangGraph | Wrap `graph.invoke` in a callable that returns an `Observation` |
| Remote agents | Wrap the SDK or HTTP invocation and extract the verdict or tool path |
| AgentCore Runtime | Wrap `invoke_agent_runtime`, then use the existing OTEL pipeline |

The adapter has one job: preserve the observation layer you care about.
`Observation.verdict` protects a routing or policy decision,
`Observation.tools` protects the ordered tool path, and `Observation.text`
protects the final response.

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

AgentVerity maps blind probes and violated relations to failures, incomplete or
undecided evidence to errors, and unexercised relations to skipped tests.
Stochasticity is guidance rather than a failure because it changes the oracle
you should use. It does not by itself prove a defective agent.

The command's exit code carries the same interpretation:

| Code | Meaning |
|---:|---|
| 0 | Evidence is interpretable and no relation was violated |
| 1 | Blind or vacuous probes, a violated relation, or snapshot drift |
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

## AgentCore validation plan

Use the AWS account for a small canary integration after the local path is
green:

1. Enable AgentCore Observability and verify ordinary agent spans in
   CloudWatch.
2. Create a callable around the deployed runtime invocation. Extract a
   categorical verdict or tool path into `Observation`.
3. Start with `precision="cheap"` and six non-sensitive probes. This bounds the
   first validation run while checking the wiring.
4. Call `record_otel_run(result)` inside the configured OTEL process.
5. In CloudWatch, verify one `agentverity.run` span and the
   `agentverity.status`, meter, blindness, and aggregate relation attributes.
6. Move to `balanced` only after confirming call cost and latency.

This validation needs a deployed AgentCore ARN, region, response parser, and
AWS credentials. Keep those deployment details outside the repository.

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
