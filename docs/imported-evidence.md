# Assessing runs you already have

You probably already run your agent repeatedly. promptfoo, DeepEval, LangSmith,
a script someone wrote. Running it again through AgentVerity to get an
admission decision pays for the same information twice.

`agentverity assess` reads the observations you already collected.

```console
$ agentverity assess --evidence runs.json --suite suite.json
```

No model is called. Everything below is arithmetic over decisions you recorded.

## Promptfoo: direct import

Promptfoo already supports repeated runs and JSON export. Keep its assertions
for quality, then assess the same outputs:

```console
$ promptfoo eval --repeat 26 --output results.json
$ agentverity assess \
    --promptfoo results.json \
    --suite decision-suite.json \
    --isolation unknown
```

With six one-case routes, 26 repeats supply enough zero-change pairs for the
pooled 5% check, not for six separate route-level claims. The report keeps
those routes `undecided`. Run `agentverity plan --suite decision-suite.json`
before collecting stricter per-route evidence.

The adapter matches each row's rendered `prompt.raw` back to an exact reviewed
suite input. Current Promptfoo releases assign a distinct `testIdx` to each
repeat, so the importer does not treat that index as a case identity. If the
reviewed input is stored elsewhere, point to it explicitly:

Promptfoo assertion failures still carry the decision that failed its quality
check, so they remain observations for stability analysis. Provider and
runtime failures carry no usable decision and make the AgentVerity assessment
incomplete.

```console
$ agentverity assess \
    --promptfoo results.json \
    --suite decision-suite.json \
    --input-path vars.ticket
```

If a provider returns structured JSON, point at its decision label:

```console
$ agentverity assess \
    --promptfoo results.json \
    --suite decision-suite.json \
    --decision-path decision.route
```

A Promptfoo export can contain a matrix of providers and prompts. AgentVerity
refuses to pool those configurations because a model or prompt difference
would then look like random variation. Use `--provider` and `--prompt-id` to
select one cell.

Use `--isolation fresh-session` only when the harness configuration creates a
new conversation or target instance for every repeat. Promptfoo's export does
not establish that fact, so `unknown` is the conservative default.

See the [runnable local Promptfoo example](../examples/promptfoo_bridge).

## DeepEval: share precomputed test cases

DeepEval metrics operate on individual `LLMTestCase` objects. AgentVerity's
admission decision operates across repeated cases and preserves a third
outcome, insufficient evidence, so it is not represented as a Boolean custom
metric.

Collect outputs once and give both tools the same objects:

```python
from agentverity import assess_evidence, evidence_from_deepeval

# repeated_cases have already been evaluated by DeepEval
evidence = evidence_from_deepeval(
    repeated_cases,
    decision=lambda output: output["route"],
    isolation="fresh-session",
)
result = assess_evidence(evidence, suite)
```

The bridge uses structural typing and does not add DeepEval as a runtime
dependency. See the [complete shared-run example](../examples/deepeval_shared_run.py).

## The file

```json
{
  "schema": "agentverity.evidence/v2",
  "layer": "verdict",
  "isolation": "fresh-session",
  "cases": [
    {
      "input": "I do not recognise this card purchase.",
      "expected": "card_security",
      "observations": ["card_security", "merchant_dispute", "card_security",
                       "merchant_dispute", "card_security", "merchant_dispute"]
    }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | `agentverity.evidence/v2`. An unknown version is refused rather than guessed at |
| `layer` | no | `verdict`, `text`, or `tools`. Defaults to `verdict` |
| `isolation` | no | How trials were separated. Defaults to `unknown`, which is reported |
| `cases[].input` | yes | The probe text |
| `cases[].observations` | yes | Each decision or text string, or each tool path as a string list, **in the order produced** |
| `cases[].expected` | no | The route the case was written to exercise |
| `cases[].errors` | no | Runs that failed rather than returning a decision |
| `provenance` | no | Free-form: model, harness, collection date |

### Recording a run that produced no decision

A decision is a plain string. A run that produced **no** decision is an object
saying why:

```json
"observations": [
  "approve",
  {"kind": "no_decision", "reason": "refused"},
  "approve",
  {"kind": "no_decision", "reason": "extraction_failed"}
]
```

One reading rule: a string is a decision, an object is a no-decision.

`reason` is one of `no_tool_selected`, `refused`, `open_ended`,
`extraction_failed`, `malformed_response`, `runtime_error`. The last three mean
the harness failed rather than the agent answering, and a series containing one
is refused rather than scored: zero-flip pairs over repeated extraction
failures would certify the failure. `open_ended` is refused too, because
categorical stability is undefined when a run produced no decision, and
dropping those runs while keeping the repeat count would report stability over
reruns that decided nothing.

A contract must declare a reason before it counts as an acceptable outcome:

```json
"contract": {
  "allowed": ["approve", "deny"],
  "allowed_no_decisions": ["refused"]
}
```

Only `refused` and `no_tool_selected` may be declared. An undeclared reason is
refused, because silence is not permission. And `"refused"` in `allowed` and
`"refused"` in `allowed_no_decisions` are two different declarations, counted
separately in the report.

## Averages are refused, and here is why

```json
{ "input": "...", "flip_rate": 0.12, "runs": 20 }
```

```text
error: cases[0] has no 'observations'. A flip rate or pass count cannot be
assessed: disjoint pairs cannot be recovered from an average, and a pooled
number cannot be split by route. Export the individual decisions per case.
```

Two things break with a summary.

**Disjoint pairs.** The meter compares observation 1 against 2, 3 against 4,
and so on. Pairs must not overlap, or the same call would contribute evidence
twice and the interval would be narrower than the data supports. A rate of
0.12 does not say which runs disagreed, so the pairs cannot be rebuilt.

**Route grouping.** Per-route stability splits observations by the case that
produced them. One number for a whole suite cannot be divided by route, which
is precisely the hiding this package exists to stop.

```text
  what you export           what can be assessed
  ─────────────────         ─────────────────────
  flip_rate: 0.12       →   nothing
  ["a","a","b","a"]     →   pairs, routes, flip pairs, coverage
