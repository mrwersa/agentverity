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
| `open_ended` | the layer is categorical, the answer was not | **refused**, stability is undefined |
| `extraction_failed` | the adapter could not read a decision | **incomplete** |
| `malformed_response` | the provider returned something unusable | **incomplete** |
| `runtime_error` | the call itself failed | **incomplete** |

The split in the last column is the point. The first two are things the agent
did, and a contract may legitimately declare them as allowed outcomes. The
last three are things the harness could not do, and they make the evidence
incomplete rather than becoming a category that can look stable.

`open_ended` is neither, and is refused rather than filtered. Dropping those
runs and pairing what remains while keeping the original repeat count would
report stability across reruns that did not decide anything. A conditional
rate is a defensible thing to want and it needs excluded counts, a stated
interpretation, and reporting across every surface, so it is a later decision
rather than a silent one.

Two `NoDecision` values compare equal when their reasons are equal, so two
reworded refusals are one decision again. A `NoDecision` never compares equal
to a `Decision`.

**Consequences.** The evidence schema and the snapshot format both gain a
version, because a stored `"no_tool_selected"` string is ambiguous between a
label the caller invented and the reason this ADR defines. Reading old
evidence keeps the string as `Decision("no_tool_selected")`, which is what it
meant when it was written, and the migration note says so.

Adapters stop needing the workaround for the meter, which is where the
workaround was invented. An adapter that cannot read a decision returns
`NoDecision("extraction_failed")` and the meter refuses to score the series
rather than counting repeated failures as a stable decision.

Every path that cannot honestly account for a typed outcome raises the same
`OutcomeNotScorable`, which subclasses `ValueError` so existing handlers keep
working. One condition, one exception. Review found a `TypeError` in one path
and a `ValueError` in another, and that was not a considered distinction, it
was two local consistencies that disagreed.

Evidence carries the reason from `agentverity.evidence/v1`. A decision is
written as a plain string and a no-decision as an object, which is one reading
rule and the smallest form that stays unambiguous. Tagging decisions too would
triple a repeat-heavy file to record a distinction nothing acts on.
Comparison normalises the two, because a bare `"refund"` and a tagged one are
the same decision and reporting a flip between them would be this ADR's own
defect at a different seam.

There is exactly one canonical comparison, `comparison_key`, and every semantic
consumer uses it: the pooled meter, per-route stratification, blindness, and
the invariant relations. Contract coverage uses `decision_label`, the inverse,
because a contract is written in plain labels and a `Decision` satisfies one.
Storage keeps the original representation, which is why neither lives in
`Observation.key`: that feeds reporting and snapshot storage, and snapshots
refuse a tagged value, so normalising there would refuse every ordinary string
verdict.

Coverage takes a declared no-decision outcome and refuses an undeclared one,
which ADR 3 covers. One consumer is not there yet and fails closed until it is:
the snapshot format has no shape for a typed outcome, so writing one into a
snapshot is refused rather than flattened.

**Alternatives rejected.** A single `UNSET` sentinel, which merges six events
and can certify a broken harness. Keeping the text fallback, which is the
defect. Letting each adapter invent its own label, which is the status quo and
puts a statistical decision in a place nobody reviews.

## ADR 3: a contract declares no-decision outcomes in their own field

**Status.** Accepted 2026-08-03. Completes roadmap item 2.

**Context.** ADR 2 says `refused` and `no_tool_selected` are things the agent
did, and that a contract may declare them as allowed outcomes. Nothing
implemented that, so coverage refused any `NoDecision` outright. An agent that
legitimately declines could collect evidence and be scored for stability, and
then could not be assessed against a contract at all. Half a product.

The obvious shortcut is to put `"refused"` in `allowed` beside the ordinary
labels. That destroys the distinction ADR 2 exists for: `Decision("refused")`
and `NoDecision("refused")` are different outcomes, and a single `allowed` set
of strings cannot say which one a contract meant.

**Decision.** A separate field.

```python
DecisionContract(
    allowed=frozenset({"refund", "escalate"}),
    allowed_no_decisions=frozenset({"refused"}),
)
```

