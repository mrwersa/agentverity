"""Smallest useful AgentVerity example: a stable but blind router.

Run from the repository root:

    python examples/support_router.py
"""

from __future__ import annotations

from agentverity import from_callable, run

PROBES = [
    "my card was charged twice",
    "how do I reset my password",
    "the app crashes on login",
    "where is my refund",
    "the checkout button is the wrong colour",
    "a transfer is missing from my statement",
]


def support_router(_ticket: str) -> dict:
    """Deliberate defect: every ticket is routed to the same queue."""
    return {"text": "route: general", "verdict": "general"}


def build_agent():
    """Factory used by the CLI example in the README."""
    return support_router


def main() -> None:
    result = run(from_callable(support_router), inputs=PROBES)
    print(result.summary())


if __name__ == "__main__":
    main()
