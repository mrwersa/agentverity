# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows [Semantic Versioning](https://semver.org/) once it
reaches 1.0.0; before that, minor versions may include breaking changes.

## [Unreleased]

## [0.18.4] - 2026-08-22

### Added

- Generic JSONL imports accept optional provenance metadata, so converted
  harness exports can retain their source, model, and collection context.
- A reusable integration conformance kit checks that Promptfoo, DeepEval, and
  JSONL imports preserve ordering, provenance, isolation, and evidence round
  trips while refusing aggregate-only input.

### Fixed

- Isolated builds pin Hatchling below 1.32 until the release toolchain accepts
  the core metadata 2.5 that version emits, preventing an otherwise valid
  release from failing at `twine check`.

## [0.18.3] - 2026-08-08

The README named the three stability verdicts as "stable enough, unstable,
undecided" in two places, and `docs/evaluator-stability.md` in a third. The
command prints `deterministic`, `stochastic`, and `undecided`. The word
`unstable` appears nowhere in the package, so a reader who followed the PyPI
description and then ran `assess` saw two of the three words change under
them. The sample output in the README's opening section also carried no
explanation of `flip`, `stochastic`, or `undecided` at all.

### Fixed

- Documentation named two of the three stability verdicts differently from
  the values `assess` prints and the snapshot records. All three lists now
  use `deterministic`, `stochastic`, and `undecided`.
- The README's opening sample output showed `flips`, `stochastic`, and
  `undecided` with no gloss. Each is now defined once, immediately after the
  block where it first appears.


## [0.18.2] - 2026-08-05

Promptfoo has allowed a per-test repeat count since 0.121.18, and that count
overrides the global `--repeat` flag. The importer's refusal message for a
case with too few observations used to name only the global flag, so a caller
who set the per-test count could not learn why raising the global one changed
nothing. The message now names both knobs.

### Fixed

- A Promptfoo case with too few observations advised `--repeat` alone. Since
  promptfoo 0.121.18 a case can carry its own count in
  `tests[].options.repeat`, and that overrides the global flag, so a caller who
  set a per-test count was sent to the one control that could not change the
  case. Both knobs are named now. Found by testing the claim the 0.18.1 docs
  make rather than by reading them.


## [0.18.1] - 2026-08-04

Promptfoo has allowed a per-test repeat count since 0.121.18. The docs now say
what that knob does and does not do: a count decides how many calls to make,
and sizing that count from a tolerance stays the judgement AgentVerity adds.
No runtime behaviour changed.

### Changed

- `docs/imported-evidence.md` records the promptfoo per-test `options.repeat`
  knob and restates the boundary: the count is a setting, the sizing and the
  tri-state verdict are the assessment.
- The README's rerun-count section makes the same point in two sentences, so
  a reader arriving from a promptfoo tutorial does not mistake the knob for
  the judgement.
- The `promptfoo_bridge` example notes that per-test counts import the same
  way as one global count, because the importer matches each rendered input
  back to a reviewed suite case.

## [0.18.0] - 2026-08-04

The last item on the ordered roadmap. The relation catalogue is yours to
extend, from the command line as well as from Python, and a relation that
cannot be run or reported is refused when you build it rather than partway
through a run you have already paid for.

A minor rather than a patch: `Relation` now refuses names, types and callables
it used to accept, which is a change to a public contract.


### Added

- `agentverity run --relations module:func` runs your own relation catalogue,
  as `module:func` or `file.py:func`. The function takes no arguments and
  returns relations, or a single `Relation`, which is the shape
  `builtin_relations` already had. It replaces the built-in catalogue rather
  than extending it, so include the built-ins yourself when you want both.
  A user relation is scored, tabled and counted towards per-route relation
  coverage exactly like a built-in. Only `run` executes relations, so only
  `run` offers the flag.
  A catalogue that raises is not flattened into a refusal, matching how an
  `--agent` factory behaves: a bug in your own module surfaces with the stack
  you need to fix it.
- `docs/custom-relations.md` and `examples/custom_relation.py` document the
  protocol, including the part worth knowing before writing one: an input the
  transform leaves unchanged is skipped rather than passed, because a transform
  that returns its input asks the agent the same question twice. `docs/api.md`
  carries the shape too, so a reader of the API guide is not sent elsewhere for
  it.
- `examples/README.md` says what each example demonstrates. Five of them were
  reachable only by browsing the directory, which is the argument that already
  applies to CLI commands nothing names.

### Changed

- Documentation and examples import from the shallowest path that works.
  `builtin_relations` and `from_callable` were reached through their defining
  modules in files that imported their neighbours from the top level, which
  teaches a reader that the deep path is sometimes required. It is not.
- `Relation` refuses an empty name, an unknown type, or a transform or check
  that is not callable, at construction rather than mid-run. A broken relation
  was previously discovered after the source calls had been made and paid for.
  `RELATION_TYPES` names the closed set.


## [0.17.0] - 2026-08-04

A minor rather than a patch, and deliberately. The fixes below correct flags
that were accepted and discarded, and correcting them removes one and refuses
another combination, which is a command-line contract change. `STABILITY.md`
promises that patch releases preserve those contracts, so this is where the
work belongs.


### Fixed

- `agentverity snapshot --sequential` was parsed and discarded. The flag sat on
  the shared parser and only `run` read it, so a caller asking a snapshot to
  stop early got the full fixed-sample spend and no indication otherwise. Six
  inputs now record 72 pairs rather than 78.
- `check` no longer offers `--sequential` at all. It rebuilds its config from
  the snapshot, `k` included, and `k` cannot hold beside checkpoints. A parse
  error arrives before the agent is loaded, where a runtime refusal did not.
- `k` and `sequential=True` are refused together. Sequential collection ignored
  `k` outright, so `k=4` on six inputs asked for 24 calls and spent 144, and
  `k=40` asked for 240 and spent the same 144. `budget` is still threaded
  rather than refused, because a cap bounds early stopping where a second
  sizing rule conflicts with it.
- `STABILITY.md` named `agentverity.snapshot/v3` as the schema this version
  reads, while 0.16.0 writes v4 and refuses v3 outright, so the document told a
  reader their stored baseline was readable by the release that rejects it.
  Guarded now: every schema the code writes must be named there, and no
  superseded number may still be advertised.


## [0.16.0] - 2026-08-03

Isolation stopped being a caveat and became a decision: evidence collected
from a shared session can no longer certify a baseline, and adapters now state
what they did rather than leaving it unknown. A run can also stop at a
declared checkpoint instead of spending its whole budget.


### Added

