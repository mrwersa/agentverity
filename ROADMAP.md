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

**What it also asked for.** One definition of "reached". The contract check
reads the first verdict of each case, while the route table reads every
repeat, so `approve` came back 98 times out of 146 and was still reported as
never observed. Both readings are defensible on their own and they should not
disagree silently inside one report.

**A vocabulary gap it exposed.** The two unstable routes flip between acting
and resolving an identifier first, and both are reasonable opening moves. That
is a different release risk from a route flipping between a good action and a
bad one, and this library currently calls them the same thing. A per-route
ambiguity signal, derived from the flip pairs already reported, would separate
them. Not built: it needs a second graph before the concept earns its name.

**What it did not ask for.** Multi-turn support. Several models resolve an
identifier before acting, which is a reasonable plan that a single-turn probe
cannot express, and the fix is a better probe rather than a wider model.

## Next: fix what disagrees, then make the evidence cheaper

Reordered after an outside review. The review was accurate and restated the
README, which told me the positioning reads clearly and told me nothing about
what to build. What it did not raise is where the work is: the evidence costs
too much to collect, and nothing checks that the trials were independent.

### First, two things that disagree with themselves

1. **One definition of "reached".** The contract check reads the first verdict
   of each case and the route table reads every repeat, so `approve` came back
   98 times out of 146 and was still reported as never observed. Running the
   recommended command over this project's own flagship evidence returns
   `NOT TRUSTWORTHY` for that reason. Two defensible readings that disagree
   silently inside one report is a defect, and it is the first thing an
   adopter hits.
2. **A first-class unset decision.** When a model answers a tool-calling
   contract with prose, `Observation.key` falls back to comparing raw text, so
   two differently worded refusals count as a changed decision. That measures
   wording rather than choice. The AgentKit adapter works around it by naming
   the outcome, and no caller should have to know that.

### Then, the cost of evidence

A 5% claim needs 73 zero-change pairs per route. That is the honest number and
it is also the reason a team tries this once and stops.

3. **Sequential evidence.** Today a run collects the full planned budget and
   then decides. It should stop as soon as the bound is reached, and stop
   early when a route is already clearly unstable. Same guarantee from the
   same arithmetic, often a fraction of the calls. The sizing already exists
   in `plan`; this makes it adaptive rather than fixed.
4. **Independence checks.** Every interval assumes the repeats were
   independent trials. Nothing verifies it. A harness that reuses one session
   turns repeats into turns of a single conversation, the model then agrees
   with itself, and stability is overstated with no error anywhere. The
   LangGraph adapter mints a fresh `thread_id` per call for exactly this
   reason, and the library should refuse, or at least flag, evidence that
   looks contaminated: repeated identical session identifiers, inputs that
   grow monotonically across trials, or verdicts that stop changing partway
   through a run. Refusing on absent evidence is already this library's
   position. Computing an interval over evidence it cannot trust is the same
   error in the other direction.

### Then, whether the suite points at the right things

5. **Production coverage.** A suite that certifies six routes evenly, against
   traffic that is eighty per cent one route, is well measured and misdirected.
   Given an observed route distribution, report what share of production
   volume the suite actually certifies. This stays inside the mission: it is a
   statement about the evidence, not about whether any answer was correct.

### Then, easier import

6. **More evaluator importers.** LangSmith and a generic CSV or JSONL shape.
   The evidence schema already refuses aggregates, which is the part that
   matters; each importer is a mapping onto it. Worth saying plainly: import
   only helps a team that already repeated. Most Promptfoo and DeepEval runs
   are one pass per case, and one pass is `undecided` by construction. The
   importer removes the second bill, not the first.
7. **User-extensible relations.** The catalogue is a closed set of
   transforms. A documented protocol for registering a domain relation, with
   the coverage report treating a user relation the same as a built-in.

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

An outside review listed five things this does not prove: correctness, safety,
semantic representativeness, open-ended quality, and production distribution
coverage. Four of those are permanent and are above. The fifth is item 5, and
it belongs here only because it is about the evidence rather than the answer.
Treating a boundary list as a backlog is how a tool that answers one question
well becomes one that answers several badly.
