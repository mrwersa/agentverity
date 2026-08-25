"""Live curtailment stops only on fixed-endpoint admission impossibility."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    EvidenceCase,
    EvidenceError,
    EvidenceSet,
    RunConfig,
    assess_evidence,
    create_snapshot,
    from_callable,
    run,
)
from agentverity.cli import main
from agentverity.reporting import run_result_to_dict, run_result_to_junit_xml
from agentverity.snapshot import SnapshotRefused
from agentverity.telemetry import run_result_to_otel_attributes

REPLAY = Path(__file__).parent / "fixtures" / "curtailment" / "replay.json"


def _pair_agent(outcomes: list[bool]):
    calls = 0

    def agent(_text: str) -> dict[str, str]:
        nonlocal calls
        pair = calls // 2
        within_pair = calls % 2
        calls += 1
        flipped = outcomes[pair] if pair < len(outcomes) else False
        verdict = "review" if flipped and within_pair else "approve"
        return {"verdict": verdict}

    return from_callable(agent), lambda: calls


def _replay(prefix: list[bool], endpoint_pairs: int):
    outcomes = [*prefix, *([False] * (endpoint_pairs - len(prefix)))]
    agent, calls = _pair_agent(outcomes)
    result = run(
        agent,
        ["case"],
        relations=[],
        config=RunConfig(
            k=2 * endpoint_pairs,
            epsilon=0.05,
            curtail=True,
            run_blindness=False,
        ),
    )
    return result, calls()


def _evidence_from_pairs(outcomes: list[bool]) -> EvidenceSet:
    observations = []
    for flipped in outcomes:
        observations.extend(("approve", "review" if flipped else "approve"))
    return EvidenceSet(
        cases=(EvidenceCase(input="case", observations=tuple(observations)),),
        isolation="fresh-session",
    )


def test_versioned_replays_match_exact_fixed_endpoint_boundaries():
    """Committed ordered prefixes exercise both sides of the strict boundary."""
    fixture = json.loads(REPLAY.read_text(encoding="utf-8"))
    assert fixture["schema"] == "agentverity.curtailment-replay/v1"

    for scenario in fixture["scenarios"]:
        result, calls = _replay(scenario["prefix_outcomes"], scenario["endpoint_pairs"])
        stop = result.curtailment
        expected = scenario["expected_stopping_pair"]
        if expected is None:
            assert stop is None, scenario["name"]
            assert result.meter is not None
            assert result.meter.call == "verdict-deterministic"
            assert calls == 2 * scenario["endpoint_pairs"]
        else:
            assert stop is not None, scenario["name"]
            assert stop.stopping_pair == expected
            assert stop.observed_flips == scenario["expected_observed_flips"]
            assert stop.avoided_pairs == scenario["expected_avoided_pairs"]
            assert calls == stop.meter_calls_spent


def test_retrospective_replay_matches_live_curtailment_path_by_path():
    """The offline counterfactual uses the audited live rule and pair order."""
    fixture = json.loads(REPLAY.read_text(encoding="utf-8"))

    for scenario in fixture["scenarios"]:
        endpoint = scenario["endpoint_pairs"]
        outcomes = [
            *scenario["prefix_outcomes"],
            *([False] * (endpoint - len(scenario["prefix_outcomes"]))),
        ]
        live, _calls = _replay(scenario["prefix_outcomes"], endpoint)
        assessed = assess_evidence(
            _evidence_from_pairs(outcomes),
            epsilon=0.05,
            replay_curtailment=True,
        )
        replay = assessed.curtailment_replay

        assert replay is not None
        assert assessed.meter is not None
        assert assessed.status != "curtailed"
        assert replay.endpoint_pairs == endpoint
        assert replay.stopping_pair == (
            live.curtailment.stopping_pair if live.curtailment is not None else None
        )
        assert replay.observed_flips == (
            live.curtailment.observed_flips
            if live.curtailment is not None
            else sum(outcomes)
        )
        assert replay.avoided_pairs == scenario["expected_avoided_pairs"]


def test_retrospective_replay_is_supplementary_and_labelled_counterfactual():
    """A replay never replaces the observed endpoint classification."""
    outcomes = [True, *([False] * 72)]
    result = assess_evidence(
        _evidence_from_pairs(outcomes),
        epsilon=0.05,
        replay_curtailment=True,
    )
    payload = run_result_to_dict(result)

    assert result.meter is not None
    assert result.meter.call.startswith("undecided")
    assert result.status != "curtailed"
    assert payload["meter"]["call"].startswith("undecided")
    assert payload["curtailment"] is None
    assert payload["curtailment_replay"] == {
        "analysis": "post-hoc-counterfactual",
        "schedule": "round-robin-case-order",
        "outcome": "admission-unreachable",
        "stopping_pair": 1,
        "endpoint_pairs": 73,
        "observed_flips": 1,
        "avoided_pairs": 72,
        "meter_calls_avoided": 144,
        "reason": (
            "admission became unreachable at the recorded fixed endpoint even "
            "if every remaining pair agreed"
        ),
        "changes_endpoint_classification": False,
    }
    summary = result.summary()
    assert "post-hoc; not an admissible stopping procedure" in summary
    assert "endpoint classification above is unchanged" in summary


def test_retrospective_replay_refuses_missing_ordered_work():
    """A recorded error cannot be assigned a favourable position post hoc."""
    evidence = EvidenceSet(
        cases=(
            EvidenceCase(
                input="case",
                observations=("approve", "approve"),
                errors=1,
            ),
        )
    )

    with pytest.raises(EvidenceError, match="missing pair position unknown"):
        assess_evidence(evidence, replay_curtailment=True)


def test_retrospective_replay_retains_only_aggregate_counts():
    """The optional JSON member does not widen report retention."""
    result = assess_evidence(
        EvidenceSet(
            cases=(
                EvidenceCase(
                    input="PRIVATE-PROBE-INPUT",
                    observations=("PRIVATE-A", "PRIVATE-B")
                    + ("PRIVATE-A",) * 144,
                ),
            )
        ),
        replay_curtailment=True,
    )

    encoded = json.dumps(run_result_to_dict(result)["curtailment_replay"])
    assert "PRIVATE-PROBE-INPUT" not in encoded
    assert "PRIVATE-A" not in encoded
    assert "PRIVATE-B" not in encoded


def test_an_all_agree_path_reaches_the_unchanged_fixed_endpoint():
    """Curtailment can never turn favourable partial evidence into admission."""
    result, calls = _replay([], 73)

    assert result.curtailment is None
    assert result.meter is not None
    assert result.meter.call == "verdict-deterministic"
    assert result.meter.pair_trials == 73
    assert calls == 146


def test_an_endpoint_flip_receives_the_real_fixed_classification():
    """The final pair is an observed endpoint, not an early curtailment."""
    result, calls = _replay([*([False] * 72), True], 73)

    assert result.curtailment is None
    assert result.meter is not None
    assert result.meter.pair_flips == 1
    assert result.meter.call.startswith("undecided")
    assert calls == 146


def test_a_curtailment_is_an_execution_outcome_not_a_final_meter_class():
    """Partial evidence must not be relabelled stochastic or undecided."""
    result, _calls = _replay([True], 73)

    assert result.status == "curtailed"
    assert result.meter is None
    assert result.curtailment is not None
    assert result.curtailment.reason.startswith("admission is unreachable")
    assert "classification: none" in result.summary()


def test_reports_retain_the_stop_boundary_and_avoided_work():
    """Machine and CI reports expose the same early-impossibility result."""
    result, _calls = _replay([True], 73)
    payload = run_result_to_dict(result)

    assert payload["status"] == "curtailed"
    assert payload["meter"] is None
    assert payload["curtailment"] == {
        "outcome": "admission-unreachable",
        "stopping_pair": 1,
        "endpoint_pairs": 73,
        "observed_flips": 1,
        "avoided_pairs": 72,
        "meter_calls_spent": 2,
        "meter_calls_avoided": 144,
        "reason": (
            "admission is unreachable at the predeclared fixed endpoint even if "
            "every remaining pair agrees"
        ),
        "final_classification": None,
    }
    xml = ET.fromstring(run_result_to_junit_xml(result))
    assert xml.attrib["failures"] == "1"
    assert xml.find(".//failure") is not None
    attributes = run_result_to_otel_attributes(result)
    assert attributes["agentverity.curtailment.stopping_pair"] == 1
    assert attributes["agentverity.curtailment.meter_calls_avoided"] == 144


def test_curtailment_reports_do_not_retain_partial_inputs_or_outputs():
    """The new aggregate result does not widen existing retention boundaries."""
    calls = 0

    def agent(_text):
        nonlocal calls
        calls += 1
        return {
            "verdict": "approve" if calls % 2 else "review",
            "text": "PRIVATE-PARTIAL-OUTPUT",
        }

    result = run(
        from_callable(agent),
        ["PRIVATE-PROBE-INPUT"],
        relations=[],
        config=RunConfig(
            k=146,
            epsilon=0.05,
            curtail=True,
            run_blindness=False,
        ),
    )
    encoded = json.dumps(run_result_to_dict(result))
    junit = run_result_to_junit_xml(result)
    telemetry = repr(run_result_to_otel_attributes(result))

    for surface in (encoded, junit, telemetry):
        assert "PRIVATE-PROBE-INPUT" not in surface
        assert "PRIVATE-PARTIAL-OUTPUT" not in surface


def test_snapshot_admission_refuses_a_curtailed_run_explicitly():
    """The missing endpoint cannot be mistaken for an admissible snapshot."""
    result, _calls = _replay([True], 73)

    with pytest.raises(SnapshotRefused, match="without assigning a final"):
        create_snapshot(result, approved=True)


def test_run_cli_reports_curtailment_as_a_finding(monkeypatch, tmp_path, capsys):
    """The live option reaches the runner and retains an interpretable exit."""
    inputs = tmp_path / "inputs.txt"
    inputs.write_text("case\n", encoding="utf-8")
    calls = 0

    def factory():
        def agent(_text):
            nonlocal calls
            calls += 1
            return {"verdict": "approve" if calls % 2 else "review"}

        return agent

    monkeypatch.setattr("agentverity.cli._load_agent", lambda _spec: factory)
    code = main(
        [
            "run",
            "--agent",
            "fixture:factory",
            "--inputs",
            str(inputs),
            "--k",
            "146",
            "--epsilon",
            "0.05",
            "--curtail",
            "--no-blindness",
            "--no-relations",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["status"] == "curtailed"
    assert payload["curtailment"]["stopping_pair"] == 1
    assert calls == 2


def test_snapshot_cli_refuses_curtailment_without_writing_a_reference(
    monkeypatch, tmp_path, capsys
):
    """An early impossibility finding is not silently converted to a snapshot."""
    inputs = tmp_path / "inputs.txt"
    output = tmp_path / "snapshot.json"
    inputs.write_text("case\n", encoding="utf-8")
    calls = 0

    def factory():
        def agent(_text):
            nonlocal calls
            calls += 1
            return {"verdict": "approve" if calls % 2 else "review"}

        return agent

    monkeypatch.setattr("agentverity.cli._load_agent", lambda _spec: factory)
    code = main(
        [
            "snapshot",
            "--agent",
            "fixture:factory",
            "--inputs",
            str(inputs),
            "--output",
            str(output),
            "--accept-reference",
            "--k",
            "146",
            "--epsilon",
            "0.05",
            "--curtail",
        ]
    )

    assert code == 2
    assert "without assigning a final" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"run_meter": False}, "requires the meter"),
        ({"sequential": True}, "choose one"),
        ({"max_workers": 2}, "max_workers=1"),
    ],
)
def test_ambiguous_curtailment_combinations_are_refused(kwargs, message):
    """One opt-in rule owns collection order and the fixed endpoint."""
    with pytest.raises(ValueError, match=message):
        RunConfig(curtail=True, **kwargs)


def test_the_additive_option_does_not_shift_existing_positional_config_fields():
    """The 0.20.0 positional max_workers and error_policy slots stay intact."""
    config = RunConfig(
        None,
        "balanced",
        None,
        None,
        0.9,
        "verdict",
        True,
        True,
        True,
        False,
        3,
        "record",
    )

    assert config.max_workers == 3
    assert config.error_policy == "record"
    assert config.curtail is False


def test_route_specific_endpoints_are_refused_before_agent_calls():
    """A pooled stopping rule cannot silently override per-route sizing."""
    calls = 0

    def agent(_text):
        nonlocal calls
        calls += 1
        return {"verdict": "approve"}

    suite = DecisionSuite(
        contract=DecisionContract(
            allowed={"approve"},
            stability_targets={"approve": 0.05},
        ),
        cases=(DecisionCase("case", "approve"),),
    )
    with pytest.raises(ValueError, match="separate endpoints"):
        run(
            from_callable(agent),
            suite=suite,
            relations=[],
            config=RunConfig(curtail=True),
        )
    assert calls == 0


def test_recorded_call_failure_is_not_relabelled_statistical_curtailment():
    """Incomplete execution remains incomplete even when admission is impossible."""
    calls = 0

    def failing(_text: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("provider failed")
        return {"verdict": "approve"}

    result = run(
        from_callable(failing),
        ["case"],
        relations=[],
        config=RunConfig(
            k=4,
            epsilon=0.5,
            curtail=True,
            run_blindness=False,
            error_policy="record",
        ),
    )

    assert result.status == "incomplete"
    assert result.curtailment is None
