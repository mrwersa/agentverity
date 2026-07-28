"""Tests for comparing two independently collected evidence windows."""

from __future__ import annotations

import json

import pytest

from agentverity import EvidenceCase, EvidenceSet, compare_evidence
from agentverity.cli import main


def window(card_flips: int, *, model: str = "router-v3", isolation: str = "fresh-session"):
    """One window where `card_security` flips on `card_flips` of 13 pairs."""
    observations = ["card_security", "merchant_dispute"] * card_flips
    observations += ["card_security", "card_security"] * (13 - card_flips)
    return EvidenceSet(
        cases=(
            EvidenceCase("card case", tuple(observations), expected="card_security"),
            EvidenceCase("dup case", ("duplicate_charge",) * 26, expected="duplicate_charge"),
        ),
        isolation=isolation,
        provenance={"model": model},
    )


class TestTheVerdictMoveIsTheEvent:
    """A rate wandering inside one conclusion is noise. A route crossing from
    one tri-state result to another is a release event."""

    def test_a_route_that_becomes_stochastic_is_reported(self):
        drift = compare_evidence(window(0), window(9), epsilon=0.05)
        card = next(r for r in drift.routes if r.decision == "card_security")

        assert card.verdict_changed is True
        assert card.after_call == "verdict-stochastic"
        assert drift.changed_routes == ("card_security",)
        assert drift.drifted is True

    def test_an_unchanged_route_is_not_reported_as_changed(self):
        drift = compare_evidence(window(0), window(0), epsilon=0.05)
        dup = next(r for r in drift.routes if r.decision == "duplicate_charge")

        assert dup.verdict_changed is False
        assert dup.direction == "unchanged"

    def test_a_rate_moving_within_one_verdict_is_direction_only(self):
        drift = compare_evidence(window(9), window(11), epsilon=0.05)
        card = next(r for r in drift.routes if r.decision == "card_security")

        assert card.verdict_changed is False
        assert card.direction == "higher"

    def test_a_route_settling_down_is_lower(self):
        """`higher` and `lower` describe the observed change rate. They
        deliberately do not say `wider` or `tighter`, which would suggest a
        statement about interval width that this comparison does not make."""
        drift = compare_evidence(window(11), window(9), epsilon=0.05)
        card = next(r for r in drift.routes if r.decision == "card_security")
        assert card.direction == "lower"


class TestIndependenceIsNeverClaimed:
    """Two correlated runs agree with each other very comfortably, so
    agreement across windows says nothing about independence within one."""

    def test_the_note_travels_with_every_comparison(self):
        drift = compare_evidence(window(0), window(0))
        assert "does not establish that trials were independent" in drift.independence_note

    def test_the_note_names_both_isolation_levels(self):
        drift = compare_evidence(
            window(0, isolation="shared-session"), window(0, isolation="unknown")
        )
        assert "'shared-session'" in drift.independence_note
        assert "'unknown'" in drift.independence_note

    def test_the_note_appears_in_the_rendered_output(self):
        assert "independent" in compare_evidence(window(0), window(0)).render()


class TestStructuralChanges:
    def test_a_new_decision_is_reported_as_gained_not_compared(self):
        after = EvidenceSet(
            cases=(
                EvidenceCase("card case", ("card_security",) * 26, expected="card_security"),
                EvidenceCase("dup case", ("duplicate_charge",) * 26, expected="duplicate_charge"),
                EvidenceCase("new case", ("cash_withdrawal",) * 26, expected="cash_withdrawal"),
            ),
        )
        drift = compare_evidence(window(0), after)

        assert drift.gained_decisions == ("cash_withdrawal",)
        assert drift.lost_decisions == ()
        assert drift.drifted is True

    def test_a_disappearing_decision_is_reported_as_lost(self):
        drift = compare_evidence(
            window(0),
            EvidenceSet(
                cases=(
                    EvidenceCase("card case", ("card_security",) * 26, expected="card_security"),
                )
            ),
        )
        assert drift.lost_decisions == ("duplicate_charge",)

    def test_a_new_flip_pair_is_reported(self):
        drift = compare_evidence(window(0), window(9))
        assert drift.gained_flip_pairs == ("card_security <-> merchant_dispute",)

    def test_a_resolved_flip_pair_is_reported_as_lost(self):
        drift = compare_evidence(window(9), window(0))
        assert drift.lost_flip_pairs == ("card_security <-> merchant_dispute",)