Only the two declarable reasons may appear there. `extraction_failed`,
`malformed_response` and `runtime_error` are harness failures and can never be
declared allowed, because a contract cannot make a broken harness acceptable.
`open_ended` cannot either, because categorical stability is undefined over it.

An undeclared `NoDecision` keeps the existing refusal, so silence still fails
closed rather than being read as permission.

**Consequences.** `allowed_no_decisions` is additive and optional, so it is
not a schema change: every suite written before it parses correctly without
it. See `STABILITY.md` for when a version does move.

Coverage counts a declared no-decision outcome under its reason, never under a
label. `refused` in `allowed_no_decisions` and `refused` in `allowed` are two
different declarations, and a suite may hold both without ambiguity.

**Alternatives rejected.** Putting the reason in `allowed`, which merges the
two shapes. A prefixed string such as `"<no-decision:refused>"` as the counting
key, which the first implementation used: it leaked a synthetic label into the
public `allowed` set, had to be stripped again on write, and would have made a
real label sharing the prefix vanish on round trip. The counting key is a tuple
instead, which cannot collide with a label and never needs stripping, and it is
rendered for a report rather than escaping. Making `allowed` hold typed objects, which does not
survive JSON without inventing the tagged form anyway, and would force every
existing suite through a migration for a field most of them will never use.

## ADR 4: a snapshot stores a typed outcome the way evidence does

**Status.** Accepted 2026-08-03. Completes roadmap item 2.

**Context.** ADR 2 gave a run a typed outcome and ADR 3 let a contract declare
one. A snapshot could hold neither: `create_snapshot` serialises through
`json_value(..., strict=True)`, which refuses a `Decision` or a `NoDecision`
outright. So an agent whose contract legitimately allows a refusal could be
measured and assessed, and then could not be baselined. The feature worked
right up to the point of using it.

**Decision.** The snapshot format carries an outcome exactly as evidence does:
a decision is a plain string, and a no-decision is
`{"kind": "no_decision", "reason": ...}`. One encoding across both stored
formats, so a reader learns the rule once.

Only a **declarable** reason can reach a snapshot, and not because the
serialiser filters it. A run holding an incomplete outcome is refused by the
meter long before admission, and an `open_ended` one is refused there too. By
the time a snapshot is created, the only no-decision that can survive is one a
contract declared. The serialiser still refuses the others rather than relying
on that, because a guarantee that depends on an upstream check holding is not a
guarantee.

A stored outcome is validated as it is read, against the same vocabulary the
writer can produce. Evidence already did this and a snapshot did not, so a
hand-edited file carried garbage into a comparison, and two differently
malformed probes compared equal to each other because an absent reason became
the same `None` in both.

Comparison normalises through `comparison_key`, so a snapshot storing
`"refund"` matches a current run returning `Decision("refund")`. Without it, an
adapter adopting the types would fail every baseline it had written before
adopting them, which is the string-versus-typed defect one more layer out.

**Consequences.** `agentverity.snapshot/v3`. Precisely: a v2 reader does not
reject a stored no-decision, it loads the object and then compares it unequal
to every string a current run produces, so every probe reads as changed. A
silent misread rather than a refusal, which is worse and still meets the bar
`STABILITY.md` sets: the reader cannot correctly interpret the file. No v2 reader is kept: there are no known external
consumers, and the one-version rule stands.

**Alternatives rejected.** Flattening a no-decision to its reason string, which
loses the distinction from a decision with the same label and would silently
turn a refusal into a route. Storing the tagged form for decisions too, which
evidence already rejected for tripling a file to record a distinction nothing
acts on. Leaving snapshots unable to hold one, which is the status quo and
makes ADR 3 half a feature.

## ADR 5: shared-state evidence is refused a baseline, and a baseline records what it was admitted under

**Status.** Accepted 2026-08-03. Roadmap item 4, the policy half.

**Context.** Every interval this library reports assumes independent trials.
`EvidenceSet.isolation` has recorded whether they were since v0.12.0, and
`shared-session` already produces a caveat saying in plain words that "repeats
are not independent and the interval is narrower than the evidence supports".

