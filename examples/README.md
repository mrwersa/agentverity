# Runnable examples

Every file here runs offline with no provider key unless its own docstring says
otherwise. Start with the first one.

| Example | What it shows |
|---|---|
| [`payment_dispute_gate.py`](payment_dispute_gate.py) | The evidence gate. Two probe sets both score 6/6 on an exact-match evaluator; one is refused a baseline because every probe takes the same route, the other is admitted. |
| [`custom_relation.py`](custom_relation.py) | A domain relation the built-in catalogue cannot express, and how to run it with `--relations`. See [docs/custom-relations.md](../docs/custom-relations.md). |
| [`evaluator_stability.py`](evaluator_stability.py) | The same tri-state rule applied to a categorical LLM judge, without confusing repeatability with agreement. |
| [`support_router.py`](support_router.py) | A small router with a declared decision suite, for reading the per-route table. |
| [`bugfix_pipeline.py`](bugfix_pipeline.py) | Where the checks sit in a change-and-release loop. |
| [`deepeval_shared_run.py`](deepeval_shared_run.py) | Reusing precomputed DeepEval test cases instead of paying for the calls twice. |
| [`promptfoo_bridge/`](promptfoo_bridge) | A recorded Promptfoo run, assessed without calling the model again. |
| [`otel_monitoring.py`](otel_monitoring.py) | The privacy-minimised OpenTelemetry summary span. |
| [`strands_example.py`](strands_example.py) | The Strands adapter, using a factory so trials start from equivalent state. |
| [`production_stack/`](production_stack) | The recorded AgentCore canary: real deployment evidence, and why six pairs per route certify nothing. |

Supporting files rather than examples in their own right:
`toy_agent.py` is the agent the CLI examples point at, `support_tickets.txt`
and `payment_decisions.json` are its probes and declared suite,
`route_stability_plan.json` carries declared per-route targets, and
`imported_evidence.json` is a minimal `agentverity.evidence/v2` file for trying
`assess` without collecting anything.