- `RunConfig(sequential=True)` and `agentverity run --sequential` stop a run at
  the first declared checkpoint that decides. Collection goes in rounds of one
  pair per input, and a decision reads exactly the first n pairs, so a round
  that overshoots a checkpoint waits for the next one rather than moving the
  boundary.
  Measured against the default sizing: an agent flipping 30% of the time
  finishes in 33% to 60% fewer calls, and a stable agent saves little or
  nothing because the planner already sizes the fixed-sample path close to the
  checkpoint budget. It is for not paying to confirm what a run has already
  shown, which is why it is opt-in.
  The call comes from the plan, and both the terminal report and the JSON say
  which count decided. Reading the Wilson interval at a stopping point it did
  not choose is the optional stopping this avoids, believed rather than done.
  `budget` still caps the calls, and a budget too small to reach a decision
  gives `undecided` here exactly as it does on the fixed-sample path. Refused
  together with declared route stability targets, because a cap bounds early
  stopping happily while a second sizing rule conflicts with it.
  A suite run keeps its per-route table, so stopping early costs no analysis.

- `plan_sequential` and `decide_sequentially` stop collecting once the answer
  is in, without invalidating it. Checkpoints are declared before collection
  starts, so this is not the Wilson interval recomputed after every pair, which
  is optional stopping and destroys the coverage the interval claims.
  The error budget is split by direction rather than evenly. Certification is
  tested once, at the final checkpoint, so it carries no multiplicity penalty:
  72 pairs at a 5% tolerance against the fixed sample's 73. The earlier looks
  test only the stochastic direction, and an obviously unstable route stops in
  a quarter of the budget.
  A decision reads exactly the first n pairs in collection order, so results
  that overshoot a checkpoint under concurrency are kept as evidence and never
  change a call.
  Not yet driven by `run`, so the saving is available to a caller driving
  collection rather than from the command line.

- Adapters declare the isolation they produce, and `run` records it, so the
  admission policy below now applies to a live run instead of only to imported
  evidence. `from_strands_factory` declares `fresh-instance`, `from_langgraph`
  declares `fresh-session`, `from_strands` and `from_langgraph_thread` declare
  `shared-session`, and `from_callable` declares nothing.
  The declaration follows what the adapter did rather than which function was
  called: `from_langgraph` respects a caller-supplied `thread_id`, and every
  repeat then runs on that one thread, so it declares `shared-session` in that
  case. Keying it on the function name would have asserted independence
  exactly where the caller opted out.
- `from_callable` carries an underlying declaration rather than dropping it.
  It reshapes a return value and changes nothing about how trials are
  separated, so the statement is still true afterwards. This is what makes the
  policy reach the CLI, which loads every agent through it: without it a
  Strands factory reported `unknown` at the command line and its baseline was
  admitted on the caveat the policy exists to replace.
- The LangGraph adapters copy their `config` at construction, so the declared
  isolation and the calls describe one thing. Mutating the mapping afterwards
  to add a `thread_id` previously sent later repeats down one shared thread
  while the declaration still claimed independence.
- `declare_isolation` and `isolation_of` for anyone writing an adapter,
  exported from the top-level package where the rest of the API lives.

- Isolation now decides whether evidence may certify a baseline.
  `shared-session` is refused, `unknown` is admitted with its caveat
  travelling, and `fresh-session` and `fresh-instance` are admitted. Before
  this the caveat had no consequence: the same run printed "repeats are not
  independent and the interval is narrower than the evidence supports" and
  then produced a snapshot resting on that interval.
- A snapshot records the isolation it was admitted under, and `check` reports
  when the current run establishes less than the evidence that certified the
  baseline. A snapshot previously recorded no isolation at all, so the
  provenance died at the admission boundary.

### Changed

- **Behaviour change.** A run collected through a shared-session adapter is now
  refused a baseline. Anyone snapshotting through `from_strands` or
  `from_langgraph_thread` was previously admitted, because the run recorded
  `unknown` whatever it had done. Use `from_strands_factory`, or
  `from_langgraph` without pinning a `thread_id`, for evidence intended to
  certify.
- `agentverity.snapshot/v4`. A v3 reader cannot apply the policy, because the
  field is absent and neither default is safe: reading a missing isolation as
  `fresh-*` claims provenance nobody asserted, and reading it as
  `shared-session` refuses baselines that were legitimately admitted.
- `check` can print a `provenance:` line before its verdict. A parser reading
  the first line of output to decide pass or fail now sees it on a weakened
  run. Exit codes are unchanged: `0` clean, `1` drift, `2` refused. Key on the
  `snapshot clean:` and `snapshot drift:` prefixes rather than on position, or
  on the exit code, which is the stable contract.
- `assess --isolation` is refused with `--evidence` instead of being accepted
  and discarded. An evidence file records its own isolation, and since that
  value now decides whether the evidence may certify a baseline, silently
  overriding the flag let a caller believe they had upgraded the provenance of
  a baseline they were about to freeze.

### Migration

- **A stored v3 snapshot is refused, and re-admission is the path.** There is
  no upgrade script and there should not be one: a v3 file does not record how
  its trials were isolated, and filling that in now would manufacture the
  provenance the policy exists to establish. Re-run and snapshot again,
  stating the isolation the run actually had. The refusal says this, so the
  answer arrives where the problem does.


## [0.15.0] - 2026-08-03

Route reach became three quantities instead of one, the absence of a decision
became a type instead of a missing field, and any harness that can write one
JSON object per run can now be assessed. Every schema a file is written at is
listed below, because two of them moved.


### Added

- `evidence_from_jsonl` and `load_jsonl` read repeated decisions from a JSONL
  file any harness can produce: one JSON object per run, with dotted paths
  naming the input and decision fields. `agentverity assess --jsonl` exposes
  it. A harness with no bridge, a production log and a converted CSV are
  between them most of the evidence teams already hold.
  The order in the file is the order runs are paired, so a log sorted by
  decision reports a stability the run never had. An input appearing once is
  refused rather than imported, because it carries no comparison, and the
  refusal stops the whole import rather than dropping the offending input.
- `agentverity assess` refuses a flag the chosen source cannot act on rather
  than discarding it. It reads three sources through one set of options, and a
  flag the caller set that quietly does nothing is the same defect as a default
  that silently overrides one they named.
- `docs/evidence/agentkit/`: 4,380 real model calls against the tool set the
  Coinbase AgentKit Strands example exposes, across three models, with every
  observation committed so re-assessing costs nothing. The collector, the
  adapter, the suite, and a summariser are there too.
