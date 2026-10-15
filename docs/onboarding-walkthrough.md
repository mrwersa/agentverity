# First-use walkthrough protocol

This protocol tests the [roadmap's onboarding gate](../ROADMAP.md): four of
five fresh users reach an interpretable result within 15 minutes, and none
mistakes repeatability qualification for correctness. It is a usability
exercise, separate from a design-partner pilot or evidence of independent
adoption.

**State: exercise verified; five simulated persona walkthroughs completed.**
The [simulation report](evidence/onboarding-personas-2026-10-15.md) records
findings and resulting copy changes. Human completion time, installation
success, and the fresh-user metric remain unmeasured.

## Run a session

Use five people who have not previously used AgentVerity. They should be able
to run a Python CLI; record relevant prior evaluation-tool experience without
names. Supply [the participant exercise](onboarding-task.md), the README, and
a fresh checkout. Keep this facilitator guide and its answer key separate.
Run participant sessions after this exercise has merged, so the README's
checkout includes its short JSONL fixture. Pre-merge command verification
uses the PR branch and contributes no participant results.

Record the tested commit, installed version, Python version, and operating
system. Start the clock when the participant first opens the README, before
installation. Note time to first report and time to its first correct
interpretation. Installation failures and delays count toward the 15 minutes;
record them separately so setup and explanation problems can be distinguished.

Ask the participant to think aloud. Let them use existing linked guidance;
do not explain the concepts or point to answers during the timed exercise.
If help is necessary, record the intervention and mark that result assisted.
Stop the unaided exercise at 15 minutes, record what remains unresolved, then
debrief and correct misunderstandings. Complete the remaining prompts during
the debrief when useful; they do not turn a timeout into a timed success.

Copy [the session template](templates/onboarding-session.md) into a private
tracker. Use opaque IDs. Keep participant identities, contact details, raw
responses, terminal captures, and populated session notes outside this
repository. Use only the bundled synthetic data. Publish aggregate findings
only with participant permission and when they cannot identify a person.

## Scoring and answer key

An unaided interpretable first result requires recognizing the changing
route, refusing that evidence as a reference, and separating assessment exit
0 from admission, all before minute 15. A report appearing on screen is
insufficient. The remaining exercises probe coverage and inconclusive
evidence; record their answers separately from the first-result timing.

| Exercise | Expected interpretation | Verified command outcome |
|---|---|---|
| README Promptfoo assessment | Allowed answers can still change route across repeats. This evidence is rejected as a regression reference. Exit 0 means the assessment completed, not admission. | `REPEATABILITY REJECTED`; exit 0 |
| Payment-dispute example | Both sets score 6/6. The narrow set reaches one required route and is refused; the repaired set reaches all six and is admitted at pooled level. Untargeted route intervals remain inconclusive. Acceptability is a separate review. | `REFUSED`, then `ADMITTED`; exit 0 |
| Short JSONL collection | Two quiet pairs are insufficient at the declared tolerance. Zero observed flips do not establish repeatability. More usable evidence is needed under suitable isolation assumptions. | `INCONCLUSIVE`; exit 2 |

The final correctness/safety question is scored separately for all five users.
Require an explicit unaided answer. A missing answer is **not observed**;
an answer after help is **assisted**. Neither demonstrates understanding or
counts as a successful correctness interpretation.
Qualification supports bounded repeatability for the supplied cases and
assumptions; it does not prove correctness or safety. An evaluator or human
must review acceptable behavior. `deterministic` does not mean zero randomness,
and pooled qualification does not certify every route separately.

The gate passes only after five sessions, with at least four unaided first
interpretations within 15 minutes, all five giving an explicit correct,
unaided correctness/safety answer, and no participant making a correctness
claim during their unaided exercise. Missing or assisted correctness answers
leave that criterion unverified. Count timeouts and failed setups in the
cohort; do not replace them with successful participants. Missing,
assisted, or timed-out observations cannot be counted as unaided successes.
Debrief corrections do not erase the original misunderstanding.

## Decide the next change

Summarize counts and recurring blockers, distinguishing installation,
terminology, report navigation, and interpretation. For each proposed change,
record the observed question, the existing surface that failed to answer it,
and an observable acceptance condition. Change the relevant README paragraph,
linked guide, or report first, then run the exercise with fresh participants.

Keep `explain` deferred unless sessions demonstrate a post-hoc task that
existing summaries, refusals, `inspect`, or `check` cannot serve. Document the
task and why an existing surface is insufficient before proposing a command.
No new command or schema is approved by preparing this exercise.

The session exercise, synthetic fixture, and command verification are ready.
The simulated study supports the recorded copy fixes. Fresh-user validation
remains unmeasured, and `explain` remains deferred.
