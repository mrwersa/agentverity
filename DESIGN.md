# AgentVerity design

AgentVerity is a test adequacy tool for agents that choose among named
decisions. Adequacy criteria measure the test suite rather than the program:
statement coverage, branch coverage, and mutation score all ask whether the
tests were worth reading. AgentVerity asks the same kind of question for an
agent. Its diversity check is a lower bound rather than an equivalent of
branch coverage. It detects a probe set that collapses onto one highly
dominant observed decision. An optional decision contract separately checks
whether every required label was intended and observed. Neither check knows
whether every important boundary within a decision was exercised. Decision
stability is a
precondition for that dynamic signal because unstable decisions make the
observed distribution unrepeatable. The target may be a deterministic gate or
an LLM agent. This document records the technical boundaries and the reasons
behind them.

Both checks are dynamic by design. Static analysis can inspect orchestration
branches, route schemas, and expected labels. For a source-available
deterministic gate, a static proof may even be cheaper and stronger than a
sampled run. A hosted model's route choice is different: source can declare
the allowed routes but cannot establish which route the provider returns for
each input or whether identical reruns disagree. AgentVerity treats either
target as a callable and measures those execution properties through one
interface. That places it with dynamic adequacy tools such as `coverage.py`
and mutation testing rather than with Ruff or mypy, and it is why model-backed
runs cost real agent calls.

## Identity

**Name:** `agentverity`, from "agent" and "verity". The library checks whether
the evidence behind an agent test is stable and covers more than one decision
before that test is treated as a reusable baseline.

**Boundary:** AgentVerity qualifies test evidence. It does not compete with
quality evaluators on metric breadth or with observability systems on trace
storage and dashboards. It qualifies one observed run, not the correctness,
safety, or complete route coverage of the agent.

## Related approaches (reviewed 2026-07-06)

| Tool | Non-determinism | Relation checks | Suite-quality diagnostic | License |
|---|---|---|---|---|
| DeepEval | Repeated runs | No | No | Apache-2.0 |
| promptfoo | Repeated runs | No | Red-team coverage | MIT |
| agentevals (LangChain) | No | No | No | MIT |
| CheckList | Assumes deterministic | Invariance and directional checks | No | MIT |
| AgentAssay | Wilson intervals | Yes | Mutation testing | AGPL |
| agentrial | Wilson intervals | No | No | MIT |
| **AgentVerity** | **Tri-state stability check** | **Optional** | **Decision stability and coverage** | **Apache-2.0** |

**Four design choices:**

1. **Decision-layer baseline admission.** Existing tools repeat tests, report
   uncertainty, and in AgentAssay's case calibrate trial budgets. AgentVerity
   asks whether the chosen categorical decision layer is stable enough that a
   frozen baseline is supportable. The distinctive use is test-strategy
   selection, not awareness that agents are non-deterministic.

2. **Decision-collapse diagnostic.** A gate that returns `"allow"` on 96%
   of a probe set can satisfy many invariance checks without exercising a
   boundary. The detector flags the pass as potentially vacuous. This is a
   suite-power warning, not a correctness judgement.

3. **Evidence-gated snapshots.** A baseline is admitted only when the chosen
   observation layer is deterministic at epsilon, the probe set is non-blind,
   the run is complete, and a human approves the outputs as correct. The same
   diagnostics run again before comparison.

4. **Suite-quality diagnostic framing.** Not "run tests and report pass/fail"
   but "tell you if your tests are meaningful before you trust them." The
   report leads with the diagnostics, then per-relation results.

**Established foundations:**
- **Metamorphic relations** (Chen et al. 1998): assert a law between two runs
  (transform input, check the outputs relate correctly). They support testing
  when no complete golden output is available.
- **Semantic-invariance transforms** (CheckList / LLMORPH): normalisation,
  casing, whitespace.
- **Wilson CIs** (AgentAssay, agentrial use them for pass-rate CIs; we use
  them for verdict-stability certification — same primitive, different use).

---

## 1. What it is

