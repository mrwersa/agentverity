# AgentVerity

> **Check whether an agent's decisions repeat and whether your test cases reach
> more than one path.**

[![PyPI](https://img.shields.io/pypi/v/agentverity.svg)](https://pypi.org/project/agentverity/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20--%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml/badge.svg)](https://github.com/mrwersa/agentverity/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/mrwersa/agentverity/blob/main/LICENSE)

AgentVerity tests agents that choose from a known set of decisions. Consider a
payment-dispute router: it reads a complaint and returns a label such as
`duplicate_charge` or `missing_refund`. That label is the **route**, the next
specialist workflow that receives the case. AgentVerity compares this named
decision, exposed as `verdict`, rather than comparing explanation text.

It also measures an ordered tool path through `Observation.tools`. If the
system produces only open-ended text and has no reviewed decision or trajectory
contract, AgentVerity is not the right evaluator.

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

The four test inputs form the **probe set**: deliberately varied cases used by
the coverage check. The default `balanced` precision sizes the repeat count
automatically.

From a repository checkout, run the same example directly:

```bash
python examples/support_router.py

agentverity run \
  --agent examples/support_router.py:build_agent \
  --inputs examples/support_tickets.txt
```

## Why rerun counts are harder than they look

Start with the rerun. An ad hoc check might pick three repeats, or perhaps five.
Here is roughly what you would write to check whether that is enough. It pairs
separate runs and counts a **flip** whenever the same case reaches two
different decisions:

```python
import math

def looks_stable(agent, cases, k=12, tolerance=0.05):
    flips = trials = 0
    for case in cases:
        answers = [agent(case) for _ in range(k)]
        for i in range(0, k - 1, 2):
            trials += 1
            flips += answers[i] != answers[i + 1]
    p, z = flips / trials, 1.96
    d = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / d
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / d
    return min(1, centre + margin) < tolerance
```

A small helper. Here, `tolerance=0.05` means that you want to certify a route
change rate below 5%. The formula makes a cautious estimate from the sample,
but the yes-or-no return value forces every underpowered result into `False`.
Run it against a router with no randomness in it, using 6 cases at 12 repeats:

```
flip rate 0.0    upper bound 0.096    tolerance 0.05    ->  NOT STABLE
```

The displayed `upper bound` is the highest change rate that this small sample
cannot yet rule out. At 9.6%, it misses the requested 5% threshold. The label is
still wrong: zero flips in 36 pairs means **undecided**, not unstable.
Certification needs 73 pairs with no flips. That arithmetic is easy to miss
when the rerun count is chosen by convention.

AgentVerity preserves that third answer and sizes the repeats before answering
the two adequacy questions:

- **Decision stability:** does the agent reach the same named decision, exposed
  as `verdict`, across repeated runs of one case? It sizes the repeats from the
  tolerance you ask for rather than making you guess.
- **Decision coverage:** do the test cases reach more than one decision?

Coverage is easier to miss. A suite where every case takes the same path scores
6/6 but says nothing about the paths it never touched.

These are two scoped [test adequacy
checks](https://arxiv.org/abs/2212.06118). Like statement coverage, branch
coverage, or mutation score, they measure the test evidence rather than
claiming that the program is correct.

Use it on agents that choose from a known set: routers, approval or policy
gates, and supervisors that select the next agent or tool. The implementation
can be rules-based or LLM-based. It does not replace DeepEval, promptfoo, or
AgentCore Evaluations. It tells you how much evidence their scores rest on.

### Why this needs a runtime check

Static tools can inspect orchestration code, types, allowed route labels, and
expected labels in a test set. A quick rule that warns when six labelled cases
all declare one route is useful. Use it.

A hosted model's route choice still arrives at runtime. Source can list six
allowed routes, but it cannot show which route the model returns for each case
or whether identical reruns disagree. AgentVerity measures those execution
properties. That makes it a dynamic adequacy check, closer to code coverage or
mutation testing than to Ruff or mypy.

## Choosing a testing strategy

The two answers point at different tools. A stable, well-covered decision can
use a reviewed baseline and ordinary comparison. A variable one needs repeated
rates read against measured noise.

**Metamorphic testing** is the third option, for when no single expected answer
fits. It changes an input in a controlled way and checks the relationship
between the two decisions: rephrasing a duplicate-charge complaint should not
change its route. AgentVerity ships relation checks for this, but treats them
as one option rather than the default, because a relation can pass on every
case while every case takes the same path.

The bundled relation runner is a convenience, not the differentiator. Keep an
existing relation implementation if it already works. AgentVerity's role is to
check whether stability and coverage make that result interpretable.

## What it catches

| Condition | Why the green result is unsafe | AgentVerity's action |
|---|---|---|
| **Poor decision coverage (`blind`)** | One verdict dominates, so relations can pass without crossing a decision boundary | Add test inputs that exercise other decisions |
| **Unstable decision (`stochastic`)** | Identical reruns disagree, so zero-tolerance checks confuse noise with regressions | Use repeated rates against measured noise |
| **Stable, varied decision** | The decision is suitable for a reviewed reference | Prefer an evidence-gated snapshot or targeted relations |
| **Relation tested nothing (`vacuous`)** | The transform returned the original input, so no comparison happened | Report `n/a`, never a false pass |

The terminal report calls these the **verdict-stochasticity meter** and the
**constant-gate-blindness detector**. They are the underlying stability and
coverage checks. The stability check reports `deterministic`, `stochastic`, or
`undecided` from a Wilson interval, so a small sample cannot fake certainty.
Stability is not correctness, so snapshots still require explicit human
approval.

## The evidence gate

AgentVerity will not freeze a baseline it cannot justify. A **baseline** is the
reviewed set of expected decisions that future versions are compared against.
The accompanying
[`payment_dispute_gate.py`](https://github.com/mrwersa/agentverity/blob/main/examples/payment_dispute_gate.py)
runs the same router against two probe sets:

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

A snapshot is the versioned file that stores the approved baseline for later
comparison.

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

## Where AgentVerity fits

AgentVerity is an **evaluation runner**, not middleware in the serving path. It
makes isolated calls with reviewed test inputs so it can compare repeated
decisions and the decisions reached across the set. A quality evaluator makes
its own calls against reviewed labels. Your release policy combines the two
results.

```text
CONTROLLED EVALUATION PATH

reviewed test inputs
       |
       +-- labelled calls -----> agent or workflow -----> quality evaluator
       |                                                "Was it correct?"
       |
       +-- isolated repeats ---> agent or workflow -----> AgentVerity
                                                        "Is the evidence
                                                         stable and varied?"
                                                                |
                         quality result + qualified evidence ----+
                                                                v
                                                       release policy
                                                  snapshot / deploy decision

DEPLOYED TARGET

customer request ------------> deployed agent ------------> response
reviewed canary input --------^
       (controlled evaluation, never sampled customer traffic)
```

The target can be a local callable, a staging endpoint, or the deployed agent.
When a release check or scheduled canary targets the deployed endpoint, it
still uses controlled inputs rather than sampled customer requests.

### When to run it

Evaluation platforms often split work into
[offline and online](https://docs.langchain.com/langsmith/evaluation-concepts)
runs. AgentVerity belongs in the controlled part of either workflow:

| Lifecycle phase | Recommended use | Typical budget |
|---|---|---|
| Experimentation | Diagnose a local agent while the decision contract is changing | `precision="cheap"`, a handful of cases |
| Pull request | Exercise a fast, representative subset | `precision="cheap"`, local or stubbed target |
| Release gate | Qualify the full reviewed set before admitting a snapshot or deploying | `precision="balanced"`, full probe set |
| Operations | Run a scheduled synthetic canary against the deployed endpoint | Measured cadence, never per request |

Budget the run before wiring it into delivery. On a managed runtime a remote
trial can take far longer than model execution: in the [measured AgentCore
canary](https://github.com/mrwersa/agentverity/blob/main/examples/production_stack/RESULTS.md)
the median runtime execution was 0.58s while the isolated caller's median
end-to-end time was 5.87s. Six cases at `cheap` precision planned 78 calls.
Twenty would plan 100 because the repeat planner uses evidence across the whole
probe set.
At `balanced` precision, twenty cases plan 180 calls. Inspect the printed call
count and measured latency before choosing the cadence.

### Where the result goes

```text
AgentVerity RunResult
       |
       +---- terminal text ----> developer or reviewer
       +---- versioned JSON ---> automation or retained evidence
       +---- JUnit XML --------> GitHub / Jenkins / GitLab / Azure DevOps
       +---- OTEL span --------> CloudWatch / Phoenix / LangSmith / OTLP
```

AgentVerity is deliberately small at these boundaries. The core has no runtime
dependencies, hosted account, or dashboard to adopt.

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
- `1`: poor probe coverage (`blind`), a relation that tested nothing
  (`vacuous`), a relation violation, or snapshot drift
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

Run this at the release gate or as a scheduled canary, per
[Where AgentVerity fits](#where-agentverity-fits) above.

[Integration guide and AgentCore validation result](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md)

### Production-stack example

The repository contains a payment-dispute router built with Strands and Amazon
Bedrock. DeepEval checks labelled route quality. AgentVerity decides whether
that score rests on stable, varied decisions. The same agent runs on AgentCore
Runtime, with operational evidence in CloudWatch.

![A real AgentCore canary passes DeepEval quality, AgentVerity evidence, and cloud health checks before its baseline is admitted](https://raw.githubusercontent.com/mrwersa/agentverity/main/docs/assets/agentcore-release-gate.svg)

The redacted London canary made 78 isolated calls through Nova Micro. All six
reviewed routes were correct, no flips appeared in 36 repeat pairs, all six
routes were reached, and CloudWatch recorded no errors or throttles. The first
run had been stable but only 5/6 correct. The example
now refuses snapshot admission unless quality and evidence both pass.

```bash
pip install -e ".[showcase]"

python examples/production_stack/evaluate_stack.py \
  --target local \
  --precision cheap
```

The live run prints its planned call count before starting. It is separate
from the zero-credential quickstart so a first run remains fast and
reproducible.

[Run or deploy the production-stack example](https://github.com/mrwersa/agentverity/tree/main/examples/production_stack) ·
[Read the measured canary result](https://github.com/mrwersa/agentverity/blob/main/examples/production_stack/RESULTS.md)

## Multi-agent systems

Measure the whole pipeline and its critical steps separately. In
[`bugfix_pipeline.py`](https://github.com/mrwersa/agentverity/blob/main/examples/bugfix_pipeline.py)
the whole supervisor is stochastic while its triage step is stable and blind.
Either scope alone misses one failure. Use `layer="tools"` when the ordered
handoff path is the contract.

[Multi-agent and step-level integration guidance](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md#multi-agent-systems)

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

`k=` and `epsilon=` remain exact overrides. `k` sets repeats per input.
`epsilon` sets how much verdict flakiness the stability check will tolerate.
Repeated calls for one input stay sequential, while distinct inputs can run
concurrently. Recorded provider failures mark evidence incomplete and never
become passing verdicts.

## Examples

Each one belongs to a phase in [Where AgentVerity fits](#where-agentverity-fits).

| Example | Phase | What it shows |
|---|---|---|
| [`support_router.py`](https://github.com/mrwersa/agentverity/blob/main/examples/support_router.py) | Experimentation | The smallest blind agent, no credentials |
| [`bugfix_pipeline.py`](https://github.com/mrwersa/agentverity/blob/main/examples/bugfix_pipeline.py) | Experimentation | One step and a whole pipeline, measured separately |
| [`payment_dispute_gate.py`](https://github.com/mrwersa/agentverity/blob/main/examples/payment_dispute_gate.py) | Release gate | A green evaluator whose narrow baseline is refused, then admitted once the inputs widen |
| [`production_stack/`](https://github.com/mrwersa/agentverity/tree/main/examples/production_stack) | Release gate and nightly canary | The same gate on live Strands, Bedrock, AgentCore, DeepEval, and CI |
| [`otel_monitoring.py`](https://github.com/mrwersa/agentverity/blob/main/examples/otel_monitoring.py) | Operational steady state | One diagnostic span through OTEL |
| [`strands_example.py`](https://github.com/mrwersa/agentverity/blob/main/examples/strands_example.py) | Any | The optional Strands adapter |

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

- a judge of whether an answer is correct
- a benchmark or leaderboard
- a trace store, dashboard, or production monitoring service
- a claim that relation checks or Wilson intervals are new

The distinctive part is the ordering: check decision stability and probe
coverage before interpreting the ordinary test result.

## Documentation

- [Integrations and AgentCore validation](https://github.com/mrwersa/agentverity/blob/main/docs/integrations.md)
- [API guide](https://github.com/mrwersa/agentverity/blob/main/docs/api.md)
- [Design decisions](https://github.com/mrwersa/agentverity/blob/main/DESIGN.md)
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
generated README diagnostic.

## Status and licence

Alpha. Pin a minor series for production use, for example
`agentverity~=0.8.0`. Patch releases preserve its public API. See the
[stability policy](STABILITY.md) for the pre-1.0 guarantees and exit criteria.

Apache-2.0. Contributions are welcome through the pull-request workflow.
