# Applicability and limits

AgentVerity is a conservative admission policy for regression references
involving named decisions. It is useful when a model-backed component behaves
like a classifier, router, gate, supervisor, or bounded controller even if it
also generates explanatory text.

It qualifies evidence produced beside correctness and trajectory evaluators.
It does not qualify the whole agent.

## The conceptual model

AgentVerity evaluates a declared categorical projection of a trace, not the
complete trace:

```text
trace T
  -> predeclared projection g
  -> categorical decision D
  -> ordered repeated decisions
  -> disjoint-pair flips
  -> repeatability qualification
```

The projection may extract a route, approval, selected tool, supervisor
handoff, or bounded tool-path class. It must preserve every distinction that
matters to the regression contract. A projection that maps meaningfully
different traces onto one label can appear repeatable while hiding the change
a release check was meant to catch.

Acceptability and repeatability answer separate questions. A grader or human
reviews whether behaviour is acceptable; AgentVerity asks whether the repeated
categorical evidence is adequate and repeatable at the declared tolerance.
Only after both hold should `snapshot` preserve a regression reference for a
later `check` or evidence-window comparison.

## The fit checklist

Use AgentVerity when all three conditions hold:

1. **There is a reviewable decision contract.** Each run produces a value from
   a finite set, such as `billing`, `refund`, `approve`, `review`, `deny`, or
   the ordered tools or handoffs that form the contract.
2. **Trials are comparable.** The same input can start from equivalent state.
   Use a fresh conversation, agent instance, or remote session where the
   framework retains history.
3. **The test set is deliberately varied.** Inputs are selected to reach
   different valid decisions and important boundaries, rather than being
   accidental paraphrases of one case.

The target does not have to use an LLM. A deterministic Python gate is a useful
control, and a hosted black box is a valid target when its decision can be
extracted.

## Examples

| Target | Fit | What AgentVerity checks |
|---|---|---|
| Support, payment, fraud, or incident router | Strong | Repeatability and spread of named routes |
| Approval or policy gate | Strong | Repeatability and spread of `approve`, `review`, and `deny` decisions |
| Multi-agent supervisor | Strong at a decision point | Final route, next-agent handoff, or a contracted tool path |
| Tool-using workflow | Conditional | A bounded, reviewed tool sequence, not arbitrary reasoning |
| Chat or RAG assistant | Usually poor | Only a separate route, citation policy, escalation, or other named decision |
| Coding or research agent | Usually poor end to end | Only an instrumented approval, handoff, completion state, or bounded tool path |
| Creative generation | Poor | Use semantic or human quality evaluation instead |

A system can contain both suitable and unsuitable layers. For example, a
research agent's prose is open ended, while its `continue`, `ask_for_review`,
or `finish` controller may have a finite contract. AgentVerity can assess the
controller without claiming to assess the research.

## Multi-agent systems

Choose the layer that owns the contract:

- **Step level:** test a router, guard, or handoff independently.
- **System level:** test the final pipeline decision.
- **Tool-path level:** compare an ordered tool or agent sequence only when that
  sequence is itself reviewed behaviour.

Run step and system checks separately for critical paths. A repeatable step can
be blind while the surrounding pipeline changes. One aggregate end-to-end
score can hide both facts.

If many trajectories are equally valid, do not use exact tool-path repeatability
as a quality claim. Prefer the final named decision or define a coarser,
reviewed path contract.

## What a result means

A trustworthy result supports this bounded statement:

> For these test inputs, observation layer, isolated trial method, and
> tolerance, the run produced enough repeatability evidence and did not collapse
> onto one highly dominant observed decision. When a decision contract was
> supplied, every required decision was intended and observed.

It does not prove:

- that the selected decisions were correct
- that every important boundary within a decision was tested
- that the inputs were semantically diverse
- that the agent is safe, secure, unbiased, or reliable on production traffic
- that provider calls were statistically independent
- that the result generalises beyond the tested model, prompt, tools, state,
  provider version, or environment

Use labelled assertions or another evaluator for correctness. Use a declared
decision contract for known labels. Static analysis remains useful for local
branches and paths that the runtime interface does not expose.
Use security tests for prompt injection, unsafe agency, data leakage, and
authorisation boundaries.

## What decision coverage means here

Without a declared contract, AgentVerity's coverage check is deliberately a
minimum dynamic diagnostic. It reports observed decision count and skew, then
warns when one decision dominates the probe set above the configured
threshold.

