"""Tests for agentverity.relations."""

from __future__ import annotations

from agentverity.observation import Observation
from agentverity.relations import (
    INVARIANT,
    MONOTONE,
    Relation,
    _change_case,
    _insert_whitespace,
    _normalise,
    builtin_relations,
)


class TestTransforms:
    def test_normalise_strips_accents(self):
        assert _normalise("café") == "cafe"
        assert _normalise("naïve") == "naive"

    def test_normalise_whitespace(self):
        assert _normalise("hello   world") == "hello world"
        assert _normalise("  hello  world  ") == "hello world"

    def test_change_case(self):
        assert _change_case("Hello") == "hELLO"
        assert _change_case("HeLLo World") == "hEllO wORLD"

    def test_insert_whitespace(self):
        result = _insert_whitespace("hello")
        assert result.startswith("\n")
        assert result.endswith("  ")
        assert "hello" in result


class TestBuiltinRelations:
    def test_returns_four_relations(self):
        rels = builtin_relations()
        assert len(rels) == 4

    def test_all_are_invariant(self):
        rels = builtin_relations()
        assert all(r.rtype == INVARIANT for r in rels)

    def test_names(self):
        rels = builtin_relations()
        names = {r.name for r in rels}
        assert "normalisation-invariance" in names
        assert "case-invariance" in names
        assert "whitespace-invariance" in names
        assert "tool-selection-invariance" in names

    def test_have_descriptions(self):
        rels = builtin_relations()
        assert all(r.description for r in rels)


class TestParaphraseInvarianceCheck:
    def test_holds_when_verdict_unchanged(self):
        rel = next(r for r in builtin_relations() if r.name == "normalisation-invariance")
        src = Observation(text="allow", verdict="allow")
        fol = Observation(text="allow", verdict="allow")
        assert rel.check(src, fol) is True

    def test_violated_when_verdict_changes(self):
        rel = next(r for r in builtin_relations() if r.name == "normalisation-invariance")
        src = Observation(text="allow", verdict="allow")
        fol = Observation(text="block", verdict="block")
        assert rel.check(src, fol) is False


class TestToolSelectionInvariance:
    def test_holds_when_tools_unchanged(self):
        rel = next(r for r in builtin_relations() if r.name == "tool-selection-invariance")
        src = Observation(text="ok", tools=("search", "lookup"))
        fol = Observation(text="ok", tools=("search", "lookup"))
        assert rel.check(src, fol) is True

    def test_violated_when_tools_change(self):
        rel = next(r for r in builtin_relations() if r.name == "tool-selection-invariance")
        src = Observation(text="ok", tools=("search",))
        fol = Observation(text="ok", tools=("lookup",))
        assert rel.check(src, fol) is False

    def test_holds_when_no_tools(self):
        rel = next(r for r in builtin_relations() if r.name == "tool-selection-invariance")
        src = Observation(text="ok", tools=())
        fol = Observation(text="ok", tools=())
        assert rel.check(src, fol) is True


class TestCustomRelation:
    def test_custom_monotone(self):
        rel = Relation(
            name="escalation",
            rtype=MONOTONE,
            transform=lambda s: s + " urgent",
            check=lambda src, fol: src.verdict <= fol.verdict if src.verdict and fol.verdict else True,
        )
        assert rel.name == "escalation"
        assert rel.rtype == MONOTONE