class TestProvenance:
    def test_a_model_change_is_surfaced(self):
        drift = compare_evidence(window(0, model="router-v3"), window(0, model="router-v4"))

        assert drift.provenance_changes == (("model", "router-v3", "router-v4"),)
        assert drift.drifted is True

    def test_identical_provenance_produces_no_change(self):
        assert compare_evidence(window(0), window(0)).provenance_changes == ()

    def test_a_provenance_key_appearing_is_surfaced(self):
        before = EvidenceSet(cases=window(0).cases, provenance={})
        after = EvidenceSet(cases=window(0).cases, provenance={"prompt": "v9"})

        assert compare_evidence(before, after).provenance_changes == (
            ("prompt", None, "v9"),
        )

    def test_provenance_change_alone_counts_as_drift(self):
        """A model swap with identical decisions is still the fact you most
        want to see next to a comparison."""
        drift = compare_evidence(window(0, model="a"), window(0, model="b"))

        assert drift.changed_routes == ()
        assert drift.drifted is True


def test_evidence_without_intended_decisions_cannot_be_compared():
    plain = EvidenceSet(cases=(EvidenceCase("x", ("approve",) * 4),))
    with pytest.raises(ValueError, match="intended decision on every case"):
        compare_evidence(plain, plain)


def test_drift_serialises():
    payload = compare_evidence(window(0), window(9, model="router-v4")).to_dict()

    assert payload["drifted"] is True
    assert payload["changed_routes"] == ["card_security"]
    assert payload["provenance_changes"][0]["after"] == "router-v4"
    assert "independence_note" in payload


class TestCli:
    @staticmethod
    def write(tmp_path, name, evidence):
        from agentverity import save_evidence

        path = tmp_path / name
        save_evidence(evidence, path)
        return str(path)

    def test_drift_exits_non_zero_and_names_the_route(self, tmp_path, capsys):
        before = self.write(tmp_path, "before.json", window(0))
        after = self.write(tmp_path, "after.json", window(9))

        assert main(["compare-evidence", before, after]) == 1
        out = capsys.readouterr().out
        assert "card_security" in out
        assert "DRIFTED" in out

    def test_no_drift_exits_zero(self, tmp_path, capsys):
        before = self.write(tmp_path, "before.json", window(0))
        after = self.write(tmp_path, "after.json", window(0))

        assert main(["compare-evidence", before, after]) == 0
        assert "NO CHANGE" in capsys.readouterr().out

    def test_json_output_is_written(self, tmp_path):
        before = self.write(tmp_path, "before.json", window(0))
        after = self.write(tmp_path, "after.json", window(9))
        out = tmp_path / "drift.json"

        main(["compare-evidence", before, after, "--json", str(out)])
        payload = json.loads(out.read_text())

        assert payload["changed_routes"] == ["card_security"]


def test_two_windows_with_no_shared_route_report_that_plainly():
    left = EvidenceSet(
        cases=(EvidenceCase("a", ("approve",) * 4, expected="approve"),)
    )
    right = EvidenceSet(cases=(EvidenceCase("b", ("deny",) * 4, expected="deny"),))
    drift = compare_evidence(left, right)

    assert drift.routes == ()
    assert "no routes in common" in drift.render()
    assert drift.gained_decisions == ("deny",)
    assert "routes gained: deny" in drift.render()


