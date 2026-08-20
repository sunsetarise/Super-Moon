#!/usr/bin/env python3
"""Real petsc4py distributed 1-D Poisson correctness worker."""

from __future__ import annotations

import hashlib
import json

from mpi4py import MPI
from petsc4py import PETSc


def main() -> int:
    comm = MPI.COMM_WORLD
    size = 257
    matrix = PETSc.Mat().createAIJ([size, size], nnz=3, comm=comm)
    matrix.setUp()
    start, end = matrix.getOwnershipRange()
    for row in range(start, end):
        matrix.setValue(row, row, 2.0)
        if row:
            matrix.setValue(row, row - 1, -1.0)
        if row + 1 < size:
            matrix.setValue(row, row + 1, -1.0)
    matrix.assemble()
    rhs, solution = matrix.createVecs()
    rhs.set(1.0)
    solver = PETSc.KSP().create(comm)
    solver.setOperators(matrix)
    solver.setType("cg")
    solver.getPC().setType("jacobi")
    solver.setTolerances(rtol=1e-10, max_it=10000)
    solver.solve(rhs, solution)
    residual = rhs.duplicate()
    matrix.mult(solution, residual)
    residual.axpy(-1.0, rhs)
    relative_residual = residual.norm() / rhs.norm()
    local = solution.getArray(readonly=True).tobytes()
    local_hash = hashlib.sha256(local).hexdigest()
    rows = comm.gather({"rank": comm.rank, "host": MPI.Get_processor_name(), "ownership": [start, end], "residual": relative_residual, "local_sha256": local_hash, "reason": int(solver.getConvergedReason())}, root=0)
    if comm.rank == 0:
        print(json.dumps({"format": "SM35_PETSC_WORKER_V1", "ranks": comm.size, "rows": rows}, sort_keys=True))
    return 0 if relative_residual <= 1e-8 and solver.getConvergedReason() > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