- The README presents both real runs as one arc rather than one example and a
  footnote. AgentCore shows the analysis surviving a real deployment and says
  plainly that six pairs per route certify nothing; AgentKit is the run with
  enough repeats to certify, and it exists because of that limitation.
- The write-up is pinned to the evidence by a test. Three numbers in it were
  wrong before that existed, including a wall time quoted as 25 minutes in one
  place and 33 in another against a recorded 30.1.
- The result is this library's caveat with numbers behind it. One model
  returned the same tool on all ten probes and was correct on five of them,
  while a model that is unstable on two routes was correct on seven. A
  stability gate alone prefers the worse agent.
- `Decision(label)` and `NoDecision(reason)` type what a run decided, or why it
  did not. Two reworded refusals are now one decision rather than two, because
  a `NoDecision` compares on its reason. The reason vocabulary is closed and
  splits in two: `refused` and `no_tool_selected` are things the agent did and
  a contract may declare them, while `extraction_failed`, `malformed_response`
  and `runtime_error` are things the harness could not do and make the evidence
  incomplete. A single sentinel would have merged all six, and a run of
  extraction failures would then have certified as perfectly stable. See
  DESIGN.md ADR 2.
- `Observation.outcome` and `Observation.is_incomplete` read that typed result.
  A string verdict stays a `Decision`, and an unset verdict on an agent that
  produced prose is `open_ended`, which is comparable to nothing on a
  categorical layer.
- Both the pooled meter and per-route stratification refuse a series they
  cannot honestly score, through one shared check. Repeated extraction
  failures would otherwise contribute zero-flip pairs and certify the failure.
  An `open_ended` result is refused rather than filtered out: dropping those
  runs while keeping the repeat count would report stability across reruns
  that did not decide anything.
- The JSON report serialises a typed outcome tagged, as
  `{"kind": "decision", "label": ...}` or `{"kind": "no_decision", "reason":
  ...}`, so a decision whose label happens to be `refused` is distinguishable
  from a run that refused.

- `OutcomeNotScorable` is raised by every path that cannot account for a typed
  outcome: the meter refusing an incomplete series, the meter refusing a series
  with too few comparable observations, and coverage refusing a `NoDecision`.
  It subclasses `ValueError`, so a caller already catching that keeps working.

- The evidence schema records a no-decision as
  `{"kind": "no_decision", "reason": ...}` and a decision as a plain string.
  One reading rule, and the smallest form that stays unambiguous: tagging both
  would triple a repeat-heavy file to record a distinction nothing acts on,
  because comparison already treats a bare label and a `Decision` as one.

- `DecisionContract.allowed_no_decisions` declares which no-decision outcomes
  satisfy a contract. Its own field, because `refused` there and `refused` in
  `allowed` are two different declarations, and coverage counts them
  separately. Only `refused` and `no_tool_selected` may be declared: a harness
  failure cannot be made acceptable, and categorical stability is undefined
  over an open-ended answer. Declaring a reason permits it and does not require
  it. An undeclared one is still refused, because silence is not permission.
- `allowed_no_decisions` is additive and optional, so it is not a schema
  change: a suite written without it parses correctly.

### Changed

- **Breaking, with no known external consumers.** `agentverity.evidence` moves
  to v2 because the shape of an observation changed: a run that produced no
  decision is now an object, and the 0.14.0 reader rejects one. Run, telemetry
  and snapshot stay at v2 because nothing about them changed, and the decision
  suite stays at v1 because `allowed_no_decisions` is optional and additive.
  Only the current version of each is readable; there are no legacy readers.
- `STABILITY.md` states when a version changes: only when a reader cannot
  correctly interpret a file written at the previous version. Adding an
  optional field is not a version change. Different schemas therefore sit at
  different numbers, which is what it looks like when a version records the
  history of one format rather than a release.

- `agentverity.snapshot/v3` stores a typed outcome the way evidence does: a
  decision as a plain string, a no-decision as
  `{"kind": "no_decision", "reason": ...}`. Before this a contract could
  declare a refusal and never baseline one, so the feature worked right up to
  the point of using it. Only a reason a contract can declare reaches a
  snapshot; the meter refuses the rest long before admission, and the
  serialiser refuses them again rather than trusting that.
- A stored snapshot outcome is validated on read, against the same vocabulary
  the writer can produce. Evidence already did this. A snapshot did not, so a
  hand-edited file carried an invented reason into a comparison, and a probe
  missing its reason compared equal to any other probe missing one.
- Snapshot comparison normalises both sides, so a baseline written before an
  adapter adopted the typed outcomes still matches the runs it makes
  afterwards. A diff still reports what is stored rather than the normalised
  form.


- The README opens with the finding rather than the positioning. A recorded
  `run` shows the result before the tool explains itself, because a reader
  who has not seen the failure has no reason to care about the library.
- Design and stability documentation now reflects the shipped 0.14 loop,
  including temporal comparison, LangGraph isolation, and the externally
  authored AgentKit evidence. The stale changelog comparison links are also
  restored through every published minor and patch release.
- Simple diagrams now keep Mermaid as their reviewable source and SVG as the
  documentation render, with PNG reserved for Medium. The bespoke release-gate
  dashboard remains SVG because its denser layout does not benefit from a
  generic flow renderer.

### Fixed

- The `run`, `snapshot`, and `check` commands crashed with a Python traceback
  when `--agent` named a missing module or function or `--inputs` pointed at a
  file that does not exist. A typo in CI therefore reported as a failed
  stability gate (exit 1) instead of the caller-input problem it is. These
  now refuse with a one-line message and exit 2, the same contract `assess`
  already used, so a bad flag can no longer masquerade as a verdict.
- `agentverity --version` fell through to the required-subcommand error even
  though the sibling tool had a version flag. It now prints the installed
  version.
- `STABILITY.md` still pinned `agentverity~=0.13.0` after the README was
  corrected, because the pin guard scanned one file. The README pinned
  `agentverity~=0.13.0` in the 0.14.0 release, so a reader following it pinned
  a series one behind the one they had installed. A test now checks every
  prose markdown file against the packaged version rather than trusting
  anyone to remember it.
- `compare-evidence` shipped as the 0.13.0 headline and reached 0.14.0 without
  a mention in the README, so it was discoverable only from the roadmap. It is
  described where the other checks are, and a test requires every CLI command
  to appear on the front page.

## [0.14.0] - 2026-07-31

### Added

- A LangGraph adapter. `from_langgraph(graph)` wraps a compiled graph into the
  `run(input) -> Observation` shape, reading the final text, the ordered tool
  calls, and a decision from `verdict`, `decision`, `route`, or
  `classification`.
