"""Tests for agentverity.adapters.langgraph.

Fakes reproduce the shapes a compiled graph returns, so these run without
langgraph installed. That is deliberate: the core must keep installing without
any agent library, and a test that needs the framework present cannot check
that.
"""

from __future__ import annotations

import pytest

from agentverity.adapters.langgraph import (
    extract,
    from_langgraph,
    from_langgraph_thread,
)


class Message:
    """A LangChain-style message object."""

    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class ToolCall:
    def __init__(self, name):
        self.name = name


class Graph:
    """A compiled graph that records how it was invoked."""

    def __init__(self, state):
        self.state = state
        self.calls: list[tuple[dict, dict]] = []

    def invoke(self, state, config=None):
        self.calls.append((state, config or {}))
        return self.state


def test_the_last_text_message_is_the_answer() -> None:
    state = {
        "messages": [
            {"role": "user", "content": "I was charged twice"},
            Message("Let me look that up.", [ToolCall("search_cases")]),
            Message("I have refunded 42.00."),
        ]
    }

    observation = extract(state)

    assert observation.text == "I have refunded 42.00."
    assert observation.tools == ("search_cases",)


def test_a_trailing_tool_result_is_not_the_answer() -> None:
    # A ToolMessage arriving last is a result, not a response. Taking it would
    # make the observed text a JSON blob rather than what the agent said.
    state = {
        "messages": [
            Message("Refunding now.", [ToolCall("issue_refund")]),
            Message(""),
        ]
    }

    assert extract(state).text == "Refunding now."


def test_tool_order_is_the_order_the_agent_chose() -> None:
    state = {
        "messages": [
            Message("", [ToolCall("search_cases"), ToolCall("get_case")]),
            Message("", [ToolCall("issue_refund")]),
            Message("Done."),
        ]
    }

    assert extract(state).tools == ("search_cases", "get_case", "issue_refund")


def test_serialised_tool_calls_are_read_too() -> None:
    state = {
        "messages": [
            {"content": "", "tool_calls": [{"name": "issue_refund"}]},
            {"content": "", "tool_calls": [{"function": {"name": "close_case"}}]},
            {"content": "Done."},
        ]
    }

    assert extract(state).tools == ("issue_refund", "close_case")


def test_content_blocks_are_joined() -> None:
    state = {
        "messages": [
            Message([{"type": "text", "text": "Refund "}, {"type": "text", "text": "issued."}])
        ]
    }

    assert extract(state).text == "Refund issued."


@pytest.mark.parametrize("key", ["verdict", "decision", "route", "classification"])
def test_a_decision_is_read_from_the_usual_state_keys(key: str) -> None:
    assert extract({"messages": [], key: "refund_approved"}).verdict == "refund_approved"


def test_an_explicit_verdict_key_wins() -> None:
    state = {"messages": [], "verdict": "wrong", "outcome": "refund_approved"}

    assert extract(state, verdict_key="outcome").verdict == "refund_approved"


def test_a_state_with_no_decision_reports_none() -> None:
    assert extract({"messages": [Message("hello")]}).verdict is None
    assert extract({"messages": [], "verdict": ""}).verdict is None


def test_a_state_that_is_not_a_mapping_still_yields_text() -> None:
    assert extract("just a string").text == "just a string"


def test_each_call_gets_its_own_thread(monkeypatch) -> None:
    # The isolation that matters. A graph compiled with a checkpointer keeps
    # state per thread, so reusing one turns repeated trials into successive
    # turns of a single conversation, and the intervals assume independence.
    graph = Graph({"messages": [Message("ok")]})
    run = from_langgraph(graph)

    run("first")
    run("second")

    threads = [config["configurable"]["thread_id"] for _, config in graph.calls]
    assert threads[0] != threads[1]
    assert all(t.startswith("agentverity-") for t in threads)


def test_a_thread_id_supplied_in_config_is_respected() -> None:
    # Opting out has to be possible, and deliberate.
    graph = Graph({"messages": [Message("ok")]})

    from_langgraph(graph, config={"configurable": {"thread_id": "mine"}})("x")

    assert graph.calls[0][1]["configurable"]["thread_id"] == "mine"


def test_extra_config_survives() -> None:
    graph = Graph({"messages": [Message("ok")]})

    from_langgraph(graph, config={"recursion_limit": 10})("x")

    assert graph.calls[0][1]["recursion_limit"] == 10


