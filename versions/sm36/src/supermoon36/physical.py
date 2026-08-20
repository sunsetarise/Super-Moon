"""CFD, CAD, CUDA capability probes and quantitative validation functions."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import math
import shutil
from statistics import mean
from typing import Mapping, Sequence

from .contracts import ValidationError


COMMANDS = {
    "petsc_mpi": ("mpiexec",),
    "slurm": ("sbatch", "sacct"),
    "openfoam": ("foamRun", "checkMesh"),
    "su2": ("SU2_CFD", "SU2_CFD_AD"),
    "cuda": ("nvidia-smi", "nvcc"),
}
MODULES = {"petsc_mpi": ("petsc4py", "mpi4py"), "cad": ("cadquery", "OCP"), "cuda": ("cupy",)}


@dataclass(frozen=True, slots=True)
class Capability:
    track_id: str
    available: bool
    commands: Mapping[str, str | None]
    modules: Mapping[str, bool]
    reason: str


def detect_capability(track_id: str) -> Capability:
    if track_id not in set(COMMANDS) | set(MODULES):
        raise ValidationError("unknown physical track")
    commands = {name: shutil.which(name) for name in COMMANDS.get(track_id, ())}
    modules = {name: importlib.util.find_spec(name) is not None for name in MODULES.get(track_id, ())}
    checks = [bool(value) for value in commands.values()] + list(modules.values())
    available = bool(checks) and all(checks)
    return Capability(track_id, available, commands, modules, "all components detected" if available else "one or more components unavailable")


def capability_matrix() -> tuple[Capability, ...]:
    return tuple(detect_capability(track) for track in sorted(set(COMMANDS) | set(MODULES)))


@dataclass(frozen=True, slots=True)
class GridPoint:
    characteristic_size: float
    value: float


@dataclass(frozen=True, slots=True)
class GCIResult:
    observed_order: float
    extrapolated_value: float
    fine_gci_percent: float
    asymptotic_ratio: float
    passed: bool


def grid_convergence(points: Sequence[GridPoint], safety_factor: float = 1.25) -> GCIResult:
    if len(points) != 3 or not math.isfinite(safety_factor) or safety_factor <= 1:
        raise ValidationError("GCI requires three points and safety factor >1")
    fine, medium, coarse = sorted(points, key=lambda item: item.characteristic_size)
    if any(not math.isfinite(item.characteristic_size) or item.characteristic_size <= 0 or not math.isfinite(item.value) for item in points):
        raise ValidationError("invalid GCI point")
    r21 = medium.characteristic_size / fine.characteristic_size
    r32 = coarse.characteristic_size / medium.characteristic_size
    if min(r21, r32) <= 1 or abs(r21 - r32) / max(r21, r32) > 0.1:
        raise ValidationError("GCI requires near-uniform refinement ratio")
    d21 = medium.value - fine.value; d32 = coarse.value - medium.value
    if d21 == 0 or d32 == 0 or d21 * d32 <= 0:
        raise ValidationError("GCI values must show monotonic nonzero convergence")
    ratio = 0.5 * (r21 + r32)
    order = math.log(abs(d32 / d21)) / math.log(ratio)
    if not math.isfinite(order) or order <= 0:
        raise ValidationError("invalid observed order")
    extrapolated = fine.value + (fine.value - medium.value) / (ratio**order - 1)
    denominator = max(abs(fine.value), 1e-15)
    gci_fine = safety_factor * abs((fine.value - medium.value) / denominator) / (ratio**order - 1) * 100
    gci_medium = safety_factor * abs((medium.value - coarse.value) / max(abs(medium.value), 1e-15)) / (ratio**order - 1) * 100
    asymptotic = gci_medium / max(gci_fine * ratio**order, 1e-15)
    return GCIResult(order, extrapolated, gci_fine, asymptotic, gci_fine <= 5.0 and 0.8 <= asymptotic <= 1.2)


def conservation_balance(inputs: float, outputs: float, accumulation: float, sources: float, scale: float) -> float:
    values = (inputs, outputs, accumulation, sources, scale)
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values) or scale <= 0:
        raise ValidationError("invalid conservation terms")
    return abs(inputs + sources - outputs - accumulation) / scale


def cross_solver_discrepancy(first: Mapping[str, float], second: Mapping[str, float], quantities: Sequence[str], tolerance: float) -> dict[str, float]:
    if not quantities or not 0 < tolerance < 1:
        raise ValidationError("invalid cross-solver configuration")
    if set(quantities) - set(first) or set(quantities) - set(second):
        raise ValidationError("cross-solver quantity missing")
    result = {}
    for name in quantities:
        a, b = first[name], second[name]
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValidationError("non-finite solver result")
        result[name] = abs(a - b) / max(abs(a), abs(b), 1e-15)
    return result


@dataclass(frozen=True, slots=True)
class CADReceipt:
    route: str
    translator_done: bool
    brep_valid: bool
    solids: int
    shells: int
    faces: int
    edges: int
    vertices: int
    volume_relative_drift: float
    area_relative_drift: float
    centroid_drift_m: float
    units_preserved: bool
    metadata_preserved: bool
    evidence_ids: tuple[str, ...]

    def passes(self) -> bool:
        allowed = {"STEP", "IGES", "ASSEMBLY_STEP", "TESSELLATION"}
        if self.route not in allowed:
            raise ValidationError("unsupported CAD route")
        counts = (self.solids, self.shells, self.faces, self.edges, self.vertices)
        drifts = (self.volume_relative_drift, self.area_relative_drift, self.centroid_drift_m)
        if any(not isinstance(value, int) or value < 0 for value in counts) or any(not math.isfinite(value) or value < 0 for value in drifts):
            raise ValidationError("invalid CAD topology or drift")
        return all((self.translator_done, self.brep_valid, self.units_preserved, self.metadata_preserved, bool(self.evidence_ids))) and self.volume_relative_drift <= 1e-8 and self.area_relative_drift <= 1e-8 and self.centroid_drift_m <= 1e-7


def validate_cad_matrix(receipts: Sequence[CADReceipt]) -> bool:
    rows = tuple(receipts)
    if len(rows) != 4 or {row.route for row in rows} != {"STEP", "IGES", "ASSEMBLY_STEP", "TESSELLATION"}:
        raise ValidationError("CAD matrix incomplete or duplicated")
    return all(row.passes() for row in rows)


@dataclass(frozen=True, slots=True)
class CUDAReceipt:
    device_uuid: str
    device_name: str
    driver_version: str
    runtime_version: str
    compute_capability: str
    kernel_launches: int
    cpu_fallback_detected: bool
    max_absolute_error: float
    sanitizer_errors: int
    timing_samples_ms: tuple[float, ...]
    temperature_max_c: float
    throttling_detected: bool
    evidence_ids: tuple[str, ...]

    def passes(self) -> bool:
        identities = (self.device_uuid, self.device_name, self.driver_version, self.runtime_version, self.compute_capability)
        if any(not value for value in identities) or self.kernel_launches <= 0 or self.sanitizer_errors < 0:
            raise ValidationError("invalid CUDA identity/counters")
        numeric = (self.max_absolute_error, self.temperature_max_c, *self.timing_samples_ms)
        if len(self.timing_samples_ms) < 3 or any(not math.isfinite(value) or value < 0 for value in numeric):
            raise ValidationError("invalid CUDA metrics")
        timing_cv = 0.0
        if len(self.timing_samples_ms) > 1 and mean(self.timing_samples_ms) > 0:
            variance = sum((value - mean(self.timing_samples_ms)) ** 2 for value in self.timing_samples_ms) / (len(self.timing_samples_ms) - 1)
            timing_cv = math.sqrt(variance) / mean(self.timing_samples_ms)
        return not self.cpu_fallback_detected and self.max_absolute_error <= 1e-10 and self.sanitizer_errors == 0 and self.temperature_max_c <= 90 and not self.throttling_detected and timing_cv <= 0.2 and bool(self.evidence_ids)

