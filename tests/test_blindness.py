"""Tests for agentverity.blindness."""

from __future__ import annotations

import pytest

from agentverity.adapters import from_callable
from agentverity.blindness import detect, score
from agentverity.decision import Decision, NoDecision, OutcomeNotScorable
from agentverity.observation import Observation


class TestDetect:
    def test_constant_gate_is_blind(self):
        """A gate that always returns the same verdict is blind."""
        def fn(x: str) -> dict:
            return {"text": "allow", "verdict": "allow"}

        agent = from_callable(fn)
        result = detect(agent, ["hello", "world", "foo", "bar"])
        assert result.blind is True
        assert result.skew == 1.0
        assert result.distinct == 1
        assert result.warning is not None

    def test_balanced_gate_is_not_blind(self):
        """A gate that splits 50/50 is not blind."""
        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = detect(agent, ["hello", "world", "a secret", "foo", "bar", "another secret"])
        assert result.blind is False
        assert result.skew < 0.9
        assert result.distinct == 2
        assert result.warning is None

    def test_near_constant_gate_is_blind(self):
        """A gate that returns the same verdict on 95% of inputs is blind at 0.9."""
        inputs = [f"input_{i}" for i in range(20)]
        inputs[3] = "secret"  # only 1/20 = 5% is different

        def fn(x: str) -> dict:
            v = "block" if "secret" == x else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = detect(agent, inputs, threshold=0.9)
        assert result.blind is True
        assert result.skew == 19 / 20

    def test_custom_threshold(self):
        """A 80% skew is blind at 0.8 but not at 0.9."""
        inputs = [f"input_{i}" for i in range(10)]
        inputs[0] = "secret"

        def fn(x: str) -> dict:
            v = "block" if "secret" == x else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result_low = detect(agent, inputs, threshold=0.8)
        result_high = detect(agent, inputs, threshold=0.95)
        assert result_low.blind is True
        assert result_high.blind is False

    def test_empty_inputs_rejected(self):
        agent = from_callable(lambda x: "ok")
        with pytest.raises(ValueError, match="inputs"):
            detect(agent, [])

    def test_invalid_threshold_rejected(self):
        agent = from_callable(lambda x: "ok")
        with pytest.raises(ValueError, match="threshold"):
            detect(agent, ["hello"], threshold=0)


class TestScoreOnCollectedObservations:
    """score() lets a caller reuse observations another phase already drew."""

    def test_score_matches_detect(self):
        from agentverity.adapters import from_callable
        from agentverity.blindness import detect, score

        def fn(x: str) -> dict:
            return {"text": x, "verdict": "allow" if "a" in x else "block"}

        agent = from_callable(fn)
        inputs = ["alpha", "beta", "gamma", "xyz"]
        via_detect = detect(agent, inputs)
        via_score = score([agent(x) for x in inputs])

        assert via_score.skew == via_detect.skew
        assert via_score.distinct == via_detect.distinct
        assert via_score.majority_verdict == via_detect.majority_verdict
        assert via_score.blind == via_detect.blind

    def test_score_rejects_empty_observations(self):
        import pytest

        from agentverity.blindness import score

        with pytest.raises(ValueError, match="must not be empty"):
            score([])

    def test_score_rejects_bad_threshold(self):
        import pytest

        from agentverity.blindness import score
        from agentverity.observation import Observation

        with pytest.raises(ValueError, match="threshold"):
            score([Observation(text="a", verdict="a")], threshold=0)

    def test_sequence_verdicts_are_compared_as_hashable_values(self):
        from agentverity.blindness import score
        from agentverity.observation import Observation

        result = score([
            Observation(verdict=["search", "answer"]),
            Observation(verdict=["search", "answer"]),
            Observation(verdict=["escalate"]),
        ])

        assert result.distinct == 2
        assert result.majority_verdict == ("search", "answer")


class _KeyOnlyObservation:
    def __init__(self, verdict, *, text="", tools=()):
        self.verdict = verdict
        self.text = text
        self.tools = tools
        self.key_calls = []

    def key(self, layer):
        self.key_calls.append(layer)
        return getattr(self, layer)


