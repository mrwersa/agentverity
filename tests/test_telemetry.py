"""Tests for the vendor-neutral OpenTelemetry handoff."""

from __future__ import annotations

from contextlib import contextmanager

from agentverity import from_callable, run
from agentverity.runner import RunConfig
from agentverity.telemetry import (
    TELEMETRY_SCHEMA,
    record_otel_run,
    run_result_to_otel_attributes,
)


class RecordingSpan:
    def __init__(self) -> None:
        self.attributes = {}

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value


class RecordingTracer:
    def __init__(self) -> None:
        self.name = None
        self.span = RecordingSpan()

    @contextmanager
    def start_as_current_span(self, name):
        self.name = name
        yield self.span


def _result():
    return run(
        from_callable(
            lambda text: {
                "text": f"do not retain {text}",
                "verdict": "allow" if text.startswith("a") else "block",
            }
        ),
        ["account-123", "private-token-456"],
        relations=[],
        config=RunConfig(k=4, epsilon=0.9),
    )


def test_otel_attributes_are_aggregate_and_privacy_minimised():
    attributes = run_result_to_otel_attributes(_result())
    encoded = repr(attributes)
    assert attributes["agentverity.schema"] == TELEMETRY_SCHEMA
    assert attributes["agentverity.version"]
    assert attributes["agentverity.status"] == "deterministic"
    assert attributes["agentverity.inputs"] == 2
    assert "account-123" not in encoded
    assert "private-token-456" not in encoded
    assert "majority_verdict" not in encoded


def test_record_otel_run_uses_injected_tracer_without_runtime_dependency():
    tracer = RecordingTracer()
    record_otel_run(_result(), tracer=tracer)
    assert tracer.name == "agentverity.run"
    assert tracer.span.attributes["agentverity.meter.flip_rate"] == 0.0
    assert tracer.span.attributes["agentverity.blindness.distinct"] == 2
