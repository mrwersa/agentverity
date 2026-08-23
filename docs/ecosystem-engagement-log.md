# Ecosystem Engagement Log

Public, append-only record of artifacts already contributed on relevant
standards and tooling threads. Entries reference our own posts after they are
public. Prospective targets, contact details, planned follow-ups, private
correspondence, participant identities, and populated funnel rows stay in the
private tracker described by [the playbook](design-partner-playbook.md).

Each entry records the date, channel, contribution, and public relevance. This
file is not sufficient context for further contact: consult the private tracker
before replying or following up.

An entry here does not count as a design-partner contact, discovery, or pilot
unless a separate interaction satisfies the playbook definition and is recorded
in the private funnel.

## Entries

### 2026-08-22 | EvalPort spec proposal

- Channel: [adhabnr-ux/evalport#20](https://github.com/adhabnr-ux/evalport/issues/20)
- Segment: evaluation-interchange standards community
- Contributed: concrete gap analysis of ResultSet repetition and trial-isolation semantics, three resolution options, and an offer of conformance fixtures from our integration contract
- Relevance: repetition/isolation semantics would make ordered results usable by downstream stability qualifiers without weakening the interchange spec into an AgentVerity-specific format

### 2026-08-22 | LangSmith native-export feature request

- Channel: [langchain-ai/langsmith-sdk#3428](https://github.com/langchain-ai/langsmith-sdk/issues/3428#issuecomment-5382977879)
- Segment: evaluation-platform users
- Contributed: downstream-consumer requirement that repetition structure survive any LangSmith-to-EvalPort bridge, with a link to the spec proposal above
- Relevance: records a concrete downstream need for repetition-preserving export while leaving the interchange shape to EvalPort and LangSmith maintainers

### 2026-08-23 | EvalPort repetition RFC refinements

- Channel: [adhabnr-ux/evalport#22](https://github.com/adhabnr-ux/evalport/discussions/22#discussioncomment-18122995)
- Segment: evaluation-interchange standards community
- Contributed: technical review of the proposed attempt/isolation fields, three refinements (open isolation string, per-group consistency, ascending-attempt observation order), and confirmation of the conformance-fixture offer
- Relevance: shapes the interchange format so repeated categorical evidence survives export with pairing order and isolation provenance intact

## Rules for updating this log

- Append entries; never delete or edit history except to add an outcome note dated after the fact.
- One entry per distinct thread or conversation.
- Link only our attributable artifacts after they are already public.
- Never record an uncontacted target, follow-up schedule, private handle, or next action here.
- When a thread produces a real raw-run sample or pilot commitment, graduate it: create a discovery note from [the template](templates/design-partner-discovery.md), store it privately, and record only the aggregate effect here.