That caveat had no consequence. `_require_snapshot_evidence` refuses
incomplete, underpowered, stochastic, blind, uncovered and contract-failing
evidence, eight conditions in all, and never looked at isolation. Verified
before writing this: six probes, eighty identical repeats each, isolation
`shared-session`, and `create_snapshot` admits it while the caveat sits in
`result.caveats` describing exactly why the number that admitted it is wrong.

The second half is worse and is not in the roadmap text. **A snapshot recorded
no isolation at all.** So once admitted, a baseline carried no trace of how its
evidence was collected, and a later `check` comparing against it could not know
it was matching against something certified from a shared session. The
provenance died at the admission boundary.

**Decision.** A stated policy at the one boundary where the number becomes a
commitment:

- `fresh-session`, `fresh-instance` — **admit.** The caller asserts trials were
  separated and the interval means what it says.
- `unknown` — **admit with the caveat travelling.** The evidence may be fine;
  nothing establishes that it is.
- `shared-session` — **refused.** The caller has stated the trials were not
  independent. Certifying a baseline from them publishes an interval the
  evidence does not support, and doing so *after* printing a caveat saying so
  is the library disagreeing with itself.

A snapshot stores the isolation it was admitted under, and `check` reports when
a later run was collected under weaker isolation than the baseline was. Same
principle as ADR 4: the stored artefact carries what the evidence knew.

**Consequences.** `agentverity.snapshot/v4`. A v3 reader cannot correctly
interpret a v4 file, because the field it needs to apply the policy is absent
and there is no safe default: reading a missing isolation as `fresh-*` claims
provenance nobody asserted, and reading it as `shared-session` refuses
baselines that were legitimately admitted. That is exactly the bar
`STABILITY.md` sets for moving a number.

**The policy is inert for live runs today, and that is worth saying rather
than leaving to be discovered.** The runner never sets isolation, so a
baseline and a later check both read `unknown` and nothing is refused. It
bites on imported evidence, which is the only place isolation is recorded.
The other half of roadmap item 4, per-trial execution identifiers and adapter
assertions about what was actually fresh, is what makes a live run able to
claim `fresh-instance` honestly. Until then this change buys the boundary and
the storage, not enforcement on the path most callers use.

`unknown` remains the default of all three importers, so the strict half of
this policy is avoidable by not saying. That is deliberate and worth stating
rather than hiding: the policy refuses a **claim** of shared state, not an
unstated one. Inferring the unstated case is rejected below. The honest reading
is that this converts a caveat into a refusal for callers who tell the truth,
and it is paired with strengthening provenance so that telling the truth
becomes the easy path.

**Alternatives rejected.**

*Refusing `unknown` too.* It is the default everywhere, including all three
importers, so this would refuse most imported evidence on the day it shipped
and teach callers to write `fresh-session` to make the error go away. A policy
that manufactures false assertions is worse than one with a caveat.

*A flag to override the refusal.* The deliberate shared-thread path
(`from_langgraph_thread`) exists to measure a conversation, and multi-turn
stability is out of scope by a separate decision. An override would make the
policy advisory, and an advisory policy is the caveat that already existed.

*Inferring contamination from behaviour.* Inputs that grow across trials are
often legitimate test inputs, and verdicts settling partway through a run is
not evidence of anything. Both reject valid evidence, and neither absence
establishes independence. Strengthen what is asserted; do not guess at what is
not.

## ADR 6: an adapter declares the isolation it actually produced

**Status.** Accepted 2026-08-03. Roadmap item 4, the provenance half.

**Context.** ADR 5 made isolation decide whether evidence may certify a
baseline, and then admitted in its own consequences that the policy was inert
for live runs: the runner set nothing, so a baseline and its later check both
read `unknown` and nothing was ever refused. Only imported evidence could
state what it did, which is the path fewest callers use.

The knowledge was already there and was being thrown away. `from_langgraph`
generates a fresh `thread_id` per call, `from_strands_factory` builds a new
agent per trial, `from_langgraph_thread` deliberately shares one thread, and
`from_strands` deliberately shares one instance. Each of those is a mechanical
fact about what the adapter did, not a guess about what the target does.

