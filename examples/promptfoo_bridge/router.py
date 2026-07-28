"""Local payment router used by the Promptfoo bridge example."""


def route(ticket: str) -> str:
    text = ticket.lower()
    if "charged twice" in text:
        return "duplicate_charge"
    if "refund" in text:
        return "refund_delay"
    if "do not recognise" in text:
        return "card_security"
    if "merchant" in text:
        return "merchant_dispute"
    if "atm" in text:
        return "cash_withdrawal"
    return "transfer_delay"


def call_api(prompt, options, context):
    """Promptfoo Python-provider entry point."""
    del options, context
    return {"output": route(prompt)}
