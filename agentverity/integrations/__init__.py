"""Evidence bridges for evaluation frameworks.

Integrations translate observations a framework already collected into
AgentVerity's versioned evidence contract. They do not replace the framework's
quality metrics and never call the target again.
"""

from .deepeval import evidence_from_deepeval
from .promptfoo import evidence_from_promptfoo, load_promptfoo

__all__ = [
    "evidence_from_deepeval",
    "evidence_from_promptfoo",
    "load_promptfoo",
]
