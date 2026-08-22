"""Executable retention boundaries for every AgentVerity output surface."""

from __future__ import annotations

import json
from pathlib import Path

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    EvidenceCase,
    EvidenceSet,
    Relation,
    from_callable,
    run,
)
from agentverity.reporting import run_result_to_dict, run_result_to_junit_xml
from agentverity.runner import RunConfig
from agentverity.snapshot import create_snapshot
from agentverity.telemetry import run_result_to_otel_attributes

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (
        ROOT / "tests/fixtures/compatibility/v0.19.0/data-retention-contract.json"
    ).read_text(encoding="utf-8")
)

RAW_INPUT = "SENSITIVE_RAW_INPUT_8f13"
RAW_OUTPUT = "SENSITIVE_MODEL_OUTPUT_a921"
ERROR_MESSAGE = "SENSITIVE_PROVIDER_ERROR_c771"
DECISION_LABEL = "SENSITIVE_REVIEW_ROUTE_d482"
RELATION_NAME = "SENSITIVE_RELATION_NAME_e390"
PUBLIC_INPUT = "ordinary-public-input"
PUBLIC_OUTPUT = "ordinary-public-output"
PUBLIC_LABEL = "allow"


def _suite() -> DecisionSuite:
    return DecisionSuite(
        contract=DecisionContract(allowed={PUBLIC_LABEL, DECISION_LABEL}),
        cases=(
            DecisionCase(RAW_INPUT, DECISION_LABEL),
            DecisionCase(PUBLIC_INPUT, PUBLIC_LABEL),
        ),
    )


def _agent(text: str) -> dict[str, str]:
    sensitive = text.startswith(RAW_INPUT)
    return {
        "text": RAW_OUTPUT if sensitive else PUBLIC_OUTPUT,
        "verdict": DECISION_LABEL if sensitive else PUBLIC_LABEL,
    }


def _result(*, on_progress=None):
    relation = Relation(
        name=RELATION_NAME,
        rtype="invariant",
        transform=lambda text: text + "!",
        check=lambda source, followup: source.text == followup.text,
    )
    return run(
        from_callable(_agent),
        [RAW_INPUT, PUBLIC_INPUT],
        relations=[relation],
        config=RunConfig(k=4, epsilon=0.5, layer="text"),
        on_progress=on_progress,
    )


def _contract_finding():
    return run(
        from_callable(lambda _text: {"text": PUBLIC_OUTPUT, "verdict": PUBLIC_LABEL}),
        suite=_suite(),
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )


def _error_result():
    def failing(text: str) -> dict[str, str]:
        if text == RAW_INPUT:
            raise RuntimeError(ERROR_MESSAGE)
        return {"text": PUBLIC_OUTPUT, "verdict": PUBLIC_LABEL}

    return run(
        from_callable(failing),
        [RAW_INPUT, PUBLIC_INPUT],
        relations=[],
        config=RunConfig(
            k=2,
            epsilon=0.9,
            error_policy="record",
        ),
    )


def test_the_retention_matrix_is_complete_and_uses_defined_classifications():
    """Every surface classifies every reviewed sensitive-data category."""
    fields = {
        "raw_inputs",
        "observation_values",
        "input_fingerprints",
        "exception_messages",
        "decision_labels",
        "relation_names",
    }
    allowed = set(CONTRACT["classifications"])

    assert CONTRACT["schema"] == "agentverity.data-retention-contract/v1"
    assert CONTRACT["baseline"] == "agentverity==0.19.0"
    assert set(CONTRACT["surfaces"]) == {
        "decision-suite",
        "imported-evidence",
        "json-report",
        "junit-report",
        "opentelemetry",
        "progress",
        "snapshot",
        "terminal-summary",
    }
    for surface in CONTRACT["surfaces"].values():
        assert set(surface) == fields
        assert set(surface.values()) <= allowed


def test_the_documented_retention_matrix_matches_the_versioned_contract():
    """Human guidance and the machine-reviewed baseline cannot drift apart."""
    document = (ROOT / "docs/security-data-audit.md").read_text(encoding="utf-8")
    display_names = {
        "decision-suite": "Decision-suite JSON",
        "imported-evidence": "Imported evidence",
        "json-report": "JSON run report",
        "junit-report": "JUnit report",
        "terminal-summary": "Terminal summary",
        "progress": "Progress event",
        "snapshot": "Snapshot",
        "opentelemetry": "OpenTelemetry",
    }
    columns = (
        "raw_inputs",
        "observation_values",
        "input_fingerprints",
        "exception_messages",
        "decision_labels",
        "relation_names",
    )
    shown = {
        "retained": "Retained",
        "conditionally-retained": "Conditional",
        "excluded": "Excluded",
        "not-applicable": "n/a",
    }

    for surface_name, values in CONTRACT["surfaces"].items():
        row = (
            "| "
            + " | ".join(
                [display_names[surface_name], *(shown[values[key]] for key in columns)]
            )
            + " |"
        )
        assert row in document