**Decision.** An agent callable may carry a declared isolation, and `run`
reads it into `RunResult.isolation`, where ADR 5's policy already applies.
`from_callable` declares nothing, because a plain function tells the library
nothing about what happens inside it, and `unknown` is the honest answer.

**The declaration is computed from what the adapter did, not from which
function was called.** `from_langgraph` respects a caller-supplied
`thread_id`, which is the documented way to opt out, and in that case every
repeat runs on one thread. Verified before writing this: three calls produce
three thread ids by default and one pinned id when the caller supplies one. A
declaration keyed on the function name would have claimed `fresh-session`
exactly where the caller had turned it off, which is worse than the `unknown`
it replaced, because the policy would then certify a baseline on the strength
of a false assertion.

**A reshaping wrapper carries a declaration rather than dropping it.**
`from_callable` converts a return value into an `Observation` and changes
nothing about how trials are separated, so an underlying statement survives
it. This is not a detail: the CLI loads every agent through `from_callable`,
so without it the policy applied to the Python API and stopped at the command
line, which is the path the production-stack example documents. A plain
function still declares nothing, because it has nothing to carry.

**Consequences.** A live `run` through a fresh-per-trial adapter now certifies
with real provenance, and one through a shared-session adapter is refused a
baseline rather than quietly admitted. That is a behaviour change for anyone
using `from_strands` or `from_langgraph_thread` with `snapshot`, and it is the
change ADR 5 was written to make.

**A declaration decided once cannot describe state read per call.**
`from_langgraph` computed its level at construction and then read the caller's
live config mapping on every call, so adding a `thread_id` to that same dict
afterwards sent the remaining repeats down one shared thread while the
declaration still said `fresh-session`. The config is copied at construction
and both the declaration and the calls read that copy. The copy also keeps the
repeats comparable: a recursion limit that changes mid-run means the trials
were not asking the same question. The copy is one level deep, so a caller
mutating something nested inside a callback object can still change behaviour;
what they cannot change is the isolation, which is what the declaration claims.

Setting the attribute by hand with a level the format defines is trusted, and
that is the same act as calling `declare_isolation`. What the reader refuses is
an invented level, which would otherwise arrive as a value no policy covers.

An assertion is still an assertion. The adapter states what it did, and the
library cannot see whether a model provider kept state behind it, whether a
tool wrote to a shared database, or whether the graph was compiled without a
checkpointer so the fresh thread changed nothing. The claim is bounded to
what the adapter controls, and the report says `fresh-session` rather than
`independent`.

**Alternatives rejected.**

*A constructor argument on `run`.* It would work, and it would be a caller
asserting rather than an adapter reporting. The caller is the party with an
incentive to say `fresh-session` to get a baseline admitted, and the adapter
is the party that knows.

*Per-trial execution identifiers, for now.* The roadmap pairs them with this,
and they answer a different question: not what isolation was intended, but
evidence that trials were in fact distinct. That needs another evidence schema
move, one release after two of them, to serve auditability nobody has asked
for yet. Deferred under the same rule the rest of the project uses: a schema
grows when a real case forces it.

*Inferring isolation from observed behaviour.* Rejected in ADR 5 and still
rejected. Nothing in a sequence of verdicts establishes independence.

## ADR 7: stopping early is bought with predeclared looks, not by peeking at the interval

**Status.** Accepted 2026-08-03. Roadmap item 5, the statistical core.

**Context.** A 5% claim needs 73 zero-flip pairs per route. Collecting that
budget and then deciding is honest and it is also why a team runs this once. A
route flipping on a third of its pairs is obvious after a handful, and paying
for the other sixty is waste.

The tempting version is to compute the Wilson interval after every pair and
stop when it crosses `epsilon`. That is optional stopping and it destroys the
coverage the interval claims. The roadmap named three legitimate routes and
required one to be chosen and written down first.

**Decision.** Predeclared checkpoints with alpha spending, split
**asymmetrically by direction**. That last part is the whole design and it came
out of simulating the obvious version first.