AgentVerity runs two diagnostics before a green result becomes a reusable
baseline. The stability check asks whether a categorical decision changes
across isolated identical reruns. The coverage check asks whether a deliberately
varied probe set avoids collapsing onto one highly dominant decision. It is a
minimum diversity and skew check, not a percentage of a declared decision
universe. Optional relations run after those checks.

## 2. Architecture (three layers)

```text
reviewed test inputs
        |
        v
adapter: target call -> Observation(text, verdict, tools)
        |
        v
runner
  +-- execution.py    bounded calls, progress, explicit failures
  +-- meter.py        decision stability
  +-- blindness.py    decision coverage
  +-- relations.py    optional relation checks
        |
        v
RunResult
  +-- reporting.py    terminal, JSON, JUnit, and OTEL handoff
  +-- snapshot.py     reviewed baseline admission and comparison
```

### Adapter layer (`agentverity/adapters/`)
Turns a real agent into a uniform `run(input) -> Observation`. `Observation`
carries what relations can assert over:
- `text`   — final response string
- `verdict`— an optional extracted categorical decision
- `tools`  — the ordered list of tool names the agent called (the trajectory)
- `raw`    — the underlying result object, for custom relations

Adapters:
- **Strands:** `Agent(prompt) -> AgentResult`. Adapter calls the agent, reads
  the final message text and the tool-use blocks for `tools`.
- **LangGraph:** compiled graph `.invoke(state)`. Fresh thread per call by
  default; `from_langgraph_thread` for when the conversation is under test.
- **callable:** any `fn(input) -> str | dict | Observation` for non-library agents.
Adapters are optional imports. The core installs without any agent library.

### Core (`agentverity/`)
- `relations.py` — Relation = (name, type, transform, check). Built-in
  catalogue: normalisation, casing, whitespace invariance (text-level);
  tool-selection-invariance (agent-specific).
- `meter.py` — verdict-stochasticity meter. Tri-state call with Wilson CI.
- `blindness.py` — constant-gate-blindness detector. Skew scan + warning.
- `runner.py` — orchestrates meter -> blindness -> relations. Returns RunResult.
- `snapshot.py` — admits and checks reviewed frozen baselines.
- `execution.py` — overlaps distinct inputs while serialising one probe series.
- `reporting.py` — emits versioned JSON without raw probe text.
- `cli.py` — `run`, `snapshot`, and `check`.

## 3. Scope discipline (what it is NOT)

- Not a benchmark, not a leaderboard, not an LLM-judge scorer.
- Not a replacement for labelled correctness tests or model-based judges.
- Not tied to any provider, agent framework, or application-specific gate.
- No dependency on an external research codebase.

The intended target exposes a finite categorical decision or a reviewed
ordered tool path, can be reset to equivalent starting state between trials,
and has a deliberately varied probe set. A step inside a multi-agent system is
a valid target when that step owns a release contract. Open-ended answer or
trajectory quality is outside scope unless the system also exposes a reviewed
decision layer. See `docs/applicability.md`.

## 4. Status (2026-08-02)

- M1 core: DONE — observation, meter, blindness, relations, runner, CLI.
- M2 Strands adapter: DONE — adapter written, tested, worked example runs.
- M2 LangGraph adapter: DONE in v0.14.0. A compiled graph is read for its
  message list, its tool calls, and a decision under any of the usual state
  keys. Every call gets a fresh `thread_id`, because a graph compiled with a
  checkpointer would otherwise turn repeated trials into successive turns of
  one conversation, and every interval assumes independence.
- M3 agent-specific relations: PARTIAL. Tool-selection-invariance is built in.
  A public registration protocol for domain relations remains evidence-led
  future work rather than a release commitment.
- M4 packaging: DONE — PyPI, release automation, protected main, CI on Python
  3.10 to 3.14.
- M5 real-agent execution: DONE — bounded concurrency, progress, partial
  evidence, versioned JSON.
- M6 evidence-gated snapshots: DONE in v0.4.0.
- M7 delivery-stack handoff: DONE after v0.5.0 — JUnit XML for CI and one
  privacy-minimised OpenTelemetry summary span for an existing monitoring
  pipeline.
- M8 declared decision contracts: DONE in v0.9.0. The optional contract
  preserves the skew warning while separately reporting required, intended,
  observed, missing, critical, and unknown decisions. Correctness remains the
  responsibility of labelled assertions or another evaluator.
