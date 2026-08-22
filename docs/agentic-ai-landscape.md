# Agentic-AI Evaluation Landscape and Strategy

**Research date:** 22 August 2026

**Audience:** AgentVerity maintainers and technical adopters

## Executive verdict

AgentVerity should define a narrow category: an **evidence-qualification layer
for repeated categorical agent decisions**. Evaluators decide whether an
answer or trajectory is acceptable; observability systems record what
happened; AgentVerity decides whether repeated evidence is sufficiently
stable, covered, independent, and non-vacuous to admit as a regression
baseline.

That distinction is the opportunity. Repetition itself is no longer unusual:
LangSmith, Promptfoo, and Phoenix all expose repeated experiment runs. The
defensible wedge is the admission policy around those runs—confidence-bound,
tri-state conclusions; disjoint pairs; per-route evidence; declared decision
contracts; isolation provenance; and refusal to turn weak evidence green.
AgentVerity should not become another scoring library, trace store, benchmark,
or agent host.

This conclusion combines verified repository behavior and primary or official
external sources. Where a vendor's reviewed documentation did not establish a
capability, this report says so; absence from the documentation is not proof
that no private or newer capability exists. Strategic judgments are labelled
as recommendations or inferences.

### Review method

The repository audit covered all 26 package Python files, 36 test modules, 25
Markdown files, workflows, packaging and release configuration, schemas, and
the example tree, and sampled the 117-commit history for conventions and
maturity signals. Large committed evidence was inspected structurally—schema
versions, case and observation counts, decision/route distributions, isolation,
cost, and provenance—rather than treating repeated records as separate design
material. Implementation claims were cross-checked between source, tests,
documentation, and generated assets. External comparisons prioritize current
official documentation, project repositories, standards bodies, and primary
papers; the OpenAI row uses official OpenAI documentation.

## What must be evaluated

Agent evaluation is a lifecycle, not one score:

1. Curate representative datasets, risk cases, expected decisions, and
   metamorphic variants.
2. Run deterministic software tests and validate tool schemas and permissions.
3. Grade outcomes with code, reference answers, humans, or calibrated LLM
   judges.
4. Inspect tool choices, intermediate steps, and complete trajectories.
5. Repeat trials to expose stochasticity; simulate users and tool failures;
   red-team security boundaries.
6. Gate releases against reviewed baselines, then trace and evaluate production
   traffic online.
7. Feed incidents, human review, and drift discoveries back into datasets,
   contracts, and governance.