def test_a_route_with_no_usable_pairs_is_incomparable_not_unchanged():
    """Zero trials on one side means there is nothing to compare, which is a
    different statement from the rate having stayed the same."""
    from agentverity.drift import RouteDrift

    route = RouteDrift(
        decision="deny",
        before_flips=0,
        before_trials=0,
        after_flips=0,
        after_trials=13,
        before_call="undecided (add repeats or inputs)",
        after_call="undecided (add repeats or inputs)",
        epsilon=0.05,
    )
    assert route.direction == "incomparable"
    assert route.before_rate is None


def test_the_rendered_output_lists_every_provenance_change():
    drift = compare_evidence(
        EvidenceSet(cases=window(0).cases, provenance={"model": "a", "prompt": "p1"}),
        EvidenceSet(cases=window(0).cases, provenance={"model": "b", "prompt": "p2"}),
    )
    rendered = drift.render()

    assert "provenance:" in rendered
    assert "model: 'a' -> 'b'" in rendered
    assert "prompt: 'p1' -> 'p2'" in rendered


class TestWhatCountsAsDrift:
    """Printed but ignored is the worst outcome for a gate: a reader sees the
    change and the exit code says nothing happened."""

    def test_a_volatile_timestamp_is_shown_but_never_counted(self):
        """A Promptfoo export stamps its collection time, so counting it would
        report every real comparison as drifted and make the command useless
        on exactly the data it exists for."""
        before = EvidenceSet(cases=window(0).cases, provenance={"collected_at": "2026-07-01"})
        after = EvidenceSet(cases=window(0).cases, provenance={"collected_at": "2026-08-01"})
        drift = compare_evidence(before, after)

        assert drift.drifted is False
        assert drift.informational_changes == (
            ("collected_at", "2026-07-01", "2026-08-01"),
        )
        assert drift.provenance_changes == ()
        assert "not counted as drift" in drift.render()

    def test_a_new_flip_pair_counts_as_drift(self):
        """A new confusion between two routes is a behavioural change even
        when both routes keep the same tri-state result."""
        drift = compare_evidence(window(0), window(2))

        assert drift.changed_routes == ()
        assert drift.gained_flip_pairs != ()
        assert drift.drifted is True

    def test_a_resolved_flip_pair_counts_as_drift(self):
        assert compare_evidence(window(2), window(0)).drifted is True

    def test_a_change_of_isolation_counts_as_drift(self):
        """It changes what the evidence means, which is why printing it and
        then ignoring it would be worse than not printing it."""
        drift = compare_evidence(
            window(0, isolation="fresh-session"),
            window(0, isolation="shared-session"),
        )

        assert drift.isolation_changed is True
        assert drift.drifted is True
        assert "the evidence means something different" in drift.render()

    def test_identical_windows_do_not_drift(self):
        assert compare_evidence(window(0), window(0)).drifted is False


def test_evidence_on_different_layers_cannot_be_compared():
    """A verdict and a tool path are not the same observation, so a difference
    between them is not drift."""
    verdict = EvidenceSet(cases=window(0).cases, layer="verdict")
    text = EvidenceSet(cases=window(0).cases, layer="text")

    with pytest.raises(ValueError, match="different layers"):
        compare_evidence(verdict, text)


class TestCliInputErrors:
    def test_a_malformed_evidence_file_is_a_usage_error(self, tmp_path, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")

        assert main(["compare-evidence", str(bad), str(bad)]) == 2
        assert "error:" in capsys.readouterr().err

    def test_incompatible_layers_are_a_usage_error(self, tmp_path, capsys):
        from agentverity import save_evidence

        left = tmp_path / "l.json"
        right = tmp_path / "r.json"
        save_evidence(EvidenceSet(cases=window(0).cases, layer="verdict"), left)
        save_evidence(EvidenceSet(cases=window(0).cases, layer="text"), right)

        assert main(["compare-evidence", str(left), str(right)]) == 2
        assert "different layers" in capsys.readouterr().err