- M9 per-route evidence policy: DONE in v0.10.0. Per-route
  intervals name concentrated decision changes. Optional stability targets
  allocate repeats by route, can be priced before execution, and become
  explicit release conditions. Risk labels and numerical targets remain
  separate declarations.
- M10 semantic breadth diagnostics: DONE in v0.11.0. Relation
  coverage names intended routes that no transform actually changed, while
  `minimum_cases` enforces a separately reviewed case-count policy without
  pretending to infer semantic diversity.
- M11 evidence interchange: DONE in v0.12.0. The versioned
  schema keeps ordered individual decisions, route identity, errors,
  isolation, and provenance so an existing harness can supply the evidence
  without another target run. Aggregate-only exports are refused.
- M12 evaluator bridges: DONE in v0.12.0. Promptfoo has a
  direct JSON importer and DeepEval has a zero-dependency shared-test-case
  bridge. Both preserve correctness as the evaluator's responsibility.
- M13 temporal evidence comparison: DONE in v0.13.0. Two independently
  collected windows can be compared by route conclusion, decision reach,
  flip-pair structure, isolation, and non-volatile provenance.
- M14 LangGraph adapter: DONE in v0.14.0. Fresh thread IDs preserve trial
  isolation by default, while an explicit shared-thread mode keeps
  conversation state available when state is the subject of the test.
- M15 external-system evidence: DONE after v0.14.0. The AgentKit study records
  4,380 model calls across three models and twenty externally authored tools.
  It demonstrates why stability, correctness, and authority must remain
  separate claims.

## 5. Reporting boundary

AgentVerity interprets one `RunResult`; reporters do not reinterpret it.
Terminal text, versioned JSON, JUnit XML, process exit codes, and OTEL
attributes must agree on these cases:

- incomplete or undecided evidence is unsupported, never green
- blind probes and wholly vacuous relation catalogues are failed test evidence
- stochasticity is test-strategy guidance, not automatically a defective agent
- violated relations fail
- transforms that changed no input are skipped, not passed

JUnit is a delivery format rather than a new testing model. OpenTelemetry is a
monitoring handoff rather than a hosted AgentVerity service.

## 6. Telemetry privacy

The OTEL bridge emits aggregate, low-cardinality `agentverity.*` attributes.
It excludes raw prompts, outputs, fingerprints, majority-verdict values,
relation names, and exception messages. This makes the summary useful for
dashboards without turning the span into a second report store.

The bridge creates one span after a diagnostic run. It does not repeat
production requests, instrument model internals, or replace the host's trace
collector. When called inside an active trace, the span follows the current
OpenTelemetry context.

## ADR 1: observed route reach counts cases, not primaries and not occurrences

**Status.** Accepted 2026-08-03. Supersedes the primary-only reading in
`assess_decision_coverage`.

**Context.** The AgentKit run reached `approve` on 98 of 146 repeats and the
report said the route was never observed. `assess_decision_coverage` read one
primary result per case for route counts and required-route coverage, and used
the full repeat set only to detect out-of-contract labels. The docstring gives
the reason, and the instinct is right: counting every repeat would make one
case look like a hundred test cases. It was implemented too narrowly, so a
route the agent demonstrably reached could be reported as missing.

**Decision.** Three quantities, distinct in the model and in every report.

- **intended** — reviewed cases written for the route. Unchanged, from
  `suite.expected`.
- **observed** — the number of **distinct cases** that returned the route on
  **any** repeat. Not primaries only, and not occurrences.
- **admissible** — route evidence that also meets its declared stability
  target. Reported by the meter, not by this function.

Required-route coverage is computed from observed. A route reached only on a
repeat is observed. A route reached ninety-eight times within one case counts
once.

**Consequences.** `missing_observed` shrinks for suites whose agents reach a
route inconsistently, which is the intended correction. It does not shrink to
the point of certifying anything: observed says the route was exercised, and
admissible is the separate question of whether the evidence about it is
stable enough to trust. One chance occurrence therefore cannot make unstable
evidence look adequately covered, because the two are reported separately and
the gate reads both.

