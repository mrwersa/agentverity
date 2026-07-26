# Production-stack example

This example keeps quality evaluation and evidence qualification separate. The
two runners make their own calls to the same target:

```text
reviewed payment cases
   +-- one labelled call per case --> Strands routing agent --> DeepEval
   |                                                          route quality
   |
   +-- isolated repeated calls ----> Strands routing agent --> AgentVerity
                                                              stability + coverage
                                                                      |
                                                        aggregate OTEL span
                                                                      |
                                             AgentCore Observability / CloudWatch

quality passed + evidence qualified + human approval --> admit baseline
```

Here, the baseline is the reviewed set of expected route decisions used to
detect changes in later versions. AgentVerity saves an approved baseline as a
versioned snapshot file.

It uses real model calls. The repository's
[`payment_dispute_gate.py`](../payment_dispute_gate.py) remains the fast,
zero-credential version of the same evidence-gate idea.

[Read the measured London canary result](RESULTS.md), including the first
stable-but-wrong run that led to the fail-fast quality gate.

## 1. Install

From the repository root:

```bash
python -m pip install -e ".[showcase]"
```

Configure AWS credentials and enable model access. The example pins
the low-cost `amazon.nova-micro-v1:0` model by default. Set
`BEDROCK_MODEL_ID` to use another Bedrock model that supports structured
output:

```bash
export AWS_REGION=eu-west-2
aws sts get-caller-identity
```

## 2. Run locally

Start with the cheap 10% stability threshold. The script prints the planned
model-call count before making a request:

```bash
python examples/production_stack/evaluate_stack.py \
  --target local \
  --precision cheap \
  --output-dir /tmp/agentverity-live
```

DeepEval applies its deterministic exact-match metric to six reviewed routing
labels. AgentVerity then repeats those six cases from clean Strands sessions,
checks whether the route is stable, and verifies that the cases cross a
decision boundary. A failed labelled check stops before the repeat budget is
spent. Both checks must pass before the script admits a reference. Stable but
incorrect routing is still a failed run. The canary permits four concurrent
calls by default. Pass `--max-workers 1` for a sequential run.

The script does not save a snapshot by default. Review the outputs before
explicitly admitting the baseline:

```bash
python examples/production_stack/evaluate_stack.py \
  --target local \
  --precision cheap \
  --output-dir /tmp/agentverity-live \
  --accept-reference
```

## 3. Deploy on AgentCore

The runtime entry point is `agentcore_app.py`. AWS's
[current AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-get-started-cli.html)
uses a project scaffold rather than accepting an arbitrary entry-point file.
Install the CLI, create a memory-free Strands project, then replace its
generated app. Run these commands from the AgentVerity repository root:

```bash
npm install -g @aws/agentcore

agentcore create \
  --name PaymentTriage \
  --framework Strands \
  --protocol HTTP \
  --model-provider Bedrock \
  --memory none \
  --build CodeZip

cp examples/production_stack/agentcore_app.py \
  PaymentTriage/app/PaymentTriage/main.py
cp examples/production_stack/payment_agent.py \
  PaymentTriage/app/PaymentTriage/payment_agent.py

cd PaymentTriage/app/PaymentTriage
uv add "bedrock-agentcore>=1.18,<2" "pydantic>=2,<3" \
  "strands-agents>=1.0" "aws-opentelemetry-distro>=0.10"
cd ../..

agentcore dev
```

`agentcore dev` opens AWS's local inspector. Once the route response looks
right, stop the development server and deploy from the generated project:

```bash
agentcore deploy --dry-run
agentcore deploy
agentcore status
```

Keep memory disabled for this routing service. AgentVerity's repeated trials
must not inherit conversation history.

Set the deployed ARN, then run the same evaluation against Runtime:

```bash
cd ..
export AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:..."

python examples/production_stack/evaluate_stack.py \
  --target agentcore \
  --precision cheap \
  --output-dir /tmp/agentverity-agentcore \
  --otel
```

The remote adapter creates a fresh `runtimeSessionId` for every call. Reusing a
session would make later trials depend on earlier tickets and invalidate the
stability measurement. It stops each session after reading the response, which
avoids paying for an idle tail between canary trials.

The output directory contains a JUnit report and `stack-evidence.json`. The
JSON records labelled-route accuracy, AgentVerity's aggregate evidence, and
end-to-end p50 and p95 latency without storing ticket text or model responses.

## What each component answers

| Component | Question |
|---|---|
| Strands + Bedrock | Can the agent produce a structured payment route? |
| DeepEval | Does each sampled route match its reviewed label? |
| AgentVerity | Are route decisions stable, and do the cases exercise several routes? |
| Evidence gate | Is the result strong enough to freeze as a reviewed reference? |
| AgentCore + OTEL | Can the deployed canary be traced and operated in the existing stack? |

AgentVerity runs in CI, before deployment, or as a scheduled canary. It should
not repeat every live customer request.
