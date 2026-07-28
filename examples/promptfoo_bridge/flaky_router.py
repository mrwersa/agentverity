"""Local varying router used to demonstrate route-level instability."""

from random import Random

try:
    from .router import route as stable_route
except ImportError:
    from router import route as stable_route

# The fixed seed makes the committed Promptfoo export reproducible. The route
# still changes across repeated calls, which is the behaviour under test.
_random = Random(4)


def route(ticket: str) -> str:
    """Vary one boundary while leaving the other five routes stable."""
    if "do not recognise" in ticket.lower():
        return _random.choice(("card_security", "merchant_dispute"))
    return stable_route(ticket)


def call_api(prompt, options, context):
    """Promptfoo Python-provider entry point."""
    del options, context
    return {"output": route(prompt)}
