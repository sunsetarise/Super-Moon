"""Solver-neutral CFD, CAD, endurance, reproduction, and aerospace V&V gates."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from .contracts import ValidationError


@dataclass(frozen=True, slots=True)
class NeutralCFDCase:
    case_id: str
    units: str
    axes: tuple[str, str, str]
    reference_area_m2: float
    reference_length_m: float
    moment_center_m: tuple[float, float, float]
    density_kg_m3: float
    velocity_m_s: float
    angle_of_attack_deg: float
    boundaries: Mapping[str, str]
    quantities: tuple[str, ...]
    tolerance_fraction: float

    def validate(self) -> None:
        if not self.case_id or self.units != "SI" or self.axes != ("X_FORWARD", "Y_RIGHT", "Z_DOWN"):
            raise ValidationError("neutral CFD identity/units/axes invalid")
        positive = (self.reference_area_m2, self.reference_length_m, self.density_kg_m3, self.velocity_m_s, self.tolerance_fraction)
        if any(not math.isfinite(value) or value <= 0 for value in positive):
            raise ValidationError("neutral CFD positive inputs invalid")
        if not math.isfinite(self.angle_of_attack_deg) or abs(self.angle_of_attack_deg) > 90:
            raise ValidationError("angle of attack outside supported range")
        if len(self.moment_center_m) != 3 or any(not math.isfinite(value) for value in self.moment_center_m):
            raise ValidationError("invalid moment center")
        if not self.boundaries or not self.quantities:
            raise ValidationError("boundaries and quantities are mandatory")


@dataclass(frozen=True, slots=True)
class SolverComparison:
    normalized_discrepancies: Mapping[str, float]
    accepted: bool
    open_quantities: tuple[str, ...]


def compare_cfd(case: NeutralCFDCase, first: Mapping[str, float], second: Mapping[str, float]) -> SolverComparison:
    case.validate()
    missing = tuple(sorted(set(case.quantities) - set(first) | (set(case.quantities) - set(second))))
    if missing:
        raise ValidationError(f"missing CFD quantities: {missing}")
    discrepancies: dict[str, float] = {}
    for quantity in case.quantities:
        a, b = first[quantity], second[quantity]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in (a, b)):
            raise ValidationError("CFD values must be finite")
        discrepancies[quantity] = abs(a - b) / max(abs(a), abs(b), 1e-15)
    open_quantities = tuple(sorted(key for key, value in discrepancies.items() if value > case.tolerance_fraction))
    return SolverComparison(discrepancies, not open_quantities, open_quantities)


@dataclass(frozen=True, slots=True)
class CadRoundTrip:
    route: str
    brep_valid: bool
    volume_drift: float
    area_drift: float
    centroid_drift_m: float
    topology_preserved: bool
    translator_status: str
    evidence_ids: tuple[str, ...]

    def passes(self, *, relative_limit: float = 1e-8, centroid_limit_m: float = 1e-7) -> bool:
        supported = {"CADQUERY_OCCT_STEP_OCCT", "OCCT_IGES_OCCT", "ASSEMBLY_STEP_ASSEMBLY", "SOURCE_TESSELLATION_COMPARE"}
        if self.route not in supported:
            raise ValidationError("unknown CAD route")
        values = (self.volume_drift, self.area_drift, self.centroid_drift_m)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValidationError("CAD drift must be finite and nonnegative")
        return (
            self.brep_valid and self.topology_preserved and self.translator_status == "DONE"
            and self.volume_drift <= relative_limit and self.area_drift <= relative_limit
            and self.centroid_drift_m <= centroid_limit_m and bool(self.evidence_ids)
        )


def validate_cad_matrix(rows: Sequence[CadRoundTrip]) -> bool:
    required = {"CADQUERY_OCCT_STEP_OCCT", "OCCT_IGES_OCCT", "ASSEMBLY_STEP_ASSEMBLY", "SOURCE_TESSELLATION_COMPARE"}
    if {row.route for row in rows} != required or len(rows) != len(required):
        raise ValidationError("CAD matrix is incomplete or duplicated")
    return all(row.passes() for row in rows)


def validate_endurance(elapsed_seconds: float, profile_hours: int, heartbeat_gaps_seconds: Sequence[float], hash_chain_valid: bool, recovery_drills: int) -> bool:
    if profile_hours not in {24, 72}:
        raise ValidationError("profile must be 24 or 72 hours")
    if not math.isfinite(elapsed_seconds) or elapsed_seconds < 0 or any(not math.isfinite(item) or item < 0 for item in heartbeat_gaps_seconds):
        raise ValidationError("invalid endurance duration or heartbeat gap")
    required_drills = 1 if profile_hours == 24 else 2
    return elapsed_seconds >= profile_hours * 3600 and max(heartbeat_gaps_seconds, default=0.0) <= 120.0 and hash_chain_valid and recovery_drills >= required_drills


def validate_reproduction(first_machine: str, second_machine: str, first_operator: str, second_operator: str, clean_workspace: bool, output_comparison_passed: bool, evidence_ids: Sequence[str]) -> bool:
    values = (first_machine, second_machine, first_operator, second_operator)
    if any(not isinstance(item, str) or not item for item in values):
        raise ValidationError("machine/operator fingerprints must be nonempty")
    return first_machine != second_machine and first_operator != second_operator and clean_workspace and output_comparison_passed and bool(evidence_ids)


@dataclass(frozen=True, slots=True)
class TraceLink:
    requirement_id: str
    source_symbols: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    allocated_to: tuple[str, ...]

    def complete(self) -> bool:
        if not self.requirement_id:
            raise ValidationError("requirement ID must be nonempty")
        return all((self.source_symbols, self.test_ids, self.evidence_ids, self.allocated_to))


def traceability_closure(links: Sequence[TraceLink]) -> float:
    if not links:
        raise ValidationError("traceability requires at least one requirement")
    identifiers = [item.requirement_id for item in links]
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError("duplicate requirement ID")
    return sum(item.complete() for item in links) / len(links)