def test_the_input_goes_under_messages_as_a_user_turn() -> None:
    graph = Graph({"messages": [Message("ok")]})

    from_langgraph(graph)("I was charged twice")

    state, _ = graph.calls[0]
    assert state == {"messages": [{"role": "user", "content": "I was charged twice"}]}


def test_a_custom_input_key_passes_the_string_directly() -> None:
    graph = Graph({"question": "x", "verdict": "allow"})

    observation = from_langgraph(graph, input_key="question")("why?")

    assert graph.calls[0][0] == {"question": "why?"}
    assert observation.verdict == "allow"


def test_the_shared_thread_adapter_keeps_one_conversation() -> None:
    graph = Graph({"messages": [Message("ok")]})
    run = from_langgraph_thread(graph, "case-4471")

    run("first")
    run("second")

    threads = [config["configurable"]["thread_id"] for _, config in graph.calls]
    assert threads == ["case-4471", "case-4471"]


def test_the_shared_thread_adapter_takes_a_custom_input_key() -> None:
    graph = Graph({"question": "x"})

    from_langgraph_thread(graph, "t", input_key="question", config={"recursion_limit": 5})("why?")

    state, config = graph.calls[0]
    assert state == {"question": "why?"}
    assert config["recursion_limit"] == 5


def test_the_adapter_feeds_the_runner() -> None:
    from agentverity import RunConfig
    from agentverity import run as run_suite

    graph = Graph({"messages": [Message("ok")], "verdict": "refund_approved"})
    result = run_suite(
        from_langgraph(graph),
        ["I was charged twice", "The merchant took 129.99"],
        config=RunConfig(k=4),
    )

    # The point is that the adapter satisfies the runner's contract without
    # the runner knowing anything about LangGraph.
    assert result is not None
    assert graph.calls
    # The invariant, whatever the runner's call count: no two trials shared a
    # thread. Asserting a count instead would break every time the relation
    # catalogue changes, and would not be checking the thing that matters.
    threads = [config["configurable"]["thread_id"] for _, config in graph.calls]
    assert len(set(threads)) == len(threads)


def test_a_plain_string_content_block_is_kept() -> None:
    state = {"messages": [Message(["Refund ", {"type": "text", "text": "issued."}])]}

    assert extract(state).text == "Refund issued."


def test_a_non_text_content_block_is_skipped() -> None:
    # An image or tool_use block carries no answer text, and stringifying it
    # would put a dict into the observed decision.
    state = {
        "messages": [
            Message([{"type": "tool_use", "name": "search"}, {"type": "text", "text": "Done."}])
        ]
    }

    assert extract(state).text == "Done."


def test_content_that_is_neither_string_nor_list() -> None:
    assert extract({"messages": [Message(None)], "verdict": "x"}).text == ""
    assert extract({"messages": [Message(42)]}).text == "42"


def test_a_state_object_rather_than_a_dict_still_yields_a_decision() -> None:
    class State:
        def __init__(self):
            self.messages = [Message("ok")]
            self.verdict = "refund_approved"

    assert extract(State()).verdict == "refund_approved"
    assert extract(State()).text == "ok"


def test_the_extra_that_installs_the_dependency_is_declared() -> None:
    # The adapter is lazily imported, so a user without langgraph gets an
    # ImportError naming the module and not the extra that provides it. The
    # extra has to exist for the docstring's install line to be true.
    import re
    from pathlib import Path

    pyproject = (
        Path(__file__).resolve().parents[1] / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert re.search(r"^langgraph = \[", pyproject, flags=re.MULTILINE)
    assert 'agentverity[langgraph]' in (
        Path(__file__).resolve().parents[1] / "README.md"
    ).read_text(encoding="utf-8")


def test_a_boolean_decision_keeps_pythons_spelling() -> None:
    # Deliberate, not an oversight. The decision label belongs to the
    # application; lower-casing here would be this package inventing a
    # convention nobody declared. Stability is unaffected because both trials
    # render the same way, and a declared contract listing true/false reports
    # the mismatch loudly rather than hiding it.
    assert extract({"messages": [], "verdict": True}).verdict == "True"
    assert extract({"messages": [], "verdict": False}).verdict == "False"
