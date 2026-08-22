# Roadmap

AgentVerity answers one question: **is this repeated categorical evidence
strong enough to save as a regression baseline?** It does not decide whether
an answer is correct, safe, or useful. This roadmap turns the
[agentic-AI landscape review](docs/agentic-ai-landscape.md) into an OSS-first,
evidence-led 12-month plan. It is direction, not a release promise;
`DESIGN.md` retains milestone and architectural-decision history.

## Current state

As of 0.19.0, this is the released 0.19.0 picture: a complete local
qualification loop for bounded categorical decisions.

| Need | Interface | Established behavior |
|---|---|---|
| Price and collect | `plan`, `run` | Fixed or predeclared sequential budgets; callable, Strands, and LangGraph adapters |
| Reuse evidence | `assess` | Promptfoo, DeepEval test cases, and generic JSONL raw runs; aggregates refused |
| Qualify | report | Wilson-bound tri-state calls, per-route evidence, blindness, relations, and declared contracts |
| Admit and revisit | `snapshot`, `check`, `compare-evidence` | Versioned baselines, drift checks, isolation policy, and independent evidence-window comparison |
| Automate | terminal, JSON, JUnit, OTEL | CI-friendly outputs and privacy-minimized telemetry |

CI covers Python 3.10–3.14, enforces Ruff and at least 90% statement coverage,
and builds and smoke-tests the wheel. AgentKit and AgentCore assets exercise
real integration paths. These are strong implementation signals, but not
independent adoption. The project remains alpha until an external integration
and compatibility audit validate the public surface.

## Decision rules

- Build from observed adopter evidence, not a competitor checklist.
- Import raw ordered trials with provenance; never infer stability from
  aggregates.
- Require simulation and a written guarantee for statistical changes.
- Preserve backward compatibility unless a versioned schema migration has a
  demonstrated auditability benefit.
- A gate marked “defer” means document the unmet condition and stop; it does
  not mean ship an approximation.

## Phase 1: 0–3 months — validate the problem

| Item | User problem and intended outcome | Success metric | Dependencies and risks | Build/defer gate |
|---|---|---|---|---|
| Design-partner acquisition | With little external adoption, validation will not arrive by itself. Build a qualified pipeline through direct maintainer outreach, evaluation communities, integration partners, and one concise call for evidence. | 20 relevant teams contacted; six discovery conversations; three qualified pilot commitments; source and rejection reasons recorded | Clear fit/no-fit copy and ethical, targeted outreach; low response rates and unrepresentative networks | Run this before feature discovery; if 20 relevant teams have been contacted and fewer than three serious conversations result, revisit positioning and channels rather than lowering the pilot bar |
| Independent design partners | Maintainer-controlled examples do not prove usefulness. Observe real qualification decisions and publish credible case studies. | Three independent teams complete a trial; two redistributable evidence fixtures or case studies; findings logged, including failures | Acquisition pipeline, hands-on support, and permission to publish; selection bias and support burden | Continue feature work only where at least two teams share the problem; otherwise narrow the claim |
| Onboarding and category clarity | Users confuse stability with correctness or do not know whether their agent fits. Make fit, non-fit, and first result understandable in one session. | Five fresh-user walkthroughs; four reach an interpretable report in 15 minutes; no participant mistakes `TRUSTWORTHY` for correctness after reading the result | Stable quickstart and representative sample; risk of optimizing only for experts | Build copy/examples from observed confusion; defer UI work unless the CLI is the measured blocker |
| Integration demand discovery | LangSmith and telemetry exports vary, so guessed importers would be brittle. Collect real raw-run shapes and rank demand. | At least three samples from two organizations and two source systems; each can identify input, decision, trial order, and isolation or expose the missing field | Data-sharing/privacy constraints and changing exports | No vendor importer without three independent requests plus testable fixtures; publish a mapping recipe instead |
| Method validation | Unit tests do not independently validate coverage, optional-stopping behavior, or dependence sensitivity. Make the statistical claim reproducible and reviewable. | Public simulation notebook/script reproduces boundary behavior; review by one independent statistician or evaluation researcher; discrepancies become tracked decisions | Reviewer availability; simulations can reveal redesign needs | Fix correctness findings before integrations; defer new methods that lack a precise guarantee |

