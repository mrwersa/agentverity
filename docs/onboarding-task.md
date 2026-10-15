# AgentVerity first-use exercise

Use a fresh checkout and Python 3.10 or later. Allow 15 minutes, including
setup. You may consult the README and its linked guides. All exercise data is
synthetic; the commands make no model or provider calls. Installation may
download build tools.

## First report

Open [the README](../README.md) and follow **Try it without model calls**.
When you have a report, explain in your own words:

1. What did AgentVerity find?
2. Would you save this evidence as a regression reference? Why?
3. What does the command's exit code tell you?

## Another probe set

From the checkout root, run:

```bash
python examples/payment_dispute_gate.py
```

Why do the two probe sets lead to different reference decisions? What does
an admitted reference establish, and what still needs review?

## A shorter collection

```bash
agentverity assess --jsonl examples/onboarding/quiet_short.jsonl
```

What conclusion can you draw from this report? What would you do next?

Before finishing, describe what AgentVerity can tell you about correctness
and safety. Record anything you could not understand from the existing
reports or linked guides.
