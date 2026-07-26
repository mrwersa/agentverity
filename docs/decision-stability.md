# Why three reruns are not enough

Teams often pick a rerun count by convention. Three, five, and ten are common
choices, but none says how much unseen variation the sample can rule out.

This self-contained helper is the tempting implementation. It pairs independent
runs and returns one Boolean answer:

```python
import math

def looks_stable(agent, cases, k=12, tolerance=0.05):
    flips = trials = 0
    for case in cases:
        answers = [agent(case) for _ in range(k)]
        for i in range(0, k - 1, 2):
            trials += 1
            flips += answers[i] != answers[i + 1]
    p, z = flips / trials, 1.96
    d = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / d
    margin = z * math.sqrt(
        (p * (1 - p) + z * z / (4 * trials)) / trials
    ) / d
    return min(1, centre + margin) < tolerance
```

Against a deterministic router, six cases at 12 repeats produce 36 disjoint
pairs and no route changes:

```text
flip rate 0.0    upper bound 0.096    tolerance 0.05    ->  NOT STABLE
```

The interval arithmetic is correct. The Boolean interface is not. An upper
bound of 9.6% fails to certify a change rate below 5%, but it does not show that
the router is unstable. The sample is underpowered, so the honest result is
**undecided**.

With no observed changes, a 5% threshold needs 73 independent pairs.
`pairs_for_deterministic_call(0.05)` returns that number, while `plan_repeats`
translates it into repeats per input before calls begin.

The built-in precision levels therefore imply these minimum evidence budgets
when no changes are observed:

| Precision | Maximum tolerated change rate | Independent pairs |
|---|---:|---:|
| `cheap` | 10% | 35 |
| `balanced` | 5% | 73 |
| `strict` | 1% | 381 |

These are target-call budgets, not library-throughput benchmarks. Wall time is
normally dominated by the supplied agent or remote endpoint. A local
calls-per-second figure would therefore say little about the cost of a real
evaluation. `plan_repeats` exposes the budget that teams can price before a
run, while the measured
[AgentCore canary](../examples/production_stack/RESULTS.md) reports the
end-to-end latency of one real deployment path.

AgentVerity keeps three outcomes:

- `deterministic`: enough evidence supports the requested tolerance
- `stochastic`: observed changes rule out that tolerance
- `undecided`: the sample supports neither claim

Use `precision="cheap"`, `"balanced"`, or `"strict"` for the common operating
points. Set `epsilon` and `k` directly only when the deployment requirement and
call budget are already known.

Static analysis can inspect local branches, route schemas, and expected labels.
It cannot establish the repeated output distribution of a hosted model. That
is why this check executes the target rather than reading its source.
