"""Isolation decides whether evidence may certify a baseline. See ADR 5.

The caveat existed since v0.12.0 and had no consequence: a run could print
"repeats are not independent and the interval is narrower than the evidence
supports" and then be frozen as a baseline on the strength of that interval.
"""

from __future__ import annotations

import json

import pytest

from agentverity.evidence import EvidenceCase, EvidenceSet, assess_evidence
from agentverity.snapshot import (
    CERTIFIABLE_ISOLATION,
    Snapshot,
    SnapshotCompatibilityError,
    SnapshotRefused,
    compare_snapshot,
    create_snapshot,
    save_snapshot,
)


def _result(isolation: str):
    """Evidence strong enough that only isolation can refuse it."""
    cases = tuple(
        EvidenceCase(
            input=f"probe-{index}",
            observations=(("refund", "billing")[index % 2],) * 80,
        )
        for index in range(6)
    )
    evidence = EvidenceSet(cases=cases, layer="verdict", isolation=isolation)
    return assess_evidence(evidence, epsilon=0.05)


def _snapshot(isolation: str) -> Snapshot:
    """An approved baseline from evidence only isolation can refuse."""
    return create_snapshot(_result(isolation), approved=True)


def test_shared_session_evidence_cannot_certify_a_baseline():
    """The library refused to disagree with itself.

    Before this, the same run printed the caveat and produced the snapshot.
    """
    result = _result("shared-session")

    assert result.meter.call == "verdict-deterministic"
    assert any("not established" in caveat for caveat in result.caveats)
    with pytest.raises(SnapshotRefused, match="not established"):
        create_snapshot(result, approved=True)


@pytest.mark.parametrize("isolation", sorted(CERTIFIABLE_ISOLATION))
def test_every_certifiable_isolation_admits_and_is_recorded(isolation):
    """Admission and the stored value are one fact, so they are tested together."""
    snapshot = _snapshot(isolation)

    assert snapshot.isolation == isolation
    assert snapshot.to_dict()["admission_evidence"]["isolation"] == isolation


def test_unknown_is_admitted_and_is_not_an_assertion():
    """The policy refuses a claim of shared state, not an unstated one.

    Refusing `unknown` would refuse most imported evidence on day one and
    teach callers to write `fresh-session` to make the error go away.
    """
    assert _snapshot("unknown").independence_asserted is False
    assert _snapshot("fresh-session").independence_asserted is True


def test_a_stored_isolation_is_validated_on_read():
    """ADR 4's lesson, applied to the new field before it can bite.

    A snapshot naming an isolation no policy covers would otherwise load and
    be reported as a provenance change against every run it is compared with,
    rather than as the corrupt file it is.
    """
    payload = _snapshot("fresh-session").to_dict()
    assert Snapshot.from_dict(json.loads(json.dumps(payload))).isolation == (
        "fresh-session"
    )

    payload["admission_evidence"]["isolation"] = "shared-session"
    with pytest.raises(SnapshotCompatibilityError, match="cannot have certified"):
        Snapshot.from_dict(payload)

    del payload["admission_evidence"]["isolation"]
    with pytest.raises(SnapshotCompatibilityError, match="cannot have certified"):
        Snapshot.from_dict(payload)


def test_a_check_reports_provenance_that_weakened():
    """The observations match. What weakened is what the new evidence shows."""
    diff = compare_snapshot(_snapshot("fresh-session"), _result("unknown"))

    assert diff.clean, "the decisions did not change"
    assert diff.provenance_weakened
    assert "establishes less" in diff.provenance_note


def test_the_rendered_check_names_provenance_before_the_result():
    """A reader must see the weakening before the reassuring clean result."""
    diff = compare_snapshot(_snapshot("fresh-session"), _result("unknown"))
    text = diff.render()

    assert text.startswith("regression reference check")
    assert "snapshot clean" in text
    assert "establishes less" in text
    assert text.index("provenance") < text.index("result")


