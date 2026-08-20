"""Independent OpenFOAM/SU2 runners and neutral quantitative comparison."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import shutil
from typing import Mapping

import numpy as np

from .contracts import BackendKind, BackendProbe, BackendUnavailable, ExecutionStatus, InvalidInput, TolerancePolicy
from .execution import CommandPolicy, CommandReceipt, CommandRunner
from .math_metrics import normalized_discrepancy, weighted_field_l2

FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
OPENFOAM_RESIDUAL = re.compile(rf"Solving for\s+(?P<field>\w+),\s+Initial residual =\s+(?P<initial>{FLOAT}),\s+Final residual =\s+(?P<final>{FLOAT})")
SU2_ITERATION = re.compile(r"^\s*\|?\s*(?P<iteration>\d+)\s*[,|]\s*(?P<body>.*)$")


@dataclass(frozen=True, slots=True)
class SolverRun:
    solver: str
    status: ExecutionStatus
    case_sha256: str
    command: CommandReceipt
    residuals: Mapping[str, tuple[float, ...]]


@dataclass(frozen=True, slots=True)
class CFDComparison:
    qoi_discrepancies: Mapping[str, float]
    field_l2: Mapping[str, float]
    accepted: bool
    tolerance: float


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def probe_openfoam() -> BackendProbe:
    executable = shutil.which("foamRun") or shutil.which("simpleFoam")
    return BackendProbe(BackendKind.OPENFOAM, executable is not None, None, executable, {"checkMesh": shutil.which("checkMesh")})


def probe_su2() -> BackendProbe:
    executable = shutil.which("SU2_CFD")
    return BackendProbe(BackendKind.SU2, executable is not None, None, executable, {"SU2_CFD_AD": shutil.which("SU2_CFD_AD"), "SU2_DEF": shutil.which("SU2_DEF")})


def parse_openfoam_residuals(text: str) -> dict[str, tuple[float, ...]]:
    rows: dict[str, list[float]] = {}
    for match in OPENFOAM_RESIDUAL.finditer(text):
        rows.setdefault(match.group("field"), []).append(float(match.group("final")))
    return {key: tuple(value) for key, value in rows.items()}


class OpenFOAMRunner:
    def __init__(self, roots: tuple[Path, ...], *, timeout_seconds: float = 24 * 3600):
        self.runner = CommandRunner(CommandPolicy(("checkMesh", "foamRun", "simpleFoam", "postProcess"), roots, timeout_seconds))

    def run(self, case: Path, *, solver: str | None = None) -> SolverRun:
        case = case.resolve(strict=True)
        check = self.runner.run(("checkMesh", "-case", str(case)), cwd=case)
        if check.return_code != 0:
            return SolverRun("OpenFOAM", ExecutionStatus.FAIL, _tree_hash(case), check, {})
        selected = solver or ("foamRun" if shutil.which("foamRun") else "simpleFoam")
        argv = (selected, "-case", str(case)) if selected != "foamRun" else (selected, "-case", str(case))
        receipt = self.runner.run(argv, cwd=case)
        residuals = parse_openfoam_residuals(receipt.stdout + "\n" + receipt.stderr)
        status = ExecutionStatus.PASS if receipt.return_code == 0 and residuals else ExecutionStatus.FAIL
        return SolverRun("OpenFOAM", status, _tree_hash(case), receipt, residuals)


class SU2Runner:
    def __init__(self, roots: tuple[Path, ...], *, timeout_seconds: float = 24 * 3600):
        self.runner = CommandRunner(CommandPolicy(("SU2_CFD", "SU2_CFD_AD", "SU2_DEF"), roots, timeout_seconds))

    def run(self, config: Path, *, executable: str = "SU2_CFD") -> SolverRun:
        config = config.resolve(strict=True)
        receipt = self.runner.run((executable, config.name), cwd=config.parent)
        history = config.parent / "history.csv"
        residuals: dict[str, tuple[float, ...]] = {}
        if history.is_file():
            try:
                table = np.genfromtxt(history, delimiter=",", names=True, dtype=float, encoding="utf-8")
                if table.dtype.names:
                    residuals = {name: tuple(np.atleast_1d(table[name]).astype(float)) for name in table.dtype.names if "RMS" in name.upper() or "RES" in name.upper()}
            except (ValueError, OSError):
                residuals = {}
        status = ExecutionStatus.PASS if receipt.return_code == 0 and residuals else ExecutionStatus.FAIL
        return SolverRun("SU2", status, _tree_hash(config.parent), receipt, residuals)


def compare_solvers(
    first_qoi: Mapping[str, float],
    second_qoi: Mapping[str, float],
    first_fields: Mapping[str, np.ndarray],
    second_fields: Mapping[str, np.ndarray],
    *,
    tolerances: TolerancePolicy | None = None,
) -> CFDComparison:
    policy = tolerances or TolerancePolicy()
    if set(first_qoi) != set(second_qoi) or set(first_fields) != set(second_fields):
        raise InvalidInput("comparison keys must match exactly")
    qoi = {key: normalized_discrepancy(first_qoi[key], second_qoi[key]) for key in first_qoi}
    fields = {key: weighted_field_l2(first_fields[key], second_fields[key]) for key in first_fields}
    accepted = all(value <= policy.relative for value in qoi.values()) and all(value <= policy.relative for value in fields.values())
    return CFDComparison(qoi, fields, accepted, policy.relative)

