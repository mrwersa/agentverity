"""Tests for evidence-gated snapshots."""

from __future__ import annotations

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    from_callable,
    run,
)
from agentverity.runner import RunConfig
from agentverity.snapshot import (
    SNAPSHOT_SCHEMA,
    Snapshot,
    SnapshotCompatibilityError,
    SnapshotProbe,
    SnapshotRefused,
    compare_snapshot,
    create_snapshot,
    load_snapshot,
    save_snapshot,
)

INPUTS = ["allow-a", "allow-b", "block-a", "block-b"]
CONFIG = RunConfig(k=4, epsilon=0.5, blindness_threshold=0.9)


def _gate(text: str) -> dict:
    verdict = "block" if text.startswith("block") else "allow"
    return {"text": verdict, "verdict": verdict}


def _result(agent=_gate, inputs=INPUTS):
    return run(from_callable(agent), inputs, relations=[], config=CONFIG)


def test_snapshot_requires_explicit_reference_approval():
    with pytest.raises(SnapshotRefused, match="repeatability is not correctness"):
        create_snapshot(_result(), approved=False)


def test_snapshot_records_admission_evidence_not_raw_inputs():
    snapshot = create_snapshot(_result(), approved=True)
    value = snapshot.to_dict()
    assert value["schema"] == SNAPSHOT_SCHEMA
    assert value["admission_evidence"]["meter_call"] == "verdict-deterministic"
    assert value["admission_evidence"]["reference_approved"] is True
    assert not any(text in repr(value) for text in INPUTS)


def test_snapshot_refuses_blind_probe_set():
    blind = run(
        from_callable(lambda _text: {"verdict": "allow"}),
        INPUTS,
        relations=[],
        config=CONFIG,
    )
    with pytest.raises(SnapshotRefused, match="blind"):
        create_snapshot(blind, approved=True)


def test_snapshot_refuses_undecided_meter():
    undecided = run(
        from_callable(_gate),
        INPUTS,
        relations=[],
        config=RunConfig(k=2, epsilon=0.01),
    )
    with pytest.raises(SnapshotRefused, match="not enough evidence") as excinfo:
        create_snapshot(undecided, approved=True)

    message = str(excinfo.value)
    # "undecided" alone reads like a bug on an obviously deterministic agent,
    # so the refusal has to say how far short the run fell and what to change.
    assert "endpoint of at least 381 pairs" in message
    assert "optimistic bound" in message
    assert "--k" in message
    assert "--epsilon" in message


def test_underpowered_refusal_scales_its_advice_to_the_probe_set():
    """The suggested k depends on how many inputs are carrying the pairs."""
    from agentverity.snapshot import _underpowered_message

    few = run(from_callable(_gate), INPUTS, relations=[], config=RunConfig(k=2))
    message = _underpowered_message(few.meter)
    assert f"across {few.meter.inputs} inputs" in message


def test_underpowered_refusal_uses_counts_without_inviting_optional_stopping():
    """Observed flips can remain admissible, but only at a declared endpoint."""
    from agentverity.meter import MeterResult
    from agentverity.snapshot import _underpowered_message

    meter = MeterResult(
        layer="verdict",
        epsilon=0.05,
        inputs=1,
        repeats=146,
        pair_trials=73,
        pair_flips=4,
        inputs_with_flip=1,
        ci_low=0.0,
        ci_high=0.1,
    )

    message = _underpowered_message(meter)

    assert "at least 202 pairs" in message
    assert "no more than 4 flips" in message
    assert "not permission to keep sampling" in message


def test_stochastic_refusal_differs_from_underpowered_refusal():
    """A flipping verdict is a different problem from a small sample."""
    import itertools

    counter = itertools.count()

    def flipping(text: str) -> dict:
        return {"text": text, "verdict": "A" if next(counter) % 2 else "B"}

    stochastic = run(from_callable(flipping), INPUTS, relations=[])
    with pytest.raises(SnapshotRefused, match="stochastic") as excinfo:
        create_snapshot(stochastic, approved=True)
    assert "disagreed" in str(excinfo.value)
    assert "pairs are needed" not in str(excinfo.value)


def test_snapshot_refuses_incomplete_run():
    def failing(text: str) -> dict:
        if text == "block-a":
            raise RuntimeError("down")
        return _gate(text)

    incomplete = run(
        from_callable(failing),
        INPUTS,
        relations=[],
        config=RunConfig(
            k=4,
            epsilon=0.5,
            blindness_threshold=0.9,
            error_policy="record",
        ),
    )
    with pytest.raises(SnapshotRefused, match="incomplete"):
        create_snapshot(incomplete, approved=True)


