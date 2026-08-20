"""Append-only requirements, interfaces, configurations, and evidence links."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable, Mapping

from ..contracts import EvidenceError, InvalidInput
from ..evidence import canonical_json, sha256_bytes


class RequirementState(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class Requirement:
    requirement_id: str
    statement: str
    rationale: str
    verification_method: str
    parent_ids: tuple[str, ...] = ()
    allocation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    state: RequirementState = RequirementState.PROPOSED
    version: int = 1

    def __post_init__(self) -> None:
        if not self.requirement_id or not self.statement or not self.rationale or not self.verification_method:
            raise InvalidInput("requirement fields must be nonempty")
        if self.version <= 0:
            raise InvalidInput("requirement version must be positive")
        if self.state is RequirementState.VERIFIED and not self.evidence_ids:
            raise EvidenceError("verified requirement needs evidence")


@dataclass(frozen=True, slots=True)
class Interface:
    interface_id: str
    producer: str
    consumer: str
    payload_schema: str
    units: str
    rate_hz: float
    latency_ms: float

    def __post_init__(self) -> None:
        if not all((self.interface_id, self.producer, self.consumer, self.payload_schema, self.units)):
            raise InvalidInput("interface fields are incomplete")
        if self.rate_hz <= 0 or self.latency_ms < 0:
            raise InvalidInput("invalid interface timing")


@dataclass(slots=True)
class DigitalThread:
    requirements: dict[str, Requirement] = field(default_factory=dict)
    history: list[Requirement] = field(default_factory=list)
    interfaces: dict[str, Interface] = field(default_factory=dict)
    artifact_links: dict[str, str] = field(default_factory=dict)

    def add_requirement(self, requirement: Requirement) -> None:
        if requirement.requirement_id in self.requirements:
            raise InvalidInput(f"duplicate requirement {requirement.requirement_id}")
        missing = tuple(parent for parent in requirement.parent_ids if parent not in self.requirements)
        if missing:
            raise InvalidInput(f"unknown parent requirements: {missing}")
        self.requirements[requirement.requirement_id] = requirement
        self.history.append(requirement)

    def revise(self, requirement_id: str, **changes) -> Requirement:
        current = self.requirements[requirement_id]
        forbidden = {"requirement_id", "version"} & changes.keys()
        if forbidden:
            raise InvalidInput(f"immutable fields cannot be revised: {forbidden}")
        revised = replace(current, version=current.version + 1, **changes)
        self.requirements[requirement_id] = revised
        self.history.append(revised)
        return revised

    def add_interface(self, interface: Interface) -> None:
        if interface.interface_id in self.interfaces:
            raise InvalidInput(f"duplicate interface {interface.interface_id}")
        self.interfaces[interface.interface_id] = interface

    def traceability(self) -> Mapping[str, object]:
        orphaned = tuple(sorted(req.requirement_id for req in self.requirements.values() if not req.parent_ids and req.requirement_id != "ROOT"))
        unallocated = tuple(sorted(req.requirement_id for req in self.requirements.values() if not req.allocation_ids))
        unverified = tuple(sorted(req.requirement_id for req in self.requirements.values() if req.state is not RequirementState.VERIFIED))
        verified = sum(req.state is RequirementState.VERIFIED for req in self.requirements.values())
        return {
            "requirements": len(self.requirements),
            "versions": len(self.history),
            "interfaces": len(self.interfaces),
            "orphaned": orphaned,
            "unallocated": unallocated,
            "unverified": unverified,
            "verified_fraction": verified / max(len(self.requirements), 1),
            "thread_sha256": sha256_bytes(canonical_json({"requirements": self.history, "interfaces": self.interfaces, "artifacts": self.artifact_links})),
        }

