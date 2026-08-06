"""A tool-selection target built from AgentKit's real tool set.

What this measures, precisely: given the 20 tools the AgentKit Strands example
exposes and one user message, which tool does a model choose, and does it
choose the same one when asked again.

It is not AgentKit's chatbot end to end. Constructing that needs CDP
credentials and a funded wallet, and executing the tools would move money.
Tool *selection* is the decision under test, so the tools are declared to the
model exactly as AgentKit declares them, and nothing is executed. The model
still makes the whole choice.
"""

from __future__ import annotations

import json
import os
import pathlib
import random
import time
import urllib.error
import urllib.request

from agentverity.observation import Observation

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
ROOT = pathlib.Path(__file__).resolve().parent

# Deliberately absent from the suite's allowed set. An agent that answers a
# tool-calling contract with prose is out of contract, and the report should
# say so rather than absorb it.
NO_TOOL = "no_tool_selected"

SYSTEM = (
    "You are an onchain agent with a wallet. Choose exactly one tool to answer "
    "the user, and call it. Do not ask clarifying questions."
)


def _tools() -> list[dict]:
    """AgentKit's real names and descriptions, as OpenAI-style tool specs."""
    raw = json.loads((ROOT / "agentkit_tools.json").read_text())
    seen: dict[str, dict] = {}
    for tool in raw:
        # Two providers declare get_balance. A tool-calling API cannot carry
        # the same name twice, so the first wins and the collision is noted
        # in the write-up rather than silently resolved.
        seen.setdefault(
            tool["name"],
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        )
    return list(seen.values())


TOOLS = _tools()


def build(model: str):
    """Return run(input) -> Observation for one OpenRouter model."""
    key = os.environ["OPENROUTER_API_KEY"]

    def run(text: str) -> Observation:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": text},
            ],
            "tools": TOOLS,
            "tool_choice": "required",
            # Left at the provider default on purpose. Pinning temperature to
            # zero would measure a configuration nobody deploys and would
            # flatter the result.
        }
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/mrwersa/agentverity",
                "X-Title": "agentverity-evidence",
            },
        )
        # Upstream providers rate-limit, and a 429 is not evidence about the
        # agent. Retrying with full jitter keeps a provider hiccup out of the
        # measurement; exhausting the retries raises, so the run records an
        # error rather than inventing an observation.
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    body = json.loads(response.read())
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in (408, 409, 429, 500, 502, 503, 504) or attempt == 5:
                    raise
                time.sleep(random.uniform(0, min(30, 2 ** attempt)))
            except (urllib.error.URLError, TimeoutError, OSError):
                # A read timeout is a gateway problem, not a decision. The
                # first run of this lost 20 minutes of collected observations
                # because only HTTPError was caught here.
                if attempt == 5:
                    raise
                time.sleep(random.uniform(0, min(30, 2 ** attempt)))
        else:  # pragma: no cover - the loop always breaks or raises
            raise RuntimeError("unreachable")

        message = body["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        names = tuple(c["function"]["name"] for c in calls if c.get("function"))

        # Declining to call a tool is a decision, and it needs a name.
        # Observation.key falls back to the raw text when verdict is None, so
        # leaving it unset compares two refusals by their prose and counts a
        # reworded refusal as a changed decision. That measures wording, not
        # choice. `tool_choice="required"` does not stop this: some providers
        # return prose anyway, which is itself worth recording.
        return Observation(
            text=message.get("content") or "",
            verdict=names[0] if names else NO_TOOL,
            tools=names,
            raw=body,
        )

    return run


# Three vendors, three sizes. Nova Micro is deliberate continuity: the earlier
# AgentVerity write-up measured the same model on Bedrock.
def mistral_small():
    # mistral-nemo was rate-limited upstream during this run; mistral-small
    # is the same vendor at a usable tier.
    return build("mistralai/mistral-small-3.2-24b-instruct")


def nova():
    return build("amazon/nova-micro-v1")


def gpt4o_mini():
    return build("openai/gpt-4o-mini")
