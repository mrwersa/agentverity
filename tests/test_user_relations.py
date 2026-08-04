"""A user relation is registered, validated, and reported like a built-in.

Roadmap item 7. The `Relation` dataclass was always public and always accepted
by `run`, so the Python half worked. What did not: the command line had no way
to reach one, and a relation that could not be run or reported was constructed
happily and failed later, after the source calls had been paid for.
"""

from __future__ import annotations

import pytest

from agentverity import Relation, RunConfig, run
from agentverity.adapters.callable_adapter import from_callable
from agentverity.cli import main
from agentverity.relations import RELATION_TYPES, builtin_relations


def _router(text: str) -> dict:
    return {"verdict": "block" if "secret" in text else "allow"}


def _currency() -> Relation:
    return Relation(
        name="currency-symbol-invariance",
        rtype="invariant",
        transform=lambda text: text.replace("GBP ", "£"),
        check=lambda source, followup: source.verdict == followup.verdict,
    )


def _probes() -> list[str]:
    return [
        "refund GBP 40", "charged GBP 12", "where is my refund",
        "secret GBP page", "secret login", "secret GBP 5 fee",
    ]


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"name": ""}, ValueError, "non-empty name"),
        ({"name": "   "}, ValueError, "non-empty name"),
        ({"rtype": "invariant-ish"}, ValueError, "unknown relation type"),
        ({"transform": "not callable"}, TypeError, "callable transform"),
        ({"check": None}, TypeError, "callable check"),
    ],
)
def test_a_relation_that_cannot_be_run_is_refused_on_construction(
    kwargs, error, message
):
    """Refused before the run, not during it.

    A relation is otherwise discovered to be broken after the source calls
    have been made and paid for, which is the same reason the CLI refuses a
    bad `--agent` before it loads probes.
    """
    valid = {
        "name": "x",
        "rtype": "invariant",
        "transform": lambda text: text,
        "check": lambda source, followup: True,
    }

    with pytest.raises(error, match=message):
        Relation(**{**valid, **kwargs})


def test_the_built_in_catalogue_satisfies_its_own_rules():
    """The validation would be theatre if the built-ins could not pass it."""
    for relation in builtin_relations():
        assert relation.rtype in RELATION_TYPES
        assert relation.name.strip()


def test_a_user_relation_is_scored_exactly_like_a_built_in():
    """Held, violated, and skipped, with skipped counting what it must.

    Two of the six probes carry no `GBP `, so the transform returns them
    unchanged and they are excluded rather than counted as passes. A relation
    that does not apply cannot manufacture evidence that it held.
    """
    result = run(
        from_callable(_router), _probes(),
        relations=[_currency()], config=RunConfig(k=2),
    )
    scored = result.relation_results[0]

    assert scored.relation.name == "currency-symbol-invariance"
    assert scored.held == 4
    assert scored.violated == 0
    assert scored.skipped == 2


def test_a_user_relation_counts_towards_route_coverage():
    """The half of item 7 that is about the report rather than the protocol."""
    from agentverity.decision_contract import (
        DecisionCase,
        DecisionContract,
        DecisionSuite,
    )

    suite = DecisionSuite(
        contract=DecisionContract(
            allowed=frozenset({"allow", "block"}),
            required=frozenset({"allow", "block"}),
        ),
        cases=tuple(
            DecisionCase(input=text, expected="block" if "secret" in text else "allow")
            for text in _probes()
        ),
    )
    result = run(
        from_callable(_router), suite=suite,
        relations=[_currency()], config=RunConfig(k=2),
    )

    assert result.relation_coverage is not None
    assert set(result.relation_coverage.probed) == {"allow", "block"}
    assert result.relation_coverage.unprobed == ()


def _catalogue_file(tmp_path, body: str) -> str:
    module = tmp_path / "user_relations.py"
    module.write_text(
        "from agentverity import Relation\n\n\n" + body, encoding="utf-8"
    )
    return str(module)


