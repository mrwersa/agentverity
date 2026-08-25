# Roadmap

AgentVerity qualifies repeated categorical AI-agent evidence before it becomes
a **regression reference**. It does not decide whether behaviour is correct,
safe, or useful. This roadmap turns the
[agentic AI landscape review](docs/agentic-ai-landscape.md) into an OSS-first,
outcome-gated plan. Horizons guide sequencing rather than promise dates;
`DESIGN.md` retains shipped milestones and architectural decisions.

## Current state

As of 0.22.0, the released 0.22.0 picture is a complete local qualification
loop for bounded categorical decisions.

| Need | Interface | Established behaviour |
|---|---|---|
| Price and collect | `plan`, `run` | Fixed, live-curtailed fixed, or predeclared sequential budgets; callable, Strands, and LangGraph adapters |
| Reuse evidence | `assess` | Promptfoo, DeepEval test cases, and generic JSONL raw runs; aggregates refused |
| Qualify | report | Wilson-bound tri-state calls, per-route evidence, blindness, relations, and declared contracts |
| Admit and revisit | `snapshot`, `check`, `compare-evidence` | Versioned regression references, drift checks, isolation policy, and independent evidence-window comparison |
| Automate | terminal, JSON, JUnit, OTEL | CI-friendly outputs and privacy-minimised telemetry |

Method validation, compatibility inventories, durable reader fixtures, CLI
exit contracts, return-semantics checks, and a data-retention matrix make the
current claims reviewable. The integration conformance kit covers all in-tree
importers. Independent adoption, an independently maintained integration,
expert statistical review, and the final security and 1.0 reviews remain open.

## Product model

AgentVerity evaluates a declared categorical projection of a trace, not the
complete trace:

```text
trace
  -> declared categorical projection
  -> ordered repeated decisions
  -> disjoint-pair flips
  -> repeatability qualification
```

Acceptability review and repeatability qualification are independent
prerequisites. When both hold, a snapshot may preserve the reviewed behaviour
as a regression reference. A later release can then be checked against that
reference or compared as a separate evidence window.

The product develops through four connected pillars:

- **Evidence semantics:** projection, decision identity, ordering, pairing,
  isolation, and provenance must be explicit.
- **Regression-reference lifecycle:** collect or import, qualify, review,
  snapshot, check, and compare without conflating repeatability with quality.
- **Interoperability:** consume evidence from evaluators and trace systems
  without recreating their scoring or observability features.
- **Statistical trust:** state the independence, optional-stopping, per-case,
  dependence, and multiple-comparison limits of every guarantee.

### Terminology

Existing API values and schema literals remain stable while explanatory prose
uses the narrower research terms.

| Current API term | Preferred explanatory term | Meaning |
|---|---|---|
| `deterministic` | repeatability qualified or admitted | Evidence supports a flip rate below the declared tolerance; it does not prove zero randomness |
| `stochastic` | repeatability rejected | Evidence supports a flip rate above the declared tolerance |
| `undecided` | inconclusive | Neither directional conclusion is supported |
| snapshot | regression-reference snapshot | Reviewed behaviour preserved for a later comparison |
| baseline | regression reference in new prose | The expected reviewed behaviour, not a competing model or experiment |

Any API alias or schema migration requires a separate pre-1.0 decision. The
current strings remain the machine contract until then.

## Decision rules

- Build terminology and the proven curtailment method from current evidence;
  gate new schemas, statistical guarantees, and vendor importers on external
  cases.
- Import raw ordered trials with provenance; never infer repeatability from
  aggregates.
- Require simulation, a written guarantee, and an ADR for statistical changes.
- Preserve backward compatibility unless a versioned migration has a
  demonstrated auditability benefit.
- Prefer an existing snapshot, report, or provenance field over a duplicate
  manifest or explanation surface.
- A “defer” gate means record the unmet condition and stop. It does not mean
  ship an approximation.

