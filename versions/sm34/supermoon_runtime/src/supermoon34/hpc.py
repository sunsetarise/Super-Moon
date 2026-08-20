"""Slurm submission/accounting adapter for real external-HPC evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from typing import Mapping

from .contracts import BackendKind, BackendProbe, BackendUnavailable, ExecutionStatus, InvalidInput
from .evidence import sha256_file
from .execution import CommandPolicy, CommandReceipt, CommandRunner

JOB_ID = re.compile(r"^(?P<job>\d+)(?:;(?P<cluster>[A-Za-z0-9_.-]+))?$")


@dataclass(frozen=True, slots=True)
class SlurmSubmission:
    job_id: str
    cluster: str | None
    script_sha256: str
    receipt: CommandReceipt


@dataclass(frozen=True, slots=True)
class SlurmAccounting:
    job_id: str
    rows: tuple[Mapping[str, str], ...]
    terminal: bool
    successful: bool
    status: ExecutionStatus
    receipt: CommandReceipt


def probe_slurm() -> BackendProbe:
    commands = {name: shutil.which(name) for name in ("sbatch", "sacct", "sstat", "squeue")}
    available = commands["sbatch"] is not None and commands["sacct"] is not None
    return BackendProbe(BackendKind.EXTERNAL_HPC, available, None, commands["sbatch"], commands)


def render_slurm_script(
    *,
    job_name: str,
    nodes: int,
    tasks_per_node: int,
    walltime: str,
    command: tuple[str, ...],
    partition: str | None = None,
) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", job_name):
        raise InvalidInput("invalid Slurm job name")
    if nodes <= 0 or tasks_per_node <= 0 or not re.fullmatch(r"\d{2}:\d{2}:\d{2}", walltime):
        raise InvalidInput("invalid Slurm resource request")
    if not command or any(not re.fullmatch(r"[A-Za-z0-9_./:=+,-]+", item) for item in command):
        raise InvalidInput("command tokens contain unsupported shell syntax")
    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --nodes={nodes}",
        f"#SBATCH --ntasks-per-node={tasks_per_node}",
        f"#SBATCH --time={walltime}",
        "#SBATCH --output=sm34-%j.out",
        "#SBATCH --error=sm34-%j.err",
    ]
    if partition is not None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", partition):
            raise InvalidInput("invalid partition")
        lines.append(f"#SBATCH --partition={partition}")
    lines.extend(("umask 077", "export OMP_NUM_THREADS=1", "srun --kill-on-bad-exit=1 " + " ".join(command), ""))
    return "\n".join(lines)


class SlurmQualification:
    def __init__(self, roots: tuple[Path, ...], *, timeout_seconds: float = 120.0):
        self.runner = CommandRunner(CommandPolicy(("sbatch", "sacct", "sstat", "squeue"), roots, timeout_seconds))

    def submit(self, script: Path, *, authorized: bool = False) -> SlurmSubmission:
        if not authorized:
            raise InvalidInput("external job submission requires explicit authorized=True")
        script = script.resolve(strict=True)
        receipt = self.runner.run(("sbatch", "--parsable", script.name), cwd=script.parent)
        if receipt.return_code != 0:
            raise BackendUnavailable(f"sbatch failed: {receipt.stderr[-500:]}")
        match = JOB_ID.fullmatch(receipt.stdout.strip())
        if match is None:
            raise InvalidInput("sbatch did not return a parsable job id")
        return SlurmSubmission(match.group("job"), match.group("cluster"), sha256_file(script), receipt)

    def accounting(self, job_id: str) -> SlurmAccounting:
        if not re.fullmatch(r"\d+", job_id):
            raise InvalidInput("invalid Slurm job id")
        fields = "JobIDRaw,JobName,Cluster,Partition,AllocNodes,AllocCPUS,Elapsed,State,ExitCode,MaxRSS,TotalCPU"
        receipt = self.runner.run(("sacct", "-j", job_id, "--parsable2", "--noheader", f"--format={fields}"), cwd=self.runner.policy.allowed_roots[0])
        names = fields.split(",")
        rows = []
        for line in receipt.stdout.splitlines():
            values = line.rstrip("|").split("|")
            if len(values) == len(names):
                rows.append(dict(zip(names, values, strict=True)))
        terminal_states = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "PREEMPTED"}
        states = {row["State"].split()[0].split("+")[0] for row in rows}
        terminal = bool(states) and states <= terminal_states
        successful = terminal and states == {"COMPLETED"} and all(row["ExitCode"].startswith("0:") for row in rows)
        return SlurmAccounting(job_id, tuple(rows), terminal, successful, ExecutionStatus.PASS if successful else (ExecutionStatus.NOT_EXECUTED if not terminal else ExecutionStatus.FAIL), receipt)

