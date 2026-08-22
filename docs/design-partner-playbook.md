# Design-Partner Acquisition Playbook

This playbook operationalizes the first Phase 1 roadmap item. It is a
maintainer procedure, not permission to send bulk or unsolicited messages.

## Outcome and funnel

The first cycle targets 20 relevant teams contacted, six discovery
conversations, and three qualified pilot commitments. Record every disposition
so silence and rejection inform positioning rather than disappearing from the
analysis.

Use these definitions consistently:

- **Contacted:** a team passed the target-mix relevance screen and one
  personalized message reached a named maintainer or team through an
  appropriate public or existing relationship channel.
- **Discovery:** a synchronous or substantive asynchronous exchange answered
  the qualification questions below.
- **Qualified pilot:** both sides agreed on a bounded decision, evidence path,
  owner, and next date.
- **Completed pilot:** the participant received and discussed an AgentVerity
  report; a green result is not required.

After 20 relevant teams have been contacted, fewer than three serious
discovery conversations triggers a positioning/channel review. Do not lower
the fit bar or begin speculative integrations to improve the count.

## Target mix

Build a balanced private target list before sending messages:

- five Promptfoo, DeepEval, or comparable evaluator users;
- five LangSmith, Phoenix, Langfuse, or OpenTelemetry-instrumented agent teams;
- five maintainers or researchers working on repeated agent reliability;
- five teams operating bounded, consequential routers, tool selectors, policy
  decisions, or categorical judges.

Favor teams with a visible evaluation workflow and a plausible repeated-run
problem. Do not scrape personal contact details, mass-message communities, or
contact the same person through multiple channels.

## Qualification rubric

A pilot must have all of the following:

- a finite decision layer or declared finite trajectory equivalence;
- a concrete release, regression, or baseline question;
- raw ordered observations, or the ability to collect at least two independent
  trials per case;
- a way to state trial isolation and the tested target revision;
- an owner able to run a local Python CLI and review the interpretation.

Prefer cases with multiple routes, a critical decision, an existing evaluator,
or uncertainty caused by rerun variance. Defer cases seeking correctness
grading, open-ended quality scores, production hosting, or analysis from
aggregates alone.

## Outreach copy

Personalize the bracketed sentence and remove claims that are not evidenced.

> I maintain AgentVerity, an open-source qualifier for repeated categorical
> agent decisions. I noticed [specific public workflow or evaluation asset].
> I am looking for a small number of design partners who need to decide whether
> repeated route/tool/judge evidence is strong enough to freeze as a regression
> baseline. The pilot runs locally, can reuse saved raw runs, and does not claim
> correctness. Would a 30-minute evidence-mapping conversation be useful? The
> scope and data policy are here: [pilot link].

Send at most one concise follow-up after seven days. A decline, no response
after the follow-up, or poor fit closes the record without further contact.

## Discovery protocol

Ask in this order and capture claims, not raw customer data:

1. What release decision is difficult today, and what happens after a false
   green or false red?
2. What is the bounded decision layer? List labels or path equivalence without
   sharing prompts or outputs.
3. What cases, repeats, ordering, isolation, target revision, and existing
   graders are available?
4. How is evidence currently compared, and which uncertainty remains?
5. Can a local-only pilot answer the question? Who owns the next action and
   date?
6. Could a sanitized fixture or case study be published? Treat “no” as fully
   acceptable.

Use [the discovery-note template](templates/design-partner-discovery.md). End
an unqualified call with the explicit reason and, where useful, point to the
complementary tool category that fits better.

## Tracking and privacy

Copy [the funnel schema](templates/design-partner-funnel.csv) into a private,
access-controlled tracker. Never commit the populated copy. Use opaque record
IDs; keep names, handles, contact details, call notes, prompts, outputs, and
trace identifiers outside this repository. Update aggregate counts in public
planning only when they cannot identify a participant.

Review the funnel after every five contacts. Compare response and qualification
rates by source segment, record repeated objections verbatim only when they
contain no identifying information, and change one positioning assumption at
a time.