## Now–6 weeks: clarify and productise the proven method

| Item | User problem and intended outcome | Success metric | Dependencies and risks | Build/defer gate |
|---|---|---|---|---|
| Terminology and concepts | “Baseline” is overloaded, while “deterministic” can sound absolute. Give readers one path from trace projection to regression reference without breaking machine contracts. | Active entry-point prose uses regression reference and within-condition repeatability; the terminology map is linked; five fresh-user walkthroughs find the fit boundary | Existing links and literal API values; a broad mechanical rename could corrupt history or compatibility artefacts | Change explanatory prose now; defer public aliases and file/schema renames to a separate reviewed migration |
| Live fixed-budget curtailment — delivered in 0.21.0 | A run can keep spending after admission is mathematically unreachable. Stop futile collection without creating early admission. | `--curtail` stops at the first unreachable pair; terminal and machine reports retain stop pair, avoided work, and reason; exact-boundary replays and two million simulated paths preserve every fixed-endpoint call | One ordered, predeclared endpoint; partial evidence receives status `curtailed` and no final repeatability class | Keep the default fixed path unchanged; extend only with evidence for parallel or route-specific endpoint semantics |
| Observed-count planning — delivered in 0.22.0 | After seeing flips, users could price only a fixed-rate projection or call a Python helper. Expose the audited fixed-count inverse without implying that its optimistic continuation is an early-admission rule. | `plan --observed FLIPS/PAIRS` reports the earliest all-agree total and, when supplied, whether a predeclared maximum remains reachable; examples reproduce the reviewed 1/73, 3/73, 4/73, and 8/73 boundaries | `best_case_admission_pairs` and its exact-boundary tests; a bare `--flips` option would omit evidence needed to validate the observation | Keep suite planning unchanged; any new planning assumption must remain explicit in `--help` and output |
| Two-budget method validation | The public validation exercises the 73-pair operating floor but not a larger fixed endpoint that can admit limited flips. Show how endpoint choice changes admission and curtailment savings without changing the rule. | The versioned validation artefact and prose add a predeclared 146-pair scenario; exact enumeration and replay tests agree; limitations remain attached to the result | Additional simulation cost and a schema revision for the validation artefact, not a product evidence schema | Extend the validation harness before making comparative efficiency claims; do not infer cross-time validity from a larger within-window budget |
| Design-partner acquisition | Maintainer-controlled studies do not establish external usefulness. Keep validation running alongside no-regret product work. | 20 relevant teams contacted; six discovery conversations; three qualified pilot commitments; source and rejection reasons recorded privately | Clear fit/no-fit copy, ethical outreach, and support capacity; public ecosystem participation can be mistaken for adoption | If 20 relevant teams yield fewer than three serious conversations, revisit positioning and channels rather than lowering the pilot bar |
| Independent cases | Users need evidence that the qualification decision changes real release work. | Three teams complete a pilot; two redistributable fixtures or case studies include costs, refusals, and negative findings | Permission to publish and representative systems; selection bias | Do not generalise a feature or claim from one maintainer-owned workload |

Acquisition uses the public [design-partner pilot](docs/design-partners.md) and
the private-process [acquisition playbook](docs/design-partner-playbook.md).
Entries in the public ecosystem log do not count as contacts, discovery, or
pilots unless a separate interaction satisfies the playbook definition.

## 1–3 months: make evidence understandable and auditable

