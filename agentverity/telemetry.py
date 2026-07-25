"""OpenTelemetry handoff for AgentVerity diagnostic runs.

AgentVerity does not own a monitoring backend. It emits one low-cardinality
summary span that can travel through an existing OpenTelemetry pipeline to
CloudWatch, Phoenix, LangSmith, or another OTLP-compatible destination.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from agentverity.runner import RunResult

TELEMETRY_SCHEMA = "agentverity.telemetry/v1"


def _package_version() -> str:
    try:
        return version("agentverity")
    except PackageNotFoundError:
        return "0+unknown"


def run_result_to_otel_attributes(result: RunResult) -> dict[str, Any]:
    """Return privacy-minimised, low-cardinality OTEL span attributes.

    Raw prompts, outputs, fingerprints, exception messages, relation names,
    and provider-specific objects are deliberately excluded. The resulting
    attributes are suitable for aggregate dashboards and alerts rather than
    case-level debugging.
    """
    relations = result.relation_results
    attributes: dict[str, Any] = {
        "agentverity.schema": TELEMETRY_SCHEMA,
        "agentverity.version": _package_version(),
        "agentverity.status": result.status,
        "agentverity.complete": result.complete,
        "agentverity.inputs": result.requested_inputs,
        "agentverity.layer": result.config.layer,
        "agentverity.relations.total": len(relations),
        "agentverity.relations.exercised": sum(r.exercised for r in relations),
        "agentverity.relations.violated": sum(r.violated for r in relations),
        "agentverity.relations.vacuous": sum(r.is_vacuous for r in relations),
        "agentverity.errors": len(result.errors),
    }
    if result.meter is not None:
        attributes.update(
            {
                "agentverity.meter.call": result.meter.call,
                "agentverity.meter.flip_rate": result.meter.flip_rate,
                "agentverity.meter.ci_low": result.meter.ci_low,
                "agentverity.meter.ci_high": result.meter.ci_high,
                "agentverity.meter.epsilon": result.meter.epsilon,
                "agentverity.meter.pairs": result.meter.pair_trials,
                "agentverity.meter.repeats": result.meter.repeats,
            }
        )
    if result.blindness is not None:
        attributes.update(
            {
                "agentverity.blindness.blind": result.blindness.blind,
                "agentverity.blindness.skew": result.blindness.skew,
                "agentverity.blindness.distinct": result.blindness.distinct,
                "agentverity.blindness.threshold": result.blindness.threshold,
            }
        )
    return attributes


def record_otel_run(
    result: RunResult,
    *,
    tracer: Any | None = None,
    span_name: str = "agentverity.run",
) -> None:
    """Record one summary span through an existing OpenTelemetry pipeline.

    If ``tracer`` is omitted, the current global OpenTelemetry tracer provider
    is used. Install ``agentverity[otel]`` and configure an exporter in the
    host application. Calling this function inside an active trace makes the
    diagnostic span its child.
    """
    if tracer is None:
        try:
            from opentelemetry import trace
        except ImportError as exc:  # pragma: no cover - environment-specific
            raise RuntimeError(
                "OpenTelemetry support is optional; install 'agentverity[otel]'"
            ) from exc
        tracer = trace.get_tracer("agentverity")

    with tracer.start_as_current_span(span_name) as span:
        for key, value in run_result_to_otel_attributes(result).items():
            span.set_attribute(key, value)