@pytest.mark.parametrize("consumer", ["detect", "score"])
class TestTypedOutcomeValidation:
    @staticmethod
    def _scan(consumer, observations, *, layer="verdict"):
        if consumer == "detect":
            by_input = dict(zip(("a", "b"), observations, strict=True))
            return detect(by_input.__getitem__, ["a", "b"], layer=layer)
        return score(observations, layer=layer)

    @pytest.mark.parametrize(
        "reason", ["runtime_error", "extraction_failed", "malformed_response"]
    )
    def test_a_harness_failure_is_refused(self, consumer, reason):
        observations = [
            Observation(verdict="allow"),
            Observation(verdict=NoDecision(reason)),
        ]

        with pytest.raises(OutcomeNotScorable, match="harness failed"):
            self._scan(consumer, observations)

    @pytest.mark.parametrize("reason", ["refused", "no_tool_selected"])
    def test_an_agent_no_decision_remains_a_distinct_outcome(self, consumer, reason):
        result = self._scan(consumer, [
            Observation(verdict=NoDecision(reason)),
            Observation(verdict=Decision(reason)),
        ])

        assert result.distinct == 2
        assert result.skew == 0.5
        assert not result.blind

    @pytest.mark.parametrize("layer", ["text", "tools"])
    def test_other_layers_use_their_own_keys(self, consumer, layer):
        result = self._scan(consumer, [
            Observation(
                text="first", tools=("search",), verdict=NoDecision("runtime_error")
            ),
            Observation(
                text="second", tools=("answer",),
                verdict=NoDecision("extraction_failed"),
            ),
        ], layer=layer)

        assert result.distinct == 2
        assert result.skew == 0.5

    def test_text_fallback_keeps_its_existing_distribution(self, consumer):
        result = self._scan(consumer, [
            Observation(text="first"),
            Observation(text="second"),
        ])

        assert result.distinct == 2
        assert result.skew == 0.5

    def test_open_ended_outcomes_keep_their_existing_distribution(self, consumer):
        result = self._scan(consumer, [
            Observation(verdict=NoDecision("open_ended")),
            Observation(verdict=Decision("allow")),
        ])

        assert result.distinct == 2
        assert result.skew == 0.5

    @pytest.mark.parametrize(
        "reason", ["runtime_error", "extraction_failed", "malformed_response"]
    )
    @pytest.mark.parametrize("status", ["missing", "false"])
    def test_duck_typed_failures_are_refused_from_their_key(
        self, consumer, reason, status
    ):
        observations = [
            _KeyOnlyObservation("allow"),
            _KeyOnlyObservation(NoDecision(reason)),
        ]
        if status == "false":
            for observation in observations:
                observation.is_incomplete = False

        with pytest.raises(OutcomeNotScorable, match="a blindness scan"):
            self._scan(consumer, observations)

        assert all(observation.key_calls == ["verdict"] for observation in observations)

    @pytest.mark.parametrize("keys, distinct", [
        (["allow", Decision("allow")], 1),
        ([NoDecision("refused"), Decision("refused")], 2),
        ([NoDecision("no_tool_selected"), Decision("no_tool_selected")], 2),
        ([NoDecision("open_ended"), "allow"], 2),
        ([["search", "answer"], ["search", "answer"]], 1),
    ])
    def test_valid_duck_typed_keys_keep_their_distribution(self, consumer, keys, distinct):
        observations = [_KeyOnlyObservation(key) for key in keys]

        result = self._scan(consumer, observations)

        assert result.inputs == 2
        assert result.distinct == distinct
        assert result.skew == 1 / distinct
        assert all(observation.key_calls == ["verdict"] for observation in observations)

    @pytest.mark.parametrize("layer", ["text", "tools"])
    def test_duck_typed_observations_use_the_requested_layer(self, consumer, layer):
        observations = [
            _KeyOnlyObservation(NoDecision("runtime_error"), text="a", tools=("search",)),
            _KeyOnlyObservation(NoDecision("extraction_failed"), text="b", tools=("answer",)),
        ]

        result = self._scan(consumer, observations, layer=layer)

        assert result.distinct == 2
        assert result.skew == 0.5
        assert all(observation.key_calls == [layer] for observation in observations)

    def test_keys_are_read_once_even_when_status_metadata_is_present(self, consumer):
        observations = [_KeyOnlyObservation("allow"), _KeyOnlyObservation("allow")]
        for observation in observations:
            observation.is_incomplete = True

        result = self._scan(consumer, observations)

        assert result.distinct == 1
        assert result.blind
        assert all(observation.key_calls == ["verdict"] for observation in observations)


