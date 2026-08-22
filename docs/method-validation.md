# Statistical Method Validation

This asset cross-checks the operating behavior of AgentVerity's fixed Wilson
and predeclared sequential rules. It also measures how quickly their
conclusions degrade when pair independence is false. The exact arguments in
`DESIGN.md` remain the basis of the method; Monte Carlo is a reproducible
diagnostic, not a proof.

## Reproduce it

From the repository root:

```bash
python scripts/validate_method.py \
  --trials 100000 \
  --output docs/evidence/method-validation.json
```

The committed result uses seed `20260822`, `epsilon=0.05`, `alpha=0.05`, five
true flip rates, and 100,000 qualification runs per scenario. It records exact
boundary probabilities, every simulated call share, Monte Carlo uncertainty,
and mean pairs spent in the versioned
[`agentverity.method-validation/v1`](evidence/method-validation.json) artifact.
The script has no dependencies outside Python and AgentVerity.

## Experiment

The independent model draws disjoint pair flips as Bernoulli trials. The fixed
rule reads 73 pairs and classifies their 95% Wilson interval. The sequential
rule reads at predeclared checkpoints 18, 36, 54, and 72, using exact-binomial
thresholds and directional alpha spending.

The sensitivity model holds the marginal flip rate constant but draws one
latent rate per qualification run from a beta distribution. Conditional pair
outcomes are Bernoulli, producing beta-binomial clustering with intraclass
correlation `rho=0.10`. This is a deliberate assumption violation, not an
estimate of production dependence.

“Wrong direction” means stochastic below the 5% boundary, deterministic above
it, and either directional claim exactly at the boundary.

## Results

| Model | True flip rate | Rule | Deterministic | Stochastic | Undecided | Wrong direction | Mean pairs |
|---|---:|---|---:|---:|---:|---:|---:|
| iid | 0.025 | fixed | 15.658% | 0.050% | 84.292% | 0.050% | 73.0 |
| iid | 0.025 | sequential | 16.045% | 0.014% | 83.941% | 0.014% | 72.0 |
| iid | 0.050 | fixed | 2.423% | 3.043% | 94.534% | 5.466% ± 0.141% | 73.0 |
| iid | 0.050 | sequential | 2.559% | 0.853% | 96.588% | 3.412% ± 0.113% | 71.8 |
| iid | 0.100 | fixed | 0.038% | 44.966% | 54.996% | 0.038% | 73.0 |
| iid | 0.100 | sequential | 0.042% | 23.210% | 76.748% | 0.042% | 66.9 |
| iid | 0.300 | fixed | 0.000% | 99.997% | 0.003% | 0.000% | 73.0 |
| iid | 0.300 | sequential | 0.000% | 99.963% | 0.037% | 0.000% | **25.0** |
| clustered, rho=0.10 | 0.050 | fixed | 35.714% | 16.355% | 47.931% | **52.069%** | 73.0 |
| clustered, rho=0.10 | 0.050 | sequential | 35.924% | 12.538% | 51.538% | **48.462%** | 68.0 |

## Findings

1. **The conservative admission wedge holds under independence.** At the
   boundary, the exact probability of a false deterministic call is 2.365% for
   fixed Wilson and 2.489% for sequential collection. At 10% the simulated
   false-deterministic rates are 0.038% and 0.042%.
2. **Wilson's 95% coverage is nominal, not an exact finite-sample error
   budget.** At the boundary its exact deterministic and stochastic call
   probabilities sum to 5.286%. The excess is on the false-stochastic side;
   it does not make weak evidence easier to admit. Documentation must not
   describe the fixed rule as an exact 5% test.
3. **Sequential collection is exact but deliberately conservative near the
   boundary.** Its exact total boundary-call probability is 3.281%. At a 10%
   true flip rate it returns undecided 76.748% of the time, so it should not be
   sold as a uniformly more powerful replacement for the fixed rule.
4. **Early stopping pays on obvious variation.** At a 30% flip rate the
   sequential rule reaches the same practical stochastic conclusion while
   averaging 25.0 pairs, 34% of the fixed path.
5. **Declared isolation is load-bearing.** With the same 5% marginal rate and
   `rho=0.10` clustering, boundary directional calls rise to roughly half of
   runs. Neither rule's interval or alpha interpretation survives that model.

## Consequences and limits

No public API, default, or evidence schema changes from this experiment. The
fixed rule remains conservative in the baseline-admission direction, while
its nominal two-sided calibration is now explicit. A future change to an exact
fixed-sample rule requires an ADR, compatibility analysis, and measured call
budget before implementation.

The sensitivity model covers one exchangeable dependence pattern, not stateful
agents generally. It does not establish that `rho=0.10` is realistic, detect
contamination from observations, validate case representativeness, or test the
correctness of any decision. Independent expert review of the method remains
an open Phase 1 outcome.
