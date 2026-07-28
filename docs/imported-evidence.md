# Assessing runs you already have

You probably already run your agent repeatedly. promptfoo, DeepEval, LangSmith,
a script someone wrote. Running it again through AgentVerity to get an
admission decision pays for the same information twice.

`agentverity assess` reads the observations you already collected.

```console
$ agentverity assess --evidence runs.json --suite suite.json
```

No model is called. Everything below is arithmetic over decisions you recorded.

## The file

```json
{
  "schema": "agentverity.evidence/v1",
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
| `schema` | yes | `agentverity.evidence/v1`. An unknown version is refused rather than guessed at |
| `layer` | no | `verdict`, `text`, or `tools`. Defaults to `verdict` |
| `isolation` | no | How trials were separated. Defaults to `unknown`, which is reported |
| `cases[].input` | yes | The probe text |
| `cases[].observations` | yes | Each decision, **in the order produced** |
| `cases[].expected` | no | The route the case was written to exercise |
| `cases[].errors` | no | Runs that failed rather than returning a decision |
| `provenance` | no | Free-form: model, harness, collection date |

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

Nothing is rejected on this basis. The point is that a reader can see which
applied, rather than inheriting a confidence the file never earned.

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

Identical to a live run, so a gate behaves the same either way.

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