def test_a_drifted_and_weakened_check_does_not_claim_a_match():
    """A check can drift and weaken at once.

    The provenance note once said "the observations match", which contradicts
    the drift result printed beside it.
    """
    base = _snapshot("fresh-session")
    cases = tuple(
        EvidenceCase(
            input=f"probe-{index}",
            observations=(("refund", "billing")[index % 2],) * 80,
        )
        for index in range(6)
    )
    drifted = EvidenceSet(
        cases=(
            EvidenceCase("probe-0", ("billing",) * 80),
            *cases[1:],
        ),
        layer="verdict",
        isolation="unknown",
    )

    diff = compare_snapshot(base, assess_evidence(drifted, epsilon=0.05))

    assert not diff.clean
    assert diff.provenance_weakened
    text = diff.render()
    assert "snapshot drift" in text
    assert "establishes less" in text
    assert "observations match" not in text


def test_a_check_is_quiet_when_provenance_held_or_improved():
    """A note printed on every run is a note nobody reads."""
    same = compare_snapshot(_snapshot("fresh-session"), _result("fresh-session"))
    stronger = compare_snapshot(_snapshot("unknown"), _result("fresh-session"))

    assert same.provenance_note is None
    assert stronger.provenance_note is None, "unknown to fresh is not a weakening"


def test_a_check_against_shared_session_evidence_is_refused_not_reported():
    """`compare_snapshot` admits the current run first, so the policy applies."""
    with pytest.raises(SnapshotRefused, match="not established"):
        compare_snapshot(_snapshot("fresh-session"), _result("shared-session"))


def test_the_cli_prints_the_weakening_before_the_verdict(tmp_path, capsys):
    """A clean check resting on weaker provenance is the reading to prevent.

    The baseline is written from a live run so the fingerprints and config
    match, then its recorded isolation is raised to `fresh-session`, which is
    what an adapter asserting its own provenance will do once that half of
    roadmap item 4 lands. The live check still reports `unknown`.
    """
    from agentverity.cli import main

    inputs = tmp_path / "inputs.txt"
    inputs.write_text(
        "\n".join(
            [f"input_{index}" for index in range(50)]
            + [f"secret_{index}" for index in range(50)]
        ),
        encoding="utf-8",
    )
    snapshot_path = tmp_path / "snapshot.json"
    argv = ["--agent", "examples.toy_agent:deterministic_gate", "--inputs", str(inputs)]
    assert (
        main([
            "snapshot", *argv, "--k", "10",
            "--output", str(snapshot_path), "--accept-reference",
        ])
        == 0
    )

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["admission_evidence"]["isolation"] == "unknown", (
        "a live run asserts nothing about isolation yet"
    )
    payload["admission_evidence"]["isolation"] = "fresh-session"
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    capsys.readouterr()

    code = main(["check", *argv, "--snapshot", str(snapshot_path)])
    printed = capsys.readouterr().out

    assert code == 0, "the decisions match"
    assert "provenance" in printed
    assert printed.index("provenance") < printed.index("snapshot clean")


def test_a_live_run_reports_the_isolation_it_declared():
    """A declaration reaches the report, rather than being read and dropped."""
    from agentverity import Observation, RunConfig, run
    from agentverity.isolation import declare_isolation

    agent = declare_isolation(
        lambda text: Observation(verdict="allow" if text == "a" else "block"),
        "fresh-instance",
    )
    result = run(agent, ["a", "b"], relations=[], config=RunConfig(k=4, epsilon=0.5))

    assert result.isolation == "fresh-instance"


def test_the_saved_file_carries_the_new_schema(tmp_path):
    path = tmp_path / "snapshot.json"
    save_snapshot(_snapshot("fresh-instance"), path)

    assert json.loads(path.read_text())["schema"] == "agentverity.snapshot/v4"


def test_an_older_baseline_is_told_what_to_do_about_it():
    """A refusal that names no remedy sends the reader to the changelog.

    The remedy is re-admission rather than an upgrade script, and the reason
    is the reason the field exists: isolation cannot be back-filled, because
    nobody asserted it when the file was written. Guessing it during a
    migration would manufacture exactly the provenance the policy establishes.
    """
    payload = _snapshot("fresh-session").to_dict()
    payload["schema"] = "agentverity.snapshot/v3"

    with pytest.raises(SnapshotCompatibilityError) as refused:
        Snapshot.from_dict(payload)

    assert "Re-run and snapshot again" in str(refused.value)
    assert "manufacture the provenance" in str(refused.value)


