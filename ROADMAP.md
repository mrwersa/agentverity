# Roadmap

AgentVerity answers one question: **is this evidence strong enough to save as
a regression baseline?** Not whether the answer was right, and not whether the
agent is good. Those are different questions with better tools, and taking
them on would make this one less trustworthy.

This is direction, not a release promise. `DESIGN.md` carries the milestone
history.

## Where it is now

As of 0.18.0 the loop is complete for a categorical decision layer, and a
[worked example](https://github.com/mrwersa/agent-release-gate) runs it beside
authority analysis on one agent, offline.

Items 1 to 5 and item 7 below are shipped, and item 6 remains optional, so the summary
that follows is the released 0.18.0 picture plus what has merged since. Read
each item for the detail, including what was deliberately not built.

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

**Shipped.** Observed coverage counts cases rather than occurrences, so a route
returned on 98 of 146 repeats no longer reports as never observed, and the
three quantities stay distinct in the model and in every report.

`DecisionCoverageResult` already carried intended and observed counts. The
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

**Shipped.** One JSON object per run, dotted paths for the input and decision
fields, exposed as `agentverity assess --jsonl`. The evidence schema already
refused aggregates, which was the part that mattered, so the importer is a
mapping onto it.

Two things it refuses rather than accepts. An input appearing once, because a
single run carries no comparison. And nothing at all about ordering: the file
order is the pairing order, so a log sorted by decision reports a stability
the run never had. That is stated in the docs and pinned by a test.

The value is still worth not overselling: an imported run with one observation
per case remains `undecided`. It removes the second bill, not the first.

LangSmith remains unbridged. Its export is a shape rather than a convention,
so it is a separate mapping when someone needs it.

### 4. Isolation provenance, and what to do with it

Every interval assumes independent trials. The recorded `isolation` field
already models this with `fresh-session`, `fresh-instance`, `shared-session`
and `unknown`, and `shared-session` already produced a caveat.

**The policy half is shipped.** `shared-session` evidence is refused a
baseline, `unknown` is admitted with its caveat travelling, and `fresh-*` is
admitted. A snapshot stores the isolation it was admitted under, so a later
check can say when the current run establishes less than the evidence that
certified the baseline. See DESIGN.md ADR 5.

The caveat had no consequence before this: a run could print "repeats are not
independent and the interval is narrower than the evidence supports" and then
be frozen as a baseline on the strength of that interval. A snapshot also
recorded no isolation at all, so the provenance died at the admission
boundary.

**Adapter provenance is shipped.** Every adapter declares what it did, `run`
reads it, and the policy above now applies to a live run. `from_strands_factory`
declares `fresh-instance`, `from_langgraph` declares `fresh-session`, the two
shared paths declare `shared-session` and are refused a baseline, and
`from_callable` declares nothing because a plain function says nothing. The
declaration is computed from what the adapter did rather than which function
was called, because `from_langgraph` respects a caller-supplied `thread_id`
and would otherwise claim independence exactly where the caller turned it off.
See DESIGN.md ADR 6.

**Per-trial execution identifiers are deferred**, not done. They answer a
different question from the one above: not what isolation was intended, but
evidence that the trials were in fact distinct. That needs another evidence
schema move, one release after two of them, for auditability nobody has asked
for. Same rule as everything else here: a schema grows when a real case forces
it.

Deliberately not attempted: inferring contamination from behaviour. Inputs
that grow across trials are often legitimate test inputs, and verdicts
settling partway through a run is not evidence of anything. Both would reject
valid evidence, and neither absence establishes independence.

### 5. Anytime-valid sequential collection

**The statistical core is shipped**, as `plan_sequential` and
`decide_sequentially`. See DESIGN.md ADR 7. Checkpoints are declared before
collection starts, and the error budget is split asymmetrically: certification
is tested once at the final checkpoint, so it carries no multiplicity penalty
and costs 72 pairs against the fixed sample's 73, while the earlier looks test
only the stochastic direction. An obviously unstable route stops in a quarter
of the budget and a well-behaved one pays nothing for the privilege.

The even split was built and measured first. It costs 99 pairs to certify and
its early looks never certify anything, so it taxed every good route to buy an
early exit for bad ones. That is in the ADR because the number is the argument.

**Runner integration is shipped**, as `RunConfig(sequential=True)` and
`agentverity run --sequential`. Collection goes in rounds of one pair per
input, and the first checkpoint that decides ends the run. The call comes from
the plan and the report says so, because reading the Wilson interval at a
stopping point it did not choose is the optional stopping the design avoids,
believed rather than done.

**What it is worth, measured rather than asserted.** Against the default
fixed-sample sizing:

| probe set | stable agent | agent flipping 30% |
|---|---|---|
| 6 inputs | 7% fewer calls | **50% fewer** |
| 20 inputs | none | **60% fewer** |
| 50 inputs | none | **33% fewer** |

So this is for not paying to confirm what a run has already shown. On a stable
agent the planner already sizes the fixed path close to the checkpoint budget
and there is nothing to save, which is why the feature is opt-in rather than
the default.

Sequential collection and declared route stability targets are refused
together. Both size the same run, and letting one quietly win is how a caller
ends up with neither.

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

**Shipped.** `agentverity run --relations module:func` takes a function
returning your relations, and a user relation is scored, tabled and counted
towards per-route coverage exactly like a built-in. See
[docs/custom-relations.md](docs/custom-relations.md) and
`examples/custom_relation.py`.

Half of this already worked and the roadmap did not say so: `Relation` was
public and `run(relations=[...])` always accepted one, so a Python caller could
extend the catalogue. The command line could not reach it at all, which is the
gap that actually mattered, since the CLI is where a first external user
starts.

The other half was validation. A relation with no name, an unknown type, or a
transform that is not callable constructed happily and failed mid-run, after
the source calls had been paid for. Refused on construction now, and a
catalogue that returns nothing or returns the wrong type is refused when the
flag is loaded.

Deliberately not added: a plugin registry or entry points. A function returning
relations is the whole protocol, it needs no installation step, and it keeps
the catalogue something a reader can see rather than something they discover.

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