Acquisition starts with the public [design-partner pilot](docs/design-partners.md)
and the maintainer [acquisition playbook](docs/design-partner-playbook.md). These
make the funnel executable; the roadmap outcome remains open until the contact,
conversation, and pilot metrics are actually met.

Method validation now has a reproducible [simulation and exact-boundary
cross-check](docs/method-validation.md), including an independence sensitivity
model. It confirms conservative baseline admission under independent pairs,
documents Wilson's nominal rather than exact two-sided calibration, and shows
why declared isolation is load-bearing. Independent expert review remains open.

## Phase 2: 3–6 months — interoperate where demand is proven

| Item | User problem and intended outcome | Success metric | Dependencies and risks | Build/defer gate |
|---|---|---|---|---|
| LangSmith evidence import | Teams should qualify existing trials without duplicate model calls. Map raw repetitions and trajectories into AgentVerity evidence with explicit ordering and provenance. | Two external projects use it; golden fixtures cover export changes and rejection paths; no mandatory LangSmith runtime dependency | Phase 1 samples and a stable export/API contract; vendor drift and ambiguous sessions | Build only after the demand threshold above; defer when isolation or trial order cannot be recovered |
| OpenTelemetry/OpenInference ingestion | Traces should be reusable across backends without one adapter per vendor. Define a strict mapping for categorical trials. | Fixtures from at least two backends produce identical evidence; ambiguous/missing attributes fail with actionable diagnostics | OpenTelemetry/OpenInference conventions and real span samples; telemetry rarely carries reviewed contracts | Build an importer only if the mapping is unambiguous; otherwise ship a producer recipe or sidecar contract |
| Integration contract and fixture kit | Contributors need a stable way to add sources without weakening evidence. Make raw-run requirements and conformance tests reusable. | One independently contributed integration; all importers pass ordering, aggregate-refusal, provenance, and round-trip fixtures | Documented minimal protocol and review capacity; surface-area growth | Accept an integration only with a maintainer, fixtures, and a real adopter; otherwise keep it external |
| Cross-tool release-gate examples | Users need to see evaluator, trace system, and qualifier working together. Demonstrate complementarity rather than replacement. | Two reproducible examples use an external grader/runner plus AgentVerity; costs and non-guarantees are explicit | Partner fixtures and stable integrations; examples can become marketing without evidence | Publish only reproducible, version-pinned cases; defer unsupported logos and claims |

The integration contract now has shared ordered-run and aggregate fixtures,
and Promptfoo, DeepEval, and generic JSONL pass the same provenance, isolation,
ordering, refusal, and round-trip checks. The item remains open until an
independently contributed integration meets its adopter and maintenance gate.

## Phase 3: 6–12 months — harden provenance and prepare 1.0

| Item | User problem and intended outcome | Success metric | Dependencies and risks | Build/defer gate |
|---|---|---|---|---|
| Verifiable provenance | Declared isolation does not prove distinct executions, and snapshots cannot fully identify the tested target. Preserve enough identity for audits without collecting secrets. | External cases validate optional trial/execution IDs and target revision identities; privacy review completed; old evidence remains readable | Schema design and real audit requirements; identifiers can leak or imply guarantees they do not provide | Version the schema only after two external cases require the same fields; otherwise retain declarations and caveats |
| Statistical hardening | Individual route intervals may be mistaken for a suite-wide guarantee, and correlated trials can be overconfident. Quantify or explicitly bound those limitations. | Simulation suite covers dependence and multiple routes; docs distinguish individual and family-wise claims; one reviewed decision on optional suite-wide control | Phase 1 method review; added conservatism may make call budgets impractical | Build an opt-in method only with a named guarantee and acceptable measured cost; otherwise document and defer |
| Ecosystem partnerships | A qualifier is useful only when it fits existing evaluation stacks. Establish maintained, reciprocal interoperability. | Three active ecosystem relationships; two partner-maintained fixtures or references; three independent public cases in total | Partner priorities and maintenance ownership; concentration risk | Count a partnership only when users can run an artifact, not when a logo or announcement exists |
| 1.0 readiness | Adopters need durable APIs, schemas, and migration behavior. Complete the alpha exit criteria in `STABILITY.md`. | Public API/CLI/schema audit; cross-version fixtures; clean security review; independent integration; documentation parity; supported-version policy | All prior evidence and maintainer capacity; premature stability can freeze mistakes | Release 1.0 only when every criterion is evidenced; otherwise continue 0.x without deadline pressure |

