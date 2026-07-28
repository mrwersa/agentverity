# Evidence per route

A payment-refund agent chooses one of three decisions:

- `approve` sends a refund for processing
- `review` sends the request to a specialist
- `deny` stops a request outside policy

The pooled stability result can hide which decision is moving. This guide
shows how AgentVerity names that route and how to budget a tighter tolerance
before calling the agent.

## One number can hide one broken route

Suppose the test suite contains two cases for each decision. Across all six
cases, 10 of 78 repeated pairs change decision, a pooled rate of 12.8%.

```text
POOLED                           BY INTENDED ROUTE
                                 approve  0 / 26 changes
  ┌──────────────────┐           deny     0 / 26 changes
  │ 10 / 78 changes  │    ==>    review  10 / 26 changes
  │      12.8%       │
  └──────────────────┘           observed change:
                                  deny <-> review  x10
```

The same calls tell a more useful story when grouped by the decision each case
was written to exercise:

```text
4. STABILITY BY ROUTE
   route              cases  pairs  flips  95% CI            result
   approve                2     26      0  [0.000, 0.129]    undecided
   deny                   2     26      0  [0.000, 0.129]    undecided
   review                 2     26     10  [0.224, 0.575]    stochastic
   flip pairs:
     deny <-> review  x10
```

`review` is proven to change more often than the declared 5% tolerance.
`approve` and `deny` were quiet, but 26 pairs only bound their change rate at
12.9%. They remain `undecided`, not green.

The flip-pair row describes what the agent returned on identical reruns. It is
not a confusion matrix because AgentVerity does not decide which answer was
correct.

## Why the observed rate is not the verdict

One change in thirteen pairs is an observed rate of 7.7% against a 5%
tolerance. That looks like a failure, but its 95% interval is
`[0.014, 0.333]`, which crosses the tolerance. The supported answer is
`undecided`.

| Evidence | Observed rate | 95% interval | At 5% |
|---|---:|---:|---|
| 0 / 13 | 0.0% | [0.000, 0.228] | undecided |
| 1 / 13 | 7.7% | [0.014, 0.333] | undecided |
| 3 / 13 | 23.1% | [0.082, 0.503] | **stochastic** |
| 0 / 36 | 0.0% | [0.000, 0.096] | undecided |
| 0 / 73 | 0.0% | [0.000, 0.050] | **deterministic** |

Finding a noisy route can be cheap. Certifying a quiet route takes more
evidence. AgentVerity keeps those outcomes separate.

## Give a route its own tolerance

`critical` identifies a high-consequence decision in coverage reports. It does
not invent a statistical policy. Declare `stability_targets` separately when
a route needs a numerical tolerance:

```python
from agentverity import DecisionCase, DecisionContract, DecisionSuite, run

suite = DecisionSuite(
    contract=DecisionContract(
        allowed={"approve", "review", "deny"},
        critical={"deny"},
        stability_targets={"deny": 0.01},
    ),
    cases=(
        DecisionCase("Refund is within policy", "approve"),
        DecisionCase("Evidence conflicts", "review"),
        DecisionCase("Refund is outside policy", "deny"),
    ),
)

result = run(agent, suite=suite)
```

Routes without an explicit target use the run's default tolerance. A target
changes two things:

1. The run allocates enough repeats for each route to reach its tolerance in
   the best case where no pair changes decision.
2. A targeted route that remains `undecided` blocks snapshot admission and
   exits CI as an incomplete measurement. A route proven above its target
   fails the declared release policy.

An explicit `budget` remains a hard cap. If the zero-change plan does not fit,
the run refuses before calling the agent.

## See the bill before making calls

The bundled planning example is a three-case refund-approval gate:

```console
$ agentverity plan --suite examples/route_stability_plan.json
agentverity — zero-flip call plan
  route              cases   target pairs*  repeats   calls
  approve                1    0.050     73      146     146
  deny                   1    0.010    381      762     762
  review                 1    0.050     73      146     146
  total                                                1054
  * minimum pairs needed if no pair changes decision

  sized per route: 1054 calls. one uniform k for every route: 2286 calls.
  sizing per route saves 1232 calls by not buying a tight bound where nothing needs one.

This is the minimum needed to certify quiet routes. Observed decision changes can leave a route undecided or prove it stochastic.
```

No agent is called. The plan states a best-case minimum, not a guarantee.
Observed changes can require more evidence or prove that the route is
stochastic.

Adding a second `deny` case roughly halves the repeats per case, from 762 to
382. It does **not** halve the total call cost, which moves from 762 to 764.
The benefit is broader test evidence rather than cheaper statistics.

Use a target tied to the consequence of a changed decision. A strict 1% target
is expensive by design and should not be copied into every route.

## What the route table does not prove

**Correctness.** Keep reviewed assertions or a quality evaluator beside
AgentVerity.

**A joint guarantee.** Each route has its own 95% interval. Six intervals are
not one 95% statement about the suite.

**Semantic breadth.** Ten near-duplicate cases can still explore one narrow
corner of a route. AgentVerity counts declared cases but cannot judge whether
they represent the input space.

**True independence.** Caching, provider routing, and shared state can make
repeated pairs correlated. See
[applicability](applicability.md#independence-and-which-way-the-error-runs).

## Quick reference

| Result | Meaning | Next action |
|---|---|---|
| targeted `stochastic` | The route is proven to change more than its declared tolerance | Release fails. Repair the route or review the policy |
| untargeted `stochastic` | The route is proven to change more than the run tolerance | Treat it as actionable diagnostic evidence |
| `undecided` with changes | The route moves, but the interval crosses the tolerance | Collect more evidence or expect a stochastic result |
| `undecided` with no changes | The route was quiet but under-measured | Add repeats up to the named pair requirement |
| `deterministic` | The route is stable enough at its declared tolerance | Review correctness before admitting a baseline |
| A flip pair | Two decisions appeared for the same input | Inspect that decision boundary |
