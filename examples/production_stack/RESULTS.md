# Production-stack canary

This example was exercised end to end on 25 July 2026 in AWS London
(`eu-west-2`). It is a systems integration check, not a model benchmark.

## What ran

The same six reviewed payment-dispute cases were sent through:

1. a Strands routing agent using Amazon Nova Micro
2. DeepEval exact match against the reviewed route
3. AgentVerity at `cheap` precision, with 12 isolated repeats per case
4. Amazon Bedrock AgentCore Runtime, with a fresh session for every call
5. AgentCore Observability and CloudWatch for runtime logs and metrics

DeepEval and AgentVerity ran outside the serving path. They belong in CI,
pre-deployment checks, or scheduled canaries. The deployed runtime contained
only the application and its runtime dependencies.

## Result

| Check | Local Bedrock | AgentCore Runtime |
|---|---:|---:|
| Reviewed routes correct | 6/6 | 6/6 |
| Verdict flips | 0/36 pairs | 0/36 pairs |
| Distinct routes reached | 6/6 | 6/6 |
| Baseline | admitted | admitted |
| Successful model calls | 78/78 | 78/78 |
| End-to-end p50 | 0.498 s | 5.869 s |
| End-to-end p95 | 0.799 s | 7.591 s |

AgentCore's internal runtime execution was much shorter than the full remote
round trip, with p50 0.576 s and p95 1.489 s. The canary intentionally created
and stopped a fresh session for every trial. Its end-to-end latency therefore
characterises this isolated evaluation path, not a normal serving session.

CloudWatch recorded 78 successful invocations for the final canary, with no
errors or throttles. The release decision required both route correctness and
interpretable AgentVerity evidence.

## The useful failure

The first live run scored 5/6 on route quality while producing a stable,
non-blind verdict distribution. That exposed an integration error in the
example: a stable snapshot could be admitted after a failed quality check.

The evaluation path now stops before snapshot creation unless both checks
pass. Stability cannot override correctness. AgentVerity qualifies the
evidence behind a quality result. It does not replace that result.

## Cost and scope

The canary used Nova Micro, `cheap` precision, four-way concurrency across
distinct cases, 60-second runtime idling, and immediate session cleanup.
Model, runtime, and log usage were deliberately small. Exact cost should be
read from the account bill rather than inferred from list prices.

AgentCore Memory, Gateway, Identity, and managed Evaluations were not enabled.
They do not test the thesis of this stateless router. Runtime and Observability
were enough to verify remote execution, state isolation, operational health,
and trace correlation.

The committed
[`agentcore-canary.json`](results/agentcore-canary.json) is a redacted extract
of the final evidence. It contains no account identifier, runtime ARN, prompt,
output, credential, session identifier, or trace identifier. The dashboard
asset is regenerated from that file:

```bash
python scripts/render_agentcore_evidence.py
```

## Declared-contract canary

The v0.9 decision-contract path was exercised separately on 28 July 2026. The
old AgentCore runtime had already been removed, so this run used the same
Strands router and Nova Micro model directly through Bedrock in London rather
than redeploying infrastructure for a library-side change.

The 78-call run passed all three release conditions:

- DeepEval scored 6/6 reviewed routes
- AgentVerity observed 0 changes in 36 non-overlapping pairs
- all six required routes were intended and observed, with no unknown or
  missing critical decision

Median end-to-end latency was 0.545 seconds and p95 was 1.160 seconds. The
redacted [`bedrock-contract-canary.json`](results/bedrock-contract-canary.json)
records the aggregate result without prompts, outputs, account identifiers, or
credentials.
