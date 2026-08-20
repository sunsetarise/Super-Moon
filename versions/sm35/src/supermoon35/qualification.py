"""Fixed 100-point SM35 scoring with all twenty mandatory blockers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .contracts import ExecutionStatus, ValidationError


WEIGHTS: dict[str, int] = {
    "Q01": 15, "Q02": 15, "Q03": 12, "Q04": 8, "Q05": 10,
    "Q06": 10, "Q07": 10, "Q08": 8, "Q09": 6, "Q10": 6,
}
BLOCKERS = tuple(f"B{index:02d}" for index in range(1, 21))


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    score: float
    status: ExecutionStatus
    passed: bool
    open_blockers: tuple[str, ...]
    completion: Mapping[str, float]
    rationale: str


def score_release(completion: Mapping[str, float], blocker_state: Mapping[str, bool], evidence_dag_valid: bool) -> ReleaseDecision:
    if set(completion) != set(WEIGHTS):
        raise ValidationError("completion must contain exactly Q01-Q10")
    if set(blocker_state) != set(BLOCKERS):
        raise ValidationError("blocker state must contain exactly B01-B20")
    normalized: dict[str, float] = {}
    for gate_id, value in completion.items():
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValidationError(f"invalid completion for {gate_id}")
        normalized[gate_id] = float(value)
    if any(not isinstance(value, bool) for value in blocker_state.values()):
        raise ValidationError("blocker states must be booleans")
    score = sum(WEIGHTS[key] * normalized[key] for key in WEIGHTS)
    open_blockers = tuple(sorted(key for key, is_open in blocker_state.items() if is_open))
    passed = score >= 95.0 and not open_blockers and evidence_dag_valid
    if passed:
        status = ExecutionStatus.PASS
        rationale = "Score is at least 95, every blocker is closed, and the evidence DAG verifies."
    elif not evidence_dag_valid:
        status = ExecutionStatus.FAIL
        rationale = "Evidence DAG verification failed."
    else:
        status = ExecutionStatus.BLOCKED
        rationale = "Mandatory qualification evidence remains open."
    return ReleaseDecision(round(score, 6), status, passed, open_blockers, normalized, rationale)


def candidate_decision(local_coverage_fraction: float = 0.0, aerospace_fraction: float = 1.0, security_fraction: float = 1.0) -> ReleaseDecision:
    completion = {key: 0.0 for key in WEIGHTS}
    completion.update({"Q01": local_coverage_fraction, "Q09": aerospace_fraction, "Q10": security_fraction})
    blockers = {key: True for key in BLOCKERS}
    blockers["B17"] = False
    blockers["B18"] = False
    blockers["B19"] = False
    blockers["B20"] = False
    return score_release(completion, blockers, True)
