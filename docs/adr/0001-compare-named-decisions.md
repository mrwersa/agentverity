# ADR 0001: Compare named decisions, not generated text

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

An agent can phrase the same answer differently while making the same
operational decision. A payment router may produce new explanatory text on
every run but still choose `duplicate_charge` each time. Treating the whole
response as the test value would report wording variation as routing
instability.

Semantic similarity or an LLM judge could reduce those false alarms, but both
introduce another model and another threshold into a check whose purpose is to
qualify evidence. They also make the zero-dependency core provider-specific or
more expensive.

## Decision

AgentVerity compares an explicit, categorical `verdict` by default. The host
owns the adapter that extracts this decision from its agent result. A caller
may instead select exact text or an ordered tool path when that is the reviewed
contract.

When no verdict is supplied, the observation falls back to exact text. This is
a compatibility path, not semantic judging. Open-ended responses without a
reviewed decision or tool-path contract remain outside the library's scope.

## Consequences

- Stability measures changes that can alter routing, approval, escalation, or
  tool selection rather than harmless prose variation.
- The core remains deterministic, inspectable, and free of model dependencies.
- Hosts must expose a meaningful decision boundary. A poor extraction function
  can hide variation, so adapters belong in the reviewed test surface.
- AgentVerity does not answer whether a decision is correct. Labelled tests or
  a separate quality evaluator retain that responsibility.
