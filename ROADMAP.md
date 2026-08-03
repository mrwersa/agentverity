# Roadmap

AgentVerity answers one question: **is this evidence strong enough to save as
a regression baseline?** Not whether the answer was right, and not whether the
agent is good. Those are different questions with better tools, and taking
them on would make this one less trustworthy.

This is direction, not a release promise. `DESIGN.md` carries the milestone
history.

## Where it is now

As of 0.14.0 the loop is complete for a categorical decision layer, and a
[worked example](https://github.com/mrwersa/agent-release-gate) runs it beside
authority analysis on one agent, offline.

| | command | what it establishes |
|---|---|---|
| **price it** | `plan` | what a declared suite will cost, before any call is made |
| **collect** | `run` | repeated trials with bounded concurrency and partial evidence on failure |
| **or import** | `assess` | the same analysis over runs some other harness already collected |
| **judge** | the report | per-route intervals, blindness, declared contract, tri-state call |
| **admit** | `snapshot`, `check` | a reviewed baseline, and whether a later run still matches it |
| **compare** | `compare-evidence` | what moved between two independently collected windows |

Every classification comes from the **bound**, never the observed rate, and
the tri-state keeps `undecided` distinct from `stable`. Incomplete evidence,
a blind probe set, and a vacuous relation catalogue are all failures rather
than quiet passes.

Adapters: Strands, LangGraph, and any callable. Evaluator bridges: Promptfoo
by direct import, DeepEval by shared test cases. Reporting: terminal, versioned
JSON, JUnit XML, and one privacy-minimised OpenTelemetry span.

### A real agent has now been measured

`docs/evidence/agentkit/` holds 4,380 model calls against the tool set the
Coinbase AgentKit Strands example exposes, across three models, for 0.70 USD.
Every observation is committed, so re-assessing costs nothing.

The result is this library's own caveat with numbers behind it. Ranked by how
often a model returned the same tool for the same request, `mistral-small`
scores 10 out of 10 and is correct on five of ten probes. `gpt-4o-mini` scores
8 and is correct on seven. A stability gate alone prefers the worse agent.

**What it confirmed.** Per-route beats pooled, on real data. Eight of
`gpt-4o-mini`'s routes settle as deterministic at a 5% tolerance, and the two
that do not are `transfer` and `approve`, which are two of the three the suite
marks critical. The pooled figure is 8.5% and says nothing about which routes
carry it.

**What it asked for.** A first-class notion of an unset decision. When a model
answers a tool-calling contract with prose, `Observation.key` falls back to
comparing raw text, so two differently worded refusals count as a changed
decision. That measures wording rather than choice. The adapter here works
around it by naming the outcome, and the library should not need a caller to
know that.

**What it also asked for.** Reach semantics that do not disagree. The contract
check reads the first verdict of each case, while the route table reads every
repeat, so `approve` came back 98 times out of 146 and was still reported as
never observed. Neither reading is wrong. They answer different questions and
the report does not say which is which.

**A vocabulary gap it exposed.** The two unstable routes flip between acting
and resolving an identifier first, and both are reasonable opening moves. That
is a different release risk from a route flipping between a good action and a
bad one, and this library currently calls them the same thing. A per-route
ambiguity signal, derived from the flip pairs already reported, would separate
them. Not built: it needs a second graph before the concept earns its name.

**What it did not ask for.** Multi-turn support. Several models resolve an
identifier before acting, which is a reasonable plan that a single-turn probe
cannot express, and the fix is a better probe rather than a wider model.

## Next

Ordered by what unblocks what. Semantics first, because an importer or a
statistical procedure built on ambiguous semantics has to be rebuilt. Each
item that changes reach semantics or the statistical procedure gets an ADR in
`DESIGN.md` before code, and the AgentKit case is pinned across terminal,
JSON, JUnit, OTEL, snapshot and imported-evidence output so a semantic change
cannot move one surface silently.

### 1. Separate intended, observed, and admissible route reach

`DecisionCoverageResult` already carries intended and observed counts. The
defect is narrower than it first looks: observed coverage reads only the
primary result of each case, so a route the model reached on 98 of 146 repeats
reports as never observed.

Three quantities, kept distinct in the model and in every report:

- **intended** — reviewed cases written for that route
- **observed** — distinct cases that returned it on any repeat
- **admissible** — route evidence that meets its declared stability target

The distinctions matter in both directions. Ninety-eight observations of
`approve` are not ninety-eight cases, so observed must count cases and not
occurrences. And one chance occurrence must not let unstable evidence pass as
adequately covered, which is what admissible is for.

### 2. A typed representation for the absence of a decision

`Observation.key` falls back to comparing raw text when no verdict is set, so
two differently worded refusals read as a changed decision. That measures
wording rather than choice.

A single `UNSET` sentinel would be worse than the fallback, because at least
six distinct events currently collapse into `verdict=None`: open-ended output,
a refusal, no tool selected, extraction failure, a malformed provider
response, and a runtime failure. Folding those into one category would make a
run of extraction failures look perfectly stable.

So: an explicit `Decision(label)` against `NoDecision(reason)`, versioned.
Runtime and extraction failures make the evidence **incomplete**, which is
already a first-class outcome here. A refusal becomes a categorical outcome
only when the contract or the adapter declares it as one.

**Shipped in full.** Snapshots carry a typed outcome too, so a contract that
declares a refusal can baseline one, and a baseline written before an adapter
adopted the types still matches the runs it makes afterwards.

### 3. A generic JSONL importer

Once the two above are settled. The evidence schema already refuses
aggregates, which is the part that matters; an importer is a mapping onto it.
Worth stating plainly so the value is not oversold: an imported run with one
observation per case remains `undecided`. The importer removes the second
bill, not the first.

### 4. Isolation provenance, and what to do with it

Every interval assumes independent trials. The recorded `isolation` field
already models this with `fresh-session`, `fresh-instance`, `shared-session`
and `unknown`, and `shared-session` already produces a caveat.

Strengthen the provenance rather than infer it. Per-trial execution
identifiers, and adapter assertions about what was actually fresh. Then a
stated policy: refuse known shared-state evidence for certification, caveat
`unknown`, and admit `fresh-*`.

Deliberately not attempted: inferring contamination from behaviour. Inputs
that grow across trials are often legitimate test inputs, and verdicts
settling partway through a run is not evidence of anything. Both would reject
valid evidence, and neither absence establishes independence.

### 5. Anytime-valid sequential collection

A 5% claim needs 73 zero-change pairs per route. Collecting the full planned
budget and then deciding is the honest way to spend that, and it is also why a
team runs this once.

Stopping early is worth having and **cannot reuse the fixed-sample interval**.
Repeatedly inspecting a Wilson interval and stopping when it crosses a
threshold is optional stopping, and it destroys the nominal coverage the
interval claims. One of three routes, chosen and written down first:

- an anytime-valid confidence sequence
- predeclared checkpoints with alpha spending
- a fixed maximum with a formally justified sequential test

Validated by simulation around `p = epsilon`, where the error inflates, rather
than by unit examples that pass either way. The design also has to state what
happens to in-flight calls under bounded concurrency, since they overshoot the
stopping point and their results must either count or be discarded by a rule
declared in advance.

### 6. Traffic-weighted route reporting, optional

Given an observed route distribution, report **traffic-weighted admitted-route
mass**, split into deterministic, stochastic, undecided, and out-of-contract,
recording the telemetry window, the model and the contract version.

Stated carefully, because the obvious version overclaims. A route-level
distribution says nothing about semantic coverage within a route. And an even
spread across six routes may be deliberate risk-based coverage rather than a
mistake, so traffic weighting is reported beside risk weighting and never
substituted for it.

### 7. User-extensible relations

Last. The catalogue is a closed set of transforms. A documented protocol for
registering a domain relation, with the coverage report treating a user
relation the same as a built-in.

## Then, if evidence demands it

Candidates, not commitments. Each needs a real suite that the current model
forces someone to distort before it earns the complexity.

- **Ordered trajectory stability beyond tool selection.** Today a trajectory
  is compared as an ordered tool path. Partial-order equivalence, where two
  orderings are both correct, needs a reviewed declaration of which pairs
  commute, and nobody has yet shown a suite where that is the blocker.
- **Continuous decisions.** Scores and rankings are not categorical, and the
  flip-pair statistics do not carry over. This would be a second meter, not a
  generalisation of the existing one.
- **Multi-turn stability.** A conversation is not repeated trials of one
  question. The independence the intervals assume does not hold, and the
  honest version needs a different statistical treatment rather than a flag.

## Not planned

- **A judge, a benchmark, or a leaderboard.** Repeatability is not
  correctness. A confidently wrong agent scores perfectly here, and it should:
  saying otherwise would make the number mean less, not more.
- **Running the agent for you in production.** This measures a release
  candidate. Production feedback belongs in observability, and the handoff is
  the OTEL summary span.
- **Provider or framework lock-in.** The core installs with no agent library
  and no provider SDK, and a CI job checks that it still does.
- **Inferring semantic diversity.** `minimum_cases` enforces a reviewed policy
  on case count. It does not pretend to know whether the cases are varied,
  because nothing in the text tells it that.

Correctness, safety, semantic representativeness and open-ended quality are
permanent boundaries rather than unstarted work. Item 6 above is adjacent to
the last of them and stays in scope only because it describes the evidence
rather than the answer. A boundary list is not a backlog, and treating it as
one is how a tool that answers a single question well becomes one that answers
several badly.
