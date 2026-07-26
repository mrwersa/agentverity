# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows [Semantic Versioning](https://semver.org/) once it
reaches 1.0.0; before that, minor versions may include breaking changes.

## [Unreleased]

### Changed

- The README and `DESIGN.md` distinguish declared structure from observed
  behaviour. Static tools can inspect orchestration branches, route schemas,
  and expected labels. AgentVerity measures which decisions a model-backed or
  black-box target actually returns and whether identical reruns disagree.
- The README now puts a runnable zero-credential example before the statistical
  explanation, states the open-ended-agent non-fit explicitly, and describes
  relation execution as an optional convenience rather than the contribution.
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
