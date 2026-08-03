"""An adapter says what it did to keep trials apart. See ADR 6.

ADR 5 shipped a policy the runner could not feed: it set no isolation, so a
live baseline and its later check both read `unknown` and nothing was ever
refused. The knowledge existed in the adapters and was discarded.
"""

from __future__ import annotations

import json

import pytest

from agentverity import RunConfig, run
from agentverity.adapters.callable_adapter import from_callable
from agentverity.adapters.langgraph import from_langgraph, from_langgraph_thread
from agentverity.adapters.strands import from_strands, from_strands_factory
from agentverity.isolation import declare_isolation, isolation_of
from agentverity.snapshot import SnapshotRefused, create_snapshot


class _Graph:
    """A compiled graph that records the thread each call ran on."""

    def __init__(self) -> None:
        self.threads: list[str] = []

    def invoke(self, state, config=None):
        self.threads.append(config["configurable"]["thread_id"])
        return {"verdict": "allow"}


class _Agent:
    def __call__(self, text: str):
        return {"verdict": "block" if "secret" in text else "allow"}


def _balanced_inputs() -> list[str]:
    """Enough spread that only isolation can decide the outcome."""
    return [f"input_{index}" for index in range(25)] + [
        f"secret_{index}" for index in range(25)
    ]


@pytest.mark.parametrize(
    ("name", "build", "expected"),
    [
        ("langgraph", lambda: from_langgraph(_Graph()), "fresh-session"),
        ("langgraph-thread", lambda: from_langgraph_thread(_Graph(), "t"),
         "shared-session"),
        ("strands", lambda: from_strands(_Agent()), "shared-session"),
        ("strands-factory", lambda: from_strands_factory(_Agent), "fresh-instance"),
        ("callable", lambda: from_callable(lambda text: "allow"), "unknown"),
    ],
)
def test_each_adapter_declares_what_it_does(name, build, expected):
    assert isolation_of(build()) == expected, name


def test_a_pinned_thread_is_declared_shared_however_it_was_reached():
    """The trap this design exists to avoid.

    `from_langgraph` respects a caller-supplied `thread_id`, which is the
    documented way to opt out, and every repeat then runs on that one thread.
    A declaration keyed on the function name would assert `fresh-session`
    exactly where the caller had turned it off, and the policy would certify a
    baseline on the strength of a false claim.
    """
    graph = _Graph()
    pinned = from_langgraph(graph, config={"configurable": {"thread_id": "one"}})
    [pinned("x") for _ in range(3)]

    assert set(graph.threads) == {"one"}, "every repeat ran on the caller's thread"
    assert isolation_of(pinned) == "shared-session"

    fresh_graph = _Graph()
    fresh = from_langgraph(fresh_graph)
    [fresh("x") for _ in range(3)]

    assert len(set(fresh_graph.threads)) == 3
    assert isolation_of(fresh) == "fresh-session"


def test_a_live_run_now_carries_the_declaration():
    """The gap ADR 5 admitted to. A live run said `unknown` whatever it did."""
    result = run(from_strands_factory(_Agent), _balanced_inputs(),
                 config=RunConfig(k=10))

    assert result.isolation == "fresh-instance"


def test_a_shared_session_adapter_is_now_refused_a_live_baseline():
    """The behaviour change, stated as a test rather than left implicit.

    Anyone snapshotting through `from_strands` or `from_langgraph_thread` was
    previously admitted with an `unknown` that hid what they had done.
    """
    inputs = _balanced_inputs()
    shared = run(from_strands(_Agent()), inputs, config=RunConfig(k=10))
    isolated = run(from_strands_factory(_Agent), inputs, config=RunConfig(k=10))

    assert shared.meter.call == "verdict-deterministic", "only isolation refuses it"
    with pytest.raises(SnapshotRefused, match="not independent"):
        create_snapshot(shared, approved=True)

    assert create_snapshot(isolated, approved=True).isolation == "fresh-instance"


def test_an_undeclared_agent_stays_unknown_rather_than_permissive():
    """A plain function tells the library nothing, and `unknown` says that.

    `unknown` is admitted with a caveat. Only a stated `shared-session` is
    refused, so silence is neither punished nor treated as an assertion.
    """
    result = run(from_callable(lambda text: {"verdict": "allow" if "in" in text
                                             else "block"}),
                 _balanced_inputs(), config=RunConfig(k=10))

    assert result.isolation == "unknown"


def test_a_declaration_must_be_a_level_the_evidence_format_defines():
    def agent(text: str) -> str:
        return text

    with pytest.raises(ValueError, match="unknown isolation"):
        declare_isolation(agent, "totally-isolated-honest")


def test_declaring_on_something_that_cannot_hold_it_does_not_crash():
    """A builtin has no writable attributes, and that is not the caller's fault."""
    assert isolation_of(declare_isolation(len, "fresh-session")) == "unknown"


def test_an_invented_attribute_value_is_not_trusted():
    """The reader validates, so a hand-set attribute cannot smuggle a level in."""
    def agent(text: str) -> str:
        return text

    agent.__agentverity_isolation__ = "perfectly-isolated"

    assert isolation_of(agent) == "unknown"


def _agent_module(tmp_path, adapter: str) -> str:
    """Write an agent factory the CLI can import, wrapped by `adapter`."""
    module = tmp_path / "cli_agent.py"
    module.write_text(
        "from agentverity.adapters.strands import "
        "from_strands, from_strands_factory\n\n\n"
        "class _Agent:\n"
        "    def __call__(self, text):\n"
        "        return {'verdict': 'block' if 'secret' in text else 'allow'}\n\n\n"
        f"def factory():\n    return {adapter}\n",
        encoding="utf-8",
    )
    return f"{module}:factory"


def test_the_cli_carries_an_adapter_declaration_through(tmp_path, capsys):
    """The CLI loads every agent through `from_callable`, which dropped it.

    So the policy applied to the Python API and not to the command line, and
    a CLI user snapshotting a Strands agent still got the `unknown` this
    change exists to replace. That is the path the production-stack example
    documents, which made the gap the whole feature rather than an edge.
    """
    from agentverity.cli import main

    inputs = tmp_path / "inputs.txt"
    inputs.write_text("\n".join(_balanced_inputs()), encoding="utf-8")
    snapshot_path = tmp_path / "snapshot.json"

    code = main([
        "snapshot",
        "--agent", _agent_module(tmp_path, "from_strands_factory(_Agent)"),
        "--inputs", str(inputs), "--k", "10",
        "--output", str(snapshot_path), "--accept-reference",
    ])
    capsys.readouterr()

    assert code == 0
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["admission_evidence"]["isolation"] == "fresh-instance"


def test_the_cli_refuses_a_baseline_from_a_shared_session_agent(tmp_path, capsys):
    """The headline refusal, on the path most callers actually use."""
    from agentverity.cli import main

    inputs = tmp_path / "inputs.txt"
    inputs.write_text("\n".join(_balanced_inputs()), encoding="utf-8")

    code = main([
        "snapshot",
        "--agent", _agent_module(tmp_path, "from_strands(_Agent())"),
        "--inputs", str(inputs), "--k", "10",
        "--output", str(tmp_path / "snapshot.json"), "--accept-reference",
    ])

    assert code == 2
    assert "not independent" in capsys.readouterr().err


def test_a_reshaping_wrapper_invents_nothing():
    """`from_callable` carries a declaration; it does not create one."""
    assert isolation_of(from_callable(lambda text: "allow")) == "unknown"
    assert isolation_of(from_callable(from_strands_factory(_Agent))) == (
        "fresh-instance"
    )
