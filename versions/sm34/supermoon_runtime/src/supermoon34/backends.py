"""Truthful optional-backend discovery without promoting probes to execution."""

from __future__ import annotations

import platform
import shutil
import sys

from .cad import probe_cad
from .cfd import probe_openfoam, probe_su2
from .contracts import BackendKind, BackendProbe
from .gpu import probe_gpu
from .hpc import probe_slurm
from .petsc_mpi import probe_petsc_mpi


def probe_all() -> tuple[BackendProbe, ...]:
    direct = (
        probe_petsc_mpi(),
        probe_openfoam(),
        probe_su2(),
        probe_cad(),
        probe_slurm(),
        probe_gpu(),
    )
    internal = BackendProbe(
        BackendKind.INTERNAL,
        True,
        sys.version.split()[0],
        sys.executable,
        {"platform": platform.platform()},
    )
    endurance = BackendProbe(BackendKind.ENDURANCE, True, None, None, {"runner": "implemented", "24h_72h": "NOT_EXECUTED"})
    second = BackendProbe(BackendKind.SECOND_MACHINE, True, None, None, {"verifier": "implemented", "independent_receipt": "NOT_EXECUTED"})
    return direct + (endurance, second, internal)

