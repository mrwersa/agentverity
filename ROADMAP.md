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

## Next: make the evidence easier to bring

1. **More evaluator importers.** LangSmith and a generic CSV or JSONL shape.
   The evidence schema already refuses aggregates, which is the part that
   matters; each importer is a mapping onto it. A team that has already paid
   for the repeats should not pay again to learn whether they were enough.
2. **User-extensible relations.** The catalogue is a closed set of
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
