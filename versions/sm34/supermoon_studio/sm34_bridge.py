from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
import sys
from typing import Any

from .config import settings


SRC = settings.supermoon_runtime_dir / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

RUNTIME_AVAILABLE = False
IMPORT_ERROR: str | None = None

try:
    import supermoon34
    from supermoon34.backends import probe_all
    from supermoon34.capabilities import GATE_BLOCKERS, GATE_WEIGHTS, TRACKS, validate_registry
    from supermoon34.qualification import decision_payload, unexecuted_release
    from supermoon34.validation import ValidationSuite

    validate_registry()
    RUNTIME_AVAILABLE = True
except Exception as exc:  # pragma: no cover - diagnostics path
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


TRACK_TERMS: dict[str, tuple[str, ...]] = {
    "P01": ("petsc", "mpi", "distributed", "sparse", "ksp", "preconditioner", "multi-node"),
    "P02": ("openfoam", "foam", "finite volume"),
    "P03": ("su2", "cfd cross-validation", "adjoint cfd"),
    "P04": ("cad", "cadquery", "occt", "open cascade", "brep", "step", "iges", "geometry kernel"),
    "P05": ("slurm", "external hpc", "cluster", "scheduler", "multi-node", "sacct", "sbatch"),
    "P06": ("gpu", "cuda", "cupy", "pytorch", "torch", "rocm", "accelerator"),
    "P07": ("endurance", "72h", "72-hour", "24h", "24-hour", "checkpoint", "recovery", "heartbeat"),
    "P08": ("second machine", "independent reproduction", "independent operator", "cross-machine"),
    "P09": ("verification", "validation", "uncertainty", "uq", "manufactured solution", "coverage"),
    "P10": ("performance", "benchmark", "scaling", "roofline", "median", "mad", "regression"),
    "P11": ("evidence", "release", "governance", "security", "sbom", "provenance", "qualification"),
    "A01": ("mbse", "system architecture", "requirements", "interface", "budget", "reliability", "airworthiness"),
    "A02": ("aircraft", "aerodynamics", "propulsion", "drag polar", "mission fuel", "isa atmosphere", "airworthiness"),
    "A03": ("structure", "structural", "materials", "aeroelastic", "fatigue", "buckling", "stress"),
    "A04": ("flight dynamics", "avionics", "control", "lqr", "6-dof", "trim", "rigid body"),
    "A05": ("digital thread", "traceability", "aerospace software", "software engineering", "artifact link"),
}

TRACK_GATES: dict[str, tuple[str, ...]] = {
    "P01": ("W01",), "P02": ("W02",), "P03": ("W02",), "P04": ("W03",),
    "P05": ("W04",), "P06": ("W05",), "P07": ("W06",), "P08": ("W07",),
    "P09": ("W08",), "P10": ("W08",), "P11": ("W08",),
    "A01": ("W08",), "A02": ("W02", "W08"), "A03": ("W03", "W08"),
    "A04": ("W08",), "A05": ("W08",),
}


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_plain(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def runtime_status() -> dict[str, Any]:
    return {
        "available": RUNTIME_AVAILABLE,
        "release": "SUPER MOON 34 NEW UNIVERSE",
        "version": getattr(supermoon34, "__version__", None) if RUNTIME_AVAILABLE else None,
        "source": str(SRC),
        "tracks": len(TRACKS) if RUNTIME_AVAILABLE else 0,
        "gates": len(GATE_WEIGHTS) if RUNTIME_AVAILABLE else 0,
        "error": IMPORT_ERROR,
    }


def capabilities() -> list[dict[str, Any]]:
    if not RUNTIME_AVAILABLE:
        return []
    return [_plain(track) for track in TRACKS]


def backends() -> list[dict[str, Any]]:
    if not RUNTIME_AVAILABLE:
        return []
    return [_plain(probe) for probe in probe_all()]


def qualification() -> dict[str, Any]:
    if not RUNTIME_AVAILABLE:
        return {
            "score": 0.0,
            "status": "UNAVAILABLE",
            "passed": False,
            "open_blockers": sorted(x for x in GATE_BLOCKERS.values() if x) if "GATE_BLOCKERS" in globals() else [],
            "gates": [],
            "evidence_graph_valid": False,
            "rationale": IMPORT_ERROR or "Super Moon 34 runtime is unavailable.",
        }
    return _plain(decision_payload(unexecuted_release()))


def validation() -> dict[str, Any]:
    if not RUNTIME_AVAILABLE:
        return {"status": "UNAVAILABLE", "error": IMPORT_ERROR}
    return _plain(ValidationSuite().run())


def overview(*, include_validation: bool = False) -> dict[str, Any]:
    payload = {
        "runtime": runtime_status(),
        "capabilities": capabilities(),
        "backends": backends(),
        "qualification": qualification(),
        "truth_boundary": (
            "Implemented adapters and local tests do not substitute for physical PETSc/MPI, independent CFD, "
            "CAD-kernel, external cluster, GPU, 24/72-hour endurance, or second-machine evidence."
        ),
    }
    if include_validation:
        payload["validation"] = validation()
    return payload


def align_prompt(text: str) -> dict[str, Any]:
    low = (text or "").lower()
    probes = {row["backend"]: row for row in backends()}
    selected: list[dict[str, Any]] = []
    for track in capabilities():
        track_id = track["track_id"]
        matched = [term for term in TRACK_TERMS[track_id] if term in low]
        if not matched:
            continue
        backend = track["backend"]
        selected.append({
            **track,
            "matched_terms": matched,
            "backend_available": bool(probes.get(backend, {}).get("available")),
            "gates": list(TRACK_GATES.get(track_id, ())),
        })

    if not selected:
        fallback_ids = {"P09", "P11", "A05"}
        selected = [
            {
                **track,
                "matched_terms": ["default research-governance route"],
                "backend_available": bool(probes.get(track["backend"], {}).get("available")),
                "gates": list(TRACK_GATES.get(track["track_id"], ())),
            }
            for track in capabilities()
            if track["track_id"] in fallback_ids
        ]

    gate_ids = sorted({gate_id for track in selected for gate_id in track["gates"]})
    gate_rows = [row for row in qualification().get("gates", []) if row.get("gate_id") in gate_ids]
    unavailable = sorted({track["backend"] for track in selected if not track["backend_available"]})
    return {
        "release": "SUPER MOON 34 NEW UNIVERSE",
        "runtime_available": RUNTIME_AVAILABLE,
        "selected_tracks": selected,
        "required_gates": gate_rows,
        "unavailable_backends": unavailable,
        "execution_state": "PLAN_READY_REAL_EXECUTION_PENDING" if unavailable else "LOCAL_ROUTE_READY",
        "truth_boundary": (
            "Capability selection is an execution plan, not proof that external solvers, hardware, endurance, "
            "certification, or independent reproduction have run."
        ),
    }