```

## Isolation is recorded, not assumed

The statistics assume trials are independent. An imported file can break that
in ways a self-run cannot: repeats drawn from one conversation, a warm provider
cache, a single session reused.

| `isolation` | Meaning | Reported |
|---|---|---|
| `fresh-session` | Each trial started a new session | no caveat |
| `fresh-instance` | Each trial used a new agent instance | no caveat |
| `shared-session` | Trials ran in one session | not independent, the interval is too narrow |
| `unknown` | Not recorded | independence assumed rather than established |

Nothing is rejected on this basis. The caveat travels through text, JSON,
JUnit, and OpenTelemetry reports so downstream readers do not inherit a
confidence claim the file never earned.

## What an import can and cannot check

| Check | Imported evidence | Why |
|---|---|---|
| Stability meter | yes | A measurement over recorded decisions |
| Blindness | yes | Same |
| Declared coverage | yes | Same |
| Per-route stability | yes | Needs `expected` on each case |
| Flip pairs | yes | Rebuilt from the ordered observations |
| **Metamorphic relations** | **no** | A relation transforms an input and asks the *transformed* question. Those calls do not exist in your file |

Relation results come back empty rather than passing. Reporting a relation as
held when it never ran would be exactly the vacuous green this package exists
to name.

If you want relation coverage, run `agentverity run`. If you want an admission
decision on evidence you already paid for, `assess` gives you everything except
relations.

## Matching a suite

Pass `--suite` and the contract checks run too: required routes, unknown
decisions, `minimum_cases`, and per-route `stability_targets`.

The suite's case inputs must match the evidence exactly. A contract checked
against a different run would report coverage the run never had, so a mismatch
is an error rather than a warning.

## Exit codes

Identical to a live run, so a gate behaves the same either way. Recorded
provider failures make the result incomplete rather than disappearing from
the denominator.

| Code | Meaning |
|---|---|
| `0` | Admissible |
| `1` | Contract failure, blindness, a missed target, or violations |
| `2` | Undecided, or the evidence could not be read |

## Privacy

`input` is stored as written. If your probes contain customer text, that text
is in the file. AgentVerity's own reports identify probes by SHA-256
fingerprint rather than raw text, but an evidence file you hand it is yours to
sanitise first. Fingerprints are identifiers, not anonymisation: a guess can be
tested against one when the probe set is small or predictable.

Observations are decision labels. If your labels embed customer data, the same
applies.

## Comparing two windows over time

A run says whether a decision is repeatable now. It cannot say whether last
month's answer was the same, which is the question after a model version
changes, a prompt is edited, or a provider reroutes traffic.

```console
$ agentverity compare-evidence july.json august.json
evidence drift
  route                     before         after  result
  card_security               0/13          9/13  undecided -> stochastic
  duplicate_charge            0/13          0/13  unchanged
  flip pairs gained: card_security <-> merchant_dispute
  provenance:
    model: 'router-v3' -> 'router-v4'

verdict: DRIFTED
```

The reportable event is a **tri-state result moving**, not a rate wandering. A
route drifting from 2% to 3% inside the same conclusion is noise. A route
crossing from deterministic to stochastic is a release event.

| Reported | Meaning |
|---|---|
| `undecided -> stochastic` | The verdict moved. Investigate |
| `higher` / `lower` | The observed change rate moved inside one verdict |
| `incomparable` | One window had no usable pairs for that route |
| routes gained or lost | An intended decision route appeared or disappeared entirely |
| flip pairs gained or lost | A new confusion appeared, or an old one resolved |
| provenance | A model, prompt, or harness difference between the files |
| isolation | The two windows were collected under different isolation, so the evidence means something different |

A provenance change alone counts as drift even when every decision held. A
model swap is the fact you most want beside a comparison, not a footnote.

Volatile keys are the exception. `collected_at`, `run_id`, and similar differ
between any two windows by construction, so they are shown under
`provenance (not counted as drift)` rather than reported as a change. Counting
them would mark every real Promptfoo comparison as drifted and make the command
useless on exactly the data it exists for.

Both windows must use the same observation layer. A verdict and a tool path are
not the same observation, so a difference between them is not drift.

Exit code is `1` on drift and `0` on none, so the command can gate CI. Whether
your pipeline blocks, requests review, or records the change is your policy.
AgentVerity reports movement without calling it a regression, an improvement,
or a relabelled taxonomy.

### What a comparison cannot establish

Agreement between two windows does not prove trials were independent within
either one. Two correlated runs agree with each other very comfortably.
Independence is a property of how each window was collected, recorded in
`isolation`, and no comparison recovers it. The note travels with every
comparison for that reason.
