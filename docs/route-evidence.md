# Evidence per route

A single stability number can be reassuring and wrong at the same time. This
page explains why, and what to do about it.

## The problem, in one picture

You run a payment-dispute router with six reviewed cases. The meter says the
verdict flips 12.8% of the time. Is that one bad route or six mediocre ones?

```text
POOLED                          PER ROUTE
                                approve  ████████████████████  0 flips
  ┌──────────────────┐          refund   ████████████████████  0 flips
  │   12.8% flips    │   ==>    card     ████████████████████  0 flips
  │  across 6 inputs │          cash     ████████████████████  0 flips
  └──────────────────┘          merchant ████████████████████  0 flips
                                transfer ██░░░░░░░░░░░░░░░░░░  10 flips
```

Same calls, same data. The pooled number averages one broken route across five
healthy ones. Nobody would sign off "transfer decisions are a coin flip", but
plenty of people sign off "12.8%".

AgentVerity splits the observations it already collected by the decision each
case was written to exercise. No extra calls.

## Reading the table

```text
4. STABILITY BY ROUTE
   route              cases  pairs  flips  95% CI            result
   approve                2     26      0  [0.000, 0.129]    undecided
   deny                   2     26      0  [0.000, 0.129]    undecided
   review                 2     26     10  [0.224, 0.575]    stochastic
   flip pairs:
     deny <-> review  x10
```

Three things to notice.

**`review` is a conclusion.** Ten flips in twenty-six pairs, and the interval
sits entirely above the 5% tolerance. This route is unstable and needs repair.

**`approve` and `deny` are not clean, they are unmeasured.** Zero flips looks
perfect, but twenty-six pairs only bounds the true rate at 12.9%. To claim 5%
you need seventy-three pairs. `undecided` says exactly that: not enough
evidence, not a pass.

**The flip pair says where the boundary is.** The agent is confusing `deny` with
`review`, not with `approve`. That is a specific thing to go and look at.

### Why the verdict never comes from the rate

One flip in thirteen pairs is a 7.7% observed rate against a 5% tolerance. It
looks like a failure. The interval is `[0.014, 0.333]`, which straddles the
tolerance, so the honest answer is `undecided`.

| Evidence | Rate | 95% interval | At ε=0.05 |
|---|---|---|---|
| 0 / 13 | 0.0% | [0.000, 0.228] | undecided |
| 1 / 13 | 7.7% | [0.014, 0.333] | undecided |
| 3 / 13 | 23.1% | [0.082, 0.503] | **stochastic** |
| 0 / 36 | 0.0% | [0.000, 0.096] | undecided |
| 0 / 73 | 0.0% | [0.000, 0.050] | **deterministic** |

Reading a point estimate as a verdict is the error this package exists to
prevent, so it does not commit that error in its own report.

### Detecting is cheap, certifying is not

This asymmetry drives everything else on the page.

```text
  finding a broken route          proving a route is sound
  ────────────────────────        ─────────────────────────
  3 flips in 13 pairs             0 flips in 73 pairs
  → stochastic, done              → deterministic
  cheap                           5.6x the calls, per route
```

A route that misbehaves announces itself with very little evidence. A route
that looks fine needs a lot of evidence before "looks fine" means anything.

## Spending the budget where it matters

Certifying every route at the same tight tolerance multiplies your bill by the
number of routes. Usually that is waste: a `card_security` decision and a
`duplicate_charge` decision do not deserve the same scrutiny.

Declare a target on the routes that carry consequence:

```python
from agentverity import DecisionCase, DecisionContract, DecisionSuite, run

suite = DecisionSuite(
    contract=DecisionContract(
        allowed={"approve", "review", "deny"},
        critical={"deny"},
        stability_targets={"deny": 0.01},   # deny is held ten times tighter
    ),
    cases=(
        DecisionCase("routine request", "approve"),
        DecisionCase("ambiguous request", "review"),
        DecisionCase("prohibited request", "deny"),
    ),
)

result = run(agent, suite=suite)
```

Repeats are then sized per route rather than uniformly:

```text
  repeats per case      uniform k              sized per route
  ──────────────────    ─────────────────      ─────────────────
  approve               ██████████████ 762     ███ 146
  review                ██████████████ 762     ███ 146
  deny                  ██████████████ 762     ██████████████ 762
                        ─────────────────      ─────────────────
                        2286 calls             1054 calls
```

Same guarantee on `deny`, for less than half the bill. The saving grows with
the number of routes that do not need the tight bound.

Without targets nothing changes: repeats stay uniform and the run behaves
exactly as it did before. Declaring a target is what opts you in to the extra
spend, and to the tighter bound you asked for.

## Knowing the cost before you spend it

```console
$ agentverity plan --suite examples/payment_decisions.json --epsilon 0.05
agentverity — call budget
  route              cases   target  pairs  repeats   calls
  card_security          1    0.010    381      762     762
  cash_withdrawal        1    0.050     73      146     146
  duplicate_charge       1    0.050     73      146     146
  merchant_dispute       1    0.050     73      146     146
  refund_delay           1    0.050     73      146     146
  transfer_delay         1    0.050     73      146     146
  total                                                1492

  sized per route: 1492 calls. one uniform k for every route: 4572 calls.
  sizing per route saves 3080 calls by not buying a tight bound where nothing needs one.
```

No agent is called. This is arithmetic on the suite, so run it before you
commit to a tolerance rather than after the invoice arrives.

Notice `card_security` needs 762 repeats because it has **one** case. Adding a
second case for that route roughly halves its repeat count, because the pairs
it needs are shared across cases. Cheaper evidence often means more cases, not
more reruns.

## What the table does not tell you

**Correctness.** A flip pair records that the agent answered `review` once and
`deny` once for the same input. Which one was right is a question for your
assertions or a quality evaluator. That is why this is a flip-pair table and
never a confusion matrix.

**A joint guarantee.** Each route's interval is its own 95% statement. Six of
them together are not a 95% statement about the suite. Read six findings, not
one.

**Semantic breadth.** A route with ten cases that are all paraphrases of the
same request is covered on paper and barely tested in practice. Repeats
establish that a decision is stable; distinct cases establish that a route is
actually explored. The tool measures the first and cannot infer the second.

**True independence.** See [applicability](applicability.md#independence-and-which-way-the-error-runs).
Caching and routing create positive dependence between trials, which narrows
the interval, so where the assumption breaks the tool is overconfident rather
than cautious.

## Quick reference

| You see | It means | Do this |
|---|---|---|
| `stochastic` | Proven to move more than the tolerance | Repair the route before trusting any relation result |
| `undecided` with flips | Moving, not yet proven | Add repeats, or accept it will resolve as stochastic |
| `undecided`, no flips | No evidence either way | Add repeats or cases up to the pairs the table names |
| `deterministic` | Proven stable at its tolerance | Safe to freeze a baseline for this route |
| A flip pair | The two decisions being confused | Look at the boundary between exactly those two |
