# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows [Semantic Versioning](https://semver.org/) once it
reaches 1.0.0; before that, minor versions may include breaking changes.

## [Unreleased]

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
  calls against 70. Those were the figures for a five-input probe. Measured
  values are 28 and 40. The general formula was correct.
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
  `n * (k + r)`, halving them on the default configuration.

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

[Unreleased]: https://github.com/mrwersa/agentverity/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/mrwersa/agentverity/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mrwersa/agentverity/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mrwersa/agentverity/releases/tag/v0.1.0
