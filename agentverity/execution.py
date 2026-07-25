"""Shared execution primitives for bounded, observable agent runs.

AgentVerity parallelises across distinct inputs only. Calls for one input stay
sequential so repeated-run evidence keeps its order and stateful agents are not
concurrently re-entered for the same probe.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar, cast

T = TypeVar("T")
ErrorPolicy = Literal["raise", "record"]


def input_fingerprint(text: str) -> str:
    """Return a stable SHA-256 content fingerprint for an input string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProgressEvent:
    """One completed unit of work.

    The event carries an input index and fingerprint rather than the input text
    so progress logging does not include probe contents by default.
    """

    phase: str
    completed: int
    total: int
    input_index: int
    input_fingerprint: str
    status: Literal["ok", "error"]


@dataclass(frozen=True)
class RunError:
    """A call or check failure retained as incomplete run evidence."""

    phase: str
    input_index: int
    input_fingerprint: str
    exception_type: str
    message: str
    relation: str | None = None


@dataclass(frozen=True)
class WorkResult(Generic[T]):
    """Ordered results and failures from one execution phase."""

    values: tuple[T | None, ...]
    errors: tuple[RunError, ...]


ProgressCallback = Callable[[ProgressEvent], None]


def map_inputs(
    inputs: Sequence[str],
    worker: Callable[[int, str], T],
    *,
    phase: str,
    max_workers: int,
    error_policy: ErrorPolicy,
    on_progress: ProgressCallback | None = None,
    status_of: Callable[[T], Literal["ok", "error"]] | None = None,
) -> WorkResult[T]:
    """Run one worker per distinct input, preserving result order.

    ``worker`` owns every call made for one input. With ``max_workers > 1``,
    separate inputs may run concurrently, but the worker itself remains
    sequential.
    """
    return map_indexed_inputs(
        list(enumerate(inputs)),
        worker,
        phase=phase,
        max_workers=max_workers,
        error_policy=error_policy,
        on_progress=on_progress,
        status_of=status_of,
    )


def map_indexed_inputs(
    inputs: Sequence[tuple[int, str]],
    worker: Callable[[int, str], T],
    *,
    phase: str,
    max_workers: int,
    error_policy: ErrorPolicy,
    on_progress: ProgressCallback | None = None,
    status_of: Callable[[T], Literal["ok", "error"]] | None = None,
) -> WorkResult[T]:
    """Run workers for an indexed subset while preserving subset order."""
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    if error_policy not in ("raise", "record"):
        raise ValueError("error_policy must be 'raise' or 'record'")

    values: list[T | None] = [None] * len(inputs)
    errors: list[RunError] = []
    completed = 0

    def finish(
        position: int,
        input_index: int,
        text: str,
        value: T | None,
        error: Exception | None,
    ) -> None:
        nonlocal completed
        status: Literal["ok", "error"] = "ok"
        if error is None:
            values[position] = value
            if status_of is not None:
                status = status_of(cast(T, value))
        else:
            status = "error"
            errors.append(
                RunError(
                    phase=phase,
                    input_index=input_index,
                    input_fingerprint=input_fingerprint(text),
                    exception_type=type(error).__name__,
                    message=str(error),
                )
            )
        completed += 1
        if on_progress is not None:
            on_progress(
                ProgressEvent(
                    phase=phase,
                    completed=completed,
                    total=len(inputs),
                    input_index=input_index,
                    input_fingerprint=input_fingerprint(text),
                    status=status,
                )
            )

    if max_workers == 1:
        for position, (input_index, text) in enumerate(inputs):
            try:
                finish(
                    position,
                    input_index,
                    text,
                    worker(input_index, text),
                    None,
                )
            except Exception as exc:
                if error_policy == "raise":
                    raise
                finish(position, input_index, text, None, exc)
        return WorkResult(tuple(values), tuple(errors))

    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="agentverity",
    ) as pool:
        futures = {
            pool.submit(worker, input_index, text): (position, input_index, text)
            for position, (input_index, text) in enumerate(inputs)
        }
        for future in as_completed(futures):
            position, input_index, text = futures[future]
            try:
                finish(position, input_index, text, future.result(), None)
            except Exception as exc:
                if error_policy == "raise":
                    for pending in futures:
                        pending.cancel()
                    raise
                finish(position, input_index, text, None, exc)

    errors.sort(key=lambda error: error.input_index)
    return WorkResult(tuple(values), tuple(errors))