def test_source_suite_and_imported_evidence_intentionally_retain_payloads():
    """Input datasets are sensitive source material, not minimised reports."""
    suite_payload = json.dumps(_suite().to_dict())
    evidence_payload = json.dumps(
        EvidenceSet(
            cases=(
                EvidenceCase(
                    RAW_INPUT,
                    (RAW_OUTPUT, RAW_OUTPUT),
                    expected=DECISION_LABEL,
                ),
                EvidenceCase(
                    PUBLIC_INPUT,
                    (PUBLIC_OUTPUT, PUBLIC_OUTPUT),
                    expected=PUBLIC_LABEL,
                ),
            ),
            layer="text",
            provenance={
                "provider_error": ERROR_MESSAGE,
                "source_fingerprint": "caller-supplied-fingerprint",
                "relation": RELATION_NAME,
            },
        ).to_dict()
    )

    assert RAW_INPUT in suite_payload
    assert DECISION_LABEL in suite_payload
    assert RAW_INPUT in evidence_payload
    assert RAW_OUTPUT in evidence_payload
    assert DECISION_LABEL in evidence_payload
    assert ERROR_MESSAGE in evidence_payload
    assert "caller-supplied-fingerprint" in evidence_payload
    assert RELATION_NAME in evidence_payload


def test_json_report_excludes_inputs_but_retains_auditable_diagnostics():
    """JSON keeps fingerprints, labels, relation names, and recorded errors."""
    payload = json.dumps(run_result_to_dict(_result()))
    error_payload = json.dumps(run_result_to_dict(_error_result()))

    assert RAW_INPUT not in payload
    assert RAW_OUTPUT in payload
    assert RELATION_NAME in payload
    assert DECISION_LABEL in json.dumps(run_result_to_dict(_contract_finding()))
    assert ERROR_MESSAGE in error_payload
    assert RAW_INPUT not in error_payload


def test_junit_excludes_inputs_fingerprints_and_error_text_but_can_echo_findings():
    """JUnit diagnostics can name observations and relations on finding paths."""
    payload = run_result_to_junit_xml(_result())
    error_payload = run_result_to_junit_xml(_error_result())

    assert RAW_INPUT not in payload
    assert RAW_OUTPUT not in payload
    assert RELATION_NAME in payload
    assert RAW_INPUT not in error_payload
    assert ERROR_MESSAGE not in error_payload
    assert _error_result().input_fingerprints[0] not in error_payload

    blind = run(
        from_callable(lambda _text: {"text": RAW_OUTPUT, "verdict": DECISION_LABEL}),
        [RAW_INPUT, PUBLIC_INPUT],
        relations=[],
        config=RunConfig(k=4, epsilon=0.5, layer="text"),
    )
    assert RAW_OUTPUT in run_result_to_junit_xml(blind)
    assert DECISION_LABEL in run_result_to_junit_xml(_contract_finding())


def test_terminal_summary_excludes_inputs_but_can_echo_outputs_and_errors():
    """Human diagnostics are not a safe sink for provider exception text."""
    payload = _result().summary()
    error_payload = _error_result().summary()

    assert RAW_INPUT not in payload
    assert RAW_OUTPUT in payload
    assert RELATION_NAME in payload
    assert DECISION_LABEL in _contract_finding().summary()
    assert ERROR_MESSAGE in error_payload
    assert RAW_INPUT not in error_payload


def test_progress_retains_only_a_fingerprint_identifier_from_the_payload():
    """Callbacks receive a fingerprint but no input, output, label, or error."""
    events = []
    _result(on_progress=events.append)
    payload = repr(events)

    assert events
    assert RAW_INPUT not in payload
    assert RAW_OUTPUT not in payload
    assert DECISION_LABEL not in payload
    assert RELATION_NAME not in payload
    assert any(event.input_fingerprint for event in events)


def test_snapshot_excludes_inputs_and_retains_approved_reference_outputs():
    """The checked value and its fingerprint are the snapshot's purpose."""
    snapshot = create_snapshot(_result(), approved=True).to_dict()
    payload = json.dumps(snapshot)

    assert RAW_INPUT not in payload
    assert RAW_OUTPUT in payload
    assert _result().input_fingerprints[0] in payload
    assert RELATION_NAME not in payload
    assert ERROR_MESSAGE not in payload

    verdict_snapshot = create_snapshot(
        run(
            from_callable(_agent),
            suite=_suite(),
            relations=[],
            config=RunConfig(k=4, epsilon=0.5),
        ),
        approved=True,
    )
    assert DECISION_LABEL in json.dumps(verdict_snapshot.to_dict())


def test_otel_excludes_every_case_level_sentinel_even_for_recorded_errors():
    """Telemetry exposes aggregate counts, never case-level diagnostics."""
    payload = repr(run_result_to_otel_attributes(_result()))
    error_payload = repr(run_result_to_otel_attributes(_error_result()))

    for sentinel in (
        RAW_INPUT,
        RAW_OUTPUT,
        DECISION_LABEL,
        RELATION_NAME,
        ERROR_MESSAGE,
    ):
        assert sentinel not in payload
        assert sentinel not in error_payload
    for fingerprint in _result().input_fingerprints:
        assert fingerprint not in payload
