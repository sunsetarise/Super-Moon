"""Twelve mandatory SM36 gates with fixed scoring and no average bypass."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .contracts import ResultState, ValidationError


GATE_WEIGHTS: dict[str, float] = {
    "G01": 6.0,
    "G02": 6.0,
    "G03": 12.0,
    "G04": 12.0,
    "G05": 10.0,
    "G06": 8.0,
    "G07": 10.0,
    "G08": 10.0,
    "G09": 8.0,
    "G10": 8.0,
    "G11": 6.0,
    "G12": 4.0,
}


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: str
    completion: float
    state: ResultState
    evidence_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    independent_reviewer: str | None

    def validate(self) -> None:
        if self.gate_id not in GATE_WEIGHTS or not isinstance(self.completion, (int, float)) or not math.isfinite(self.completion) or not 0 <= self.completion <= 1:
            raise ValidationError("invalid gate identity/completion")
        if self.state is ResultState.PASS:
            if self.completion != 1.0 or not self.evidence_ids or self.blocker_ids or not self.independent_reviewer:
                raise ValidationError("PASS gate lacks closure evidence or review")
        if self.state is not ResultState.PASS and not self.blocker_ids:
            raise ValidationError("open gate must identify blocker")


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    score: float
    state: ResultState
    passed: bool
    release_name: str
    open_gates: tuple[str, ...]
    open_blockers: tuple[str, ...]
    gate_completion: Mapping[str, float]
    rationale: str


def score_release(gates: Mapping[str, GateResult], evidence_ledger_valid: bool) -> ReleaseDecision:
    if set(gates) != set(GATE_WEIGHTS):
        raise ValidationError("release decision requires exactly G01-G12")
    for identifier, row in gates.items():
        row.validate()
        if identifier != row.gate_id:
            raise ValidationError("gate mapping identity mismatch")
    score = sum(GATE_WEIGHTS[key] * gates[key].completion for key in GATE_WEIGHTS)
    open_gates = tuple(key for key in GATE_WEIGHTS if gates[key].state is not ResultState.PASS)
    blockers = tuple(sorted({blocker for row in gates.values() for blocker in row.blocker_ids}))
    passed = score >= 95.0 and not open_gates and not blockers and evidence_ledger_valid
    if passed:
        state = ResultState.QUALIFIED
        name = "SUPER MOON 36 NEW UNIVERSE QUALIFIED"
        rationale = "All twelve mandatory gates passed with independently reviewed evidence."
    elif not evidence_ledger_valid:
        state = ResultState.FAIL
        name = "SUPER MOON 36 NEW UNIVERSE QUALIFICATION CANDIDATE"
        rationale = "Evidence ledger verification failed."
    else:
        state = ResultState.BLOCKED
        name = "SUPER MOON 36 NEW UNIVERSE QUALIFICATION CANDIDATE"
        rationale = "One or more mandatory gates remain open; averages cannot bypass them."
    return ReleaseDecision(round(score, 6), state, passed, name, open_gates, blockers, {key: gates[key].completion for key in GATE_WEIGHTS}, rationale)


def candidate_gates(local_implemented: bool = True) -> dict[str, GateResult]:
    rows = {}
    for gate_id in GATE_WEIGHTS:
        completion = 1.0 if local_implemented and gate_id in {"G01", "G02", "G12"} else 0.0
        if completion == 1.0:
            rows[gate_id] = GateResult(gate_id, 1.0, ResultState.PASS, (f"evidence:{gate_id}",), (), "local-independent-review")
        else:
            rows[gate_id] = GateResult(gate_id, 0.0, ResultState.BLOCKED, (), (f"blocker:{gate_id}",), None)
    return rows


def candidate_decision() -> ReleaseDecision:
    return score_release(candidate_gates(), True)