Anthropic's agent-evaluation guidance similarly separates tasks, trials,
graders, transcripts, outcomes, and the harness, and recommends multiple
trials because agent behavior varies. It also warns that LLM judges need
calibration against expert human judgment
([Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).
The 2026 ACL survey describes a move toward more realistic and continuously
updated benchmarks while identifying gaps in robustness, safety,
cost-efficiency, and scalable fine-grained evaluation
([Findings of ACL](https://aclanthology.org/2026.findings-acl.1330/)). AgentVerity
addresses one gap inside this lifecycle: the quality of repeated categorical
evidence. It does not replace the other stages.

Reliability research reinforces the need to look beyond mean task success.
tau-bench introduced `pass^k` to measure whether an agent succeeds consistently
over multiple tool-agent-user trials
([paper](https://arxiv.org/abs/2406.12045)). ReliabilityBench extends the
discussion to repeated consistency, semantic perturbations, and tool/API
faults, although it remains a preprint rather than an established standard
([preprint](https://arxiv.org/abs/2601.06112)). NIST's voluntary AI RMF calls
for repeatable, documented, and scalable testing, evaluation, verification,
and validation plus post-deployment monitoring
([NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)).

## Landscape

The table summarizes capabilities established in reviewed official
documentation. “No documented admission rule” means the reviewed material did
not describe a confidence-bound policy equivalent to AgentVerity's; it is not
a claim that a platform cannot calculate statistics.

| Product | Evaluation center | Repetition and statistical treatment | Agent path, lifecycle, and deployment | Relationship to AgentVerity |
|---|---|---|---|---|
| **DeepEval** | Pytest-oriented metrics, datasets, component and end-to-end evaluation | Repeated testing is possible; no documented conservative baseline-admission rule | Trace-based agent and component evaluation, CI, integrations, and managed production evaluation ([docs](https://deepeval.com/docs/getting-started-agents)) | Complementary grader and test harness; current AgentVerity test-case bridge reduces duplicate authoring |
| **LangSmith** | Offline experiments and online evaluators | `num_repetitions` retains individual runs and aggregate views; no documented confidence-bound admission policy ([docs](https://docs.langchain.com/langsmith/experiment-configuration)) | Output, single-step, and trajectory evaluation; tracing and production feedback ([concepts](https://docs.langchain.com/langsmith/evaluation-concepts), [agent guide](https://docs.langchain.com/langsmith/evaluate-complex-agent)) | High-priority evidence source if adopters supply stable export examples |
| **Promptfoo** | Configurable assertions, model judges, red teaming, and CI | CLI and test-level repeats measure variance; no documented route-specific statistical admission ([tests](https://www.promptfoo.dev/docs/configuration/test-cases/)) | Tool/trajectory assertions and coding-agent evaluation ([assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/), [agent guide](https://www.promptfoo.dev/docs/guides/evaluate-coding-agents/)) | Complementary evaluator; raw-run import already supported. OpenAI announced an agreement to acquire Promptfoo in March 2026, subject to closing conditions ([OpenAI announcement](https://openai.com/index/openai-to-acquire-promptfoo/)) |
| **OpenAI Evals and Agents** | Datasets, evaluation runs, and graders around vendor-native agents | Evaluation runs operate over declared data; reviewed docs do not establish AgentVerity-style admission | Agent orchestration, tools, tracing, and evaluation workflows ([Evals](https://developers.openai.com/api/docs/guides/evals), [Agents](https://developers.openai.com/api/docs/guides/agents)) | Potential upstream runner; AgentVerity remains provider-neutral and offline |
| **Braintrust** | Code/LLM scorers, datasets, and experiments | Experiments compare scores; no reviewed bounded admission rule | Playground-to-CI workflow, online scoring, and production feedback ([docs](https://www.braintrust.dev/docs/evaluate)) | Complementary experiment and feedback platform |
| **Phoenix** | Open-source tracing, datasets, experiments, and evaluators | Repetitions show individual results and averages; no documented conservative admission rule ([docs](https://arize.com/docs/phoenix/datasets-and-experiments/how-to-experiments/repetitions)) | OpenTelemetry/OpenInference traces, experiments, and self-hosted observability ([docs](https://arize.com/docs/phoenix/)) | Natural interoperability target and complementary trace store |
| **Langfuse** | Datasets, experiments, traces, and evaluators | Supports item- and run-level evaluators; reviewed docs do not establish bounded baseline admission | SDK/HTTP experiments, CI, OpenTelemetry ingestion, managed or self-hosted deployment ([SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk), [API](https://langfuse.com/docs/api-and-data-platform/features/experiments-api)) | Complementary observability/evaluation system and possible evidence source |
| **MLflow** | Broad GenAI lifecycle, datasets, scorers, judges, and tracking | Experiment comparison; no reviewed route-specific admission rule | Trace-derived/manual datasets, conversation simulation, tracking server ([datasets](https://mlflow.org/docs/latest/genai/datasets/), [scorers](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/index.html)) | Broader engineering platform; integration is more credible than feature competition |
| **TruLens** | Trace-based feedback functions and runtime evaluation | Metric feedback; no reviewed repeated-run confidence gate | Agent trace, tool-selection, and tool-quality feedback ([docs](https://www.trulens.org/docs/), [feedback reference](https://www.trulens.org/reference/trulens/feedback/)) | Complementary evaluator and instrumentation layer |
| **Ragas** | RAG and agent-quality metrics | Metric evaluation, not documented baseline qualification | Tool-call and agent-goal metrics, especially for retrieval systems ([docs](https://docs.ragas.io/en/stable/), [paper](https://arxiv.org/abs/2309.15217)) | Complementary domain scorer, not a direct substitute |
| **AWS AgentCore Evaluations** | Managed on-demand, batch, and online evaluation | Evaluates sessions/traces with LLM or code evaluators; no reviewed confidence-bound admission | Session-, trace-, and tool-call evaluation, reference trajectories, OpenTelemetry/OpenInference-shaped telemetry ([types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations-types.html), [overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/how-it-works-evaluations.html)) | Hosted lifecycle platform; AgentVerity can qualify exported categorical decisions |

Operationally, the products make different tradeoffs. “Baseline” below means
an experiment or regression comparison, not necessarily a statistically
qualified baseline.

| Product | Baseline and CI | Provenance and observability | Hosting, licence, and interoperability |
|---|---|---|---|
| **AgentVerity** | Explicit reviewed snapshots, drift checks, JUnit/JSON release gates | Versioned raw evidence, contracts, isolation, fingerprints, and one summary OTEL span; no trace store | Local-first, Apache-2.0, zero mandatory runtime dependencies |
| **DeepEval** | Pytest regression workflow and CI | Component traces and managed experiment/production records | Local Apache-2.0 framework plus Confident AI service ([repository](https://github.com/confident-ai/deepeval)) |
| **LangSmith** | Dataset experiments, reference comparisons, and CI workflows | First-class traces, feedback, and experiment metadata | Managed LangChain service with enterprise deployment options and broad SDK integrations |
| **Promptfoo** | Config baselines/assertions and CI gating | Evaluation artifacts and provider outputs, but not a general production trace store | Local MIT CLI with hosted/enterprise offerings ([repository](https://github.com/promptfoo/promptfoo)) |
| **OpenAI** | Stored eval definitions/runs callable from automation | Native agent traces and API resource identity | Managed proprietary API and official SDKs |
| **Braintrust** | Immutable comparable experiments and CI | Traces, annotations, scorers, datasets, and online feedback | Primarily managed proprietary service with SDK/API integration |
| **Phoenix** | Dataset experiments, comparisons, and pytest CI | OpenTelemetry/OpenInference trace provenance and evaluators | Self-hosted or cloud; Elastic License 2.0 ([licence](https://github.com/Arize-ai/phoenix/blob/main/docs/phoenix/self-hosting/license.mdx)) |
| **Langfuse** | Dataset experiments and CI-capable SDK/API | OTEL traces, prompts, scores, and experiment metadata | Cloud or self-hosted; core MIT except enterprise folders ([licence](https://github.com/langfuse/langfuse/blob/main/CONTRIBUTING.md#license)) |
| **MLflow** | Tracked runs and experiment comparison; CI is user-assembled | Tracking server joins datasets, traces, scorers, and model/application versions | Self-hosted or managed through platform vendors; Apache-2.0 core ([repository](https://github.com/mlflow/mlflow)) |
| **TruLens** | Recorded app versions and feedback comparisons; CI is library-driven | Instrumented records, spans, and runtime feedback | Open-source MIT library with ecosystem/platform integrations ([repository](https://github.com/truera/trulens)) |
| **Ragas** | Dataset score comparison; CI is library-driven | Evaluation samples and metric results rather than full operational observability | Local Apache-2.0 library and integrations ([repository](https://github.com/vibrantlabsai/ragas)) |
| **AWS AgentCore** | Managed evaluation jobs can support release workflows | AWS sessions and OTEL/OpenInference traces, with online evaluation | Managed proprietary AWS service and API |

Licensing and editions can change. This report does not treat “open source” as
equivalent to feature parity or unrestricted managed use; adopters should
verify the current licence and deployment terms before selection.

OpenTelemetry semantic conventions and the OpenInference conventions provide
the strongest cross-vendor transport opportunity
([OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/),
[OpenInference](https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md)).
They describe telemetry, not automatically the trial ordering, categorical
decision identity, isolation, or reviewed contract that AgentVerity needs.
An importer must therefore reject ambiguous mappings rather than infer them.

## AgentVerity baseline

### Verified implementation

The 0.18.3 package is a zero-mandatory-dependency Python 3.10–3.14 library and
CLI. Its public workflow is:

- `plan` prices a suite before calls are made;
- `run` collects paired repeated observations through callable, Strands, or
  LangGraph adapters;
- `assess` imports Promptfoo, DeepEval test cases, or generic JSONL evidence;
- `snapshot` admits reviewed evidence, `check` compares a later run with that
  baseline, and `compare-evidence` compares two collection windows;
- terminal, versioned JSON, JUnit XML, and privacy-minimized OpenTelemetry
  reporting serve people, CI, and telemetry backends.

The statistical core forms disjoint observation pairs and places a Wilson
interval around the flip rate. It calls a route deterministic only when the
upper bound is below the declared tolerance, stochastic only when the lower
bound exceeds it, and otherwise returns `undecided`. At the default 5%
tolerance, proving stability with zero flips requires 73 independent pairs.
Optional sequential collection uses predeclared checkpoints and alpha
spending rather than repeatedly peeking at a fixed-sample interval.

The evidence model carries decision contracts, intended/observed/admissible
route reach, critical-route requirements, blindness/skew diagnostics,
metamorphic relations and vacuity checks, per-route budgets, typed
no-decision outcomes, and isolation provenance. `shared-session` evidence is
refused for baseline admission; unknown isolation retains a caveat. Evidence,
telemetry, snapshots, and decision suites are versioned as
`agentverity.evidence/v2`, `agentverity.telemetry/v2`,
`agentverity.snapshot/v4`, and `agentverity.decision-suite/v1`; collected runs
use `agentverity.run/v2`. Raw evidence can contain prompts and outputs, while
the OpenTelemetry summary intentionally omits prompts, outputs, fingerprints,
labels, relation names, and errors; fingerprints are identifiers, not
anonymization.

### Validation and maturity

On 22 August 2026 the full suite collected 801 tests: 796 passed, five skipped,
and statement coverage was 95.65% against a 90% CI floor. CI also spans Python
3.10–3.14, Ruff, package construction, and wheel smoke tests. Committed AgentKit
evidence contains 4,380 model calls across three models; its result demonstrates
the core caveat empirically—a highly stable agent can still be less correct.
The AgentCore canary validates production-shaped integration but has only six
pairs per route, so it is not a per-route certificate.

Maturity is the principal weakness. The repository was created on 24 July
2026 and, as of the research date, public adoption signals remained
single-digit and the contribution history was maintainer-led. These are crude
indicators, not quality measures, but they show that independent validation is
not yet established
([repository snapshot](https://github.com/mrwersa/agentverity)). The project
correctly remains alpha: it has neither a full public compatibility audit nor
demonstrated independent adopters.

### Limitations that must stay visible

- Stability is not correctness, safety, semantic coverage, or usefulness.
- Independence is declared provenance, not proof; correlated trials can make
  intervals overconfident.
- Per-route intervals are individual claims, not a suite-wide simultaneous
  guarantee.
- Categorical decisions and finite trajectory equivalence fit; open-ended
  answer quality does not.
- Conservative evidence can be expensive, especially for rare routes.
- Import breadth is narrow, there is no collaboration dashboard, and several
  important examples remain maintainer-controlled.

## Positioning

**Category.** Evidence qualification and baseline admission for stochastic,
bounded agent decisions.

**Ideal users.** Teams shipping routers, tool selectors, policy decisions,
finite workflow transitions, or categorical LLM judges where a false-green
regression baseline is costly. They already have cases and a runner or can use
the small built-in harness; they need an auditable release decision more than
another score dashboard.

**Jobs to be done.** Determine the call budget before testing; distinguish
stable, unstable, and insufficient evidence; find which route is weak; prevent
blind or shared-session evidence from becoming a baseline; preserve the
contract and provenance behind a release gate; and compare later evidence
without rerunning the original platform.

**Complements.** DeepEval, Promptfoo, Ragas, and custom graders judge quality;
LangSmith, Braintrust, Phoenix, Langfuse, MLflow, OpenAI, and AgentCore run,
trace, and operate agents; security tools and red teams test abuse paths.
AgentVerity can consume the bounded decisions those systems produce.

**Substitutes.** A team may accept raw rerun averages, write its own bootstrap
or confidence policy, or use an experiment platform's comparison view. Those
are reasonable substitutes when consequences are low or the policy does not
need to be portable and auditable.

**Recommendation.** Own the sentence: *“Is this repeated categorical evidence
strong enough to freeze?”* Do not claim generic agent reliability. The wedge
is conservative admission, not the Wilson formula alone: the defensible unit
is statistics plus contracts, route semantics, provenance, schemas, reports,
and explicit refusal behavior.

## SWOT and opportunity

| Strengths | Weaknesses |
|---|---|
| Narrow, intelligible release question; conservative tri-state semantics; route-level evidence; offline and provider-neutral; versioned evidence; low dependency and hosting burden | New category requires explanation; negligible independent adoption; large call budgets; independence is asserted; limited importers; no UI or team workflow; narrow applicability |

| Opportunities | Threats |
|---|---|
| Open evidence-qualification contract across evaluation platforms; qualify categorical LLM judges as well as agents; OpenTelemetry/OpenInference-shaped import; regulated and high-consequence release gates; partner case studies; reusable statistical test assets | Horizontal platforms can add confidence policies; averages may be “good enough”; standards and exports may move; users may confuse stability with quality; integration maintenance can consume the project; a commercial push could erode OSS trust |

OpenAI's announced agreement to acquire Promptfoo is a concrete encroachment
signal: evaluation, red teaming, and vendor-native agent infrastructure are
consolidating. The announcement said the transaction remained subject to
customary closing conditions
([OpenAI announcement](https://openai.com/index/openai-to-acquire-promptfoo/));
Promptfoo's repository subsequently describes the project as part of OpenAI
and still MIT-licensed ([repository](https://github.com/promptfoo/promptfoo)).
That makes competing horizontally less credible and strengthens the case for
a portable admission primitive that can operate across those stacks.

The market signal is directional, not a market-size estimate. LangChain's
vendor survey of more than 1,300 respondents reports quality as the leading
production barrier and widespread use of observability, offline evaluation,
and human or LLM-based review; its sampling and self-reporting limit
generalization ([survey](https://www.langchain.com/state-of-agent-engineering)).
The important inference is that evaluation stacks are becoming layered. A
small, interoperable qualifier can matter without owning execution or traces.

An OSS-first distribution model is appropriate: publish evidence fixtures,
method validation, and strict schemas; integrate with systems that own traces
and graders. Optional later commercial paths—hosted evidence retention,
policy administration, audit exports, or enterprise support—should be tested
only after independent demand. They should never make the core admission
method opaque or cloud-only.

## Strategic boundaries

Permanently defer correctness judging, production serving, trace storage,
open-ended answer scoring, generalized agent benchmarking, and security
scanning. Agentic threats such as tool abuse and excessive autonomy are real
but adjacent; they require dedicated controls and red teaming
([OWASP](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)).

Build integrations only from real raw-run samples, never from aggregate
scores. Prefer a small import contract over vendor SDK dependencies. Every new
schema field must improve the admissibility decision or its auditability.
Every statistical extension needs simulation near the decision boundary and
an explicit statement of what it guarantees.

The phased implementation plan, metrics, dependencies, and build/defer gates
are maintained in [ROADMAP.md](../ROADMAP.md).
