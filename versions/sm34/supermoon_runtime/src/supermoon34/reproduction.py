"""Independent-machine receipt creation and conservative comparison."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import platform
from typing import Mapping

from .contracts import ExecutionStatus, InvalidInput, TolerancePolicy
from .evidence import canonical_json


@dataclass(frozen=True, slots=True)
class MachineReceipt:
    machine_fingerprint_sha256: str
    operator_fingerprint_sha256: str
    release_sha256: str
    deterministic_outputs: Mapping[str, str]
    numeric_outputs: Mapping[str, float]
    clean_workspace: bool
    independent_operator_attestation: bool
    distinct_physical_machine_attestation: bool


@dataclass(frozen=True, slots=True)
class ReproductionComparison:
    status: ExecutionStatus
    distinct_machine: bool
    distinct_operator: bool
    deterministic_matches: bool
    numeric_discrepancies: Mapping[str, float]
    accepted: bool


def local_machine_fingerprint() -> str:
    private_anchor = b""
    for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            private_anchor = path.read_bytes().strip()
            if private_anchor:
                break
        except OSError:
            continue
    payload = {
        "machine_anchor_sha256": hashlib.sha256(private_anchor).hexdigest(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def operator_fingerprint(operator_token: str) -> str:
    if len(operator_token.strip()) < 8:
        raise InvalidInput("operator token must be an opaque value of at least eight characters")
    return hashlib.sha256(operator_token.encode("utf-8")).hexdigest()


class ReproductionVerifier:
    def __init__(self, tolerances: TolerancePolicy | None = None):
        self.tolerances = tolerances or TolerancePolicy()

    def compare(self, first: MachineReceipt, second: MachineReceipt) -> ReproductionComparison:
        distinct_machine = first.machine_fingerprint_sha256 != second.machine_fingerprint_sha256
        distinct_operator = first.operator_fingerprint_sha256 != second.operator_fingerprint_sha256
        deterministic_matches = first.deterministic_outputs == second.deterministic_outputs and bool(first.deterministic_outputs)
        if set(first.numeric_outputs) != set(second.numeric_outputs):
            raise InvalidInput("numeric output keys must match")
        discrepancies = {
            key: abs(first.numeric_outputs[key] - second.numeric_outputs[key]) / max(abs(first.numeric_outputs[key]), abs(second.numeric_outputs[key]), self.tolerances.physical_floor)
            for key in first.numeric_outputs
        }
        accepted = (
            distinct_machine
            and distinct_operator
            and deterministic_matches
            and first.release_sha256 == second.release_sha256
            and first.clean_workspace
            and second.clean_workspace
            and first.independent_operator_attestation
            and second.independent_operator_attestation
            and first.distinct_physical_machine_attestation
            and second.distinct_physical_machine_attestation
            and all(value <= self.tolerances.relative for value in discrepancies.values())
        )
        return ReproductionComparison(ExecutionStatus.PASS if accepted else ExecutionStatus.FAIL, distinct_machine, distinct_operator, deterministic_matches, discrepancies, accepted)