| Item | User problem and intended outcome | Success metric | Dependencies and risks | Build/defer gate |
|---|---|---|---|---|
| Onboarding and result explanation | Users can mistake qualification for correctness or fail to understand an inconclusive result. Improve existing reports before adding another command. | Four of five fresh users reach an interpretable result within 15 minutes; none mistakes qualification for correctness; recurring questions become tested guidance | Representative walkthroughs; report prose is a compatibility-sensitive surface | Add `explain` only if users need a post-hoc workflow that existing summaries and refusals cannot serve |
| Retrospective curtailment replay | Teams with ordered evidence cannot see how much a predeclared impossibility rule would have saved. Replay the fixed-endpoint rule without rewriting the historical qualification. | `assess` reports the first unreachable pair and avoided pairs for each eligible series; the original endpoint call remains visible; replay fixtures match live curtailment path by path | Ordered raw observations, one declared endpoint, and preserved errors; post-hoc endpoint selection would exaggerate savings | Build only as a labelled counterfactual unless collection provenance proves the endpoint and rule were predeclared; never create an early class |
| Window-aware claim language | A single collection window can be mistaken for evidence of repeatability across deployments or time. Make the estimand visible at the point of use. | Text and machine reports distinguish “within this window” from an across-window claim and say when the evidence cannot support the latter | Collection-window identity is not yet a structured contract; caller provenance may be incomplete or sensitive | Improve conservative report guidance first; add structured fields only through the projection/provenance gate below |
| Decision-projection identity | A change to trace-to-decision projection can silently change the measured object. Define how name, version, and bounded domain belong in provenance. | ADR covers identity, privacy, comparison, and migration; two external audit cases agree on the required fields | Existing arbitrary provenance and expected decisions may already suffice; identifiers can leak details or imply validation | Use existing provenance first; change evidence or snapshot schemas only after two external cases require the same structured contract |
| Regression-reference view | Snapshot evidence is machine-readable but not always easy to audit. Make the existing snapshot legible rather than inventing a second manifest. | One human-readable view exposes projection, tolerance, confidence, pairing, budget, observed evidence, isolation, approval, and limits from the snapshot/report source of truth | Some fields are not yet structured; duplicated artefacts can drift | Render existing data when possible; defer new fields to the projection/provenance gate |

## 3–6 months: interoperate through evidence-preserving standards

| Item | User problem and intended outcome | Success metric | Dependencies and risks | Build/defer gate |
|---|---|---|---|---|
| EvalPort repetition contract | A vendor-neutral interchange can preserve attempts, ordering, and isolation for several producers at once. Contribute conformance evidence rather than create a private dialect. | A merged repetition/isolation contract passes shared ordered-run and aggregate-refusal fixtures; one external producer and consumer round-trip it | The public RFC may change or stall; a specification can promise more than implementations enforce | Supply fixtures if the RFC lands; keep the bridge external while semantics remain unsettled |
| LangSmith evidence path | Teams should reuse repeated experiments without duplicate model calls. Prefer the EvalPort bridge, with a direct importer only when it cannot preserve required evidence. | Two external projects qualify exported repetitions; case identity, attempt order, decision, provenance, and isolation survive; no mandatory LangSmith dependency | Stable export/API samples and EvalPort support; CSV or aggregate views may flatten repetitions | Build direct support only when two adopters demonstrate a gap and provide testable raw fixtures |
| OpenTelemetry/OpenInference mapping | Trace standards identify agents, tools, and evaluators but do not by themselves establish AgentVerity’s evidence contract. Publish the missing requirements clearly. | A recipe maps fixtures from two backends to identical evidence or produces actionable refusals for ambiguous order/isolation | Real span samples and a declared categorical projection; sensitive trace attributes | Build ingestion only when the mapping is unambiguous across two backends; otherwise keep a producer recipe |
| Maintained integration contract | In-tree adapters must not weaken ordering, provenance, isolation, or aggregate refusal. | Two external adopters, versioned success and rejection fixtures, optional dependencies, a named maintainer, and one independently contributed integration | Contributor and maintenance capacity; vendor drift | Keep integrations external when ownership or a real adopter is missing |

## 6–12 months: extend the method and prepare 1.0