def test_snapshot_check_is_order_independent():
    snapshot = create_snapshot(_result(), approved=True)
    current = _result(inputs=list(reversed(INPUTS)))
    assert compare_snapshot(snapshot, current).clean


def test_snapshot_check_reports_drift():
    snapshot = create_snapshot(_result(), approved=True)

    def changed(text: str) -> dict:
        if text == "allow-a":
            return {"verdict": "block"}
        return _gate(text)

    diff = compare_snapshot(snapshot, _result(agent=changed))
    assert diff.clean is False
    assert diff.checked == 4
    assert len(diff.changes) == 1
    assert diff.changes[0].expected == "allow"
    assert diff.changes[0].actual == "block"


def test_snapshot_check_rejects_different_probe_set():
    snapshot = create_snapshot(_result(), approved=True)
    with pytest.raises(SnapshotCompatibilityError, match="fingerprints"):
        compare_snapshot(
            snapshot,
            _result(inputs=["allow-a", "allow-b", "block-a", "block-c"]),
        )


def test_snapshot_round_trip(tmp_path):
    snapshot = create_snapshot(_result(), approved=True)
    path = tmp_path / "baseline.json"
    save_snapshot(snapshot, path)
    assert load_snapshot(path) == snapshot


def test_contract_snapshot_records_intent_and_rechecks_the_contract():
    suite = DecisionSuite(
        contract=DecisionContract(
            allowed={"allow", "review", "deny"},
            critical={"deny"},
        ),
        cases=(
            DecisionCase("allow-a", "allow"),
            DecisionCase("review-a", "review"),
            DecisionCase("block-a", "deny"),
        ),
    )

    def contract_gate(text: str) -> dict:
        if text.startswith("allow"):
            return {"verdict": "allow"}
        if text.startswith("review"):
            return {"verdict": "review"}
        return {"verdict": "deny"}

    result = run(
        from_callable(contract_gate),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )
    snapshot = create_snapshot(result, approved=True)
    value = snapshot.to_dict()

    assert value["decision_contract"]["critical"] == ["deny"]
    assert [probe["intended"] for probe in value["probes"]] == [
        "allow",
        "review",
        "deny",
    ]
    assert compare_snapshot(snapshot, result).clean

    changed_intent = DecisionSuite(
        contract=suite.contract,
        cases=(
            DecisionCase("allow-a", "review"),
            DecisionCase("review-a", "allow"),
            DecisionCase("block-a", "deny"),
        ),
    )
    changed_result = run(
        from_callable(contract_gate),
        suite=changed_intent,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )
    with pytest.raises(SnapshotCompatibilityError, match="intended decisions"):
        compare_snapshot(snapshot, changed_result)


def test_snapshot_refuses_an_incomplete_declared_contract():
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"allow", "review", "deny"}),
        cases=(
            DecisionCase("allow-a", "allow"),
            DecisionCase("block-a", "deny"),
        ),
    )
    result = run(
        from_callable(_gate),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )

    with pytest.raises(SnapshotRefused, match="decision contract"):
        create_snapshot(result, approved=True)


