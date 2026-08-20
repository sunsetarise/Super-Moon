"""Aerospace certification-readiness objective and assurance-case controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .contracts import ValidationError


READINESS_AREAS = (
    "certification_basis", "standards_applicability", "assurance_levels",
    "software_planning", "development_plan", "verification_plan",
    "configuration_plan", "quality_plan", "requirements_standard",
    "design_standard", "coding_standard", "high_level_requirements",
    "low_level_requirements", "architecture", "source_conformance",
    "object_traceability", "requirements_tests", "structural_coverage", "mcdc",
    "data_coupling", "control_coupling", "robustness", "parameter_data",
    "tool_assessment", "tool_evidence", "model_based", "object_oriented",
    "formal_methods", "previous_software", "cots", "partitioning",
    "compiler_object", "problem_reports", "derived_requirements", "system_safety",
    "fmea", "fault_tree", "common_cause", "stpa", "assurance_case",
    "independence", "lifecycle_index", "conformity", "review_rehearsal",
    "authority_liaison", "environmental_linkage", "cyber_airworthiness",
    "continued_assurance", "accomplishment_summary", "readiness_board",
)


@dataclass(frozen=True, slots=True)
class ObjectiveEvidence:
    area: str
    objective_id: str
    applicable: bool
    evidence_ids: tuple[str, ...]
    independence_required: bool
    independent_reviewer: str | None
    compliant: bool
    open_actions: tuple[str, ...]
    authority_accepted: bool = False

    def validate(self) -> None:
        if self.area not in READINESS_AREAS or not self.objective_id:
            raise ValidationError("unknown certification-readiness objective")
        if self.applicable and not self.evidence_ids:
            raise ValidationError("applicable objective lacks evidence")
        if self.independence_required and not self.independent_reviewer:
            raise ValidationError("objective lacks required independent review")
        if self.compliant and self.open_actions:
            raise ValidationError("compliant objective cannot retain open actions")
        if self.authority_accepted and not self.compliant:
            raise ValidationError("authority acceptance cannot bypass compliance")


@dataclass(frozen=True, slots=True)
class CertificationReadinessDecision:
    applicable_objectives: int
    compliant_objectives: int
    open_actions: int
    authority_accepted_objectives: int
    readiness_fraction: float
    certification_claim_allowed: bool
    readiness_passed: bool


def assess_readiness(rows: Sequence[ObjectiveEvidence], certification_basis_agreed: bool) -> CertificationReadinessDecision:
    values = tuple(rows)
    if len(values) != len(READINESS_AREAS) or {row.area for row in values} != set(READINESS_AREAS):
        raise ValidationError("certification-readiness matrix incomplete or duplicated")
    for row in values:
        row.validate()
    applicable = [row for row in values if row.applicable]
    if not applicable:
        raise ValidationError("at least one readiness objective must be applicable")
    compliant = sum(row.compliant for row in applicable)
    open_actions = sum(len(row.open_actions) for row in applicable)
    authority = sum(row.authority_accepted for row in applicable)
    fraction = compliant / len(applicable)
    readiness = certification_basis_agreed and fraction == 1.0 and open_actions == 0
    return CertificationReadinessDecision(len(applicable), compliant, open_actions, authority, fraction, False, readiness)


def validate_assurance_case(claims: Mapping[str, Mapping[str, Sequence[str]]], terminal_claim: str) -> bool:
    if terminal_claim not in claims:
        raise ValidationError("terminal assurance claim missing")
    visiting: set[str] = set(); visited: set[str] = set()
    def walk(identifier: str) -> None:
        if identifier in visiting:
            raise ValidationError("assurance-case cycle")
        if identifier in visited:
            return
        row = claims.get(identifier)
        if not isinstance(row, Mapping) or set(row) != {"subclaims", "evidence", "assumptions", "defeaters"}:
            raise ValidationError("malformed assurance claim")
        if not row["evidence"] and not row["subclaims"]:
            raise ValidationError("unsupported assurance claim")
        visiting.add(identifier)
        for child in row["subclaims"]:
            if child not in claims:
                raise ValidationError("missing assurance subclaim")
            walk(child)
        visiting.remove(identifier); visited.add(identifier)
    walk(terminal_claim)
    return True

