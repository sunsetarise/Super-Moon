"""Industrial quality, security, supply-chain, support, and audit controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .contracts import ValidationError


INDUSTRIAL_DOMAINS = (
    "quality_management", "requirements", "configuration", "change_control",
    "release_reproducibility", "supplier_quality", "sbom", "vulnerability_management",
    "secure_development", "threat_model", "data_governance", "model_governance",
    "evidence_governance", "risk_management", "fracas", "root_cause",
    "corrective_action", "reliability", "maintainability", "serviceability",
    "support", "operational_readiness", "disaster_recovery", "business_continuity",
    "capacity", "benchmarks", "scalability", "interoperability", "compatibility",
    "installation", "deployment", "identity_access", "cryptography", "penetration_test",
    "red_team", "safety_security", "human_factors", "training", "documentation",
    "licensing", "export_control", "independent_validation", "customer_acceptance",
    "pilot", "production_readiness", "lifecycle_cost", "obsolescence",
    "audit_rehearsal", "product_acceptance", "qualification_board",
)


@dataclass(frozen=True, slots=True)
class ControlEvidence:
    domain: str
    procedure_id: str
    owner: str
    independent_reviewer: str
    evidence_ids: tuple[str, ...]
    findings_open: int
    mandatory_findings_open: int
    effective: bool

    def validate(self) -> None:
        if self.domain not in INDUSTRIAL_DOMAINS:
            raise ValidationError("unknown industrial domain")
        if not self.procedure_id or not self.owner or not self.independent_reviewer or self.owner == self.independent_reviewer:
            raise ValidationError("industrial control lacks procedure or independence")
        if not self.evidence_ids or self.findings_open < 0 or self.mandatory_findings_open < 0:
            raise ValidationError("invalid industrial evidence/findings")


@dataclass(frozen=True, slots=True)
class IndustrialDecision:
    domains_complete: int
    controls_effective: int
    open_findings: int
    mandatory_open_findings: int
    passed: bool


def assess_industrial_controls(rows: Sequence[ControlEvidence]) -> IndustrialDecision:
    values = tuple(rows)
    if len(values) != len(INDUSTRIAL_DOMAINS) or {row.domain for row in values} != set(INDUSTRIAL_DOMAINS):
        raise ValidationError("industrial control matrix must contain each domain exactly once")
    for row in values:
        row.validate()
    effective = sum(row.effective for row in values)
    findings = sum(row.findings_open for row in values)
    mandatory = sum(row.mandatory_findings_open for row in values)
    return IndustrialDecision(len(values), effective, findings, mandatory, effective == len(values) and mandatory == 0)


def validate_traceability(requirements: Mapping[str, Mapping[str, Iterable[str]]]) -> float:
    if not requirements:
        raise ValidationError("industrial traceability matrix is empty")
    complete = 0
    required_links = {"source", "test", "evidence", "risk", "release"}
    for requirement_id, links in requirements.items():
        if not requirement_id or not isinstance(links, Mapping) or set(links) != required_links:
            raise ValidationError("industrial traceability row malformed")
        if all(tuple(links[key]) for key in required_links):
            complete += 1
    return complete / len(requirements)