| Item | User problem and intended outcome | Success metric | Dependencies and risks | Build/defer gate |
|---|---|---|---|---|
| Across-window qualification research | A within-window result does not establish repeatability across time, model updates, or deployments. Determine whether repeated independent windows support a useful second claim without pretending they repair dependence inside a window. | An ADR defines the cross-time estimand, window unit, aggregation rule, and error guarantee; simulation covers unequal windows, drift, and clustered trials; an independent statistician reviews the result | Multiple genuinely independent windows and stable projection identity; simply multiplying a one-window budget has no cross-time guarantee | Do not add `--windows`, a report class, or schema fields until the guarantee and affordable budget are demonstrated; document and defer if they are not |
| Identity-aware qualification | Pairwise disagreement can be low while decisions consistently disagree with an accepted category. Research reference fidelity separately from repeatability. | ADR and simulation distinguish pairwise disagreement `q` from mismatch `r = P(D != d*)`; a precise guarantee and independent review precede any API | Expected decisions already exist, but a second rate changes statistical meaning and call budgets | Do not implement from intuition or reuse `q` as a proxy for `r`; defer if the guarantee or cost is not acceptable |
| Suite-wide statistical decision | Per-case intervals can be mistaken for a family-wise guarantee. Determine whether control across routes/cases is useful at an affordable budget. | Simulation quantifies cost; docs distinguish individual and suite-wide claims; one reviewed build/defer decision is recorded | Design-partner risk priorities and method review; conservatism may make evidence unaffordable | Ship only an opt-in method with a named guarantee and measured cost; otherwise document and defer |
| Structured provenance | Auditors may need projection and target revision identity beyond declarations. Preserve only fields justified by real cases. | Two external audits require the same fields; privacy review passes; old evidence remains readable or has an explicit migration | Schema design and data minimisation; identifiers are not anonymisation | No schema change for speculative completeness |
| 1.0 readiness | Adopters need durable APIs, schemas, and migration behaviour. Complete every criterion in `STABILITY.md`. | Final API/CLI/schema and documentation review; compatibility fixtures; independent integration; independent security and statistical review; supported-version policy | Evidence from prior phases and maintainer capacity; premature stability can freeze confusing terms | Release 1.0 only when every criterion is evidenced; continue 0.x without deadline pressure otherwise |

## Delivery and release strategy

Each roadmap item is one reviewable branch and pull request. Finish its stated
artefact and checks, request independent review, apply accepted feedback, and
merge before starting the next implementation item. A PR is the unit of review;
a package release is triggered only by user-visible package behaviour under
`RELEASING.md`.

| Change delivered | Release treatment |
|---|---|
| Roadmap, research, terminology prose, outreach records, or internal documentation | Merge without a PyPI release; GitHub is the delivery surface |
| Backward-compatible importer, CLI option, or public Python capability | Normally the next 0.x minor release with a dated changelog |
| User-facing defect fixed without changing accepted inputs or contracts | Patch release |
| Evidence schema, admission policy, terminology alias, or statistical guarantee | 0.x minor only after ADR, simulation where applicable, cross-version fixtures, and compatibility notes |
| 1.0 | Release only when every `STABILITY.md` criterion and the final phase gate is evidenced; never release to satisfy a calendar target |

## Ongoing scorecard

Review quarterly: active independent users; completed qualification runs;
public and private case studies; time to first interpretable result; evidence
reused without new model calls; curtailment savings; integration requests and
external contributors; schema rejection reasons; misleading-report incidents;
and maintenance cost per integration. Stars and downloads are distribution
signals, not proof that the qualification policy works.

## Permanent boundaries

AgentVerity will not become a correctness or safety judge, production agent
server, trace database, dashboard suite, red-team scanner, general benchmark,
or open-ended response scorer. It may qualify a bounded categorical judge or
trajectory projection, but it does not validate the rubric or projection.
Traffic weighting may be reported beside risk-weighted route evidence, never
used instead of semantic coverage. Multi-turn and partial-order trajectories
remain deferred until independent cases establish a bounded decision
representation that the current model cannot express.
