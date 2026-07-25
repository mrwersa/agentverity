# agentverity — design

A side project, NOT a research paper: an open-source framework for
**measure-first testing of non-deterministic LLM agents**. Created 2026-07-05.
Career artifact: "I build reusable tooling for testing agentic AI."

## Identity

**Name:** `agentverity` — "agent" + "verity" (truth). The tool tells you the
truth about whether your test suite is meaningful before you trust it.

**Wedge:** not "run metamorphic relations" but "diagnose whether your agent
test suite is lying to you" — suite-quality diagnostics for non-deterministic
agents. Compete on non-determinism honesty, NOT on breadth (lose to
DeepEval/promptfoo) or on the MR taxonomy (CheckList).

## Prior-art landscape (researched 2026-07-06)

| Tool | Stars | Non-determinism | Metamorphic | Suite-quality diagnostic | License |
|---|---|---|---|---|---|
| DeepEval | 16.7k | Repeated runs | No | No | Apache-2.0 |
| promptfoo | 22.9k | Repeated runs | No | Red-team coverage only | MIT |
| agentevals (langchain) | 636 | No | No | No | MIT |
| CheckList | 2k | Assumes deterministic | INV/DIR (owns it) | No | MIT |
| AgentAssay | paper | Yes (Wilson CIs) | Yes | Mutation testing | AGPL |
| agentrial | 17 | Yes (Wilson CIs) | No | No | MIT |
| **agentverity** | — | **Yes + measure-first** | **Yes (inherited)** | **Meter + blindness** | **Apache-2.0** |

**The three differentiators that survive the research:**

1. **Verdict-layer oracle selection.** Existing tools repeat tests, report
   uncertainty, and in AgentAssay's case calibrate trial budgets. AgentVerity
   asks whether the chosen categorical decision layer is stable enough that a
   frozen baseline dominates MRs. The novelty claim is this oracle-selection
   use, not awareness that agents are non-deterministic.

2. **Constant-gate-blindness detector.** A gate that returns `"allow"` on 96%
   of a probe set can satisfy many invariance checks without exercising a
   boundary. The detector flags the pass as potentially vacuous. This is a
   suite-power warning, not a correctness judgement.

3. **Suite-quality diagnostic framing.** Not "run tests and report pass/fail"
   but "tell you if your tests are meaningful before you trust them." The
   report leads with the diagnostics, then per-relation results.

**Borrowed, established (cite in README):**
- **Metamorphic relations** (Chen et al. 1998): assert a law between two runs
  (transform input, check the outputs relate correctly) — no golden output
  needed. The escape from the oracle problem for non-deterministic systems.
- **Semantic-invariance transforms** (CheckList / LLMORPH): normalisation,
  casing, whitespace.
- **Wilson CIs** (AgentAssay, agentrial use them for pass-rate CIs; we use
  them for verdict-stability certification — same primitive, different use).

**Apache-2.0** is an adoption edge over AgentAssay's AGPL.

---

## 1. What it is (one line)

`agentverity` runs two diagnostics before any test relation: does the agent's
verdict flip across identical reruns (meter), and does the agent return a
near-constant verdict across a diverse input set (blindness). The first guides
oracle selection. The second warns when green relation results may be vacuous.

## 2. Architecture (three layers)

```
your agent (Strands / LangGraph / any callable)
        |  adapter: normalise to Observation
        v
  agentverity.core
    |
    ├── meter.py        — verdict-stochasticity meter (headline #1)
    ├── blindness.py    — constant-gate-blindness detector (headline #2)
    ├── relations.py     — typed metamorphic relations (the vehicle)
    ├── runner.py        — orchestrates meter -> blindness -> relations
    └── cli.py           — `agentverity run` entry point
```

### 3a. Adapter layer (`agentverity/adapters/`)
Turns a real agent into a uniform `run(input) -> Observation`. `Observation`
carries what relations can assert over:
- `text`   — final response string
- `verdict`— an optional extracted categorical decision
- `tools`  — the ordered list of tool names the agent called (the trajectory)
- `raw`    — the underlying result object, for custom relations

Adapters:
- **Strands:** `Agent(prompt) -> AgentResult`. Adapter calls the agent, reads
  the final message text and the tool-use blocks for `tools`.
- **LangGraph:** compiled graph `.invoke(state)` (planned).
- **callable:** any `fn(input) -> str | dict | Observation` for non-library agents.
Adapters are OPTIONAL imports — the core installs without any agent library.

### 3b. Core (`agentverity/`)
- `relations.py` — Relation = (name, type, transform, check). Built-in
  catalogue: normalisation, casing, whitespace invariance (text-level);
  tool-selection-invariance (agent-specific, our emphasis).
- `meter.py` — verdict-stochasticity meter. Tri-state call with Wilson CI.
- `blindness.py` — constant-gate-blindness detector. Skew scan + warning.
- `runner.py` — orchestrates meter -> blindness -> relations. Returns RunResult.
- `cli.py` — `agentverity run --agent module:func --inputs file.txt`.

## 3. Scope discipline (what it is NOT)

- Not a benchmark, not a leaderboard, not an LLM-judge scorer.
- Not correctness testing — it tests *relations*, and explicitly warns it cannot
  tell a correct agent from an indifferent one (blindness detector).
- Not tied to any provider or the research programme's own gate.
- Zero dependency on the `mnem`/sibling-paper code. Fully standalone.

## 4. Status (2026-07-06)

- M1 core: DONE — observation, meter, blindness, relations, runner, CLI.
- M2 Strands adapter: DONE — adapter written, tested, worked example runs.
- M2 LangGraph adapter: PLANNED.
- M3 agent-specific relations: PLANNED (tool-selection-invariance is built-in;
  more user-extensible relations to follow).
- M4 packaging: pyproject.toml written, README written, LICENSE added.
  PyPI name `agentverity` verified free. Not yet published.