- Every call gets a fresh `thread_id`. A graph compiled without a checkpointer
  is unaffected; one compiled with a checkpointer would otherwise make each
  repeat a further turn in a single conversation, and the intervals this
  library reports assume independent trials. A `thread_id` supplied in
  `config` is respected, so opting out is possible and deliberate.
- `from_langgraph_thread(graph, thread_id)` for the case where the
  conversation itself is under test. Evidence collected that way should record
  `isolation: shared-session`, and the report then names the caveat.
- The adapter reads both message shapes: LangChain objects carrying
  `tool_calls`, and serialised dicts carrying `name` or `function.name`. The
  answer is the last message with text, so a trailing tool result is not
  mistaken for the response.
- A `langgraph` extra, so `pip install "agentverity[langgraph]"` gets the
  dependency. The adapter is lazily imported, so without it a user got an
  ImportError naming the module rather than the extra that provides it. The
  README says where both adapters come from, in the section about letting
  AgentVerity make the calls rather than in the one that makes none.
- A `ROADMAP.md`, which the project did not have. It names what each command
  establishes, what is next, and what is deliberately not planned.

### Changed

- Releases are cut by merging the version bump. The release notes come from
  that version's changelog section, so the prose is written once rather than
  once there and again by hand in the GitHub Release.
- The release runs when CI finishes on `main` and only when it succeeded, not
  when the push happens, and it reads the version from the exact commit that
  passed. Artefacts are built and checked before the tag and the GitHub
  Release are created, because tagging first leaves a public release behind
  whenever an upload fails. Only a commit still at the tip of `main` releases,
  since `workflow_run` events arrive as each CI run finishes rather than in
  commit order.
- The packaging smoke test compares three numbers rather than two: the literal
  in `pyproject.toml`, the installed distribution metadata, and what the
  imported package reports. Comparing only the first two is how a sibling
  project shipped a wheel whose `__version__` was a release behind.
