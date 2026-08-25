# Statistical Method Validation

This asset cross-checks the operating behaviour of AgentVerity's fixed Wilson,
live fixed-endpoint curtailment, and predeclared sequential rules. It also
compares predeclared 73- and 146-pair fixed endpoints and measures how quickly
the operating rule's conclusions degrade when pair independence is false. The
exact arguments in `DESIGN.md` remain the basis of the method; Monte Carlo is
a reproducible diagnostic, not a proof.

## Reproduce it

From the repository root:

```bash
python scripts/validate_method.py \
  --trials 100000 \
  --output docs/evidence/method-validation.json
```

The committed result uses seed `20260822`, `epsilon=0.05`, `alpha=0.05`, five
true flip rates, four dependence settings (`rho=0, 0.02, 0.05, 0.10`), and
100,000 qualification runs per scenario. It records exact boundary
probabilities, every simulated call share, Monte Carlo uncertainty, and mean
pairs spent in the versioned
[`agentverity.method-validation/v4`](evidence/method-validation.json) artifact.
The script has no dependencies outside Python and AgentVerity.

## Experiment

The independent model draws disjoint pair flips as Bernoulli trials. The fixed
rule reads 73 pairs and classifies their 95% Wilson interval. Its curtailed
form keeps that endpoint and counterfactual classification but stops live work
as soon as an all-agree continuation cannot admit. The sequential rule reads
at predeclared checkpoints 18, 36, 54, and 72, using exact-binomial thresholds
and directional alpha spending.

The sensitivity model holds the marginal flip rate constant but draws one
latent rate per qualification run from a beta distribution. Conditional pair
outcomes are Bernoulli, producing beta-binomial clustering with intraclass
correlations `rho=0.02`, `0.05`, and `0.10`. These are deliberate assumption
violations, not estimates of production dependence. The compact table below
shows the strongest setting; the JSON artifact carries the full sweep.

A separate paired IID replay uses the same 100,000 paths per true rate at
predeclared endpoints of 73 and 146 pairs. The larger endpoint can admit at
most two flips rather than none. Exact binomial enumeration checks the call
probabilities at the 5% boundary. The replay also checks every feasible
prefix-count state against the production inverse, then compares ordered-path
stopping and admission against the ordinary endpoint result.
This replay uses seed `20260823`, derived as the main seed plus one so the
added stream does not rewrite the established `20260822` dependence sweep.

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
| clustered, rho=0.10 | 0.050 | fixed | 35.816% | 16.615% | 47.569% | **52.431%** | 73.0 |
| clustered, rho=0.10 | 0.050 | sequential | 36.005% | 12.721% | 51.274% | **48.726%** | 67.9 |

### Two fixed endpoints

| Endpoint | Most flips that can admit | Exact deterministic at p=5% | Exact stochastic | Exact undecided | Exact directional total |
|---:|---:|---:|---:|---:|---:|
| 73 pairs | 0 | 2.365% | 2.921% | 94.714% | 5.286% |
| 146 pairs | 2 | 2.126% | 3.197% | 94.677% | 5.323% |

| Endpoint | Mean pairs at p=2.5% | Mean pairs at p=5% | Mean pairs at p=30% | Prefix-state mismatches | Replay mismatches |
|---:|---:|---:|---:|---:|---:|
| 73 pairs | 33.6 | 19.5 | 3.3 | 0 / 2,700 | 0 |
| 146 pairs | 102.6 | 59.6 | 10.0 | 0 / 10,730 | 0 |

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
6. **Observed counts and a projected rate answer different planning
   questions.** The exact score-test inversion gives the following totals at
   `epsilon=0.05`. “Fixed count” assumes every future pair agrees; “fixed
   rate” projects the observed rate indefinitely.

   | Observed | Fixed-count best case | Fixed-rate projection |
   |---:|---:|---:|
   | 1/73 | 110 | 139 |
   | 2/73 | 142 | 358 |
   | 3/73 | 173 | 2,302 |
   | 4/73 | 202 | impossible |
   | 8/73 | 311 | impossible |

   The best-case column supports early **refusal** against a predeclared
   maximum: if the endpoint cannot admit even with no further flips, stop
   spending. It does not support inspecting a fixed-sample interval after
   every pair and stopping at its first favourable value.

7. **Fixed-endpoint curtailment preserves decisions path by path while
   concentrating savings on variable runs.** Across the two million simulated
   paths, its counterfactual endpoint call matched the ordinary fixed rule in
   every case. Under independence, mean spend was 73.0 pairs when the true
   flip rate was zero, 33.6 at 2.5%, 19.5 at the 5% boundary, 10.0 at 10%, and
   3.3 at 30%. It never admits early: a stopped path carries an impossibility
   result and no final repeatability class.
8. **A larger predeclared endpoint changes power and curtailment timing, not
   the claim.** The 146-pair endpoint can admit up to two flips and increases
   admission probability below the boundary, but it waits for a third flip
   before admission becomes impossible. Exact enumeration remains nominal
   rather than an exact 5% directional budget. Across 13,430 feasible prefix
   states and 500,000 paired IID replay paths, the threshold and production
   inverse disagree zero times and curtailment loses zero endpoint admissions.

## Consequences and limits

The fixed admission rule and durable product evidence schemas remain
unchanged. The validation artifact moves to v4 because it now records two
fixed endpoints and their replay checks; this is a validation-artefact change,
not a product schema migration. The public `best_case_admission_pairs` helper
supplies the count-aware boundary used by the runner. The fixed rule remains
conservative in the regression-reference admission direction, while its nominal
two-sided calibration is explicit. A future change to an exact fixed-sample
rule requires an ADR, compatibility analysis, and measured call budget before
implementation.

The sensitivity model covers one exchangeable dependence pattern, not stateful
agents generally. It does not establish that `rho=0.10` is realistic, detect
contamination from observations, validate case representativeness, or test the
correctness of any decision. Independent expert review of the method remains
an open Phase 1 outcome. A 146-pair budget is still one within-window claim:
it neither repairs dependent trials nor supports a cross-time claim. Repeated
collection windows require a separately specified estimand and guarantee.