class TestBaseliningADeclaredRefusal:
    """ADR 4. Before this, a contract could declare a refusal and never baseline it.

    The feature worked right up to the point of using it: `create_snapshot`
    serialises through strict `json_value`, which refused every typed outcome.
    """

    def _agent(self, refuse: bool = False):
        from agentverity import NoDecision, Observation

        def run(text: str) -> Observation:
            if text.startswith("b"):
                return Observation(
                    text="I cannot help with that.", verdict=NoDecision("refused")
                )
            return Observation(text="ok", verdict="refund")

        return run

    def _suite(self):
        from agentverity import DecisionCase, DecisionContract, DecisionSuite

        return DecisionSuite(
            contract=DecisionContract(
                allowed=frozenset({"refund"}),
                required=frozenset({"refund"}),
                allowed_no_decisions=frozenset({"refused"}),
            ),
            cases=(
                DecisionCase(input="a1", expected="refund"),
                DecisionCase(input="b1", expected="refund"),
            ),
        )

    def test_a_declared_refusal_round_trips_through_a_snapshot(self, tmp_path):
        import json

        from agentverity import RunConfig, run
        from agentverity.snapshot import (
            SNAPSHOT_SCHEMA,
            create_snapshot,
            load_snapshot,
            save_snapshot,
        )

        result = run(
            self._agent(),
            suite=self._suite(),
            config=RunConfig(budget=200, epsilon=0.2),
        )
        snapshot = create_snapshot(result, approved=True)
        path = tmp_path / "baseline.json"
        save_snapshot(snapshot, path)

        stored = json.loads(path.read_text())
        assert stored["schema"] == SNAPSHOT_SCHEMA
        shapes = [probe["expected"] for probe in stored["probes"]]
        assert {"kind": "no_decision", "reason": "refused"} in shapes
        assert "refund" in shapes, "a decision stays a plain string"

        assert load_snapshot(path).probes == snapshot.probes

    def test_the_same_agent_still_matches_its_own_baseline(self, tmp_path):
        from agentverity import RunConfig, run
        from agentverity.snapshot import compare_snapshot, create_snapshot

        config = RunConfig(budget=200, epsilon=0.2)
        baseline = create_snapshot(
            run(self._agent(), suite=self._suite(), config=config),
            approved=True,
        )
        again = run(self._agent(), suite=self._suite(), config=config)

        assert compare_snapshot(baseline, again).changes == ()

    def test_a_baseline_written_before_the_types_still_matches_after(self):
        """Adoption must not invalidate every baseline a team already holds."""
        from agentverity import Decision
        from agentverity.snapshot import _comparable

        # what a pre-adoption run stored, and what a post-adoption run returns
        assert _comparable("refund") == _comparable(Decision("refund"))

    def test_a_reason_never_matches_a_label_of_the_same_name(self):
        from agentverity import Decision, NoDecision
        from agentverity.reporting import json_value
        from agentverity.snapshot import _comparable

        stored_reason = json_value(NoDecision("refused"), strict=True)
        stored_label = json_value(Decision("refused"), strict=True)

        assert _comparable(stored_reason) != _comparable(stored_label)


class TestAStoredOutcomeIsValidatedOnRead:
    """Evidence validated a reason on load and a snapshot did not.

    Found reviewing my own PR. A hand-edited or corrupted snapshot carried
    garbage into a comparison, and two differently malformed probes compared
    equal to each other because an absent reason became the same `None` in
    both.
    """

    def _snapshot_file(self, tmp_path):
        import json

        from agentverity import (
            DecisionCase,
            DecisionContract,
            DecisionSuite,
            NoDecision,
            Observation,
            RunConfig,
            run,
        )
        from agentverity.snapshot import create_snapshot, save_snapshot

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed=frozenset({"refund"}),
                required=frozenset({"refund"}),
                allowed_no_decisions=frozenset({"refused"}),
            ),
            cases=(
                DecisionCase(input="a1", expected="refund"),
                DecisionCase(input="b1", expected="refund"),
            ),
        )

        def agent(text: str) -> Observation:
            if text.startswith("b"):
                return Observation(text="no", verdict=NoDecision("refused"))
            return Observation(text="ok", verdict="refund")

        path = tmp_path / "baseline.json"
        save_snapshot(
            create_snapshot(
                run(agent, suite=suite, config=RunConfig(budget=200, epsilon=0.2)),
                approved=True,
            ),
            path,
        )
        return path, json.loads(path.read_text())

    @pytest.mark.parametrize(
        "field, value",
        [
            ("reason", "invented"),
            ("reason", "extraction_failed"),
            ("reason", None),
            ("kind", "decision"),
        ],
    )
    def test_a_malformed_stored_outcome_is_refused(self, tmp_path, field, value):
        import json

        from agentverity.snapshot import SnapshotCompatibilityError, load_snapshot

        path, doc = self._snapshot_file(tmp_path)
        for probe in doc["probes"]:
            if isinstance(probe["expected"], dict):
                if value is None:
                    probe["expected"].pop(field, None)
                else:
                    probe["expected"][field] = value
        path.write_text(json.dumps(doc))

        with pytest.raises(SnapshotCompatibilityError):
            load_snapshot(path)

    def test_a_harness_failure_could_not_have_been_written(self, tmp_path):
        """So reading one back is a corruption, not an outcome."""
        import json

        from agentverity.snapshot import SnapshotCompatibilityError, load_snapshot

        path, doc = self._snapshot_file(tmp_path)
        for probe in doc["probes"]:
            if isinstance(probe["expected"], dict):
                probe["expected"]["reason"] = "runtime_error"
        path.write_text(json.dumps(doc))

        with pytest.raises(SnapshotCompatibilityError, match="contract can declare"):
            load_snapshot(path)

    @pytest.mark.parametrize("corrupt", [42, True, 3.14, None])
    def test_a_corrupt_scalar_is_refused_too(self, tmp_path, corrupt):
        """It loaded and surfaced as a permanent change rather than a refusal.

        The same reasoning as the reason check: no run produces a number here,
        so reading one back is a corrupt file rather than an outcome, and a
        baseline that reports a change forever is worse than one that says the
        file is broken.
        """
        import json

        from agentverity.snapshot import SnapshotCompatibilityError, load_snapshot

        path, doc = self._snapshot_file(tmp_path)
        doc["probes"][0]["expected"] = corrupt
        path.write_text(json.dumps(doc))

        with pytest.raises(SnapshotCompatibilityError):
            load_snapshot(path)

    def test_a_string_and_a_tool_path_still_load(self, tmp_path):
        """The shapes a run does produce are untouched."""
        import json

        from agentverity.snapshot import load_snapshot

        path, doc = self._snapshot_file(tmp_path)
        doc["probes"][0]["expected"] = ["search", "answer"]
        path.write_text(json.dumps(doc))

        assert load_snapshot(path).probes[0].expected == ["search", "answer"]

    def test_a_valid_file_still_loads(self, tmp_path):
        from agentverity.snapshot import load_snapshot

        path, _ = self._snapshot_file(tmp_path)
        probes = load_snapshot(path).probes

        assert {"kind": "no_decision", "reason": "refused"} in [
            p.expected for p in probes
        ]

    def test_a_non_string_isolation_is_refused_not_a_traceback(self, tmp_path):
        """A JSON array for isolation is corrupt input, not a Python crash.

        The membership test read the value straight from the file, so a list
        raised TypeError out of the loader and past the CLI's refusal path.
        """
        import json

        from agentverity.snapshot import SnapshotCompatibilityError, load_snapshot

        path, doc = self._snapshot_file(tmp_path)
        doc["admission_evidence"]["isolation"] = ["fresh-session"]
        path.write_text(json.dumps(doc))

        with pytest.raises(SnapshotCompatibilityError, match="isolation"):
            load_snapshot(path)


