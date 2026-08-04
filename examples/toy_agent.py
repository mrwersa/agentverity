"""Toy agents for offline smoke-testing agentverity — no API keys, deterministic
seeds. NOT real agents; they exist so the whole pipeline runs and the two
instruments can be validated (a stochastic agent should meter as stochastic; a
near-constant agent should trip the blindness detector).

Usage::

    from examples.toy_agent import stochastic_gate, constant_gate, deterministic_gate
    from agentverity import from_callable, run

    agent = from_callable(stochastic_gate(flip_prob=0.15, seed=42))
    result = run(agent, inputs=["hello", "a secret", "world", "foo"])
    print(result.summary())
"""

from __future__ import annotations

import random


def stochastic_gate(flip_prob: float = 0.15, seed: int = 0):
    """A gate whose verdict flips with probability ``flip_prob`` per call.

    Returns a dict the callable adapter reads. Used to check the meter
    detects stochasticity.

    Args:
        flip_prob: Probability of flipping the verdict on each call.
        seed: Random seed for reproducibility.

    Returns:
        A callable ``fn(text: str) -> dict``.
    """
    rng = random.Random(seed)

    def fn(text: str) -> dict:
        base = "block" if "secret" in text.lower() else "allow"
        verdict = base
        if rng.random() < flip_prob:
            verdict = "allow" if base == "block" else "block"
        return {"text": f"decision: {verdict}", "verdict": verdict}

    return fn


def constant_gate(verdict: str = "allow"):
    """A gate that returns the same verdict regardless of input.

    Used to check the blindness detector fires (a passing suite here would
    be meaningless).

    Args:
        verdict: The verdict to always return.

    Returns:
        A callable ``fn(text: str) -> dict``.
    """
    def fn(text: str) -> dict:
        return {"text": f"decision: {verdict}", "verdict": verdict}
    return fn


def deterministic_gate():
    """A sensible deterministic gate: block iff the input mentions a secret.

    Returns:
        A callable ``fn(text: str) -> dict``.
    """
    def fn(text: str) -> dict:
        v = "block" if "secret" in text.lower() else "allow"
        return {"text": f"decision: {v}", "verdict": v}
    return fn


if __name__ == "__main__":
    from agentverity import from_callable, run

    inputs = [
        "hello world",
        "this is a secret",
        "share my data",
        "the weather is nice",
        "a secret message",
        "allow this request",
    ]

    print("=== Stochastic gate (flip_prob=0.15) ===")
    agent = from_callable(stochastic_gate(flip_prob=0.15, seed=42))
    result = run(agent, inputs=inputs, config=None)
    print(result.summary())

    print("\n=== Constant gate (always 'allow') ===")
    agent2 = from_callable(constant_gate(verdict="allow"))
    result2 = run(agent2, inputs=inputs)
    print(result2.summary())

    print("\n=== Deterministic gate ===")
    agent3 = from_callable(deterministic_gate())
    result3 = run(agent3, inputs=inputs)
    print(result3.summary())
