"""Complete operational work-item schema for all 15,000 prompt obligations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import gzip
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import MethodologyRecord, ResultState, ValidationError, timestamp
from .methodology import PHASE_BLOCKERS, PHYSICAL_PHASES


PHASE_PREREQUISITES = {
    "P01": ("immutable SM34/SM35 sources", "all inherited tests", "branch-aware coverage runner"),
    "P02": ("PETSc", "MPI runtime", "external multi-node scheduler", "physical host attestation"),
    "P03": ("OpenFOAM", "SU2", "OCCT CAD translator", "CUDA GPU and sanitizer"),
    "P04": ("exclusive endurance allocation", "monotonic telemetry", "independent second physical machine"),
    "P05": ("approved QMS scope", "control owners", "independent industrial reviewers"),
    "P06": ("agreed certification basis", "safety assessment", "designated assurance independence"),
}
PHASE_COMMANDS = {
    "P01": "python3 tools/run_sm36_coverage.py ... && python3 tools/score_local_quality.py ...",
    "P02": "python3 tools/run_physical_campaign.py petsc_mpi --authorize-real-execution ...",
    "P03": "python3 tools/run_physical_campaign.py {openfoam|su2|cad|cuda} --authorize-real-execution ...",
    "P04": "python3 tools/run_physical_campaign.py {endurance_24h|endurance_72h|second_machine} --authorize-real-execution ...",
    "P05": "python3 -m supermoon36 methodology REGISTRY METHOD_ID --evidence CONTROL_EVIDENCE --reviewer REVIEWER",
    "P06": "python3 -m supermoon36 methodology REGISTRY METHOD_ID --evidence ASSURANCE_EVIDENCE --reviewer REVIEWER",
}


@dataclass(frozen=True, slots=True)
class MethodologyWorkItem:
    methodology_id: str
    phase_id: str
    technique_kernel: str
    qualification_lens: str
    objective: str
    prerequisites: tuple[str, ...]
    commands_or_procedure: str
    configuration_id: str
    hardware_and_environment_id: str
    input_artifact_ids_and_hashes: Mapping[str, str]
    raw_evidence_ids_and_hashes: Mapping[str, str]
    quantitative_metrics: Mapping[str, Any]
    pre_registered_acceptance_criteria: str
    result_state: ResultState
    deviations: tuple[str, ...]
    problem_report_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    responsible_owner: str
    independent_reviewer: str
    review_signature: str
    completion_timestamp: str
    format: str = "SM36_METHODOLOGY_WORK_ITEM_V1"

    def validate(self) -> None:
        if self.format != "SM36_METHODOLOGY_WORK_ITEM_V1" or self.phase_id != self.methodology_id[:3]:
            raise ValidationError("invalid work-item identity")
        timestamp(self.completion_timestamp, "completion_timestamp")
        required_strings = (
            self.technique_kernel, self.qualification_lens, self.objective,
            self.commands_or_procedure, self.configuration_id, self.hardware_and_environment_id,
            self.pre_registered_acceptance_criteria, self.responsible_owner,
            self.independent_reviewer, self.review_signature,
        )
        if any(not isinstance(value, str) or not value for value in required_strings) or not self.prerequisites:
            raise ValidationError("work-item required field is empty")
        for mapping in (self.input_artifact_ids_and_hashes, self.raw_evidence_ids_and_hashes):
            if any(not isinstance(key, str) or not key or not isinstance(value, str) or not value for key, value in mapping.items()):
                raise ValidationError("work-item artifact/evidence mapping malformed")
        if self.result_state is ResultState.PASS:
            if not self.raw_evidence_ids_and_hashes or self.blocker_ids or self.responsible_owner == "UNASSIGNED" or self.independent_reviewer == "UNASSIGNED" or self.review_signature == "UNSIGNED":
                raise ValidationError("PASS work item lacks evidence, closure, ownership, or signed review")
        elif not self.blocker_ids:
            raise ValidationError("open work item must identify a blocker")
        if self.phase_id in PHYSICAL_PHASES and self.result_state is ResultState.PASS and self.hardware_and_environment_id == "UNASSIGNED":
            raise ValidationError("physical PASS lacks hardware identity")

    def payload(self) -> dict[str, Any]:
        self.validate(); row = asdict(self); row["result_state"] = self.result_state.value; return row


def pending_work_item(
    record: MethodologyRecord,
    *,
    prompt_sha256: str,
    registry_sha256: str,
    completion_timestamp: str,
) -> MethodologyWorkItem:
    record.validate(); timestamp(completion_timestamp, "completion_timestamp")
    item = MethodologyWorkItem(
        methodology_id=record.methodology_id, phase_id=record.phase_id,
        technique_kernel=record.technique_kernel, qualification_lens=record.qualification_lens,
        objective=record.objective, prerequisites=PHASE_PREREQUISITES[record.phase_id],
        commands_or_procedure=PHASE_COMMANDS[record.phase_id],
        configuration_id=f"sm36:{record.record_sha256[:24]}", hardware_and_environment_id="UNASSIGNED",
        input_artifact_ids_and_hashes={"master_prompt": prompt_sha256, "methodology_registry": registry_sha256},
        raw_evidence_ids_and_hashes={}, quantitative_metrics={},
        pre_registered_acceptance_criteria=record.pass_gate,
        result_state=ResultState.NOT_EXECUTED if record.phase_id in PHYSICAL_PHASES else ResultState.BLOCKED,
        deviations=(), problem_report_ids=(f"PR-{record.methodology_id}-OPEN",),
        blocker_ids=tuple(PHASE_BLOCKERS[record.phase_id].split(":")),
        responsible_owner="UNASSIGNED", independent_reviewer="UNASSIGNED",
        review_signature="UNSIGNED", completion_timestamp=completion_timestamp,
    )
    item.validate(); return item


def validate_work_items(items: Iterable[MethodologyWorkItem]) -> bool:
    rows = tuple(items)
    if len(rows) != 15000 or len({row.methodology_id for row in rows}) != 15000:
        raise ValidationError("work-item ledger requires 15,000 unique obligations")
    for row in rows:
        row.validate()
    for number in range(1, 7):
        phase = f"P{number:02d}"
        if sum(row.phase_id == phase for row in rows) != 2500:
            raise ValidationError("work-item phase cardinality mismatch")
    return True


def write_work_items(path: Path, items: Iterable[MethodologyWorkItem]) -> None:
    rows = tuple(items); validate_work_items(rows); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as stream:
            for row in rows:
                stream.write(json.dumps(row.payload(), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")


def read_work_items(path: Path) -> tuple[MethodologyWorkItem, ...]:
    rows = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                payload = json.loads(line); payload["result_state"] = ResultState(payload["result_state"])
                for key in ("prerequisites", "deviations", "problem_report_ids", "blocker_ids"):
                    payload[key] = tuple(payload[key])
                rows.append(MethodologyWorkItem(**payload))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
        raise ValidationError("malformed work-item ledger") from exc
    validate_work_items(rows); return tuple(rows)
