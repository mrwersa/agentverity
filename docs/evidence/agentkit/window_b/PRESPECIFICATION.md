# Window B — prespecified re-collection study

This directory holds the second collection window for the tool-selection
study, and the criterion that was declared before any of it ran.

## What is being tested

Whether the requests admitted in the first collection window stay stable
across a later one. A provider can silently change routing behaviour between
windows; a frozen baseline recorded before such a change stops identifying
real regressions afterwards. This study measures that risk directly on the
same ten reviewed requests.

## Prespecified drift criterion

Declared 2026-08-23, before Window B collection started.

- **Primary outcome**: the number of the ten requests whose call class
  (admit / reject / undecided) differs between Window A
  (`../evidence-<model>.json`) and Window B. Computed per model with
  `agentverity compare-evidence` at $\epsilon = 0.05$.
- **Secondary outcomes**: per-request flip-rate change; modal-action changes;
  any request newly out of contract (a `no_tool_selected` observation).
- **Interpretation, fixed in advance**: zero class changes means the frozen
  baselines held across the gap. Any class change counts as drift and is
  reported as such regardless of direction; no post hoc reclassification into
  "small" or "large" drift.

## Running it

Requires `OPENROUTER_API_KEY` in the environment. From this directory:

```bash
python3 ./collect.py --factory gpt4o_mini \
  --model "openai/gpt-4o-mini" --out window_b/window-b-gpt4o_mini.json
python3 ./collect.py --factory mistral_small \
  --model "mistralai/mistral-small-3.2-24b-instruct" --out window_b/window-b-mistral_small.json
python3 ./collect.py --factory nova \
  --model "amazon/nova-micro-v1" --out window_b/window-b-nova.json
```

Then compare each window pair. The Window A evidence files sit in this same
directory (`evidence-<model>.json`), so:

```bash
for m in gpt4o_mini mistral_small nova; do
  agentverity compare-evidence "evidence-$m.json" \
    "window_b/window-b-$m.json" \
    --epsilon 0.05 --json "window_b/drift-$m.json"
done
```

## Storage

Window B evidence files and the three drift JSON files are committed here
after collection, alongside a dated outcome note in
[the engagement-free findings record](FINDINGS.md) when one exists.
