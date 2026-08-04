# Writing your own relation

The built-in catalogue knows about text normalisation, letter case, and tool
selection. It does not know your domain. In a payments product `GBP 40` and
`£40` are one amount written two ways, and a router that treats them
differently is a defect the catalogue cannot see.

A relation is a transform and a check.

```python
from agentverity import Relation

currency = Relation(
    name="currency-symbol-invariance",
    rtype="invariant",
    transform=lambda text: text.replace("GBP ", "£"),
    check=lambda source, followup: source.verdict == followup.verdict,
    description="`GBP 40` and `£40` are one amount, so one route.",
)
```

- **`transform`** maps an input to a follow-up input.
- **`check`** receives both observations and returns `True` when the relation
  held.
- **`rtype`** is `invariant`, `monotone`, or `directional`. The set is closed
  because the report and the coverage table render by type, and a fourth value
  would be counted under a name no reader can interpret.

## Running it

```python
from agentverity import run
result = run(agent, inputs, relations=[currency])
```

From the command line, point at a function that returns your relations:

```bash
agentverity run --agent app:router --inputs probes.txt \
  --relations examples/custom_relation.py:catalogue
```

The function takes no arguments, which is the shape `builtin_relations` has.
Return a list, or a single `Relation` when you have one. **It replaces the
built-in catalogue rather than adding to it**, so include the built-ins
yourself when you want both:

```python
from agentverity import builtin_relations

def catalogue():
    return [*builtin_relations(), currency]
```

Only `run` executes relations, so only `run` offers the flag. `snapshot` and
`check` deliberately run none.

## What the library does with it

**A user relation is scored exactly like a built-in.** It appears in the
relation table with the same held, violated, skipped and error counts, and it
counts towards per-route relation coverage. There is no second class.

**An input the transform leaves unchanged is skipped, not passed.** This is the
part worth understanding before you write one. A transform that returns its
input asks the agent the same question twice, and counting that as a pass
manufactures evidence. Two of the four built-ins were once no-ops on plain
ASCII and reported perfect scores while asking nothing, which is why the
distinction exists.

So a relation that applies to a third of your probe set reports as partial:

```
currency-symbol-invariance   invariant       4        0       2      0    0.0%

PARTIAL: currency-symbol-invariance ran on 4/6 inputs (2 left unchanged by
the transform).
```

That is the honest reading. Widen the probe set, or accept that the relation
speaks for the part of it that it reached.

**A route no relation perturbed is reported as unprobed**, and its relation
results are called vacuous rather than green.

## What is refused

A relation with no name, an unknown type, or a transform or check that is not
callable is refused when you construct it, before any agent call is made. A
catalogue that returns nothing, returns `None`, or returns something that is
not a `Relation` is refused when the flag is loaded, for the same reason: a
broken catalogue discovered mid-run has already spent the source calls.

A catalogue function that *raises* is not flattened into a refusal. The
traceback surfaces, exactly as it does for an `--agent` factory that raises,
because a bug in your own module is something you need the stack for.

Relation results are never collected from imported evidence, because a relation
needs calls the imported file did not make.
