"""Protocol and stopping logic for the BFCL repeated evaluation.

The study uses one preregistered corpus and model set. Most cells stop when
qualification becomes impossible at the fixed endpoint. A predeclared subset
runs to the full budget so alternative mappings can be compared without
informative truncation.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path

from agentverity import best_case_admission_pairs

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reduce import REDUCTIONS, count_flips

SCHEMA = "agentverity.bfcl-evaluation-protocol/v1"
DEFAULT_PROTOCOL = ROOT / "single-evaluation-protocol.json"


@dataclass(frozen=True)
class StudyProtocol:
    case_ids: tuple[str, ...]
    full_budget_validation_case_ids: frozenset[str]
    models: tuple[tuple[str, str], ...]
    primary_mapping: str
    comparison_mappings: tuple[str, ...]
    endpoint_pairs: int
    epsilon: float
    alpha: float
    z: float
    periods: tuple[tuple[str, date], ...]
    maximum_terminal_errors_per_cell: int
    source: dict
    digest: str

    @property
    def endpoint_calls(self) -> int:
        return 2 * self.endpoint_pairs

    def model_endpoint(self, key: str) -> str:
        try:
            return dict(self.models)[key]
        except KeyError:
            known = ", ".join(model_key for model_key, _ in self.models)
            raise ValueError(f"unknown model key {key!r}; expected one of {known}") from None

    def period_not_before(self, period_id: str) -> date:
        try:
            return dict(self.periods)[period_id]
        except KeyError:
            known = ", ".join(identifier for identifier, _ in self.periods)
            raise ValueError(
                f"unknown evaluation period {period_id!r}; expected one of {known}"
            ) from None


def _canonical_json(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def load_protocol(path: Path = DEFAULT_PROTOCOL) -> StudyProtocol:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != SCHEMA:
        raise ValueError(f"unsupported protocol schema: {document.get('schema')!r}")

    case_ids = tuple(document["case_ids"])
    validation_ids = frozenset(document["full_budget_validation_case_ids"])
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case_ids must be unique")
    if not validation_ids or not validation_ids < set(case_ids):
        raise ValueError("validation cases must be a non-empty proper subset of case_ids")

    ranked = sorted(
        case_ids,
        key=lambda value: (hashlib.sha256(value.encode()).hexdigest(), value),
    )[: len(validation_ids)]
    if validation_ids != frozenset(ranked):
        raise ValueError("validation subset does not match its declared SHA-256 selection")

    models = tuple((item["key"], item["endpoint"]) for item in document["models"])
    if len(models) != len({key for key, _ in models}):
        raise ValueError("model keys must be unique")
    if document["primary_mapping"] not in REDUCTIONS:
        raise ValueError("primary_mapping is not implemented")
    if any(name not in REDUCTIONS for name in document["comparison_mappings"]):
        raise ValueError("a comparison mapping is not implemented")

    endpoint_pairs = document["endpoint_pairs"]
    if endpoint_pairs < 1:
        raise ValueError("endpoint_pairs must be positive")
    if not 0 < document["epsilon"] < 1:
        raise ValueError("epsilon must be between zero and one")
    if not 0 < document["alpha"] < 1:
        raise ValueError("alpha must be between zero and one")
    if document["z"] <= 0:
        raise ValueError("z must be positive")

    periods = tuple(
        (item["id"], date.fromisoformat(item["not_before"]))
        for item in document["periods"]
    )
    if len(periods) < 2 or any(later[1] <= earlier[1] for earlier, later in pairwise(periods)):
        raise ValueError("evaluation periods must contain increasing dates")

    return StudyProtocol(
        case_ids=case_ids,
        full_budget_validation_case_ids=validation_ids,
        models=models,
        primary_mapping=document["primary_mapping"],
        comparison_mappings=tuple(document["comparison_mappings"]),
        endpoint_pairs=endpoint_pairs,
        epsilon=document["epsilon"],
        alpha=document["alpha"],
        z=document["z"],
        periods=periods,
        maximum_terminal_errors_per_cell=document["maximum_terminal_errors_per_cell"],
        source=document,
        digest=hashlib.sha256(_canonical_json(document)).hexdigest(),
    )


def mapped_observations(observations: list[str], mapping: str) -> list[str]:
    try:
        reduction = REDUCTIONS[mapping]
    except KeyError:
        raise ValueError(f"unknown mapping {mapping!r}") from None
    return [reduction(observation) for observation in observations]


def qualification_is_impossible(
    observations: list[str], protocol: StudyProtocol, case_id: str
) -> bool:
    """Return whether a non-validation cell can stop at a completed pair."""
    if case_id in protocol.full_budget_validation_case_ids:
        return False
    if len(observations) % 2:
        raise ValueError("stopping is evaluated only after a complete pair")
    pairs = len(observations) // 2
    if pairs < 1 or pairs >= protocol.endpoint_pairs:
        return False
    mapped = mapped_observations(observations, protocol.primary_mapping)
    flips = count_flips(mapped)
    return best_case_admission_pairs(
        protocol.epsilon,
        flips=flips,
        pairs=pairs,
        max_pairs=protocol.endpoint_pairs,
        z=protocol.z,
    ) is None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()