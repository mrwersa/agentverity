"""A structured-output Strands router backed by Amazon Bedrock."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

SYSTEM_PROMPT = """\
You route card-payment support tickets.
Choose exactly one route:
- duplicate_charge: the same card purchase was charged more than once
- refund_delay: a merchant promised a refund that has not arrived
- card_security: the customer does not recognise a card purchase
- merchant_dispute: the customer recognises the merchant but disputes the
  amount, goods, or service
- cash_withdrawal: an ATM cash withdrawal is missing or incorrect
- transfer_delay: a bank transfer is pending or late

Return the route and a short reason. Do not resolve the dispute.
"""

DEFAULT_MODEL_ID = "amazon.nova-micro-v1:0"


class RouteDecision(BaseModel):
    """Structured payment route returned by the Strands agent."""

    route: Literal[
        "duplicate_charge",
        "refund_delay",
        "card_security",
        "merchant_dispute",
        "cash_withdrawal",
        "transfer_delay",
    ] = Field(description="One route from the system prompt")
    reason: str = Field(description="One short reason for the route")


def _build_components() -> tuple[Callable[[], Any], Callable[[Any, str], Any]]:
    try:
        from strands import Agent
        from strands.models import BedrockModel
    except ImportError as exc:  # pragma: no cover - exercised by a live example
        raise RuntimeError(
            'Install the live stack with: pip install -e ".[showcase]"'
        ) from exc

    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION"))
    model_options: dict[str, object] = {
        "model_id": os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
        "temperature": 0.0,
        "streaming": False,
    }
    if region:
        model_options["region_name"] = region
    model = BedrockModel(**model_options)

    def factory():
        return Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
        )

    def invoke(agent, ticket: str):
        return agent(ticket, structured_output_model=RouteDecision)

    return factory, invoke


def build_route_callable() -> Callable[[str], RouteDecision]:
    """Return a service callable that starts each ticket with a fresh agent."""
    factory, invoke = _build_components()

    def route(ticket: str) -> RouteDecision:
        result = invoke(factory(), ticket)
        decision = result.structured_output
        if not isinstance(decision, RouteDecision):
            decision = RouteDecision.model_validate(decision)
        return decision

    return route


def build_isolated_router():
    """Return an AgentVerity runner with empty history for every trial."""
    from agentverity.adapters.strands import from_strands_factory

    factory, invoke = _build_components()
    return from_strands_factory(factory, invoke=invoke, verdict_key="route")
