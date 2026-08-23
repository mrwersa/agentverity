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

### 2026-08-23 | Outcome note on both entries above

- Channel: [adhabnr-ux/evalport#22](https://github.com/adhabnr-ux/evalport/discussions/22)
- Outcome: the EvalPort maintainer confirmed the gap against the enforcement
  code rather than the spec prose, noting that `validate_result_set()` carries
  no duplicate `test_case_id` check while `validate_suite()` does, so repeated
  results are currently unaddressed rather than supported or rejected. They
  opened an RFC titled for the requirement and credited this project in the
  title, are leaning toward the additive `attempt` and `isolation` fields on
  `Result` over fragmenting into separate ResultSets, and took up the
  conformance-fixture offer. On the LangSmith thread they stated that the
  adapter's `evaluate()` conversion will adopt whatever repetition semantics
  land so `num_repetitions` round-trips rather than being flattened.
- Status: RFC open, nothing merged. This is engagement, not a spec change, and
  it does not yet meet the Phase 1 pilot definition in the playbook.

### 2026-08-23 | ICC reliability team outreach

- Channel: [youdotcom-oss/stochastic-agent-evals#13](https://github.com/youdotcom-oss/stochastic-agent-evals/issues/13)
- Segment: repeated-reliability researchers
- Contributed: the distinction between convergence budgets for measuring instability and certification budgets for admitting a baseline, two questions for their Evaluation Cards proposal, and a request to calibrate the sensitivity axis against their GAIA and FRAMES variance data
- Relevance: their ICC reporting and our admission rule are adjacent layers of the same reliability question, making this team both a methodological reviewer candidate and a calibration source

## Rules for updating this log

- Append entries; never delete or edit history except to add an outcome note dated after the fact.
- One entry per distinct thread or conversation.
- Link only our attributable artifacts after they are already public.
- Never record an uncontacted target, follow-up schedule, private handle, or next action here.
- When a thread produces a real raw-run sample or pilot commitment, graduate it: create a discovery note from [the template](templates/design-partner-discovery.md), store it privately, and record only the aggregate effect here.
