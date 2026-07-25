# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows [Semantic Versioning](https://semver.org/) once it
reaches 1.0.0; before that, minor versions may include breaking changes.

## [Unreleased]

## [0.2.0] - 2026-07-25

### Added

- Distribution build and clean-install validation in CI.
- PyPI Trusted Publishing workflow and a documented maintainer release
  procedure.

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
- Added a reproducible supervisor-pattern example that contrasts a blind
  triage step with a stochastic full pipeline.
- Added a pull-request-only contribution workflow and CI across Python
  3.10--3.12.

### Fixed

- Empty probe sets and invalid meter/blindness thresholds now fail with clear
  `ValueError`s.
- The CLI no longer invokes an agent with a hidden probe input before the
  configured suite, avoiding side effects and wasted model calls.
- Passing `relations=[]` now runs no relations instead of restoring built-ins.

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

[Unreleased]: https://github.com/mrwersa/agentverity/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mrwersa/agentverity/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mrwersa/agentverity/releases/tag/v0.1.0
