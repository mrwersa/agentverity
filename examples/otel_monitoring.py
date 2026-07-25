"""Send one AgentVerity summary span through OpenTelemetry.

Install the optional integration and SDK for this standalone console demo:

    pip install "agentverity[otel]" opentelemetry-sdk
    python examples/otel_monitoring.py

In AgentCore, Phoenix, or LangSmith, keep the host's existing tracer provider
and exporter. Only the final ``record_otel_run`` call is AgentVerity-specific.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from agentverity import from_callable, record_otel_run, run

PROBES = [
    "my card was charged twice",
    "the app crashes on login",
    "where is my refund",
    "the checkout button is the wrong colour",
]


def route(ticket: str) -> dict:
    ticket = ticket.lower()
    verdict = "payments" if "card" in ticket or "refund" in ticket else "technical"
    return {"text": f"route: {verdict}", "verdict": verdict}


def main() -> None:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    result = run(from_callable(route), inputs=PROBES)
    record_otel_run(result)


if __name__ == "__main__":
    main()