- The README comparison table names AgentMandate, which answers the question
  next to this one rather than the same one, and links
  [agent-release-gate](https://github.com/mrwersa/agent-release-gate).

## [0.13.2] - 2026-07-30

### Added

- A provider-free evaluator-stability example and guide show how to qualify
  repeated `pass`, `fail`, or `uncertain` judgements without claiming that
  repeatability establishes validity.

### Changed

- The README and integration guide place AgentVerity in the full evaluation
  loop from capability exploration through regression admission and reviewed
  production feedback.
- Production pinning examples now name the current `0.13` minor series.

## [0.13.1] - 2026-07-28

### Changed

- The README opens with the developer's rerun question, defines a regression
  baseline in plain language, and shows how AgentVerity complements Promptfoo,
  DeepEval, and observability before introducing the detailed workflow.

## [0.13.0] - 2026-07-28

### Added

- `agentverity compare-evidence before.json after.json` compares two
  independently collected evidence windows and reports what moved: per-route
  intervals, decisions that appeared or disappeared, flip-pair structure, and
  any model, prompt, or harness difference recorded in provenance.
- The reportable event is a tri-state result changing rather than a rate
  wandering. A route drifting inside one conclusion is noise, reported as
  `higher` or `lower`; a route crossing from deterministic to stochastic is a
  release event. The direction names describe the observed change rate rather
  than interval width.
- A provenance change counts as drift even when every decision held, because a
  model swap is the fact you most want beside a comparison.
- `compare_evidence`, `EvidenceDrift`, and `RouteDrift` are exported.
- Volatile provenance keys such as `collected_at` are shown separately and not
  counted as drift. A Promptfoo export stamps its collection time, so counting
  it would report every real comparison as drifted.
- A changed flip pair and a changed isolation level both count as drift.
  Printing a change and then leaving the exit code silent is worse for a gate
  than not printing it.
- Comparing two windows on different observation layers is refused. A verdict
  and a tool path are not the same observation.
- Malformed evidence files produce a usage error rather than a traceback.

### Changed

- The README describes the target using the established agent-pattern
  vocabulary: routing, orchestrator-workers, evaluator-optimiser, tool use,
  multi-agent supervisor, and guardrail or policy gate, each paired with the
  decision that is actually under test.

### Notes

- A comparison never claims that agreement between two windows establishes
  independence within either one. Two correlated runs agree comfortably.
  Independence is a property of collection, recorded in `isolation`, and the
  caveat travels with every comparison.

## [0.12.2] - 2026-07-28

### Changed

- The README now follows a developer decision path: a fully green Promptfoo
  run, why its moving route matters, a no-model-call trial, integration points,
  and the baseline workflow. The measured AgentCore release-gate visual now
  appears where the delivery-stack placement is explained.
- The Promptfoo example's configured quality policy accepts either plausible
  fraud queue for one ambiguous case. All 156 assertions pass, while
  AgentVerity independently identifies the route as unstable for baseline use.

## [0.12.1] - 2026-07-28

### Added

- `examples/promptfoo_bridge/results.json`, generated by Promptfoo from the
  included local varying router, so `agentverity assess --promptfoo` can be
  tried without installing Promptfoo or making another provider call. The
  export has six reviewed cases, 26 repeats each, and one unstable route.

### Changed

- The README now leads with a route-level stability finding and the
  no-duplicate-call import path, while retaining the scope and limits below.
- Promptfoo assertion failures with returned outputs remain stability
  observations. Only provider or runtime failures make the imported
  AgentVerity evidence incomplete.

## [0.12.0] - 2026-07-28

### Added

- `agentverity assess --evidence runs.json` applies the admission checks to
  repeated runs collected by another harness, making no model calls. Most
  teams already run their agent repeatedly through promptfoo, DeepEval,
  LangSmith, or a script of their own, and paying twice for the same
  information is the main reason not to adopt a second tool.
- An `agentverity.evidence/v1` schema carrying individual observations grouped
  per case and kept in order, with optional intended decisions, error counts,
  and provenance. `EvidenceSet`, `EvidenceCase`, `assess_evidence`,
  `load_evidence`, and `save_evidence` are exported.
- Aggregates are refused with the reason rather than a bare error. A flip rate
  cannot be turned back into the disjoint pairs it came from, and a pooled
  number cannot be split by route.
- `isolation` records how trials were separated. An imported file can break
  independence in ways a self-run cannot, so a shared session or an unrecorded
  method is reported rather than silently assumed away.
- `docs/imported-evidence.md` covers the format, the refusal, the isolation
  levels, and what an import cannot check.
- Promptfoo JSON exports can be assessed directly with
  `agentverity assess --promptfoo results.json --suite suite.json`. Mixed
  provider or prompt matrices are refused until one configuration is
  selected, so configuration differences are not misreported as random
  decision changes. Repeated rows map back to reviewed inputs rather than
  relying on Promptfoo's per-execution `testIdx`.
- `evidence_from_deepeval` groups repeated precomputed `LLMTestCase` objects.
  DeepEval keeps ownership of per-case quality while AgentVerity makes the
  suite-level evidence decision, with no second target run.
- Imported `text` and `tools` layers preserve their real observation shapes.
  Provider errors make the result incomplete, and isolation caveats now travel
  through text, JSON, JUnit, and OpenTelemetry reports.

### Changed

- An assessment from imported evidence reports no relation results. A relation
  needs the agent to answer a transformed question, and those calls do not
  exist in an imported file. Claiming a relation held when it never ran would
  be the vacuous green this package exists to name.
- Imported assessments populate source observations and enabled-check
  configuration consistently, so the ordinary snapshot path can admit stable
  imported evidence rather than rejecting it as an incomplete live run.

## [0.11.0] - 2026-07-28

### Added

- Relation probing per route. A relation whose transform returns the input
  unchanged has tested nothing, and pooled totals hide which routes that
  happened to. On plain ASCII inputs the accent and tool-selection relations
  are no-ops, so a suite can report a flawless pass while two of three routes
  were never perturbed at all. Unprobed routes are now named, and their
  violation rate reads as absent rather than as zero.
- `DecisionContract.minimum_cases` asks for a number of distinct reviewed
  cases on a route. It is a declaration, not a calculation: repeats establish
  that one input's decision is stable, distinct cases establish that a route
  was approached from more than one angle, and no bound turns the first into
  the second. A shortfall is reported as a contract finding and counted from
  the cases that were written rather than from what the agent returned.
- `RelationCoverage`, `RouteRelationCoverage`, and `stratify_relations` are
  exported, and `RunResult.relation_coverage` is populated whenever a suite
  and relations are supplied.
- JSON reports include the complete per-route relation table. JUnit and
  OpenTelemetry include aggregate probed and unprobed route counts without
  exposing route labels in telemetry.

### Changed

- Public positioning now states the narrow role directly: AgentVerity is a
  conservative admission policy for regression baselines involving bounded
  decisions, beside correctness and trajectory evaluators rather than in
  place of them.

## [0.10.0] - 2026-07-28

### Added

- `DecisionContract.stability_targets` gives a route its own flip-rate
  tolerance, so a consequential decision can be held to a tighter bound than a
  routine one. Targets are numerical policy and remain separate from the
  `critical` coverage label.
- Repeats are sized per route when targets are declared. A suite with one case
  for a tightly targeted decision and five routine cases would otherwise give
  the targeted route the least evidence. On the three-route example, the
  zero-change plan is 1054 calls against 2286 for one uniform repeat count.
- `agentverity plan --suite` prints that best-case call plan without calling
  the agent. An explicit run budget remains a hard cap and is checked before
  execution.
- `docs/route-evidence.md`, a worked guide to reading the route table, why a
  verdict never comes from the observed rate, and where the budget goes.
- Per-route stability. When a decision suite is declared, the same repeated
  observations the pooled meter uses are split by each case's intended
  decision, so a route that misbehaves is named instead of averaged away.
  A pooled interval of 12.8% across six routes can be one route flipping
  constantly and five that never move. No extra agent calls: per-route trials
  sum to the pooled total, and a test asserts it.
- A flip-pair table recording the unordered pair of decisions the agent
  returned for one input, such as `deny <-> review`. It is not a confusion
  matrix, because this package does not judge which answer was correct.
- `RouteStability`, `FlipPair`, `StratifiedStability`, and `stratify_runs`
  are exported. `RunResult.route_stability` is populated whenever a suite is
  supplied and the meter is enabled, with no new flag to set.

### Changed

- Repeat series may now differ in length, which is what lets a run size
  repeats per route. Reports expose the minimum and maximum repeats rather
  than hiding the allocation behind one `k`. A series carrying fewer than two
  observations is still rejected because it contributes no pair.
- A declared target is a release condition. If its route remains undecided,
  run status, JUnit, and snapshot admission refuse. If the route is proven
  above the target, status and JUnit fail the declared policy.
- Route plans now appear in JSON and aggregate OpenTelemetry attributes.
- Without declared targets nothing changes. Repeats stay uniform and the run
  behaves as before.
- The tri-state rule moved into `classify_call`, shared by the pooled meter
  and the per-route view so the two cannot drift apart. A route is classified
  from its confidence bound, never from its observed rate: one flip in
  thirteen pairs is a rate of 7.7% against a 5% threshold and an interval of
  [0.014, 0.333], which is undecided rather than stochastic.
- The report distinguishes a route proven to move from a route with too little
  evidence to tell, and states that each interval is a separate 95% statement
  rather than a joint one.
- Proven route-level stochasticity now flows into the canonical run status and
  blocks snapshot admission even when the pooled meter looks deterministic.
  Untargeted undecided routes remain an explicit diagnostic rather than
  silently multiplying the default call budget.
- JSON reports include the route table. Route-stability entries in JUnit and
  OpenTelemetry carry privacy-minimised aggregate counts without decision
  labels.
- Cases whose repeated calls fail remain visible in their intended route with
  zero usable pairs instead of disappearing from the table.
- The payment-dispute example now labels its admitted baseline as a pooled
  stability result and keeps undecided route-level intervals visible.

## [0.9.1] - 2026-07-28

### Fixed

- A decision-suite file with no `contract` key raised `TypeError` while every
  other malformed suite raised `ValueError`, so a caller had to write two
  except clauses to load one file. Loading now reports every malformed suite
  as `ValueError`. `DecisionContract.from_dict` still raises `TypeError` when
  handed the wrong kind of object directly, which is a programming error
  rather than bad input.

### Added

- `DecisionCount` is now exported. It is the element type of
  `DecisionCoverageResult.intended_counts` and `observed_counts`, both public,
  so it could be received but not imported for an annotation.

## [0.9.0] - 2026-07-28

### Added

- Optional `DecisionContract`, `DecisionCase`, and `DecisionSuite` types for
  applications with finite reviewed decisions.
- Separate intended and observed coverage, missing-required and
  missing-critical decisions, and detection of outputs outside the allowed
  contract.
- Contract-aware Python and `--suite` CLI paths, JUnit release checks,
  privacy-minimised OpenTelemetry attributes, and snapshot admission.

### Changed

- JSON reports and OpenTelemetry attributes now use their v2 schemas.
- Snapshots now use `agentverity.snapshot/v2` and retain the decision contract
  plus each case's intended label. The loader remains compatible with v1
  snapshots.
- The payment-dispute and AgentCore examples now require all six declared
  routes before admitting a baseline.

## [0.8.6] - 2026-07-28

### Added

- An applicability guide that identifies the bounded decision points
  AgentVerity can assess, including steps inside multi-agent and otherwise
  open-ended systems.

### Changed

- The README now gives a three-part fit test: a finite reviewed decision
  contract, equivalent starting state across trials, and deliberately varied
  test inputs.
- The README and design guide now define decision coverage as a minimum
  dynamic skew and diversity check rather than exhaustive coverage of every
  declared route or important boundary.

## [0.8.5] - 2026-07-27

### Changed

- The README now describes the exact branch-protection topology: the Coverage
  job enforces the 90% floor and the required `CI gate` depends on it.
- Local coverage data is ignored so the documented development command leaves
  the working tree clean.

## [0.8.4] - 2026-07-27

### Added

- Public PNG versions of the evidence-gate comparison and AgentCore
  release-gate figures for publishing surfaces that do not preserve SVG or
  HTML tables.

### Changed

- The README states the complete tri-state stability rule, explains why
  reruns are paired without reuse, and distinguishes established Wilson
  statistics from AgentVerity's evidence-gated release design.

## [0.8.3] - 2026-07-27

### Changed

- The README names the two consequences of weak test evidence: a vacuous green
  result and the regression trap created when that narrow run becomes a
  baseline.
- The integration guide documents a layered agent test and release pipeline,
  places AgentVerity after labelled quality evaluation and before baseline
  admission, and gives one replaceable AWS-oriented tool stack.

## [0.8.2] - 2026-07-26

### Added

- A required CI coverage job and a badge backed by a 90% statement-coverage
  floor.
- An architecture decision record explaining why AgentVerity compares named
  decisions rather than generated text.
- A call-budget table for the three precision levels, with explicit guidance
  on why target-call budgets are more useful than a synthetic local throughput
  benchmark.

### Changed

- The README quickstart now shows a fully parameterised return type and links
  directly to the decision-layer ADR.
- Edge-case tests now cover invalid observation layers, execution
  configuration, sequence verdicts, and nested report values.

## [0.8.1] - 2026-07-26

### Changed

- The README and `DESIGN.md` distinguish declared structure from observed
  behaviour. Static tools can inspect orchestration branches, route schemas,
  and expected labels. AgentVerity measures which decisions a model-backed or
  black-box target actually returns and whether identical reruns disagree.
- The README now puts a runnable zero-credential example before the statistical
  explanation, states the open-ended-agent non-fit explicitly, and describes
  relation execution as an optional convenience rather than the contribution.
- The README is now a short first-use path. Statistical derivation and
  integration mechanics live in focused guides instead of competing with the
  quickstart.
- The package and CLI descriptions now use the same decision-stability and
  coverage language as the README.
- A pre-1.0 stability policy documents patch compatibility, versioned schema
  handling, safe pinning, and concrete exit criteria for 1.0.

## [0.8.0] - 2026-07-26

### Added

- `from_strands_factory`, which builds a fresh Strands agent for each trial so
  repeated measurements do not inherit conversation history from earlier
  calls.
- A live payment-triage showcase combining Strands, Amazon Bedrock, DeepEval,
  AgentVerity, AgentCore Runtime, OpenTelemetry, and JUnit-compatible CI
  output. It remains optional, while the zero-dependency quickstart stays the
  default path.
- A `showcase` optional dependency group for running that integration.
- A machine-readable showcase evidence bundle with labelled-route accuracy,
  AgentVerity diagnostics, and end-to-end p50 and p95 latency.
- A redacted result bundle and generated dashboard from a real AgentCore
  Runtime canary in London.

### Changed

- Public documentation now presents AgentVerity as an evaluation runner for
  agents with named decisions, including deterministic gates and LLM agents.
  It frames stability and decision coverage as two scoped test-adequacy checks,
  defines baselines and snapshots at first use, and aligns the README,
  integration diagrams, package metadata, and generated reports.
- The README now keeps the measured AgentCore canary as its single visual
  showcase. The multi-agent diagnostic remains in the integration guide,
  beside the step-level guidance it supports.
- Terminal guidance now says `WHAT TO DO NEXT` and `test strategy` instead of
  reintroducing the retired research term `oracle`.
- The production showcase defaults to low-cost Amazon Nova Micro and separates
  runtime dependencies from the external evaluation stack.
- The showcase admits a reference only when both labelled-route quality and
  AgentVerity's evidence qualification pass. Stability can no longer mask an
  incorrect route.
- The AgentCore canary stops every isolated runtime session after reading its
  response, avoiding the idle-cost tail between repeated trials.
- The live canary exposes bounded concurrency through `--max-workers`, using
  four independent calls by default so a real runtime check finishes promptly.

## [0.7.0] - 2026-07-25

Reports that read well where people actually read them.

### Added

- A payment-dispute evidence-gate demo where both probe sets score 6/6, while
  only the set that crosses the routing boundary can become a snapshot. It can
  write JUnit artifacts, emit before-and-after OTEL spans, and print a
  comparison table with `--markdown` for a README or a CI job summary.
- `RunResult.duration_seconds`, the wall-clock time a run took.

### Changed

- JUnit output carries a `time` attribute. Without it, report collectors
  computed the duration as `NaNms` in every rendered section.
- `preflight.relation_coverage` is omitted when the caller passed no relations,
  instead of appearing as a skipped case. A check nobody requested is noise in
  a dashboard, and it rendered as an icon that reads as broken. Anything
  parsing the JUnit for that case should treat its absence as "not requested".

## [0.6.0] - 2026-07-25

The diagnosis now leaves the terminal. Same two questions, carried into the CI
and monitoring surfaces a team already runs.

### Added

- JUnit XML output through `--format junit`, `run_result_to_junit_xml`, and
  `write_junit_xml`. Blind probes and relation violations become failures,
  incomplete or undecided evidence becomes errors, and relations that tested
  nothing become skipped cases.
- A vendor-neutral OpenTelemetry handoff. `run_result_to_otel_attributes`
  returns low-cardinality aggregate fields, while `record_otel_run` emits one
  optional summary span through the host application's tracer provider.
- A directly runnable support-router example, an OTEL console example, a
  shorter product-first README, and integration guidance for AgentCore,
  CloudWatch, Phoenix, LangSmith, and quality-evaluation tools.
- A canonical `RunResult.status` shared by machine-readable reports,
  telemetry, and downstream integrations.
- CLI agent factories can be loaded directly from `file.py:func` as well as
  importable `module:func` paths.

### Fixed

- `agentverity run` could print `NO ANSWER YET` for an undecided meter and still
  exit successfully. It now returns exit code 2 for unsupported evidence.
- A relation catalogue that exercised no input could print `NOT TRUSTWORTHY`
  and still return exit code 0. It now returns exit code 1.

## [0.5.0] - 2026-07-25

A default run now answers the question instead of declining to.

### Changed

- **`k` is sized for you.** A zero-randomness agent used to report
  `undecided` on a default run, which reads as a broken tool rather than a
  result. Repeats are now derived from the precision you asked for, so the
  default run reaches a verdict. Set `k=` to take the wheel; it still wins.
- **`precision` replaces a bare epsilon as the main dial**: `"cheap"` (10%),
  `"balanced"` (5%, the default), `"strict"` (1%). Nobody knows what epsilon to
  pick, everybody knows how much they care. `epsilon=` still overrides it.
- **`budget` caps agent calls** when you need a ceiling. It defaults to `None`,
  meaning spend what the precision needs, because refusing to answer is worse
  than costing a predictable amount. Two repeats per input is a structural
  floor, and a budget below it is rejected rather than silently ignored.
- The default epsilon moved from 0.01 to 0.05 by way of `balanced`. The old
  default demanded 381 disjoint pairs, roughly 800 agent calls, to certify
  anything.
- **Reports lead with one plain sentence.** `RunResult.headline` says whether
  the suite can be trusted before any numbered section. A reader should not
  have to assemble a verdict from four tables.
- `agentverity run`, `snapshot`, and `check` accept `--precision` and
  `--budget`. `--k` and `--epsilon` are now overrides rather than defaults.

### Added

- `plan_repeats(inputs, epsilon, budget=None)` and `PRECISION_LEVELS`, both
  exported, so the sizing decision can be inspected or reused.

### Migration

`RunConfig(k=..., epsilon=...)` keeps working unchanged. Code reading
`config.k` or `config.epsilon` before a run now sees `None` where it used to
see a default; read them from `result.config` afterwards, where they are always
resolved to the values the run actually used.

Accuracy is a side effect worth noting. On the bundled example the old default
of `k=5` estimated a 66.7% flip rate from 12 pairs against a true rate of
45.5%. The new default measures 42.3% from 78 pairs, with an interval half as
wide.

### Added

- `agentverity.meter.pairs_for_deterministic_call(epsilon)` returns the minimum
  number of disjoint pairs that can certify determinism, so the cost of a
  snapshot can be budgeted before the run rather than discovered by refusal.

### Fixed

- Refusal advice assumed zero flips, so a run with 1,200 pairs and 6 flips was
  told to drop to 128. It now sizes against the observed rate, and says plainly
  that more pairs cannot help once that rate has met epsilon.
- `agentverity snapshot` refuses an unreachable configuration before running
  the agent instead of after. The bound is arithmetic, so paying a model to
  discover it was waste.
- `pairs_for_deterministic_call` rejects a non-positive or non-finite `z`.
  Passing `float("inf")` previously looped until integer overflow.

### Changed

- A snapshot refused for insufficient evidence now says how far short the run
  fell and which flag to change. "undecided" alone reads like a bug on an
  obviously deterministic agent, when the real answer is that 12 pairs cannot
  clear a 1% epsilon and 381 are needed. Stochastic verdicts get a distinct
  message, because a flipping decision is a different problem from a small
  sample.
- The README sizes the snapshot gate. At the default epsilon of 0.01 a
  deterministic agent still needs about 800 agent calls to be certified, which
  was previously something you found out by being refused.

## [0.4.0] - 2026-07-25

### Added

- **Evidence-gated snapshots.** `agentverity snapshot` refuses to freeze a
  reference unless the exact observation layer is deterministic at the
  configured epsilon, the probe set is non-blind, all requested evidence is
  complete, and a human explicitly approves the outputs.
- `agentverity check` re-runs the same admission diagnostics before comparing
  current observations with an approved snapshot. Unsupported evidence
  returns exit code 2 rather than a false regression result.
- Bounded concurrency across distinct inputs through `RunConfig.max_workers`
  and `--max-workers`. Repeated calls for one input stay sequential.
- Explicit `raise` and `record` error policies. Recorded failures produce
  structured `RunError` values and mark the run incomplete. They never become
  synthetic verdicts or passing checks.
- Versioned `agentverity.run/v1` JSON reports and
  `agentverity.snapshot/v1` baseline files.
- Non-plaintext progress events and input identifiers based on SHA-256
  fingerprints rather than raw probe text.
- `--no-relations`, `--format json`, `--output`, and `--progress` CLI options.
- A README diagnostic image generated from the executable multi-agent example.

### Changed

- Runner phases share one bounded execution primitive while preserving the
  sequential default and the existing unchanged-call reuse.
- Relation reports include failures separately from held, violated, and
  skipped cases.
- The bug-fix example exports the public versioned JSON report instead of a
  bespoke schema.
- `RunResult.suite_is_meaningful` documents why `relations=[]` returns `True`.
  A diagnostics-only run produced no green relation result to distrust.

## [0.3.0] - 2026-07-25

Post-release review of v0.2.0. Two correctness defects and a set of
documentation claims that did not match the code.

### Fixed

- **Duplicate inputs could report a varying agent as constant.** The
  first-call recorder keys observations by input text, so every copy of a
  repeated input resolved to one cached observation. An agent alternating
  between two verdicts across four identical probes was reported as 100% skew
  and `BLIND` instead of 50% and `ok`. Duplicates also distort the skew scan
  without any caching, because one verdict is counted once per copy. `run`
  now rejects a probe set containing the same input twice and names the
  duplicates. Repeating a measurement is what `k` is for.
- `README.md` documented the reuse saving on the four-input Quickstart as 35
  calls against 70. Measured values for that example are 28 and 40. The
  general formula was correct.
- The published v0.2.0 description on PyPI still said the package was not on
  PyPI and told readers to install from git, because the documentation fix
  landed after the release tag. PyPI metadata is immutable, so this release
  carries the corrected text.
- The test-count badge and the tests section claimed 85 while 86 passed.

### Changed

- **`RelationResult.violation_rate` returns `None` instead of `0.0` when the
  relation was never exercised.** The text report already printed `n/a`, but
  programmatic callers and exported JSON received a clean zero, which is the
  same false green the report refuses to print. Type is now `float | None`.
- The `langgraph` optional dependency was removed. It installed LangGraph for
  an adapter that does not exist yet.

## [0.2.0] - 2026-07-25

### Added

- Distribution build and clean-install validation in CI.
- PyPI Trusted Publishing workflow and a documented maintainer release
  procedure.
- `RelationResult.skipped`, `.exercised`, and `.is_vacuous`, plus
  `RunResult.vacuous_relations`, so a relation whose transform never changed
  an input is reported instead of counted as a pass.
- `RunConfig.reuse_unchanged_calls` (default on) and
  `agentverity.blindness.score`, which scores observations another phase has
  already collected.
- A reproducible supervisor-pattern example that contrasts a blind triage step
  with a stochastic full pipeline.
- A pull-request-only contribution workflow and CI across Python 3.10 to 3.14.

### Changed

- The verdict-stochasticity interval now uses disjoint repeat pairs. The
  earlier all-pairs calculation reused the same calls across comparisons and
  overstated the effective sample size.
- The runner now executes both diagnostics before any metamorphic relation.
- The built-in accent/whitespace transform is named
  `normalisation-invariance`, matching what it actually does.
- `suite_is_meaningful` now reports whether relation passes may be vacuous
  under the skew scan. Meter calls remain separate oracle guidance.
- Public novelty claims now distinguish repeated-trial and calibration tools
  from AgentVerity's narrower oracle-selection and verdict-skew diagnostics.
- `violation_rate` is now measured over exercised pairs rather than over all
  inputs, so inputs the transform left untouched no longer dilute it.
- A run reuses the meter's first draw per input for the blindness scan and for
  each relation's source side. Agent calls drop from `n * (k + 1 + 2r)` to
  `n * (k + r)`, removing one unchanged source call per relation.

### Fixed

- Empty probe sets and invalid meter/blindness thresholds now fail with clear
  `ValueError`s.
- The CLI no longer invokes an agent with a hidden probe input before the
  configured suite, avoiding side effects and wasted model calls.
- Passing `relations=[]` now runs no relations instead of restoring built-ins.
- `normalisation-invariance` and `tool-selection-invariance` normalise accents
  and whitespace, so on plain ASCII input the follow-up string was identical to
  the source. Both relations reported a perfect pass without the agent ever
  being asked a different question. Those inputs are now skipped, the rate
  reads `n/a`, and the report names the relation as not exercised.

## [0.1.0] - 2026-07-24

Initial public release.

### Added

- Verdict-stochasticity meter (`agentverity.meter`): a Wilson-CI-backed
  tri-state call (`verdict-stochastic` / `verdict-deterministic` /
  `undecided`) on whether an agent's decision is stable across identical
  reruns, refusing to label an underpowered probe "deterministic."
- Constant-gate-blindness detector (`agentverity.blindness`): flags when
  a passing test suite is trivially satisfied because the agent returns
  a near-constant verdict regardless of input.
- Typed metamorphic relations (`agentverity.relations`): invariant,
  monotone, and directional, with four built-in relations (paraphrase,
  case, whitespace, and tool-selection invariance).
- Runner (`agentverity.runner`) orchestrating meter, then relations,
  then blindness into a single diagnostics-first report.
- CLI (`agentverity run --agent module:func --inputs file.txt`).
- Callable adapter (zero dependencies) and an optional Strands adapter.
- 64 tests, all passing.

### Fixed (found during pre-release review, before this version shipped)

- `from_callable` was not exported from the top-level `agentverity`
  package, only from `agentverity.adapters`, so the README's own
  Quickstart (`from agentverity import run, from_callable`) raised
  `ImportError` for anyone who copy-pasted it. Now exported at the top
  level and covered by `tests/test_public_api.py` so the documented
  import surface can't silently drift again.
- The Quickstart's shown output didn't match what the shown code
  actually produces (stale pair counts, a tri-state call that wasn't
  reachable with that input size). Replaced with output captured from
  an actual run against the fixed code.
- Lint cleanup across the package: unused imports, a test asserting a
  bare `Exception` narrowed to the specific `FrozenInstanceError` it's
  actually checking for, missing trailing newlines.

[Unreleased]: https://github.com/mrwersa/agentverity/compare/v0.18.4...HEAD
[0.18.4]: https://github.com/mrwersa/agentverity/compare/v0.18.3...v0.18.4
[0.18.3]: https://github.com/mrwersa/agentverity/compare/v0.18.2...v0.18.3
[0.18.2]: https://github.com/mrwersa/agentverity/compare/v0.18.1...v0.18.2
[0.18.1]: https://github.com/mrwersa/agentverity/compare/v0.18.0...v0.18.1
[0.18.0]: https://github.com/mrwersa/agentverity/compare/v0.17.0...v0.18.0
[0.17.0]: https://github.com/mrwersa/agentverity/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/mrwersa/agentverity/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/mrwersa/agentverity/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/mrwersa/agentverity/compare/v0.13.2...v0.14.0
[0.13.2]: https://github.com/mrwersa/agentverity/compare/v0.13.1...v0.13.2
[0.13.1]: https://github.com/mrwersa/agentverity/compare/v0.13.0...v0.13.1
[0.13.0]: https://github.com/mrwersa/agentverity/compare/v0.12.2...v0.13.0
[0.12.2]: https://github.com/mrwersa/agentverity/compare/v0.12.1...v0.12.2
[0.12.1]: https://github.com/mrwersa/agentverity/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/mrwersa/agentverity/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/mrwersa/agentverity/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/mrwersa/agentverity/compare/v0.9.1...v0.10.0
[0.9.1]: https://github.com/mrwersa/agentverity/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/mrwersa/agentverity/compare/v0.8.6...v0.9.0
[0.8.6]: https://github.com/mrwersa/agentverity/compare/v0.8.5...v0.8.6
[0.8.5]: https://github.com/mrwersa/agentverity/compare/v0.8.4...v0.8.5
[0.8.4]: https://github.com/mrwersa/agentverity/compare/v0.8.3...v0.8.4
[0.8.3]: https://github.com/mrwersa/agentverity/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/mrwersa/agentverity/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/mrwersa/agentverity/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/mrwersa/agentverity/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mrwersa/agentverity/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mrwersa/agentverity/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/mrwersa/agentverity/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/mrwersa/agentverity/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mrwersa/agentverity/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mrwersa/agentverity/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mrwersa/agentverity/releases/tag/v0.1.0