def _inputs_file(tmp_path) -> str:
    path = tmp_path / "inputs.txt"
    path.write_text("\n".join(_probes()), encoding="utf-8")
    return str(path)


def test_the_command_line_can_reach_a_user_relation(tmp_path, capsys):
    """The gap item 7 actually names.

    `Relation` was public and `run(relations=[...])` always worked, so a
    Python caller could extend the catalogue. A CLI caller was stuck with the
    closed set, because nothing on the parser led anywhere else.
    """
    catalogue = _catalogue_file(tmp_path, '''def catalogue():
    return [Relation(
        name="currency-symbol-invariance",
        rtype="invariant",
        transform=lambda text: text.replace("GBP ", "\\u00a3"),
        check=lambda source, followup: source.verdict == followup.verdict,
    )]
''')

    main([
        "run", "--agent", "examples.toy_agent:deterministic_gate",
        "--inputs", _inputs_file(tmp_path), "--relations", f"{catalogue}:catalogue",
    ])
    printed = capsys.readouterr().out

    assert "currency-symbol-invariance" in printed
    assert "normalisation-invariance" not in printed, "it replaces, not appends"


def test_one_relation_needs_no_list(tmp_path, capsys):
    """One domain relation is the ordinary case; a list is friction."""
    catalogue = _catalogue_file(tmp_path, '''def one():
    return Relation(
        name="solo-relation", rtype="invariant",
        transform=lambda text: text.upper(),
        check=lambda source, followup: source.verdict == followup.verdict,
    )
''')

    main([
        "run", "--agent", "examples.toy_agent:deterministic_gate",
        "--inputs", _inputs_file(tmp_path), "--relations", f"{catalogue}:one",
    ])

    assert "solo-relation" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("body", "target", "message"),
    [
        ("def empty():\n    return []\n", "empty", "returned no relations"),
        ("def wrong():\n    return ['not a relation']\n", "wrong", "not a Relation"),
        ("def catalogue():\n    return []\n", "missing", "has no 'missing'"),
    ],
)
def test_a_catalogue_that_cannot_be_used_is_refused_before_the_run(
    tmp_path, capsys, body, target, message
):
    """Refused at load, so no agent call is spent on a catalogue that fails."""
    catalogue = _catalogue_file(tmp_path, body)

    code = main([
        "run", "--agent", "examples.toy_agent:deterministic_gate",
        "--inputs", _inputs_file(tmp_path), "--relations", f"{catalogue}:{target}",
    ])

    assert code == 2
    assert message in capsys.readouterr().err


def test_relations_and_no_relations_are_refused_together(tmp_path, capsys):
    """One says run this catalogue and the other says run none."""
    catalogue = _catalogue_file(tmp_path, "def catalogue():\n    return []\n")

    code = main([
        "run", "--agent", "examples.toy_agent:deterministic_gate",
        "--inputs", _inputs_file(tmp_path),
        "--relations", f"{catalogue}:catalogue", "--no-relations",
    ])

    assert code == 2
    assert "Drop one" in capsys.readouterr().err


def test_only_run_offers_the_flag():
    """`snapshot` and `check` pass no relations, so they do not offer it.

    The lesson from `--sequential`: a flag on a command that cannot act on it
    is a flag accepted and discarded.
    """
    from agentverity.cli import _build_parser

    offering = sorted(
        name
        for action in _build_parser()._subparsers._group_actions
        for name, parser in action.choices.items()
        if any("--relations" in option.option_strings for option in parser._actions)
    )

    assert offering == ["run"]


def test_the_documented_example_runs():
    """The example the docs point at must work, not merely exist."""
    import runpy

    module = runpy.run_path("examples/custom_relation.py")
    catalogue = module["catalogue"]()

    assert any(r.name == "currency-symbol-invariance" for r in catalogue)
    assert len(catalogue) == len(builtin_relations()) + 1
    assert isinstance(module["domain_only"](), Relation)
