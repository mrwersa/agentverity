"""AgentCore Runtime adapter with one isolated session per trial."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable

from agentverity import Observation


def build_runtime_router() -> Callable[[str], Observation]:
    """Return an AgentVerity-compatible AgentCore Runtime callable."""
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - live integration
        raise RuntimeError(
            'Install the live stack with: pip install -e ".[showcase]"'
        ) from exc

    runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN")
    if not runtime_arn:
        raise RuntimeError("Set AGENTCORE_RUNTIME_ARN to the deployed runtime ARN.")
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION"))
    client = boto3.client("bedrock-agentcore", region_name=region)

    def invoke(ticket: str) -> Observation:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            qualifier="DEFAULT",
            # Reusing a session would make later trials depend on earlier
            # conversation state, invalidating an identical-rerun check.
            runtimeSessionId=str(uuid.uuid4()),
            contentType="application/json",
            accept="application/json",
            payload=json.dumps({"prompt": ticket}).encode(),
        )
        body = response["response"].read()
        value = json.loads(body.decode("utf-8"))
        return Observation(
            text=str(value.get("explanation", "")),
            verdict=str(value["route"]),
            raw=value,
        )

    return invoke
