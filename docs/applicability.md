# Applicability and limits

AgentVerity qualifies test evidence for a named decision point. It is useful
when a model-backed component behaves like a classifier, router, gate,
supervisor, or bounded controller even if it also generates explanatory text.

It qualifies a test run, not the whole agent.

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
| Support, payment, fraud, or incident router | Strong | Stability and spread of named routes |
| Approval or policy gate | Strong | Stability and spread of `approve`, `review`, and `deny` decisions |
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

Run step and system checks separately for critical paths. A stable step can be
blind while the surrounding pipeline is unstable. One aggregate end-to-end
score can hide both facts.

If many trajectories are equally valid, do not use exact tool-path stability
as a quality claim. Prefer the final named decision or define a coarser,
reviewed path contract.

## What a result means

A trustworthy result supports this bounded statement:

> For these test inputs, observation layer, isolated trial method, and
> tolerance, the run produced enough stability evidence and did not collapse
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

```python
from agentverity import DecisionCase, DecisionContract, DecisionSuite

suite = DecisionSuite(
    contract=DecisionContract(
        allowed={"approve", "review", "deny"},
        critical={"deny"},
    ),
    cases=(
        DecisionCase("routine request", "approve"),
        DecisionCase("ambiguous request", "review"),
        DecisionCase("prohibited request", "deny"),
    ),
)
```

Version 0.9 records critical decisions and reports when one is missing. It
does not assign a separate statistical threshold to each route. Run critical
cases as a separate stratum when they need a stricter tolerance. Treat
AgentVerity as one release condition beside correctness, security, latency,
cost, and operational health.

## Trial assumptions and cost

AgentVerity uses isolated non-overlapping rerun pairs. Isolation prevents
conversation history from contaminating a repeat, but it cannot remove
provider-side caching, model rollouts, routing changes, or shared external
state.

The global stability interval can also conceal a small unstable subgroup.
`inputs_with_flip` makes that risk visible at aggregate level. For a critical
route or boundary, run its cases separately rather than relying only on the
pooled result.

Lower tolerated change rates require more calls. Budget the run before
execution and use a tolerance tied to the consequences of a changed decision.
The `cheap`, `balanced`, and `strict` presets are sampling choices, not
universal safety grades.

See [decision stability](decision-stability.md) for the arithmetic and
[integrations](integrations.md) for placement in CI, release, and canary
workflows.

## Independence, and which way the error runs

Trials are treated as independent Bernoulli draws. Starting each trial from a
fresh conversation, agent instance, or remote session removes history leakage,
but it cannot remove provider caching, shared infrastructure state, model
rollouts, routing changes, or correlated external tool state.

Positive dependence between trials, which is what those mechanisms produce,
reduces the effective sample size and can make the interval too narrow. The
practical consequence is worth stating plainly: where the assumption fails this
way, the tool is **overconfident** rather than cautious, so a clean result
deserves more suspicion than a dirty one. Other dependence structures affect
coverage differently.

Treat the intervals as a practical diagnostic, not as laboratory evidence.

## Per-route intervals are not a joint guarantee

When a decision suite is declared, stability is also reported per route. Each
route's interval is its own 95% statement. Six of them together are not a 95%
statement about the suite, and the report does not claim otherwise. Read the
table as six separate findings.