`observed_counts` keeps its primary-result meaning for continuity and is now
named as such in the report. `observed_case_counts` carries the new quantity.

**Alternatives rejected.** Counting occurrences, which inflates one case into
many and would make a repeat budget look like breadth. Leaving primary-only,
which is the defect. Introducing a threshold such as "reached on at least k
repeats", which invents a policy nobody declared and would need its own
justification.

## ADR 2: the absence of a decision is typed, not a sentinel

**Status.** Accepted 2026-08-03. Roadmap item 2.

**Context.** `Observation.key("verdict")` returns the verdict, or the raw text
when no verdict is set. For a categorical layer that is the wrong fallback:
two differently worded refusals compare unequal and count as a changed
decision, so the meter measures wording rather than choice.

The AgentKit collector shows what callers do about it today. It sets
`verdict = names[0] if names else "no_tool_selected"`, with a comment
explaining that leaving the verdict unset would compare refusals by their
prose. That workaround is correct and it should not be the caller's job.

It also shows the trap in the obvious repair. `no_tool_selected` appears 176
times across the nova run, and it covers more than one event: a model that
refused, a model that answered in prose, and a model whose tool call could not
be read all arrive at the same label. On the "Convert my WETH back into ETH"
probe it appears 80 times out of 146, which a naive reading would score as a
strongly stable decision. Nothing decided anything.

At least six distinct events currently reach `verdict=None`: open-ended
output, a refusal, no tool selected, extraction failure, a malformed provider
response, and a runtime failure. A single `UNSET` sentinel would make all six
one stable category, which is worse than the text fallback it replaced,
because a run of extraction failures would certify perfectly.

**Decision.** Two shapes, not one sentinel.

- `Decision(label)` — the agent chose, and the label is the choice.
- `NoDecision(reason)` — the agent did not choose, and the reason says why.

`reason` is a closed vocabulary, versioned with the evidence schema:

| reason | meaning | effect on evidence |
|---|---|---|
| `no_tool_selected` | contract asked for a tool, none was called | categorical, in-contract only if declared |
| `refused` | the agent declined, deliberately | categorical, in-contract only if declared |
| `open_ended` | the layer is categorical, the answer was not | not comparable, excluded from pairs |
| `extraction_failed` | the adapter could not read a decision | **incomplete** |
| `malformed_response` | the provider returned something unusable | **incomplete** |
| `runtime_error` | the call itself failed | **incomplete** |

The split in the last column is the point. The first three are things the
agent did, and a contract may legitimately declare them as allowed outcomes.
The last three are things the harness could not do, and they make the evidence
incomplete rather than becoming a category that can look stable.

Two `NoDecision` values compare equal when their reasons are equal, so two
reworded refusals are one decision again. A `NoDecision` never compares equal
to a `Decision`.

**Consequences.** The evidence schema and the snapshot format both gain a
version, because a stored `"no_tool_selected"` string is ambiguous between a
label the caller invented and the reason this ADR defines. Reading old
evidence keeps the string as `Decision("no_tool_selected")`, which is what it
meant when it was written, and the migration note says so.

Adapters stop needing the workaround. An adapter that cannot read a decision
returns `NoDecision("extraction_failed")` and the run reports incomplete
evidence, rather than the caller inventing a label to avoid a text comparison.

**Alternatives rejected.** A single `UNSET` sentinel, which merges six events
and can certify a broken harness. Keeping the text fallback, which is the
defect. Letting each adapter invent its own label, which is the status quo and
puts a statistical decision in a place nobody reviews.

## 7. Candidate direction after independent use

The collection, import, admission, and temporal-comparison loop is complete.
Do not add another named adapter until an external user demonstrates a format
the generic schema cannot express.

The AgentKit evidence exposed two narrower design questions. A missing tool
choice currently needs an application adapter to name it, otherwise raw text
can become the comparison key. The contract and route table also use different
definitions of whether a decision was reached. Resolve either only through an
explicit schema and migration, not by silently changing a published report.

Correctness scoring, full trajectory evaluation, red-teaming, hosted
dashboards, and production request interception remain outside the project.
