# Fixed-budget qualification: workshop reproduction

This self-contained supplement reproduces the analytical calculations and
derived maintenance table in *When More Runs Cannot Help: Fixed-Budget Stopping
for Agent Evaluation*, accepted as a poster at the non-archival
[Who Verifies the Agents? workshop at NeurIPS 2026](https://verify-agents-workshop.github.io/).
It makes no model or provider calls.

## Contents

- [Run the checks](#run-the-checks)
- [Choose a pair budget](#choose-a-pair-budget)
- [What each file establishes](#what-each-file-establishes)
- [Maintenance evidence boundary](#maintenance-evidence-boundary)
- [Relationship to AgentVerity](#relationship-to-agentverity)
- [Source record and licence](#source-record-and-licence)

## Run the checks

Use Python 3.12 with no third-party dependencies. From this directory:

```bash
python3 validate_method.py --check
python3 analyse_maintenance.py --check
python3 budget_analysis.py --check
python3 -m unittest discover -s tests -v
```

The first command runs 100,000 Monte Carlo replicates per scenario with seed
20260822 and checks the reported ranges. It also enumerates exact binomial and
beta-binomial classification probabilities. The remaining commands check the
committed maintenance results, generated budget tables and curves, and 24
numerical, pathwise and table-rendering tests. The finite tests verify the
boundary, its inverse, the recomputed maintenance table and table formatting.

The package can be copied out of this repository and run without installing
AgentVerity. CI also runs its tests in a separate Python process, keeping the
standalone modules separate from the library's validation runner.

## Choose a pair budget

From this directory:

```bash
python3 -c 'from budget_analysis import first_budget; print(first_budget(q=0.02, target=0.8, ceiling=1200))'
```

This prints `311`: at tolerance 0.05 and nominal 95% Wilson confidence, that is
the first budget attaining an 80% qualification probability under independent
pairs at a planned disagreement rate of 2%. Each pair requires two runs.

Declare the planning rate before collection. Qualification probability can fall
between increases in the allowed disagreement count, so rounding a budget up
requires another check. The search examines every integer up to its ceiling
and returns `None` if no budget attains the target.

Admission mode stops once qualification at the declared endpoint is impossible
and leaves the final classification unset. Diagnostic mode continues until
one of the full-budget classifications is forced. Neither mode qualifies early.
These analytical calculations assume independent Bernoulli pair indicators at
one fixed rate. They are not measurements of provider performance.

## What each file establishes

| File | Purpose |
| --- | --- |
| [validate_method.py](validate_method.py) | Fixed-seed sensitivity cross-check and exact classification probabilities at 73 and 146 pairs, plus an off-boundary example. |
| [budget_analysis.py](budget_analysis.py) | Qualification probability, expected collection length, length distributions and admission/diagnostic records. |
| [budget_results.json](budget_results.json) | Generated analytical results, including illustrative operational records. |
| [budget_table.tex](budget_table.tex), [budget_cost_table.tex](budget_cost_table.tex), [budget_figure.tex](budget_figure.tex) | Generated manuscript tables and curves. Run `python3 budget_analysis.py` to regenerate them. |
| [maintenance_input.json](maintenance_input.json) | Disagreement counts and stopping positions for 40 conditions at 146 pairs each. |
| [analyse_maintenance.py](analyse_maintenance.py) | Recomputes classifications, checks stopping counts against the boundary and recomputes savings. |
| [maintenance_results.json](maintenance_results.json) | Generated maintenance aggregate: 79.8% of the 292 pairs in the two stopped conditions, which is 4.0% of all 5,840 scheduled pairs. |
| [tests/](tests/) | Wilson/grid checks, independent Bernoulli convolution, exhaustive small-budget paths, derived-record consistency and table-rendering tests. |
| [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) | Input hashes and the source revision for this reproduction package. |

## Maintenance evidence boundary

The maintenance input is the analysis record: for each condition, the stopping
pair, the disagreement count at that pair and the final disagreement count.
The program recomputes the classifications and the savings from those fields.
The classification uses the mapped decision, so the package does not include
the trace.

On the two conditions that crossed the boundary, stopping would have avoided
79.8% of their 292 pairs. Across all 40 conditions the same figure is 4.0% of
5,840 scheduled pairs, because the other 38 qualified and ran to the full
budget, including 36 with zero disagreements. The savings are what sequential
collection in the assigned pair order would have avoided. The reported saving
is the admission-mode saving.

The AgentKit evidence elsewhere in this repository is a separate collection.
This package includes no prompts, traces, tool outputs, credentials or model
responses.

## Relationship to AgentVerity

The library's [method-validation evidence](../../docs/method-validation.md)
tests its production fixed-endpoint and predeclared sequential rules. This
folder is a separate reproduction of the workshop's calculations, including
budget planning and diagnostic collection. It adds no public library API and
does not change AgentVerity's evidence schemas or default admission rule.

| Paper/supplement outcome | AgentVerity public outcome |
| --- | --- |
| `qualify` | `deterministic` |
| `exceeds_tolerance` | `stochastic` |
| `undecided` | `undecided` |

An admission-mode early stop has no final outcome. Qualification concerns
repeatability of a declared categorical mapping within an evaluation period,
not correctness, zero randomness, or stability across periods. The positive
correlation scenarios are stress tests, not estimates of production dependence.

## Source record and licence

The numerical sources and derived maintenance records come from the core
workshop supplement. Legacy `anonymous.*` schema identifiers are retained for
compatibility with that package. The manifest records their origin. A
parenthesised string concatenation in `validate_method.py` is the only
formatting change to the imported numerical code and has no numerical effect.
The table generator, generated TeX and tests include the camera-ready's column
alignment and width corrections at the source revision in the manifest.

The existing Python 3.12 budget JSON is retained. Its normal quantile differs
from the pinned source snapshot in the last floating-point bit of nine `z` fields;
classifications, budgets, probabilities and collection lengths match. The
manifest records both hashes and this difference. The maintenance input and
results are identical to the source. Use an exact AgentVerity commit when
citing this folder, rather than a moving branch or the PyPI package version.

This folder's software and derived records use the [MIT licence](LICENSE.md),
with attribution to Saeed Aghaee. The surrounding AgentVerity library remains
Apache-2.0. This folder redistributes no upstream model or tool catalogue.
