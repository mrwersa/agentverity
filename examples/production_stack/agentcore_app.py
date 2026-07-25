"""Deploy the payment router on Amazon Bedrock AgentCore Runtime."""

from __future__ import annotations

from bedrock_agentcore import BedrockAgentCoreApp
from payment_agent import build_route_callable

app = BedrockAgentCoreApp()
router = build_route_callable()


@app.entrypoint
def invoke(payload: dict) -> dict[str, str]:
    """Route one ticket. AgentVerity runs separately as a CI or canary job."""
    ticket = str(payload.get("prompt", ""))
    if not ticket:
        return {"error": "payload.prompt is required"}
    decision = router(ticket)
    return {
        "route": decision.route,
        "explanation": decision.reason,
    }


if __name__ == "__main__":
    app.run()