This catches a vacuous green suite that exercises one route. It is not the same
as measuring all declared routes. Two observed decisions out of twenty may
avoid the blindness warning while still being inadequate.

For release decisions, add a `DecisionSuite`. It distinguishes:

- **Observed diversity:** does one decision dominate the current probe set?
- **Declared coverage:** which required decisions were observed or missing?
- **Intended coverage:** did the reviewed cases include every required
  decision?
- **Contract drift:** did the agent emit a decision outside the allowed set?

This turns a warning such as "the suite did not collapse onto one route"
into the stronger but still bounded statement "the suite exercised every
decision this application declared as required". It does not prove that the
labels were correct, the inputs were semantically representative, or unknown
behaviour was impossible.

This is required-decision presence, not comprehensive behavioural-boundary
coverage. Use `minimum_cases` to enforce a reviewed case-count policy and
relation coverage to reveal routes no transformation touched. Neither feature
can decide that the cases represent every meaningful boundary.

```python
from agentverity import DecisionCase, DecisionContract, DecisionSuite

suite = DecisionSuite(
    contract=DecisionContract(
        allowed={"approve", "review", "deny"},
        critical={"deny"},
        stability_targets={"deny": 0.02},
        minimum_cases={"deny": 3},
    ),
    cases=(
        DecisionCase("routine request", "approve"),
        DecisionCase("ambiguous request", "review"),
        DecisionCase("prohibited request", "deny"),
    ),
)
```

`critical` records consequence and reports when a high-consequence decision is
missing. `stability_targets` is a separate, explicit policy: it gives a
required route its own tolerance, sizes the zero-change call plan, and makes an
undecided target a release refusal. Keeping those declarations separate avoids
inventing a numerical threshold merely because a route is marked critical.
Treat AgentVerity as one release condition beside correctness, security,
latency, cost, and operational health.

## Why use a library instead of a local loop?

A local loop is reasonable when a project only needs a few exploratory reruns.
The reusable part is the admission policy around those calls: non-overlapping
comparisons, evidence sizing from a tolerance, a separate insufficient-evidence
state, route-specific targets, declared coverage, and consistent CI and
snapshot behaviour. AgentVerity packages those decisions. A team that already
implements and reviews the same policy in its evaluation platform does not
need a second implementation.

## Trial assumptions and cost

AgentVerity uses isolated non-overlapping rerun pairs. Isolation prevents
conversation history from contaminating a repeat, but it cannot remove
provider-side caching, model rollouts, routing changes, or shared external
state.

The global repeatability interval can also conceal a small changing subgroup.
Per-route evidence names that subgroup when a decision suite is supplied.
Use `agentverity plan --suite` before assigning a tighter target to a
high-consequence route.

Lower tolerated change rates require more calls. Budget the run before
execution and use a tolerance tied to the consequences of a changed decision.
The `cheap`, `balanced`, and `strict` presets are sampling choices, not
universal safety grades.

See [decision repeatability](decision-stability.md) for the arithmetic and
[integrations](integrations.md) for placement in CI, release, and canary
workflows.

## Independence, and which way the error runs

Trials are treated as independent Bernoulli draws. Starting each trial from a
fresh conversation, agent instance, or remote session removes history leakage,
but it cannot remove provider caching, shared infrastructure state, model
rollouts, routing changes, or correlated external tool state.

Positive dependence between trials, a plausible effect of shared caching or
infrastructure state, reduces the effective sample size and can make the
interval too narrow. The practical consequence is worth stating plainly:
where the assumption fails this way, the tool is **overconfident** rather than
cautious, so a clean result deserves more suspicion than a dirty one. Provider
rollouts, routing changes, and other non-stationarity can create different
dependence structures with different effects.

Treat the intervals as a practical diagnostic, not as laboratory evidence.

## Per-route intervals are not a joint guarantee

When a decision suite is declared, repeatability is also reported per route. Each
route's interval is its own 95% statement. Six of them together are not a 95%
statement about the suite, and the report does not claim otherwise. Read the
table as six separate findings.

A route whose repeatability is rejected (`stochastic`) blocks snapshot admission
because pooling cannot erase a conclusive subgroup finding. An untargeted
undecided route remains an explicit limit on a pooled regression reference
rather than a clean route. A route named
in `stability_targets` is different: the run budgets for its declared
tolerance. An undecided result blocks release and snapshot admission, while a
result proven above the target fails the declared policy.