def _reference(**overrides):
    """A stored reference with fixed fields, so the rendered view is exact."""
    fields = {
        "schema": SNAPSHOT_SCHEMA,
        "created_at": "2026-10-11T09:00:00+00:00",
        "agentverity_version": "0.23.1",
        "layer": "verdict",
        "epsilon": 0.5,
        "k": 4,
        "blindness_threshold": 0.9,
        "meter_pair_trials": 8,
        "meter_ci_high": 0.31,
        "blindness_skew": 0.5,
        "blindness_distinct": 2,
        "decision_contract": None,
        "probes": (SnapshotProbe("a" * 64, "allow"),),
        "isolation": "fresh-session",
    }
    fields.update(overrides)
    return Snapshot(**fields)


class TestTheRegressionReferenceView:
    """A snapshot was machine-only JSON, so auditing a reference meant reading
    raw fields. The view renders the stored record and nothing else."""

    def test_the_default_view_is_exact(self):
        assert _reference().render() == (
            "regression reference agentverity.snapshot/v4\n"
            "  created                2026-10-11T09:00:00+00:00\n"
            "  library                0.23.1\n"
            "  projection layer       verdict\n"
            "  tolerance              0.5\n"
            "  configured k           4\n"
            "  blindness threshold    0.9\n"
            "\n"
            "admission evidence\n"
            "  call                   verdict-deterministic\n"
            "  disjoint pairs         8\n"
            "  diagnostic bound       0.3100\n"
            "  probe skew             0.5000\n"
            "  distinct verdicts      2\n"
            "  isolation              fresh-session\n"
            "  independence           asserted from separated trials\n"
            "  reference approved     yes\n"
            "\n"
            "references (1)\n"
            "  sha256=aaaaaaaaaaaa  expected=\"allow\"\n"
            "\n"
            "limits\n"
            "  this record admits repeatability at the recorded tolerance, not\n"
            "  correctness, and only for the projection, tolerance and contract\n"
            "  above. A later match shows the decision layer was preserved.\n"
            "  the schema does not record which rule admitted the reference (a\n"
            "  fixed Wilson interval or a declared sequential checkpoint) or the\n"
            "  repeats actually collected, so the bound above is diagnostic and\n"
            "  configured k is a minimum, not the count that ran."
        )

    def test_it_shows_a_reference_by_fingerprint_not_by_input(self):
        text = _reference().render()
        assert "aaaaaaaaaaaa" in text
        assert "expected=\"allow\"" in text

    def test_it_says_when_independence_was_not_asserted(self):
        text = _reference(isolation="unknown").render()
        assert "not asserted (isolation unknown)" in text

    def test_it_renders_a_no_decision_by_its_reason(self):
        probe = SnapshotProbe("b" * 64, {"kind": "no_decision", "reason": "refused"})
        text = _reference(probes=(probe,)).render()
        assert "expected=no decision: refused" in text

    def test_it_lists_a_declared_contract_and_intent(self):
        contract = DecisionContract(allowed={"allow", "block"}, critical={"block"})
        probe = SnapshotProbe("a" * 64, "allow", intended="allow")
        text = _reference(decision_contract=contract, probes=(probe,)).render()
        assert "declared decision contract" in text
        assert "allowed                allow, block" in text
        assert "critical               block" in text
        assert "intended=allow" in text

    def test_it_states_what_a_match_does_not_establish(self):
        text = _reference().render()
        assert "admits repeatability at the recorded tolerance" in text
        assert "A later match shows the decision layer was preserved." in text

    def test_it_renders_contract_mappings_sorted(self):
        contract = DecisionContract(
            allowed={"allow", "block"},
            minimum_cases={"block": 2, "allow": 3},
            stability_targets={"block": 0.01, "allow": 0.05},
        )
        text = _reference(decision_contract=contract).render()
        assert "minimum cases          allow=3, block=2" in text
        assert "stability targets      allow=0.05, block=0.01" in text

    def test_it_names_k_as_configured_and_calls_the_bound_diagnostic(self):
        """`k` is a configured minimum and the bound may not explain admission.

        A route plan can raise the per-input count above `k`, and a declared
        sequential checkpoint can admit at a Wilson bound above the tolerance.
        Neither the rule nor the counts collected are in the schema, so the
        view must not present them as the admission reason.
        """
        text = _reference().render()
        assert "configured k           4" in text
        assert "repeats per input" not in text
        assert "confidence" not in text
        assert "diagnostic bound       0.3100" in text
        assert "does not record which rule admitted the reference" in text
        assert "repeats actually collected" in text

    def test_a_no_decision_without_a_reason_falls_back_to_json(self):
        probe = SnapshotProbe("a" * 64, {"kind": "no_decision"})
        text = _reference(probes=(probe,)).render()
        assert 'expected={"kind": "no_decision"}' in text

    def test_the_view_never_prints_a_raw_input(self):
        text = create_snapshot(_result(), approved=True).render()
        assert text
        assert not any(probe in text for probe in INPUTS)

    def test_a_sequential_reference_marks_the_bound_diagnostic(self):
        inputs = [f"input_{i}" for i in range(12)] + [
            f"secret_{i}" for i in range(12)
        ]

        def stable(text: str) -> dict:
            return {"verdict": "block" if "secret" in text else "allow"}

        result = run(
            from_callable(stable), inputs, config=RunConfig(sequential=True)
        )
        snapshot = create_snapshot(result, approved=True)

        # The declared checkpoint admitted at the zero-flip budget, where the
        # Wilson bound sits above the tolerance the checkpoint never read.
        assert snapshot.meter_ci_high > snapshot.epsilon
        text = snapshot.render()
        assert "diagnostic bound" in text
        assert "not the count that ran" in text

    def test_a_route_target_reference_names_k_as_a_minimum(self):
        suite = DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "deny"},
                stability_targets={"deny": 0.05},
            ),
            cases=(
                DecisionCase("approve_req", "approve"),
                DecisionCase("deny_req", "deny"),
            ),
        )

        def agent(text: str) -> dict:
            return {"verdict": "deny" if text.startswith("deny") else "approve"}

        result = run(
            from_callable(agent), suite=suite, config=RunConfig(epsilon=0.5)
        )
        snapshot = create_snapshot(result, approved=True)

        # A route plan raises the collected repeats above the configured floor.
        allocated = {plan.decision: plan.repeats_each for plan in result.route_plans}
        assert max(allocated.values()) > snapshot.k
        text = snapshot.render()
        assert "configured k" in text
        assert "repeats per input" not in text
        assert "repeats actually collected" in text