The current loaders now read and canonically rewrite durable fixtures produced
by 0.16.0. This closes the earlier-minor fixture check for the supported schema
set; the final API/CLI audit, security review, and independent integration keep
1.0 readiness open.

A machine-checked 0.19.0 inventory now makes top-level Python signatures and
parser-enforced CLI drift reviewable. This is a preliminary surface audit; the
remaining class, behavior, documentation, security, and adopter checks keep the
1.0 gate open.

All six commands now execute against a reviewed 0/1/2 behavior matrix in CI.
This closes process-classification drift, not public class members,
help/documentation parity, security review, or adopter validation.

Every current data surface now executes against a reviewed 0.19.0 retention
matrix covering inputs, observations, fingerprints, errors, decisions, and
relation names. This establishes the implementation baseline and corrects an
overbroad snapshot claim; the independent security review and wider threat
model remain open before 1.0.

Representative public Python boundaries now execute against a published-wheel
return-semantics fixture, including all ten canonical run statuses and the
planning, assessment, drift, snapshot, and reporting families. Public class
members, exact help/documentation parity, independent adoption, and release
security review keep the final 1.0 audit open.

## Delivery and release strategy

Each roadmap item is one reviewable branch and pull request. Finish its stated
artifact and checks, request independent review, apply accepted feedback, and
merge before starting the next item. Do not combine unrelated roadmap items to
manufacture a larger release. A PR is the unit of review; a package release is
triggered only by user-visible package behavior, following `RELEASING.md`.

| Change delivered | Release treatment |
|---|---|
| Strategy, research, outreach records, evidence, or internal documentation only | Merge without a PyPI release; GitHub is the delivery surface |
| Backward-compatible importer, CLI option, or public API capability | Normally the next 0.x minor release, with a dated changelog and migration notes where relevant |
| User-facing defect fixed without changing accepted inputs or contracts | Patch release |
| Evidence-schema, admission-policy, or statistical guarantee change | 0.x minor release only after ADR, simulation, cross-version fixtures, and explicit compatibility notes |
| 1.0 | Release only when every `STABILITY.md` criterion and the Phase 3 gate is evidenced; never release it to satisfy a calendar target |

Batch multiple changes that land on the same day when they belong to one
coherent release, but do not let a completed user-visible change sit
unreleased. After publication, verify the GitHub Release, PyPI version, clean
installation, and CLI smoke test as required by `RELEASING.md`.

## Ongoing scorecard

Review quarterly: independent active users; completed qualification runs;
public and private case studies; time to first interpretable result; evidence
reused without new model calls; external integration requests and contributors;
schema rejection reasons; false-green or misleading-report incidents; and
maintenance cost per integration. Stars and downloads are distribution signals,
not proof that the admission policy works.

## Permanent boundaries

AgentVerity will not become a correctness or safety judge, production agent
server, trace database, dashboard suite, red-team scanner, general benchmark,
or open-ended response scorer. It may qualify a bounded categorical judge or
trajectory equivalence relation, but it does not validate that judge's rubric.
Traffic weighting may be reported beside risk-weighted route evidence, never
used as a substitute for semantic coverage. Multi-turn and partial-order
trajectories remain deferred until independent cases establish a bounded
decision representation that the current model cannot express.