The obvious version spends alpha evenly across every look in both directions.
Simulated, it costs 99 pairs to certify determinism against the 73 the
fixed-sample interval needs, a 36% tax on every well-behaved route, and the
early looks never certify anything anyway: with alpha split four ways, no
attainable flip count certifies before the final checkpoint.

So the early looks only ever fire in one direction, and spending certification
alpha on them buys nothing. The rule is:

- **Certification is tested once**, at the final predeclared checkpoint, with
  half the alpha and no multiplicity correction, because there is only one such
  test.
- **Early looks test only the stochastic direction**, splitting the other half
  of the alpha across them by the union bound.
- Both use exact binomial tails rather than a normal approximation.

Simulated over 4,000 runs per point, against the 73-pair fixed-sample cost:

| true flip rate | usual call | pairs spent |
|---|---|---|
| 0.00 | deterministic | **0.99x** |
| 0.05 | undecided | 0.98x |
| 0.15 | stochastic | 0.73x |
| 0.30 | stochastic | **0.34x** |
| 0.50 | stochastic | **0.25x** |

**Certifying determinism costs nothing**, and an obviously unstable route stops
in a quarter of the budget. The first design would have taxed the first row by
36% to buy the last.

**The error guarantee does not rest on the simulation.** Certification is one
exact binomial test at `alpha / 2`, and stopping early can only remove paths
that would have reached it, never add one. That holds for any budget.

At the default budget it is stronger than that and worth stating separately,
because the argument is checkable by eye. Certifying at 72 pairs requires zero
flips, and a run with no flips cannot have tripped an early look either, so the
two rules cannot interact at all and the false certification rate is exactly
`(1 - p)^n`. At `p = epsilon` that is 0.02489 against a budget of 0.025, and a
400,000-run simulation reads 2.508%, which is that number plus noise. The tests
assert the closed form.

A larger budget certifies with some flips allowed, three at 200 pairs and
fifteen at 500, and then only the general argument applies.
`SequentialPlan.certification_is_closed_form` says which case a plan is in
rather than leaving a reader to work it out from the default.

**In-flight calls under bounded concurrency.** A decision at a checkpoint reads
exactly the first `n` pairs **in collection order**. Concurrency overshoots the
boundary, and those extra results are kept as evidence but never change the
call. So the count a decision is computed from is fixed in advance rather than
being whatever happened to have finished, which is what would put the
multiplicity correction back into doubt. Nothing is wasted by this: if the run
continues, the overshoot is simply the first part of the next checkpoint.

**Consequences.** Sequential collection is opt-in and the fixed-sample path is
unchanged. A caller who wants the simplest thing keeps getting it.

A declared **budget still caps the run**, and the two paths agree under one: a
budget too small to reach a decision produces `undecided` from both. A budget
is threaded rather than refused because a cap bounds early stopping happily,
where a second rule that *sizes* the run does not.

That distinction decides every other interaction. Declared route stability
targets and an explicit `k` both size the run, so both are refused alongside
sequential collection. `check` is refused too, and at the parser rather than at
runtime: it rebuilds its configuration from the snapshot, `k` included, so it
cannot also size from checkpoints. A caller learns that before the agent is
loaded rather than after.

The checkpoints have to be declared before collection starts, which is the same
discipline the rest of the library already asks for with declared suites,
declared contracts and declared route targets. A checkpoint chosen after seeing
the data is the peeking this ADR exists to prevent, wearing a different hat.

**Alternatives rejected.**

*Recomputing the Wilson interval after every pair.* The thing that motivated
the item. It is what a developer writes first, it looks right, and its coverage
is not what it says.

*A betting or mixture confidence sequence.* Genuinely anytime-valid at every
observation and sharper than this, so a run could stop at any point rather than
at four. It is also materially more code, harder to check by hand, and its
correctness is not visible to a reader the way `(1 - p)^n` is. Left open: if a
real suite shows the four looks are the binding constraint, that is the
evidence needed to justify the complexity.

*Spending alpha evenly.* Rejected on the numbers above rather than on taste.

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
