"""Shell-free, bounded external execution with environment and binary receipts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Mapping, Sequence

from .contracts import BackendUnavailable, InvalidInput, confined_path


@dataclass(frozen=True, slots=True)
class CommandPolicy:
    allowed_names: tuple[str, ...]
    allowed_roots: tuple[Path, ...]
    timeout_seconds: float = 3600.0
    max_output_bytes: int = 64 * 1024**2
    environment_allowlist: tuple[str, ...] = (
        "PATH", "LANG", "LC_ALL", "TZ", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "PETSC_DIR", "PETSC_ARCH", "SU2_RUN", "WM_PROJECT_DIR", "SLURM_JOB_ID",
        "CUDA_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES",
    )

    def __post_init__(self) -> None:
        if not self.allowed_names or not self.allowed_roots:
            raise InvalidInput("command policy requires executable names and work roots")
        if self.timeout_seconds <= 0 or self.max_output_bytes <= 0:
            raise InvalidInput("command limits must be positive")


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    argv: tuple[str, ...]
    executable: str
    executable_sha256: str
    cwd: str
    return_code: int
    stdout: str
    stderr: str
    runtime_seconds: float


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CommandRunner:
    def __init__(self, policy: CommandPolicy):
        self.policy = policy

    def resolve(self, name: str) -> Path:
        if name not in self.policy.allowed_names or "/" in name or "\\" in name:
            raise BackendUnavailable(f"executable is not authorized: {name}")
        found = shutil.which(name)
        if found is None:
            raise BackendUnavailable(f"required executable is unavailable: {name}")
        return Path(found).resolve(strict=True)

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        environment: Mapping[str, str] | None = None,
        stdin: bytes | None = None,
    ) -> CommandReceipt:
        if not argv or any(not isinstance(item, str) or not item or "\x00" in item for item in argv):
            raise InvalidInput("argv must contain nonempty NUL-free strings")
        executable = self.resolve(argv[0])
        work = confined_path(cwd, self.policy.allowed_roots, must_exist=True)
        source = os.environ if environment is None else environment
        sanitized = {name: source[name] for name in self.policy.environment_allowlist if name in source}
        started = time.perf_counter()
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                completed = subprocess.run(
                    [str(executable), *argv[1:]],
                    cwd=work,
                    env=sanitized,
                    input=stdin,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=self.policy.timeout_seconds,
                    check=False,
                    shell=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError(f"command exceeded {self.policy.timeout_seconds} seconds") from exc
            stdout.seek(0, os.SEEK_END)
            stderr.seek(0, os.SEEK_END)
            size = stdout.tell() + stderr.tell()
            if size > self.policy.max_output_bytes:
                raise InvalidInput(f"command output exceeded {self.policy.max_output_bytes} bytes")
            stdout.seek(0)
            stderr.seek(0)
            stdout_payload = stdout.read().decode("utf-8", errors="replace")
            stderr_payload = stderr.read().decode("utf-8", errors="replace")
        return CommandReceipt(
            tuple([str(executable), *argv[1:]]),
            str(executable),
            _digest(executable),
            str(work),
            completed.returncode,
            stdout_payload,
            stderr_payload,
            time.perf_counter() - started,
        )

