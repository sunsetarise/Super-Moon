"""Executable composition engine for every SM36 methodology record."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any, Callable, Mapping

from .contracts import ClaimLevel, MethodologyRecord, MethodologyResult, ResultState, ValidationError


PHYSICAL_PHASES = frozenset({"P02", "P03", "P04"})
PHASE_BLOCKERS = {
    "P01": "G03",
    "P02": "G04",
    "P03": "G05:G06:G07",
    "P04": "G08:G09",
    "P05": "G10",
    "P06": "G11",
}


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    evidence: Mapping[str, Any]
    physical_execution: bool = False
    independent_review: bool = False
    reviewer: str | None = None
    authorized: bool = False


TechniqueHandler = Callable[[MethodologyRecord, ExecutionContext], tuple[dict[str, bool], dict[str, Any], tuple[str, ...]]]
LensHandler = Callable[[MethodologyRecord, ExecutionContext], tuple[dict[str, bool], tuple[str, ...]]]


def _technique_handler(record: MethodologyRecord, context: ExecutionContext) -> tuple[dict[str, bool], dict[str, Any], tuple[str, ...]]:
    evidence = context.evidence
    binding = record.technique_binding
    technique_results = evidence.get("techniques", {})
    row = technique_results.get(binding) if isinstance(technique_results, Mapping) else None
    if not isinstance(row, Mapping):
        return {"technique_executed": False}, {"binding": binding}, (f"missing technique evidence for {binding}",)
    executed = row.get("executed") is True
    accepted = row.get("accepted") is True
    finite_metrics = isinstance(row.get("metrics", {}), Mapping)
    checks = {"technique_executed": executed, "technique_accepted": accepted, "technique_metrics_present": finite_metrics}
    metrics = {"binding": binding, **dict(row.get("metrics", {}))} if finite_metrics else {"binding": binding}
    return checks, metrics, () if all(checks.values()) else (f"technique did not satisfy {binding}",)


def _lens_handler(record: MethodologyRecord, context: ExecutionContext) -> tuple[dict[str, bool], tuple[str, ...]]:
    evidence = context.evidence
    lens_results = evidence.get("lenses", {})
    row = lens_results.get(record.lens_binding) if isinstance(lens_results, Mapping) else None
    if not isinstance(row, Mapping):
        return {"lens_executed": False}, (f"missing lens evidence for {record.lens_binding}",)
    checks = {
        "lens_executed": row.get("executed") is True,
        "raw_evidence_retained": row.get("raw_evidence_retained") is True,
        "pre_registered_gate_used": row.get("pre_registered_gate_used") is True,
        "provenance_complete": row.get("provenance_complete") is True,
    }
    return checks, () if all(checks.values()) else (f"lens did not satisfy {record.lens_binding}",)


class MethodologyExecutor:
    """Executes any of 15,000 records through bound technique and lens handlers."""

    def __init__(self, technique_handler: TechniqueHandler = _technique_handler, lens_handler: LensHandler = _lens_handler):
        self.technique_handler = technique_handler
        self.lens_handler = lens_handler

    def execute(self, record: MethodologyRecord, context: ExecutionContext) -> MethodologyResult:
        record.validate()
        started = datetime.now(timezone.utc).isoformat(); monotonic = time.monotonic()
        technique_checks, metrics, technique_limits = self.technique_handler(record, context)
        lens_checks, lens_limits = self.lens_handler(record, context)
        checks = {**technique_checks, **lens_checks}
        limitations = technique_limits + lens_limits
        evidence_ids_value = context.evidence.get("evidence_ids", ())
        if not isinstance(evidence_ids_value, (tuple, list)):
            raise ValidationError("evidence_ids must be a sequence")
        evidence_ids = tuple(evidence_ids_value)
        if record.phase_id in PHYSICAL_PHASES:
            checks["physical_execution"] = context.physical_execution
            checks["explicit_authorization"] = context.authorized
            if not context.physical_execution:
                limitations += ("mandatory physical execution not demonstrated",)
        checks["independent_review"] = context.independent_review
        passed = bool(checks) and all(checks.values()) and bool(evidence_ids)
        if passed:
            state = ResultState.PASS
            claim = ClaimLevel.VERIFIED if record.phase_id not in PHYSICAL_PHASES else ClaimLevel.QUALIFIED
            reviewer_state = ResultState.PASS
            blockers: tuple[str, ...] = ()
        elif record.phase_id in PHYSICAL_PHASES and not context.physical_execution:
            state = ResultState.NOT_EXECUTED
            claim = ClaimLevel.IMPLEMENTED
            reviewer_state = ResultState.BLOCKED
            blockers = tuple(PHASE_BLOCKERS[record.phase_id].split(":"))
        else:
            state = ResultState.BLOCKED
            claim = ClaimLevel.TESTED if checks.get("technique_executed") else ClaimLevel.IMPLEMENTED
            reviewer_state = ResultState.BLOCKED
            blockers = tuple(PHASE_BLOCKERS[record.phase_id].split(":"))
        result = MethodologyResult(
            methodology_id=record.methodology_id,
            state=state,
            claim_level=claim,
            started_utc=started,
            ended_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_monotonic_seconds=time.monotonic() - monotonic,
            checks=checks,
            metrics=metrics,
            evidence_ids=evidence_ids if passed else (),
            limitations=limitations,
            blocker_ids=blockers,
            reviewer=context.reviewer if passed else None,
            reviewer_state=reviewer_state,
        )
        result.validate()
        return result

    def evaluate_phase(self, records: tuple[MethodologyRecord, ...], context: ExecutionContext) -> tuple[MethodologyResult, ...]:
        if len(records) != 2500 or len({record.phase_id for record in records}) != 1:
            raise ValidationError("phase execution requires exactly 2500 same-phase records")
        return tuple(self.execute(record, context) for record in records)


def phase_completion(results: tuple[MethodologyResult, ...]) -> float:
    if len(results) != 2500 or len({item.methodology_id[:3] for item in results}) != 1:
        raise ValidationError("phase completion requires complete phase result set")
    return sum(item.state is ResultState.PASS for item in results) / 2500.0