@pytest.mark.parametrize(
    "reason", ["runtime_error", "extraction_failed", "malformed_response"]
)
def test_detect_stops_calling_at_the_first_typed_failure(reason):
    calls = []

    def agent(text):
        calls.append(text)
        verdict = NoDecision(reason) if text == "bad" else "allow"
        return {"verdict": verdict}

    with pytest.raises(OutcomeNotScorable, match=reason):
        detect(from_callable(agent), ["ok", "bad", "never-called"])

    assert calls == ["ok", "bad"]


@pytest.mark.parametrize(
    "reason", ["runtime_error", "extraction_failed", "malformed_response"]
)
def test_detect_stops_immediately_when_the_first_input_fails(reason):
    calls = []

    def agent(text):
        calls.append(text)
        return {"verdict": NoDecision(reason)}

    with pytest.raises(OutcomeNotScorable, match=reason):
        detect(from_callable(agent), ["bad", "never-called"])

    assert calls == ["bad"]


def test_the_refusal_names_the_scan_rather_than_a_repeat_series():
    with pytest.raises(OutcomeNotScorable, match="a blindness scan"):
        score([Observation(verdict=NoDecision("runtime_error"))])


def test_score_stops_consuming_at_a_typed_failure():
    def observations():
        yield Observation(verdict="allow")
        yield Observation(verdict=NoDecision("runtime_error"))
        pytest.fail("consumed an observation after a typed failure")

    with pytest.raises(OutcomeNotScorable, match="runtime_error"):
        score(observations())


def test_distinct_harness_failures_cannot_look_like_decision_diversity():
    with pytest.raises(OutcomeNotScorable, match="harness failed"):
        score([
            Observation(verdict=NoDecision("runtime_error")),
            Observation(verdict=NoDecision("extraction_failed")),
        ])


def test_score_refuses_an_invalid_threshold_before_consuming_observations():
    def observations():
        pytest.fail("consumed observations for an invalid configuration")
        yield Observation(verdict="allow")

    with pytest.raises(ValueError, match="threshold"):
        score(observations(), threshold=0)


@pytest.mark.parametrize(
    "reason", ["runtime_error", "extraction_failed", "malformed_response"]
)
def test_detect_stops_at_a_duck_typed_failure(reason):
    calls = []

    def agent(text):
        calls.append(text)
        verdict = NoDecision(reason) if text == "bad" else "allow"
        return _KeyOnlyObservation(verdict)

    with pytest.raises(OutcomeNotScorable, match=reason):
        detect(agent, ["ok", "bad", "never-called"])

    assert calls == ["ok", "bad"]


@pytest.mark.parametrize(
    "reason", ["runtime_error", "extraction_failed", "malformed_response"]
)
def test_detect_stops_immediately_when_the_first_duck_typed_input_fails(reason):
    calls = []

    def agent(text):
        calls.append(text)
        return _KeyOnlyObservation(NoDecision(reason))

    with pytest.raises(OutcomeNotScorable, match=reason):
        detect(agent, ["bad", "never-called"])

    assert calls == ["bad"]


@pytest.mark.parametrize(
    "reason", ["runtime_error", "extraction_failed", "malformed_response"]
)
def test_score_stops_consuming_at_a_duck_typed_failure(reason):
    def observations():
        yield _KeyOnlyObservation("allow")
        yield _KeyOnlyObservation(NoDecision(reason))
        pytest.fail("consumed an observation after a duck-typed failure")

    with pytest.raises(OutcomeNotScorable, match=reason):
        score(observations())


def test_distinct_duck_typed_failures_cannot_look_like_decision_diversity():
    with pytest.raises(OutcomeNotScorable, match="harness failed"):
        score([
            _KeyOnlyObservation(NoDecision("runtime_error")),
            _KeyOnlyObservation(NoDecision("extraction_failed")),
        ])
