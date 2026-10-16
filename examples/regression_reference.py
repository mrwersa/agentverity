"""Save an approved reference and compare two fresh, offline collections.

Run from the repository root with ``python examples/regression_reference.py``.
All decisions are synthetic. There are no model or provider calls. The two
expected reference labels are declared explicitly and checked before approval.
The candidate deliberately swaps both routes to demonstrate a regression
that a repeatability check alone cannot detect.

These stateless functions have no adapter isolation declaration, so evidence
records ``unknown``. That is admitted with an independence caveat, not proof
of independence. A real stateful agent needs equivalent starting state for
every trial. The example qualifies the pooled evidence for two cases, not
every route separately or future behaviour.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from agentverity import (
    RunConfig,
    compare_snapshot,
    create_snapshot,
    from_callable,
    load_snapshot,
    run,
    save_snapshot,
)

INPUTS = ("duplicate charge", "cash withdrawal")


def reference_router(text: str) -> dict[str, str]:
    """The two decisions reviewed for the original reference."""
    return {"verdict": "billing" if "charge" in text else "cash_withdrawal"}


def changed_router(text: str) -> dict[str, str]:
    """Repeatable decisions that deliberately differ from the reference."""
    return {"verdict": "cash_withdrawal" if "charge" in text else "billing"}


def main() -> None:
    # Quality review is separate from statistical repeatability qualification.
    assert [reference_router(text)["verdict"] for text in INPUTS] == [
        "billing", "cash_withdrawal",
    ]
    result = run(from_callable(reference_router), inputs=INPUTS, relations=[])
    reference = create_snapshot(result, approved=True)

    with TemporaryDirectory(prefix="agentverity-reference-") as directory:
        path = Path(directory) / "reference.json"
        save_snapshot(reference, path)
        reference = load_snapshot(path)
        print(f"Reference: ADMITTED ({len(reference.probes)} reviewed decisions)")

        # Reuse the saved settings, as the CLI check command does. Each run
        # collects fresh decisions before compare_snapshot applies admission.
        config = RunConfig(
            k=reference.k,
            epsilon=reference.epsilon,
            layer=reference.layer,
            blindness_threshold=reference.blindness_threshold,
        )
        for name, router in (
            ("Unchanged router", reference_router),
            ("Changed router", changed_router),
        ):
            current = run(
                from_callable(router), inputs=INPUTS, relations=[], config=config,
            )
            difference = compare_snapshot(reference, current)
            outcome = "MATCH" if difference.clean else "CHANGED"
            print(
                f"{name}: {outcome} "
                f"({len(difference.changes)} changed decisions)"
            )


if __name__ == "__main__":
    main()
