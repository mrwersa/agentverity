# AgentVerity design

AgentVerity is a test adequacy tool for agents that choose among named
decisions. Adequacy criteria measure the test suite rather than the program:
statement coverage, branch coverage, and mutation score all ask whether the
tests were worth reading. Decision coverage is the same question for an agent,
and decision stability is the precondition it needs, because an unstable
decision makes any coverage number unrepeatable. The target may be a
deterministic gate or an LLM agent. This document records the technical
boundaries and the reasons behind them.

Both checks are dynamic by necessity. Static analysis reads source, and an LLM
agent's decision is not in the source: it is a string returned from a provider
call. There are no branches to instrument, and stability is a property of the
runtime distribution rather than of any text. That places AgentVerity with
`coverage.py` and mutation testing, not with Ruff or mypy, and it is why a run
costs real agent calls.

## Identity

**Name:** `agentverity`, from "agent" and "verity". The library checks whether
the evidence behind an agent test is stable and covers more than one decision
before that test is treated as a reusable baseline.

**Boundary:** AgentVerity qualifies test evidence. It does not compete with
quality evaluators on metric breadth or with observability systems on trace
storage and dashboards.

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

1. **Verdict-layer oracle selection.** Existing tools repeat tests, report
   uncertainty, and in AgentAssay's case calibrate trial budgets. AgentVerity
   asks whether the chosen categorical decision layer is stable enough that a
   frozen baseline is supportable. The distinctive use is test-strategy
   selection, not awareness that agents are non-deterministic.

2. **Constant-gate-blindness detector.** A gate that returns `"allow"` on 96%
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
varied probe set reaches more than one decision. Optional relations run after
those checks.

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
- **LangGraph:** compiled graph `.invoke(state)` (planned).
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

## 4. Status (2026-07-26)

- M1 core: DONE — observation, meter, blindness, relations, runner, CLI.
- M2 Strands adapter: DONE — adapter written, tested, worked example runs.
- M2 LangGraph adapter: PLANNED.
- M3 agent-specific relations: PLANNED (tool-selection-invariance is built-in;
  more user-extensible relations to follow).
- M4 packaging: DONE — PyPI, release automation, protected main, CI on Python
  3.10 to 3.14.
- M5 real-agent execution: DONE — bounded concurrency, progress, partial
  evidence, versioned JSON.
- M6 evidence-gated snapshots: DONE in v0.4.0.
- M7 delivery-stack handoff: DONE after v0.5.0 — JUnit XML for CI and one
  privacy-minimised OpenTelemetry summary span for an existing monitoring
  pipeline.

## 5. Reporting boundary

AgentVerity interprets one `RunResult`; reporters do not reinterpret it.
Terminal text, versioned JSON, JUnit XML, process exit codes, and OTEL
attributes must agree on these cases:

- incomplete or undecided evidence is unsupported, never green
- blind probes and wholly vacuous relation catalogues are failed test evidence
- stochasticity is oracle guidance, not automatically a defective agent
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
