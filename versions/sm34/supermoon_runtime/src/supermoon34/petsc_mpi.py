"""Real PETSc/mpi4py distributed solve adapter; no serial emulation path."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from typing import Any

import numpy as np

from .contracts import BackendKind, BackendProbe, BackendUnavailable, ExecutionStatus, InvalidInput, TolerancePolicy


@dataclass(frozen=True, slots=True)
class PetscSolveReceipt:
    status: ExecutionStatus
    ranks: int
    ownership_ranges: tuple[tuple[int, int], ...]
    convergence_reason: int
    iterations: int
    residual_norm: float
    relative_residual: float
    solution_sha256: str
    petsc_version: str
    mpi_library: str
    ksp_type: str
    pc_type: str


def probe_petsc_mpi() -> BackendProbe:
    available = importlib.util.find_spec("petsc4py") is not None and importlib.util.find_spec("mpi4py") is not None
    if not available:
        return BackendProbe(BackendKind.PETSC_MPI, False, None, None, {"petsc4py": importlib.util.find_spec("petsc4py") is not None, "mpi4py": importlib.util.find_spec("mpi4py") is not None})
    from mpi4py import MPI
    from petsc4py import PETSc
    version = ".".join(str(item) for item in PETSc.Sys.getVersion())
    return BackendProbe(BackendKind.PETSC_MPI, True, version, None, {"mpi_library": MPI.Get_library_version().strip()})


class PetscDistributedSolver:
    """Construct and solve a distributed 1-D Poisson system with real PETSc objects."""

    def __init__(self, tolerances: TolerancePolicy | None = None):
        self.tolerances = tolerances or TolerancePolicy()

    def solve_poisson_1d(self, global_size: int, *, required_ranks: int | None = None) -> PetscSolveReceipt:
        if global_size < 3:
            raise InvalidInput("global_size must be at least three")
        probe = probe_petsc_mpi()
        if not probe.available:
            raise BackendUnavailable("real petsc4py and mpi4py are mandatory")
        from mpi4py import MPI
        from petsc4py import PETSc

        comm = MPI.COMM_WORLD
        ranks = comm.Get_size()
        if required_ranks is not None and ranks != required_ranks:
            raise InvalidInput(f"required {required_ranks} MPI ranks, observed {ranks}")
        if ranks < 2:
            raise BackendUnavailable("distributed qualification rejects a single-rank PETSc run")

        matrix = PETSc.Mat().createAIJ(size=(global_size, global_size), nnz=3, comm=PETSc.COMM_WORLD)
        matrix.setUp()
        start, end = matrix.getOwnershipRange()
        for row in range(start, end):
            if row in (0, global_size - 1):
                matrix.setValue(row, row, 1.0)
            else:
                matrix.setValues(row, [row - 1, row, row + 1], [-1.0, 2.0, -1.0])
        matrix.assemblyBegin()
        matrix.assemblyEnd()

        solution, rhs = matrix.createVecs()
        rhs.set(1.0)
        if start == 0:
            rhs.setValue(0, 0.0)
        if end == global_size:
            rhs.setValue(global_size - 1, 0.0)
        rhs.assemblyBegin()
        rhs.assemblyEnd()
        solution.set(0.0)

        solver = PETSc.KSP().create(PETSc.COMM_WORLD)
        solver.setOperators(matrix)
        solver.setTolerances(rtol=self.tolerances.residual, atol=self.tolerances.absolute)
        solver.setFromOptions()
        solver.solve(rhs, solution)

        reason = int(solver.getConvergedReason())
        iterations = int(solver.getIterationNumber())
        residual_norm = float(solver.getResidualNorm())
        residual = rhs.duplicate()
        matrix.mult(solution, residual)
        residual.axpy(-1.0, rhs)
        rhs_norm = float(rhs.norm())
        relative = float(residual.norm()) / max(rhs_norm, self.tolerances.physical_floor)

        local = np.asarray(solution.getArray(readonly=True), dtype=np.float64).copy()
        gathered = comm.allgather(local)
        full = np.concatenate(gathered)
        ownership = tuple(comm.allgather((int(start), int(end))))
        reasons = tuple(comm.allgather(reason))
        if len(set(reasons)) != 1:
            status = ExecutionStatus.FAIL
        else:
            status = ExecutionStatus.PASS if reason > 0 and relative <= self.tolerances.residual else ExecutionStatus.NONCONVERGED
        ksp_type = str(solver.getType())
        pc_type = str(solver.getPC().getType())
        receipt = PetscSolveReceipt(
            status,
            ranks,
            ownership,
            reason,
            iterations,
            residual_norm,
            relative,
            hashlib.sha256(full.tobytes(order="C")).hexdigest(),
            probe.version or "unknown",
            MPI.Get_library_version().strip(),
            ksp_type,
            pc_type,
        )
        residual.destroy()
        solver.destroy()
        rhs.destroy()
        solution.destroy()
        matrix.destroy()
        return receipt

