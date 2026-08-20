#!/usr/bin/env python3
"""Generate deterministic local manifests, SBOM, test record, and blocked decision."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon36.evidence import EvidenceLedger, write_ledger
from supermoon36.industrial import INDUSTRIAL_DOMAINS
from supermoon36.certification import READINESS_AREAS
from supermoon36.qualification import candidate_decision


def file_digest(path: Path) -> tuple[int, str, str]:
    digest = hashlib.sha256(); digest512 = hashlib.sha512(); total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            total += len(chunk); digest.update(chunk); digest512.update(chunk)
    return total, digest.hexdigest(), digest512.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--sm35", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True); evidence = root / "evidence"
    excluded = {"SM36_SOURCE_MANIFEST.json", "SM36_EVIDENCE_LEDGER.json"}
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and "__pycache__" not in item.parts and not item.name.endswith((".pyc", ".pyo")) and item.name not in excluded):
        size, sha, sha512 = file_digest(path); files.append({"path": path.relative_to(root).as_posix(), "size_bytes": size, "sha256": sha, "sha512": sha512})
    sm35_size, sm35_sha, sm35_sha512 = file_digest(args.sm35)
    prompt_size, prompt_sha, prompt_sha512 = file_digest(args.prompt)
    manifest = {
        "format": "SM36_SOURCE_MANIFEST_V1", "files": files,
        "sm35_exact_prefix": {"size_bytes": sm35_size, "sha256": sm35_sha, "sha512": sm35_sha512},
        "master_prompt": {"size_bytes": prompt_size, "sha256": prompt_sha, "sha512": prompt_sha512},
    }
    write_json(evidence / "SM36_SOURCE_MANIFEST.json", manifest)
    sbom = {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "serialNumber": "urn:uuid:00000000-0000-4036-8036-000000000036", "version": 1,
        "metadata": {"component": {"type": "application", "name": "Super Moon 36 New Universe", "version": "36.0.0"}},
        "components": [{"type": "library", "name": "Python Standard Library", "version": platform.python_version()}],
    }
    write_json(evidence / "SM36_CYCLONEDX_SBOM.json", sbom)
    decision = candidate_decision()
    write_json(evidence / "SM36_RELEASE_DECISION.json", {**asdict(decision), "state": decision.state.value, "release_state": "BLOCKED_PENDING_REAL_EXECUTION"})
    limitations = {
        "format": "SM36_LIMITATIONS_V1", "release_state": "BLOCKED_PENDING_REAL_EXECUTION",
        "not_demonstrated_here": [
            "PETSc/MPI 1/2/3/4/8-rank physical matrix", "multi-node external scheduler run",
            "OpenFOAM and SU2 execution", "OCCT STEP/IGES/assembly/tessellation round trips",
            "real CUDA device execution and sanitizer", "continuous 24-hour endurance",
            "continuous 72-hour endurance", "independent second-machine reproduction",
            "certification authority acceptance", "airworthiness or safe-to-fly status",
        ],
        "claim_rule": "Unavailable physical evidence is never converted into PASS by simulation, averaging, architecture, or code coverage.",
    }
    write_json(evidence / "SM36_LIMITATIONS.json", limitations)
    write_json(evidence / "SM36_INDUSTRIAL_CONTROL_MATRIX.json", {
        "format": "SM36_INDUSTRIAL_CONTROL_MATRIX_V1", "qualification_credit": False,
        "controls": [
            {"domain": domain, "procedure_id": f"SM36-PROC-{index:02d}", "owner": "UNASSIGNED", "independent_reviewer": "UNASSIGNED", "evidence_ids": [], "findings_open": 1, "mandatory_findings_open": 1, "effective": False, "state": "BLOCKED"}
            for index, domain in enumerate(INDUSTRIAL_DOMAINS, 1)
        ],
    })
    write_json(evidence / "SM36_CERTIFICATION_READINESS_MATRIX.json", {
        "format": "SM36_CERTIFICATION_READINESS_MATRIX_V1", "certification_claim_allowed": False,
        "objectives": [
            {"area": area, "objective_id": f"SM36-CERT-{index:02d}", "applicable": True, "evidence_ids": [], "independence_required": True, "independent_reviewer": None, "compliant": False, "open_actions": [f"OA-CERT-{index:02d}"], "authority_accepted": False, "state": "BLOCKED"}
            for index, area in enumerate(READINESS_AREAS, 1)
        ],
    })
    write_json(evidence / "SM36_SAFETY_ANALYSIS_INDEX.json", {
        "format": "SM36_SAFETY_ANALYSIS_INDEX_V1", "certification_credit": False,
        "analyses": [
            {"analysis": name, "state": "BLOCKED", "owner": "UNASSIGNED", "evidence_ids": [], "open_action": f"OA-{name}"}
            for name in ("FHA", "PSSA", "SSA", "FMEA", "FTA", "CCA", "STPA", "assurance_case", "cyber_airworthiness")
        ],
    })
    write_json(evidence / "SM36_PHYSICAL_EXECUTION_STATUS.json", {
        "format": "SM36_PHYSICAL_EXECUTION_STATUS_V1", "qualification_credit": False,
        "tracks": [
            {"track": track, "state": "NOT_EXECUTED", "blocker": blocker, "evidence_ids": []}
            for track, blocker in (
                ("PETSc/MPI rank matrix and multi-node Slurm", "G04"), ("OpenFOAM", "G05"),
                ("SU2", "G06"), ("OCCT STEP/IGES/CAD", "G07"), ("real CUDA", "G08"),
                ("24-hour endurance", "G09"), ("72-hour endurance", "G09"),
                ("independent second-machine reproduction", "G10"),
            )
        ],
    })
    write_json(evidence / "SM36_RELEASE_BOARD_MINUTES.json", {
        "format": "SM36_RELEASE_BOARD_MINUTES_V1", "meeting_state": "NOT_CONVENED",
        "decision": "BLOCKED_PENDING_REAL_EXECUTION", "independent_board_acceptance": False,
        "open_gates": list(decision.open_gates), "open_blockers": list(decision.open_blockers),
        "statement": "No generated local record substitutes for the designated independent qualification board.",
    })
    ledger = EvidenceLedger()
    fixed = "2026-08-20T00:00:00+00:00"
    parent = ledger.add("baseline", manifest["sm35_exact_prefix"], created_utc=fixed)
    prompt_node = ledger.add("master_prompt", manifest["master_prompt"], (parent.node_id,), created_utc=fixed)
    ledger.add("release_decision", {"state": "BLOCKED_PENDING_REAL_EXECUTION", "open_gates": list(decision.open_gates)}, (prompt_node.node_id,), created_utc=fixed)
    write_ledger(evidence / "SM36_EVIDENCE_LEDGER.json", ledger)
    write_json(evidence / "SM36_BUILD_ENVIRONMENT.json", {
        "format": "SM36_BUILD_ENVIRONMENT_V1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
