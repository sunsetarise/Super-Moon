"""Weighted 9.5 gate engine with non-bypassable blockers."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Mapping

from .capabilities import GATE_BLOCKERS, GATE_WEIGHTS, validate_registry
from .contracts import EvidenceError, ExecutionStatus, GateDecision, InvalidInput, ReleaseDecision


def gate(
    gate_id: str,
    status: ExecutionStatus,
    *,
    fraction: float,
    evidence_ids: Iterable[str] = (),
    message: str = "",
) -> GateDecision:
    validate_registry()
    if gate_id not in GATE_WEIGHTS:
        raise InvalidInput(f"unknown gate {gate_id}")
    return GateDecision(
        gate_id,
        GATE_WEIGHTS[gate_id],
        fraction,
        status,
        GATE_BLOCKERS[gate_id],
        tuple(sorted(set(evidence_ids))),
        message,
    )


def conservative_gate(
    gate_id: str,
    evidence_checks: Mapping[str, bool],
    evidence_ids: Iterable[str],
    *,
    unavailable: bool = False,
    executed: bool = True,
    message: str = "",
) -> GateDecision:
    """Evaluate a gate without allowing partial checks to produce PASS."""

    ids = tuple(sorted(set(evidence_ids)))
    if unavailable:
        return gate(gate_id, ExecutionStatus.UNAVAILABLE, fraction=0.0, message=message)
    if not executed:
        return gate(gate_id, ExecutionStatus.NOT_EXECUTED, fraction=0.0, message=message)
    if not evidence_checks:
        raise EvidenceError("an executed gate requires prespecified checks")
    fraction = sum(bool(value) for value in evidence_checks.values()) / len(evidence_checks)
    status = ExecutionStatus.PASS if fraction == 1.0 and ids else ExecutionStatus.FAIL
    return gate(gate_id, status, fraction=fraction, evidence_ids=ids, message=message)


def evaluate_release(decisions: Iterable[GateDecision], *, evidence_graph_valid: bool) -> ReleaseDecision:
    rows = tuple(decisions)
    if {item.gate_id for item in rows} != set(GATE_WEIGHTS) or len(rows) != len(GATE_WEIGHTS):
        raise InvalidInput("release requires exactly one decision for each W01-W08 gate")
    score = sum(item.points for item in rows)
    open_blockers = tuple(
        sorted(
            item.blocker_id
            for item in rows
            if item.blocker_id is not None and item.status is not ExecutionStatus.PASS
        )
    )
    passed = score >= 95.0 and not open_blockers and evidence_graph_valid and all(item.status is ExecutionStatus.PASS for item in rows)
    if passed:
        status = ExecutionStatus.PASS
        rationale = "Score>=95, all mandatory blockers closed, all gates passed, and evidence DAG verified."
    elif not evidence_graph_valid or any(item.status is ExecutionStatus.FAIL for item in rows):
        status = ExecutionStatus.FAIL
        rationale = "One or more executed checks failed or the evidence DAG is invalid."
    else:
        status = ExecutionStatus.BLOCKED
        rationale = "Mandatory real-execution evidence remains unavailable or not executed."
    return ReleaseDecision(score, status, passed, open_blockers, rows, evidence_graph_valid, rationale)


def unexecuted_release() -> ReleaseDecision:
    labels = {
        "W01": "PETSc/MPI ranks 2/3/4/8 and multi-node runs have not executed.",
        "W02": "Independent OpenFOAM and SU2 reference cases have not executed.",
        "W03": "OCCT/CadQuery round-trip qualification has not executed.",
        "W04": "No external scheduler-managed HPC receipt is present.",
        "W05": "No real GPU device execution receipt is present.",
        "W06": "No continuous 24h and 72h endurance receipts are present.",
        "W07": "No distinct second-machine independent reproduction receipt is present.",
        "W08": "Release governance can be tested locally but cannot pass while mandatory evidence is incomplete.",
    }
    rows = [gate(gate_id, ExecutionStatus.NOT_EXECUTED, fraction=0.0, message=labels[gate_id]) for gate_id in sorted(GATE_WEIGHTS)]
    return evaluate_release(rows, evidence_graph_valid=True)


def decision_payload(decision: ReleaseDecision) -> dict[str, object]:
    return asdict(decision)


class QualificationEngine:
    """Object-oriented facade used by the capability and orchestration layers."""

    def gate(self, gate_id: str, status: ExecutionStatus, *, fraction: float, evidence_ids: Iterable[str] = (), message: str = "") -> GateDecision:
        return gate(gate_id, status, fraction=fraction, evidence_ids=evidence_ids, message=message)

    def evaluate(self, decisions: Iterable[GateDecision], *, evidence_graph_valid: bool) -> ReleaseDecision:
        return evaluate_release(decisions, evidence_graph_valid=evidence_graph_valid)

    def unexecuted(self) -> ReleaseDecision:
        return unexecuted_release()
