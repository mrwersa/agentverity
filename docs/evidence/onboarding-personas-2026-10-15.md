# Simulated first-use walkthroughs

Five independent AI subagents completed the [participant exercise](../onboarding-task.md)
as different developer personas. This is simulated usability feedback, not
five human participants or evidence of independent adoption. It does not
satisfy the roadmap's fresh-user onboarding gate.

## Method and limits

The study ran on 14–15 October 2026 in Europe/London. The tested starting
point was release commit `3325af0`, plus the new participant instructions and
short JSONL fixture on `feature/onboarding-validation`, before the copy fixes
below. Each subagent started without parent conversation history or another
persona's findings. Instructions allowed the participant brief, README, its
linked guides, and CLI help, while excluding implementation, tests,
changelog, and the facilitator answer key.

All five reused the verified 0.25.2 wheel environment. Installation and setup
were not independently exercised or timed. Exercise commands used recorded
synthetic data and a local Python router; they made no target model/provider
calls. Subagents themselves are AI model executions.

The personas share a model and instructions. Their expertise, fast reading,
and command access can hide novice problems. Persona-specific concerns are
generated hypotheses, not observations about real people. Reported durations
are agent wall-clock intervals including reading and tool use, not human
completion-time measures.

## Recorded command results

Every persona ran the same three exercises from the repository root. No
execution blocker was reported. Their reference decisions and distinctions
between repeatability, correctness, and safety were consistent with the
documented contract.

| Exercise | Observed result | Exit |
|---|---|---:|
| README Promptfoo assessment | Rejected; 8/78 flips, 10.3%, pooled interval [0.053, 0.190]; changing card-security route, five quiet routes inconclusive | 0 |
| Payment-dispute example | Narrow reference refused; repaired reference admitted at pooled level; individual repaired route intervals inconclusive | 0 |
| Short JSONL fixture | Inconclusive; 0/2 flips, interval [0.000, 0.658] | 2 |

All five also ran `plan --observed 0/2 --epsilon 0.05`: 73 total pairs and 71
additional pairs under an all-agree continuation, exit 0. This is optimistic
planning, not guaranteed qualification or an early-admission rule.

| Simulated persona | UTC start–end, 14 October | Agent elapsed | Setup |
|---|---|---:|---|
| Python developer new to repeatability checks | 22:58:37–22:59:37 | 60 seconds | Reused, unmeasured |
| QA engineer familiar with assertion scores | 22:58:48–22:59:16 | 28 seconds | Reused, unmeasured |
| Platform/CI engineer | 22:58:54–22:59:37 | 43 seconds | Reused, unmeasured |
| ML evaluation researcher | 23:00:31–23:01:05 | 34 seconds | Reused, unmeasured |
| Router application engineer | 23:00:38–23:01:05 | 27 seconds | Reused, unmeasured |

No 15-minute success rate, human comprehension score, or installation success
rate is inferred from this table. The first three sessions began before the
second pair; all used the same pre-fix README and offline exercise.

## Findings and changes

| Reported friction | Persona reports | Applied change |
|---|---:|---|
| The coverage table's qualified meter can look inconsistent with the narrow reference's refusal; the repaired admission's pooled scope is easy to miss | 5/5 | Explain pooled-meter qualification separately from missing coverage and individual route intervals beside the README table |
| Inconclusive recovery uses terms such as K and lower precision without a concrete next step at the existing tolerance | 5/5 | Add the executed 0/2 planning example to the method guide; define k and explain that cheaper precision changes policy, not display formatting |
| CLI snapshot can look like a way to save an imported assessment | 2/5 | State live collection in the command table and link the Python imported-admission path |
| Pairwise comparison can be mistaken for all possible combinations of repeats | 2/5 | State non-overlapping pairing in collection order beside the first flip definition |
| An exit-1 “target” can be read as the assessed agent rather than a declared route policy | 2/5 | Name the declared route stability target explicitly in the imported-evidence exit table |

Two additional suggestions concern future live collection: wording around
relations and measured references, and printing more numerical detail in the
compact coverage demo. No exercise failed because of those suggestions. The
study keeps the existing report and example outputs; the full assessment and
linked method guide already expose the numerical evidence.

## Build/defer decision

The observed questions have existing homes in the README and method/import
guides. No persona identified a distinct post-hoc task that needs an
`explain` command. Keep that command deferred. The simulation is complete;
fresh-user validation and its roadmap metric remain unmeasured.
