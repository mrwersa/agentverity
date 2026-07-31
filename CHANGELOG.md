# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows [Semantic Versioning](https://semver.org/) once it
reaches 1.0.0; before that, minor versions may include breaking changes.

## [Unreleased]

## [0.14.0] - 2026-07-31

### Added

- A LangGraph adapter. `from_langgraph(graph)` wraps a compiled graph into the
  `run(input) -> Observation` shape, reading the final text, the ordered tool
  calls, and a decision from `verdict`, `decision`, `route`, or
  `classification`.
- Every call gets a fresh `thread_id`. A graph compiled without a checkpointer
  is unaffected; one compiled with a checkpointer would otherwise make each
  repeat a further turn in a single conversation, and the intervals this
  library reports assume independent trials. A `thread_id` supplied in
  `config` is respected, so opting out is possible and deliberate.
- `from_langgraph_thread(graph, thread_id)` for the case where the
  conversation itself is under test. Evidence collected that way should record
  `isolation: shared-session`, and the report then names the caveat.
- The adapter reads both message shapes: LangChain objects carrying
  `tool_calls`, and serialised dicts carrying `name` or `function.name`. The
  answer is the last message with text, so a trailing tool result is not
  mistaken for the response.
- A `langgraph` extra, so `pip install "agentverity[langgraph]"` gets the
  dependency. The adapter is lazily imported, so without it a user got an
  ImportError naming the module rather than the extra that provides it. The
  README says where both adapters come from, in the section about letting
  AgentVerity make the calls rather than in the one that makes none.
- A `ROADMAP.md`, which the project did not have. It names what each command
  establishes, what is next, and what is deliberately not planned.

### Changed

- Releases are cut by merging the version bump. The release notes come from
  that version's changelog section, so the prose is written once rather than
  once there and again by hand in the GitHub Release.
- The release runs when CI finishes on `main` and only when it succeeded, not
  when the push happens, and it reads the version from the exact commit that
  passed. Artefacts are built and checked before the tag and the GitHub
  Release are created, because tagging first leaves a public release behind
  whenever an upload fails. Only a commit still at the tip of `main` releases,
  since `workflow_run` events arrive as each CI run finishes rather than in
  commit order.
- The packaging smoke test compares three numbers rather than two: the literal
  in `pyproject.toml`, the installed distribution metadata, and what the
  imported package reports. Comparing only the first two is how a sibling
  project shipped a wheel whose `__version__` was a release behind.
