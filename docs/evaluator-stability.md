# Qualify an evaluator before trusting its score

Agent evaluation commonly combines code checks, human review, and an LLM
judge. A model judge is useful when several answers can be acceptable, but it
introduces another model-backed decision:

```text
agent trace -> evaluator -> pass | fail | uncertain
```

Repeating the agent does not tell you whether the evaluator itself moves.
Repeat the judge on the same frozen trace and rubric, then keep each categorical
verdict. AgentVerity can qualify that evidence using the same three outcomes it
uses for an agent route:

- stable enough at the declared tolerance
- unstable above that tolerance
- undecided because too little evidence was collected

## Run the provider-free example

```bash
python examples/evaluator_stability.py
```

The example contains recorded verdicts for three traces. One human-labelled
class contains a trace that alternates between `pass` and `uncertain`, so the
class is reported as unstable.

```text
Evaluator verdict stability
NOT READY - decision changes exceed declared stability targets for: pass.
unstable human-labelled classes: pass
Validity still requires comparison with human-labelled examples.
```

## Stability is not validity

This check asks whether the judge gives a repeatable categorical verdict. It
does not establish that the verdict agrees with an expert.

Use both:

1. Compare the judge with human-labelled examples to calibrate validity.
2. Repeat the judge on frozen traces to qualify stability.
3. Keep `uncertain` as a real outcome instead of forcing an unsupported pass or
   fail.
4. Re-run both checks when the judge model, rubric, prompt, or parsing changes.

Record those versions in evidence provenance. A change then travels with
`compare-evidence`, even when the observed verdicts happen to stay fixed.

## Import real verdicts

Store one case per frozen trace in
[`agentverity.evidence/v1`](imported-evidence.md):

The example above is `agentverity.evidence/v1`, which is what evidence made of plain decision labels should be. A judge that sometimes returns no label at all can record why rather than inventing one, using the typed outcomes in [imported evidence](imported-evidence.md). That matters here more than most places: a judge answering with prose is not a stable verdict, and folding those runs into one category would score the judge as more consistent than it is.

```json
{
  "schema": "agentverity.evidence/v1",
  "layer": "verdict",
  "isolation": "fresh-instance",
  "provenance": {
    "target_kind": "evaluator-verdict",
    "judge": "policy-judge-v3",
    "rubric": "refund-policy/v7"
  },
  "cases": [
    {
      "input": "trace: incident-142",
      "expected": "fail",
      "observations": ["fail", "fail", "uncertain", "fail"]
    }
  ]
}
```

The `input` may be a non-sensitive trace identifier. Do not place customer
content in the evidence file. AgentVerity needs the ordered verdicts, not the
underlying transcript.

## Where this fits

This is evaluator qualification, not another quality metric:

```text
human-labelled traces -> validity calibration
frozen traces repeated -> stability qualification
both acceptable        -> evaluator may grade the agent suite
```

Current agent-evaluation guidance recommends deterministic graders where the
contract permits them and human calibration for model-based graders. Use this
recipe only where a semantic criterion genuinely needs a model judge.

Primary references:

- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [LangSmith evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)
