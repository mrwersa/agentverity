# Integration conformance contract

An evidence importer may understand a vendor export, a trace format, or a
local log. It must not change what AgentVerity evidence means. The reusable
fixtures and assertions in `tests/integration_contract.py` keep every in-tree
importer aligned.

## Required behavior

An importer must:

- consume individual categorical observations, not pass rates, counts, or
  other aggregates;
- preserve case order by first appearance and observation order within each
  case, because disjoint pairing depends on both;
- require at least two usable observations for every imported case and refuse
  the whole input instead of silently dropping thin cases;
- record the source in `provenance["harness"]` and carry the caller's declared
  isolation without inferring independence;
- produce an `EvidenceSet` that survives `to_dict()` / `from_dict()` without
  changing meaning; and
- raise `EvidenceError` with an actionable source-specific message when the
  export cannot meet these requirements.

Tool-specific configuration such as provider, prompt, model, project, or
session selection belongs in the importer. Do not pool configurations merely
to satisfy the repeat minimum.

## Add an importer

Keep optional SDK imports out of the core path. Prefer structural typing or a
documented export format, and add a focused module under
`agentverity/integrations/`.

1. Add source-shaped golden fixtures for supported and refused inputs. Fixtures
   must be synthetic and contain no customer prompts, outputs, trace IDs, or
   credentials.
2. Wrap the neutral ordered-run and aggregate fixtures with an
   `ImporterHarness` in `tests/test_integration_contract.py`.
3. Add source-specific tests for errors, configuration separation, malformed
   versions, and any typed outcomes the source can represent.
4. Document the mapping, isolation limits, export version, and maintenance
   owner in [Assessing runs you already have](imported-evidence.md).
5. Run `python -m pytest -q --cov=agentverity --cov-fail-under=90` and
   `ruff check .`.

Passing this contract is necessary, not sufficient. The roadmap still requires
a real adopter, redistributable fixtures, and a maintainer before a new source
is accepted in-tree.
