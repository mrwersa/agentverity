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

## AgentCore validation plan

Use the AWS account for a small canary integration after the local path is
green:

1. Enable AgentCore Observability and verify ordinary agent spans in
   CloudWatch.
2. Replace the demo's local router with a callable around
   `invoke_agent_runtime`. Keep the two synthetic probe sets unchanged and
   extract the returned route into `Observation.verdict`.
3. Start with `precision="cheap"`. This bounds the first live run while
   checking the wiring.
4. Run the narrow and repaired suites with `--otel` inside the configured OTEL
   process.
5. In CloudWatch, select each AgentVerity span and verify the status, meter,
   blindness, and aggregate relation attributes.
6. Capture the two real span-detail views, redacting account identifiers and
   runtime ARNs. Use those views for a labelled before-and-after image.
7. Move to `balanced` only after confirming call cost and latency.

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