def test_an_unrelated_schema_gets_no_snapshot_migration_advice():
    """The advice is about agentverity snapshots, not any stray JSON file."""
    with pytest.raises(SnapshotCompatibilityError) as refused:
        Snapshot.from_dict({"schema": "something.else/v1"})

    assert "Re-run and snapshot again" not in str(refused.value)


def test_the_isolation_flag_reaches_the_importer_and_is_refused_elsewhere(
    tmp_path, capsys
):
    """`--isolation` decides admission now, so discarding it is not cosmetic.

    It was declared on `assess` and left out of the flag table, so
    `--evidence file.json --isolation fresh-session` was accepted and thrown
    away while the file's own value won. A caller could believe they had
    upgraded the provenance of a baseline they were about to certify.
    """
    from agentverity.cli import main

    runs = tmp_path / "runs.jsonl"
    runs.write_text(
        "\n".join(
            json.dumps({"input": f"probe-{index}", "decision": decision})
            for index in range(6)
            for decision in ((("refund", "billing")[index % 2],) * 80)
        ),
        encoding="utf-8",
    )

    # Asserted on the caveat rather than the exit code, because `undecided`
    # exits 2 as well and would read as a refusal that never happened.
    main(["assess", "--jsonl", str(runs), "--isolation", "fresh-session"])
    printed = capsys.readouterr()

    assert "assessment refused" not in printed.err
    assert "independence is assumed" not in printed.out, (
        "the flag reached the importer, so the unknown caveat is gone"
    )

    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema": "agentverity.evidence/v2",
                "layer": "verdict",
                "isolation": "shared-session",
                "cases": [
                    {"input": "a", "observations": ["x", "x"]},
                    {"input": "b", "observations": ["y", "y"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["assess", "--evidence", str(evidence), "--isolation", "fresh-session"]) == 2
    assert "--isolation applies to" in capsys.readouterr().err


class TestALiveRunCarriesTheIndependenceWarning:
    """A live run must not state a conclusion while hiding that repeats were
    not independent, any more than an imported assessment may."""

    def test_a_shared_session_run_warns_in_its_report(self):
        from agentverity import Observation, RunConfig, run
        from agentverity.isolation import declare_isolation
        from agentverity.reporting import run_result_to_dict, run_result_to_junit_xml

        agent = declare_isolation(
            lambda text: Observation(verdict="allow" if text == "a" else "block"),
            "shared-session",
        )
        result = run(agent, ["a", "b"], relations=[], config=RunConfig(k=4, epsilon=0.5))

        assert result.isolation == "shared-session"
        assert any("not established" in caveat for caveat in result.caveats)
        assert "not established" in result.summary()
        assert "not established" in run_result_to_junit_xml(result)
        assert run_result_to_dict(result)["isolation"] == "shared-session"

    def test_an_undeclared_run_says_independence_is_assumed(self):
        from agentverity import Observation, RunConfig, run

        result = run(
            lambda text: Observation(verdict="allow" if text == "a" else "block"),
            ["a", "b"],
            relations=[],
            config=RunConfig(k=4, epsilon=0.5),
        )

        assert result.isolation == "unknown"
        assert any(
            "assumed rather than established" in caveat
            for caveat in result.caveats
        )

    def test_a_fresh_session_run_carries_no_independence_caveat(self):
        from agentverity import Observation, RunConfig, run
        from agentverity.isolation import declare_isolation

        agent = declare_isolation(
            lambda text: Observation(verdict="allow" if text == "a" else "block"),
            "fresh-session",
        )
        result = run(agent, ["a", "b"], relations=[], config=RunConfig(k=4, epsilon=0.5))

        assert not any(
            "not established" in caveat or "assumed" in caveat
            for caveat in result.caveats
        )
