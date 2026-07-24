"""agentverity — measure-first testing for non-deterministic LLM agents.

Before trusting any test suite, agentverity tells you whether your agent's
verdict is stable enough to test against, and whether a passing relation is
trivially satisfied by an indifferent agent. Two headline diagnostics:

  1. **Verdict-stochasticity meter** — does the agent's decision flip across
     identical reruns? If not, a frozen-output diff dominates and metamorphic
     relations add little.
  2. **Constant-gate-blindness detector** — does the agent return a near-constant
     verdict across a diverse input set? If so, every relation passes
     trivially and the suite is lying to you.

Metamorphic relations are the vehicle; the diagnostics are the product.

Quickstart::

    from agentverity import run, from_callable
    from agentverity.relations import builtin_relations

    agent = from_callable(my_agent_fn)
    result = run(agent, inputs=["hello", "world"], relations=builtin_relations())
    print(result.summary())
"""

from agentverity.adapters import from_callable
from agentverity.blindness import BlindnessResult, detect
from agentverity.meter import MeterResult, measure
from agentverity.observation import Observation
from agentverity.relations import Relation, builtin_relations
from agentverity.runner import RelationResult, RunConfig, RunResult, run

__all__ = [
    "BlindnessResult",
    "MeterResult",
    "Observation",
    "Relation",
    "RelationResult",
    "RunConfig",
    "RunResult",
    "builtin_relations",
    "detect",
    "from_callable",
    "measure",
    "run",
]

__version__ = "0.1.0"