- The README comparison table names AgentMandate, which answers the question
  next to this one rather than the same one, and links
  [agent-release-gate](https://github.com/mrwersa/agent-release-gate).

## [0.13.2] - 2026-07-30

### Added

- A provider-free evaluator-stability example and guide show how to qualify
  repeated `pass`, `fail`, or `uncertain` judgements without claiming that
  repeatability establishes validity.

### Changed

- The README and integration guide place AgentVerity in the full evaluation
  loop from capability exploration through regression admission and reviewed
  production feedback.
- Production pinning examples now name the current `0.13` minor series.

## [0.13.1] - 2026-07-28

### Changed

- The README opens with the developer's rerun question, defines a regression
  baseline in plain language, and shows how AgentVerity complements Promptfoo,
  DeepEval, and observability before introducing the detailed workflow.

## [0.13.0] - 2026-07-28

### Added

- `agentverity compare-evidence before.json after.json` compares two
  independently collected evidence windows and reports what moved: per-route
  intervals, decisions that appeared or disappeared, flip-pair structure, and
  any model, prompt, or harness difference recorded in provenance.
- The reportable event is a tri-state result changing rather than a rate
  wandering. A route drifting inside one conclusion is noise, reported as
  `higher` or `lower`; a route crossing from deterministic to stochastic is a
  release event. The direction names describe the observed change rate rather
  than interval width.
- A provenance change counts as drift even when every decision held, because a
  model swap is the fact you most want beside a comparison.
- `compare_evidence`, `EvidenceDrift`, and `RouteDrift` are exported.
- Volatile provenance keys such as `collected_at` are shown separately and not
  counted as drift. A Promptfoo export stamps its collection time, so counting
  it would report every real comparison as drifted.
- A changed flip pair and a changed isolation level both count as drift.
  Printing a change and then leaving the exit code silent is worse for a gate
  than not printing it.
- Comparing two windows on different observation layers is refused. A verdict
  and a tool path are not the same observation.
- Malformed evidence files produce a usage error rather than a traceback.

### Changed

- The README describes the target using the established agent-pattern
  vocabulary: routing, orchestrator-workers, evaluator-optimiser, tool use,
  multi-agent supervisor, and guardrail or policy gate, each paired with the
  decision that is actually under test.

### Notes

- A comparison never claims that agreement between two windows establishes
  independence within either one. Two correlated runs agree comfortably.
  Independence is a property of collection, recorded in `isolation`, and the
  caveat travels with every comparison.

## [0.12.2] - 2026-07-28

### Changed

- The README now follows a developer decision path: a fully green Promptfoo
  run, why its moving route matters, a no-model-call trial, integration points,
  and the baseline workflow. The measured AgentCore release-gate visual now
  appears where the delivery-stack placement is explained.
- The Promptfoo example's configured quality policy accepts either plausible
  fraud queue for one ambiguous case. All 156 assertions pass, while
  AgentVerity independently identifies the route as unstable for baseline use.

## [0.12.1] - 2026-07-28

### Added

- `examples/promptfoo_bridge/results.json`, generated by Promptfoo from the
  included local varying router, so `agentverity assess --promptfoo` can be
  tried without installing Promptfoo or making another provider call. The
  export has six reviewed cases, 26 repeats each, and one unstable route.

### Changed

- The README now leads with a route-level stability finding and the
  no-duplicate-call import path, while retaining the scope and limits below.
- Promptfoo assertion failures with returned outputs remain stability
  observations. Only provider or runtime failures make the imported
  AgentVerity evidence incomplete.

## [0.12.0] - 2026-07-28

### Added

- `agentverity assess --evidence runs.json` applies the admission checks to
  repeated runs collected by another harness, making no model calls. Most
  teams already run their agent repeatedly through promptfoo, DeepEval,
  LangSmith, or a script of their own, and paying twice for the same
  information is the main reason not to adopt a second tool.
- An `agentverity.evidence/v1` schema carrying individual observations grouped
  per case and kept in order, with optional intended decisions, error counts,
  and provenance. `EvidenceSet`, `EvidenceCase`, `assess_evidence`,
  `load_evidence`, and `save_evidence` are exported.
- Aggregates are refused with the reason rather than a bare error. A flip rate
  cannot be turned back into the disjoint pairs it came from, and a pooled
  number cannot be split by route.
- `isolation` records how trials were separated. An imported file can break
  independence in ways a self-run cannot, so a shared session or an unrecorded
  method is reported rather than silently assumed away.
- `docs/imported-evidence.md` covers the format, the refusal, the isolation
  levels, and what an import cannot check.
- Promptfoo JSON exports can be assessed directly with
  `agentverity assess --promptfoo results.json --suite suite.json`. Mixed
  provider or prompt matrices are refused until one configuration is
  selected, so configuration differences are not misreported as random
  decision changes. Repeated rows map back to reviewed inputs rather than
  relying on Promptfoo's per-execution `testIdx`.
- `evidence_from_deepeval` groups repeated precomputed `LLMTestCase` objects.
  DeepEval keeps ownership of per-case quality while AgentVerity makes the
  suite-level evidence decision, with no second target run.
- Imported `text` and `tools` layers preserve their real observation shapes.
  Provider errors make the result incomplete, and isolation caveats now travel
  through text, JSON, JUnit, and OpenTelemetry reports.

### Changed

- An assessment from imported evidence reports no relation results. A relation
  needs the agent to answer a transformed question, and those calls do not
  exist in an imported file. Claiming a relation held when it never ran would
  be the vacuous green this package exists to name.
- Imported assessments populate source observations and enabled-check
  configuration consistently, so the ordinary snapshot path can admit stable
  imported evidence rather than rejecting it as an incomplete live run.

## [0.11.0] - 2026-07-28

### Added

- Relation probing per route. A relation whose transform returns the input
  unchanged has tested nothing, and pooled totals hide which routes that
  happened to. On plain ASCII inputs the accent and tool-selection relations
  are no-ops, so a suite can report a flawless pass while two of three routes
  were never perturbed at all. Unprobed routes are now named, and their
  violation rate reads as absent rather than as zero.
- `DecisionContract.minimum_cases` asks for a number of distinct reviewed
  cases on a route. It is a declaration, not a calculation: repeats establish
  that one input's decision is stable, distinct cases establish that a route
  was approached from more than one angle, and no bound turns the first into
  the second. A shortfall is reported as a contract finding and counted from
  the cases that were written rather than from what the agent returned.
- `RelationCoverage`, `RouteRelationCoverage`, and `stratify_relations` are
  exported, and `RunResult.relation_coverage` is populated whenever a suite
  and relations are supplied.
- JSON reports include the complete per-route relation table. JUnit and
  OpenTelemetry include aggregate probed and unprobed route counts without
  exposing route labels in telemetry.

### Changed

- Public positioning now states the narrow role directly: AgentVerity is a
  conservative admission policy for regression baselines involving bounded
  decisions, beside correctness and trajectory evaluators rather than in
  place of them.

## [0.10.0] - 2026-07-28

### Added

- `DecisionContract.stability_targets` gives a route its own flip-rate
  tolerance, so a consequential decision can be held to a tighter bound than a
  routine one. Targets are numerical policy and remain separate from the
  `critical` coverage label.
- Repeats are sized per route when targets are declared. A suite with one case
  for a tightly targeted decision and five routine cases would otherwise give
  the targeted route the least evidence. On the three-route example, the
  zero-change plan is 1054 calls against 2286 for one uniform repeat count.
- `agentverity plan --suite` prints that best-case call plan without calling
  the agent. An explicit run budget remains a hard cap and is checked before
  execution.
- `docs/route-evidence.md`, a worked guide to reading the route table, why a
  verdict never comes from the observed rate, and where the budget goes.
- Per-route stability. When a decision suite is declared, the same repeated
  observations the pooled meter uses are split by each case's intended
  decision, so a route that misbehaves is named instead of averaged away.
  A pooled interval of 12.8% across six routes can be one route flipping
  constantly and five that never move. No extra agent calls: per-route trials
  sum to the pooled total, and a test asserts it.
- A flip-pair table recording the unordered pair of decisions the agent
  returned for one input, such as `deny <-> review`. It is not a confusion
  matrix, because this package does not judge which answer was correct.
- `RouteStability`, `FlipPair`, `StratifiedStability`, and `stratify_runs`
  are exported. `RunResult.route_stability` is populated whenever a suite is
  supplied and the meter is enabled, with no new flag to set.

### Changed

- Repeat series may now differ in length, which is what lets a run size
  repeats per route. Reports expose the minimum and maximum repeats rather
  than hiding the allocation behind one `k`. A series carrying fewer than two
  observations is still rejected because it contributes no pair.
- A declared target is a release condition. If its route remains undecided,
  run status, JUnit, and snapshot admission refuse. If the route is proven
  above the target, status and JUnit fail the declared policy.
- Route plans now appear in JSON and aggregate OpenTelemetry attributes.
- Without declared targets nothing changes. Repeats stay uniform and the run
  behaves as before.
- The tri-state rule moved into `classify_call`, shared by the pooled meter
  and the per-route view so the two cannot drift apart. A route is classified
  from its confidence bound, never from its observed rate: one flip in
  thirteen pairs is a rate of 7.7% against a 5% threshold and an interval of
  [0.014, 0.333], which is undecided rather than stochastic.
- The report distinguishes a route proven to move from a route with too little
  evidence to tell, and states that each interval is a separate 95% statement
  rather than a joint one.
- Proven route-level stochasticity now flows into the canonical run status and
  blocks snapshot admission even when the pooled meter looks deterministic.
  Untargeted undecided routes remain an explicit diagnostic rather than
  silently multiplying the default call budget.
- JSON reports include the route table. Route-stability entries in JUnit and
  OpenTelemetry carry privacy-minimised aggregate counts without decision
  labels.
- Cases whose repeated calls fail remain visible in their intended route with
  zero usable pairs instead of disappearing from the table.
- The payment-dispute example now labels its admitted baseline as a pooled
  stability result and keeps undecided route-level intervals visible.

## [0.9.1] - 2026-07-28

### Fixed

- A decision-suite file with no `contract` key raised `TypeError` while every
  other malformed suite raised `ValueError`, so a caller had to write two
  except clauses to load one file. Loading now reports every malformed suite
  as `ValueError`. `DecisionContract.from_dict` still raises `TypeError` when
  handed the wrong kind of object directly, which is a programming error
  rather than bad input.

### Added

- `DecisionCount` is now exported. It is the element type of
  `DecisionCoverageResult.intended_counts` and `observed_counts`, both public,
  so it could be received but not imported for an annotation.

## [0.9.0] - 2026-07-28

### Added

- Optional `DecisionContract`, `DecisionCase`, and `DecisionSuite` types for
  applications with finite reviewed decisions.
- Separate intended and observed coverage, missing-required and
  missing-critical decisions, and detection of outputs outside the allowed
  contract.
- Contract-aware Python and `--suite` CLI paths, JUnit release checks,
  privacy-minimised OpenTelemetry attributes, and snapshot admission.

### Changed

- JSON reports and OpenTelemetry attributes now use their v2 schemas.
- Snapshots now use `agentverity.snapshot/v2` and retain the decision contract
  plus each case's intended label. The loader remains compatible with v1
  snapshots.
- The payment-dispute and AgentCore examples now require all six declared
  routes before admitting a baseline.

## [0.8.6] - 2026-07-28

### Added

- An applicability guide that identifies the bounded decision points
  AgentVerity can assess, including steps inside multi-agent and otherwise
  open-ended systems.

### Changed

- The README now gives a three-part fit test: a finite reviewed decision
  contract, equivalent starting state across trials, and deliberately varied
  test inputs.
- The README and design guide now define decision coverage as a minimum
  dynamic skew and diversity check rather than exhaustive coverage of every
  declared route or important boundary.

## [0.8.5] - 2026-07-27

### Changed

- The README now describes the exact branch-protection topology: the Coverage
  job enforces the 90% floor and the required `CI gate` depends on it.
- Local coverage data is ignored so the documented development command leaves
  the working tree clean.

## [0.8.4] - 2026-07-27

### Added

- Public PNG versions of the evidence-gate comparison and AgentCore
  release-gate figures for publishing surfaces that do not preserve SVG or
  HTML tables.

### Changed

- The README states the complete tri-state stability rule, explains why
  reruns are paired without reuse, and distinguishes established Wilson
  statistics from AgentVerity's evidence-gated release design.

## [0.8.3] - 2026-07-27

### Changed

- The README names the two consequences of weak test evidence: a vacuous green
  result and the regression trap created when that narrow run becomes a
  baseline.
- The integration guide documents a layered agent test and release pipeline,
  places AgentVerity after labelled quality evaluation and before baseline
  admission, and gives one replaceable AWS-oriented tool stack.

## [0.8.2] - 2026-07-26

### Added

- A required CI coverage job and a badge backed by a 90% statement-coverage
  floor.
- An architecture decision record explaining why AgentVerity compares named
  decisions rather than generated text.
- A call-budget table for the three precision levels, with explicit guidance
  on why target-call budgets are more useful than a synthetic local throughput
  benchmark.

### Changed

- The README quickstart now shows a fully parameterised return type and links
  directly to the decision-layer ADR.
- Edge-case tests now cover invalid observation layers, execution
  configuration, sequence verdicts, and nested report values.

## [0.8.1] - 2026-07-26

### Changed

- The README and `DESIGN.md` distinguish declared structure from observed
  behaviour. Static tools can inspect orchestration branches, route schemas,
  and expected labels. AgentVerity measures which decisions a model-backed or
  black-box target actually returns and whether identical reruns disagree.
- The README now puts a runnable zero-credential example before the statistical
  explanation, states the open-ended-agent non-fit explicitly, and describes
  relation execution as an optional convenience rather than the contribution.
- The README is now a short first-use path. Statistical derivation and
  integration mechanics live in focused guides instead of competing with the
  quickstart.
- The package and CLI descriptions now use the same decision-stability and
  coverage language as the README.
- A pre-1.0 stability policy documents patch compatibility, versioned schema
  handling, safe pinning, and concrete exit criteria for 1.0.

## [0.8.0] - 2026-07-26

### Added

- `from_strands_factory`, which builds a fresh Strands agent for each trial so
  repeated measurements do not inherit conversation history from earlier
  calls.
- A live payment-triage showcase combining Strands, Amazon Bedrock, DeepEval,
  AgentVerity, AgentCore Runtime, OpenTelemetry, and JUnit-compatible CI
  output. It remains optional, while the zero-dependency quickstart stays the
  default path.
- A `showcase` optional dependency group for running that integration.
- A machine-readable showcase evidence bundle with labelled-route accuracy,
  AgentVerity diagnostics, and end-to-end p50 and p95 latency.
- A redacted result bundle and generated dashboard from a real AgentCore
  Runtime canary in London.

### Changed

- Public documentation now presents AgentVerity as an evaluation runner for
  agents with named decisions, including deterministic gates and LLM agents.
  It frames stability and decision coverage as two scoped test-adequacy checks,
  defines baselines and snapshots at first use, and aligns the README,
  integration diagrams, package metadata, and generated reports.
- The README now keeps the measured AgentCore canary as its single visual
  showcase. The multi-agent diagnostic remains in the integration guide,
  beside the step-level guidance it supports.
- Terminal guidance now says `WHAT TO DO NEXT` and `test strategy` instead of
  reintroducing the retired research term `oracle`.
- The production showcase defaults to low-cost Amazon Nova Micro and separates
  runtime dependencies from the external evaluation stack.
- The showcase admits a reference only when both labelled-route quality and
  AgentVerity's evidence qualification pass. Stability can no longer mask an
  incorrect route.
- The AgentCore canary stops every isolated runtime session after reading its
  response, avoiding the idle-cost tail between repeated trials.
- The live canary exposes bounded concurrency through `--max-workers`, using
  four independent calls by default so a real runtime check finishes promptly.

## [0.7.0] - 2026-07-25

Reports that read well where people actually read them.

### Added

- A payment-dispute evidence-gate demo where both probe sets score 6/6, while
  only the set that crosses the routing boundary can become a snapshot. It can
  write JUnit artifacts, emit before-and-after OTEL spans, and print a
  comparison table with `--markdown` for a README or a CI job summary.
- `RunResult.duration_seconds`, the wall-clock time a run took.

### Changed

- JUnit output carries a `time` attribute. Without it, report collectors
  computed the duration as `NaNms` in every rendered section.
- `preflight.relation_coverage` is omitted when the caller passed no relations,
  instead of appearing as a skipped case. A check nobody requested is noise in
  a dashboard, and it rendered as an icon that reads as broken. Anything
  parsing the JUnit for that case should treat its absence as "not requested".

## [0.6.0] - 2026-07-25

The diagnosis now leaves the terminal. Same two questions, carried into the CI
and monitoring surfaces a team already runs.

### Added

- JUnit XML output through `--format junit`, `run_result_to_junit_xml`, and
  `write_junit_xml`. Blind probes and relation violations become failures,
  incomplete or undecided evidence becomes errors, and relations that tested
  nothing become skipped cases.
- A vendor-neutral OpenTelemetry handoff. `run_result_to_otel_attributes`
  returns low-cardinality aggregate fields, while `record_otel_run` emits one
  optional summary span through the host application's tracer provider.
- A directly runnable support-router example, an OTEL console example, a
  shorter product-first README, and integration guidance for AgentCore,
  CloudWatch, Phoenix, LangSmith, and quality-evaluation tools.
- A canonical `RunResult.status` shared by machine-readable reports,
  telemetry, and downstream integrations.
- CLI agent factories can be loaded directly from `file.py:func` as well as
  importable `module:func` paths.

### Fixed

- `agentverity run` could print `NO ANSWER YET` for an undecided meter and still
  exit successfully. It now returns exit code 2 for unsupported evidence.
- A relation catalogue that exercised no input could print `NOT TRUSTWORTHY`
  and still return exit code 0. It now returns exit code 1.

## [0.5.0] - 2026-07-25

A default run now answers the question instead of declining to.

### Changed

- **`k` is sized for you.** A zero-randomness agent used to report
  `undecided` on a default run, which reads as a broken tool rather than a
  result. Repeats are now derived from the precision you asked for, so the
  default run reaches a verdict. Set `k=` to take the wheel; it still wins.
- **`precision` replaces a bare epsilon as the main dial**: `"cheap"` (10%),
  `"balanced"` (5%, the default), `"strict"` (1%). Nobody knows what epsilon to
  pick, everybody knows how much they care. `epsilon=` still overrides it.
- **`budget` caps agent calls** when you need a ceiling. It defaults to `None`,
  meaning spend what the precision needs, because refusing to answer is worse
  than costing a predictable amount. Two repeats per input is a structural
  floor, and a budget below it is rejected rather than silently ignored.
- The default epsilon moved from 0.01 to 0.05 by way of `balanced`. The old
  default demanded 381 disjoint pairs, roughly 800 agent calls, to certify
  anything.
- **Reports lead with one plain sentence.** `RunResult.headline` says whether
  the suite can be trusted before any numbered section. A reader should not
  have to assemble a verdict from four tables.
- `agentverity run`, `snapshot`, and `check` accept `--precision` and
  `--budget`. `--k` and `--epsilon` are now overrides rather than defaults.

### Added

- `plan_repeats(inputs, epsilon, budget=None)` and `PRECISION_LEVELS`, both
  exported, so the sizing decision can be inspected or reused.

### Migration

`RunConfig(k=..., epsilon=...)` keeps working unchanged. Code reading
`config.k` or `config.epsilon` before a run now sees `None` where it used to
see a default; read them from `result.config` afterwards, where they are always
resolved to the values the run actually used.

Accuracy is a side effect worth noting. On the bundled example the old default
of `k=5` estimated a 66.7% flip rate from 12 pairs against a true rate of
45.5%. The new default measures 42.3% from 78 pairs, with an interval half as
wide.

### Added

- `agentverity.meter.pairs_for_deterministic_call(epsilon)` returns the minimum
  number of disjoint pairs that can certify determinism, so the cost of a
  snapshot can be budgeted before the run rather than discovered by refusal.

### Fixed

- Refusal advice assumed zero flips, so a run with 1,200 pairs and 6 flips was
  told to drop to 128. It now sizes against the observed rate, and says plainly
  that more pairs cannot help once that rate has met epsilon.
- `agentverity snapshot` refuses an unreachable configuration before running
  the agent instead of after. The bound is arithmetic, so paying a model to
  discover it was waste.
- `pairs_for_deterministic_call` rejects a non-positive or non-finite `z`.
  Passing `float("inf")` previously looped until integer overflow.

### Changed

- A snapshot refused for insufficient evidence now says how far short the run
  fell and which flag to change. "undecided" alone reads like a bug on an
  obviously deterministic agent, when the real answer is that 12 pairs cannot
  clear a 1% epsilon and 381 are needed. Stochastic verdicts get a distinct
  message, because a flipping decision is a different problem from a small
  sample.
- The README sizes the snapshot gate. At the default epsilon of 0.01 a
  deterministic agent still needs about 800 agent calls to be certified, which
  was previously something you found out by being refused.

## [0.4.0] - 2026-07-25

### Added

- **Evidence-gated snapshots.** `agentverity snapshot` refuses to freeze a
  reference unless the exact observation layer is deterministic at the
  configured epsilon, the probe set is non-blind, all requested evidence is
  complete, and a human explicitly approves the outputs.
- `agentverity check` re-runs the same admission diagnostics before comparing
  current observations with an approved snapshot. Unsupported evidence
  returns exit code 2 rather than a false regression result.
- Bounded concurrency across distinct inputs through `RunConfig.max_workers`
  and `--max-workers`. Repeated calls for one input stay sequential.
- Explicit `raise` and `record` error policies. Recorded failures produce
  structured `RunError` values and mark the run incomplete. They never become
  synthetic verdicts or passing checks.
- Versioned `agentverity.run/v1` JSON reports and
  `agentverity.snapshot/v1` baseline files.
- Non-plaintext progress events and input identifiers based on SHA-256
  fingerprints rather than raw probe text.
- `--no-relations`, `--format json`, `--output`, and `--progress` CLI options.
- A README diagnostic image generated from the executable multi-agent example.

### Changed

- Runner phases share one bounded execution primitive while preserving the
  sequential default and the existing unchanged-call reuse.
- Relation reports include failures separately from held, violated, and
  skipped cases.
- The bug-fix example exports the public versioned JSON report instead of a
  bespoke schema.
- `RunResult.suite_is_meaningful` documents why `relations=[]` returns `True`.
  A diagnostics-only run produced no green relation result to distrust.

## [0.3.0] - 2026-07-25

Post-release review of v0.2.0. Two correctness defects and a set of
documentation claims that did not match the code.

### Fixed

- **Duplicate inputs could report a varying agent as constant.** The
  first-call recorder keys observations by input text, so every copy of a
  repeated input resolved to one cached observation. An agent alternating
  between two verdicts across four identical probes was reported as 100% skew
  and `BLIND` instead of 50% and `ok`. Duplicates also distort the skew scan
  without any caching, because one verdict is counted once per copy. `run`
  now rejects a probe set containing the same input twice and names the
  duplicates. Repeating a measurement is what `k` is for.
- `README.md` documented the reuse saving on the four-input Quickstart as 35
  calls against 70. Measured values for that example are 28 and 40. The
  general formula was correct.
- The published v0.2.0 description on PyPI still said the package was not on
  PyPI and told readers to install from git, because the documentation fix
  landed after the release tag. PyPI metadata is immutable, so this release
  carries the corrected text.
- The test-count badge and the tests section claimed 85 while 86 passed.

### Changed

- **`RelationResult.violation_rate` returns `None` instead of `0.0` when the
  relation was never exercised.** The text report already printed `n/a`, but
  programmatic callers and exported JSON received a clean zero, which is the
  same false green the report refuses to print. Type is now `float | None`.
- The `langgraph` optional dependency was removed. It installed LangGraph for
  an adapter that does not exist yet.

## [0.2.0] - 2026-07-25

### Added

- Distribution build and clean-install validation in CI.
- PyPI Trusted Publishing workflow and a documented maintainer release
  procedure.
- `RelationResult.skipped`, `.exercised`, and `.is_vacuous`, plus
  `RunResult.vacuous_relations`, so a relation whose transform never changed
  an input is reported instead of counted as a pass.
- `RunConfig.reuse_unchanged_calls` (default on) and
  `agentverity.blindness.score`, which scores observations another phase has
  already collected.
- A reproducible supervisor-pattern example that contrasts a blind triage step
  with a stochastic full pipeline.
- A pull-request-only contribution workflow and CI across Python 3.10 to 3.14.

### Changed

- The verdict-stochasticity interval now uses disjoint repeat pairs. The
  earlier all-pairs calculation reused the same calls across comparisons and
  overstated the effective sample size.
- The runner now executes both diagnostics before any metamorphic relation.
- The built-in accent/whitespace transform is named
  `normalisation-invariance`, matching what it actually does.
- `suite_is_meaningful` now reports whether relation passes may be vacuous
  under the skew scan. Meter calls remain separate oracle guidance.
- Public novelty claims now distinguish repeated-trial and calibration tools
  from AgentVerity's narrower oracle-selection and verdict-skew diagnostics.
- `violation_rate` is now measured over exercised pairs rather than over all
  inputs, so inputs the transform left untouched no longer dilute it.
- A run reuses the meter's first draw per input for the blindness scan and for
  each relation's source side. Agent calls drop from `n * (k + 1 + 2r)` to
  `n * (k + r)`, removing one unchanged source call per relation.

### Fixed

- Empty probe sets and invalid meter/blindness thresholds now fail with clear
  `ValueError`s.
- The CLI no longer invokes an agent with a hidden probe input before the
  configured suite, avoiding side effects and wasted model calls.
- Passing `relations=[]` now runs no relations instead of restoring built-ins.
- `normalisation-invariance` and `tool-selection-invariance` normalise accents
  and whitespace, so on plain ASCII input the follow-up string was identical to
  the source. Both relations reported a perfect pass without the agent ever
  being asked a different question. Those inputs are now skipped, the rate
  reads `n/a`, and the report names the relation as not exercised.

## [0.1.0] - 2026-07-24

Initial public release.

### Added

- Verdict-stochasticity meter (`agentverity.meter`): a Wilson-CI-backed
  tri-state call (`verdict-stochastic` / `verdict-deterministic` /
  `undecided`) on whether an agent's decision is stable across identical
  reruns, refusing to label an underpowered probe "deterministic."
- Constant-gate-blindness detector (`agentverity.blindness`): flags when
  a passing test suite is trivially satisfied because the agent returns
  a near-constant verdict regardless of input.
- Typed metamorphic relations (`agentverity.relations`): invariant,
  monotone, and directional, with four built-in relations (paraphrase,
  case, whitespace, and tool-selection invariance).
- Runner (`agentverity.runner`) orchestrating meter, then relations,
  then blindness into a single diagnostics-first report.
- CLI (`agentverity run --agent module:func --inputs file.txt`).
- Callable adapter (zero dependencies) and an optional Strands adapter.
- 64 tests, all passing.

### Fixed (found during pre-release review, before this version shipped)

- `from_callable` was not exported from the top-level `agentverity`
  package, only from `agentverity.adapters`, so the README's own
  Quickstart (`from agentverity import run, from_callable`) raised
  `ImportError` for anyone who copy-pasted it. Now exported at the top
  level and covered by `tests/test_public_api.py` so the documented
  import surface can't silently drift again.
- The Quickstart's shown output didn't match what the shown code
  actually produces (stale pair counts, a tri-state call that wasn't
  reachable with that input size). Replaced with output captured from
  an actual run against the fixed code.
- Lint cleanup across the package: unused imports, a test asserting a
  bare `Exception` narrowed to the specific `FrozenInstanceError` it's
  actually checking for, missing trailing newlines.

[Unreleased]: https://github.com/mrwersa/agentverity/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/mrwersa/agentverity/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mrwersa/agentverity/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/mrwersa/agentverity/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/mrwersa/agentverity/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mrwersa/agentverity/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mrwersa/agentverity/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mrwersa/agentverity/releases/tag/v0.1.0
