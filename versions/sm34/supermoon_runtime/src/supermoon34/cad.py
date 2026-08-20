"""Real CadQuery/OCCT Boolean, validity, assembly, and round-trip qualification."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
import importlib.util
from pathlib import Path
import tempfile

from .contracts import BackendKind, BackendProbe, BackendUnavailable, ExecutionStatus, TolerancePolicy
from .evidence import sha256_file
from .math_metrics import normalized_discrepancy


@dataclass(frozen=True, slots=True)
class CadReceipt:
    status: ExecutionStatus
    cadquery_version: str
    occt_version: str
    source_valid: bool
    roundtrip_valid: bool
    source_volume: float
    roundtrip_volume: float
    volume_drift: float
    step_sha256: str
    iges_sha256: str | None
    limitations: tuple[str, ...]


def probe_cad() -> BackendProbe:
    available = importlib.util.find_spec("cadquery") is not None and importlib.util.find_spec("OCP") is not None
    versions: dict[str, str] = {}
    for package in ("cadquery", "cadquery-ocp"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    return BackendProbe(BackendKind.OCCT_CADQUERY, available, versions.get("cadquery"), None, versions)


class CadQualificationRunner:
    def __init__(self, tolerances: TolerancePolicy | None = None):
        self.tolerances = tolerances or TolerancePolicy()

    def run_reference(self, output: Path | None = None) -> CadReceipt:
        probe = probe_cad()
        if not probe.available:
            raise BackendUnavailable("real CadQuery and OCP/OpenCascade are mandatory")
        import cadquery as cq
        from OCP.BRepCheck import BRepCheck_Analyzer
        try:
            from OCP.Standard import Standard_Version
            occt_version = str(Standard_Version())
        except (ImportError, TypeError):
            occt_version = str(probe.details.get("cadquery-ocp", "unknown"))

        shape = cq.Workplane("XY").box(40.0, 30.0, 10.0).edges("|Z").fillet(2.0).faces(">Z").workplane().hole(8.0)
        source = shape.val()
        source_valid = bool(BRepCheck_Analyzer(source.wrapped).IsValid()) and bool(source.isValid())
        source_volume = float(source.Volume())
        limitations: list[str] = []
        manager = tempfile.TemporaryDirectory() if output is None else None
        root = Path(manager.name) if manager is not None else output.resolve()
        root.mkdir(parents=True, exist_ok=True)
        step = root / "sm34_reference.step"
        cq.exporters.export(shape, str(step), exportType="STEP")
        imported = cq.importers.importStep(str(step)).val()
        roundtrip_valid = bool(BRepCheck_Analyzer(imported.wrapped).IsValid()) and bool(imported.isValid())
        roundtrip_volume = float(imported.Volume())
        drift = normalized_discrepancy(roundtrip_volume, source_volume)
        iges_hash: str | None = None
        iges = root / "sm34_reference.iges"
        try:
            cq.exporters.export(shape, str(iges), exportType="IGES")
            iges_hash = sha256_file(iges)
        except (ValueError, RuntimeError, OSError) as exc:
            limitations.append(f"IGES export unavailable: {type(exc).__name__}")
        status = ExecutionStatus.PASS if source_valid and roundtrip_valid and drift <= self.tolerances.geometry and iges_hash else ExecutionStatus.FAIL
        receipt = CadReceipt(status, probe.version or "unknown", occt_version, source_valid, roundtrip_valid, source_volume, roundtrip_volume, drift, sha256_file(step), iges_hash, tuple(limitations))
        if manager is not None:
            manager.cleanup()
        return receipt

