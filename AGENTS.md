# Repository Guidelines

## What this repo is

`agentverity/` is a dependency-light Python library + CLI (`agentverity.cli:main`) that qualifies whether AI-agent decisions are repeatable enough to save as a regression baseline. The core has **zero runtime dependencies**; framework-specific code belongs in `agentverity/adapters/` (strands, langgraph, callable) and evaluator/file-format bridges in `agentverity/integrations/` (promptfoo, deepeval, jsonl), each exposed through optional extras in `pyproject.toml`. `examples/` holds runnable demos and fixtures, `docs/` design guidance, `scripts/` release/doc utilities.

## Commands

```bash
python -m pip install -e ".[dev]"        # venv required; no other setup
python -m pytest -q                      # full suite, fully offline, ~8s
python -m pytest tests/test_cli.py -q    # single file; add -k <name> to filter
python -m pytest -q --cov=agentverity --cov-fail-under=90   # CI coverage floor
ruff check .
```

- Run pytest **from the repo root**: tests import `scripts.render_readme_report` and `examples.*` as packages, which resolves only when rootdir is on the path.
- There is no typecheck step in CI — lint, tests, coverage (>=90%), and packaging are the gates.
- For release-related changes also run `python -m build && python -m twine check dist/*`.

## Docs, examples, and assets are pinned by tests

This is the easiest way to break CI without touching library code:

- `tests/test_readme_examples.py` asserts README copy matches what `examples/payment_dispute_gate.py` actually prints, including section order.
- `tests/test_public_api.py` asserts every name listed in the README's API-surface list imports from `agentverity/__init__.py`.
- `docs/assets/*.svg` images are generated: regenerate with `python scripts/render_readme_report.py` (and `render_agentcore_evidence.py` for that asset) after changing the underlying examples; `tests/test_readme_report.py` pins exact rendered values like `"42.3% (33/78)"`.

So: change an example or public export → update README/docs and regenerate assets in the same commit.

Run every documented command or example before merging a doc that quotes it. Reading is not verification: two of the last three doc defects were invisible on read and obvious on execution (a missing flag, and sample data that triggered an unrelated warning). Paste the real output into the doc if the example prints something. Run every level the prose makes a claim about, not just the happy path: the BFCL recipe shipped claiming isolation refusal at assessment when the refusal lives at baseline admission, and only the unhappy path exposed it.

## Separate public engagement from private outreach

`docs/ecosystem-engagement-log.md` is an append-only record of public artifacts we already authored, not a contact tracker. It may link an attributable public issue or comment after publication, but must not name prospective targets, private contacts, planned follow-ups, or outreach sequencing. Those details live only in the private tracker described by `docs/design-partner-playbook.md`. Public engagement does not increment the design-partner funnel unless a separate contact meets the playbook definition. Before contacting anyone, consult the private tracker; if it is unavailable, do not infer or repeat outreach from the public log.

## Versioning and releases

The version number lives **only** in `pyproject.toml`; `agentverity.__version__` reads installed distribution metadata, and the CI package job fails if pyproject, metadata, and `__version__` disagree — never hardcode a second literal.

A release PR publishes automatically after merge to `main`: set the version, move changelog entries into a dated `## [x.y.z] - YYYY-MM-DD` section (missing/empty sections fail the release), and open the PR. Documentation-only merges do not require a release. See `RELEASING.md`; do not hand-tag except for infra-failure recovery.

## Conventions

- Commit subjects: imperative and scoped (`fix: ...`, `docs: ...`, `test: ...`, `release: ...`). Branches: `feature/short-description` off latest `main`; direct and force pushes to `main` are blocked.
- Tests are named `test_<observable_behavior>` and use deterministic fixtures/recorded evidence — no live model/provider calls anywhere in the suite.
- Preserve the package's explicit vocabulary: decisions, evidence, flips, and the three outcomes `deterministic` / `stochastic` / `undecided`.
- Public API changes must update `agentverity/__init__.py` (`__all__`), relevant docs, and `CHANGELOG.md`.
- Open an issue before implementing a large adapter.

## Security & data handling

Never commit customer prompts, model outputs, credentials, or trace identifiers. Suites, snapshots, exception text, and generated evidence under `docs/evidence/` are potentially sensitive; SHA-256 fingerprints identify inputs but are not anonymisation. Report vulnerabilities privately via GitHub Security Advisories.
