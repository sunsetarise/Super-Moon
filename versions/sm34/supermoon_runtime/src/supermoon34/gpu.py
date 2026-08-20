"""Real CUDA GPU execution and CPU-parity evidence without fallback."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
import shutil
import subprocess
import time

import numpy as np

from .contracts import BackendKind, BackendProbe, BackendUnavailable, ExecutionStatus, InvalidInput, TolerancePolicy
from .math_metrics import vector_relative_error


@dataclass(frozen=True, slots=True)
class GPUReceipt:
    status: ExecutionStatus
    backend: str
    device_name: str
    device_uuid: str | None
    driver_version: str | None
    runtime_version: str | None
    elements: int
    kernel_seconds: float
    cpu_seconds: float
    relative_error: float
    speedup: float
    telemetry: dict[str, str]


def _nvidia_telemetry() -> dict[str, str]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {}
    query = "uuid,name,driver_version,memory.total,memory.used,utilization.gpu,power.draw"
    completed = subprocess.run([executable, f"--query-gpu={query}", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10, check=False, shell=False)
    if completed.returncode != 0 or not completed.stdout.strip():
        return {}
    values = [item.strip() for item in completed.stdout.splitlines()[0].split(",")]
    keys = query.split(",")
    return dict(zip(keys, values, strict=False))


def probe_gpu() -> BackendProbe:
    cupy = importlib.util.find_spec("cupy") is not None
    torch = importlib.util.find_spec("torch") is not None
    available = False
    details: dict[str, object] = {"cupy": cupy, "torch": torch, "nvidia_smi": shutil.which("nvidia-smi")}
    if cupy:
        try:
            import cupy as cp
            available = cp.cuda.runtime.getDeviceCount() > 0
        except Exception as exc:
            details["cupy_probe_error"] = type(exc).__name__
    if not available and torch:
        try:
            import torch as th
            available = bool(th.cuda.is_available() and th.cuda.device_count() > 0)
        except Exception as exc:
            details["torch_probe_error"] = type(exc).__name__
    return BackendProbe(BackendKind.GPU, available, None, shutil.which("nvidia-smi"), details)


class GPUQualification:
    def __init__(self, tolerances: TolerancePolicy | None = None):
        self.tolerances = tolerances or TolerancePolicy(relative=1e-6)

    def run(self, elements: int = 1_000_000, seed: int = 34) -> GPUReceipt:
        if elements <= 0:
            raise InvalidInput("elements must be positive")
        probe = probe_gpu()
        if not probe.available:
            raise BackendUnavailable("a real CUDA device and executable GPU array backend are mandatory")
        rng = np.random.default_rng(seed)
        first = rng.standard_normal(elements, dtype=np.float32)
        second = rng.standard_normal(elements, dtype=np.float32)
        cpu_started = time.perf_counter()
        expected = np.tanh(first * second + first)
        cpu_seconds = time.perf_counter() - cpu_started
        telemetry = _nvidia_telemetry()

        if importlib.util.find_spec("cupy") is not None:
            import cupy as cp
            device = cp.cuda.Device()
            properties = cp.cuda.runtime.getDeviceProperties(device.id)
            a, b = cp.asarray(first), cp.asarray(second)
            cp.cuda.Stream.null.synchronize()
            started = time.perf_counter()
            output = cp.tanh(a * b + a)
            cp.cuda.Stream.null.synchronize()
            kernel_seconds = time.perf_counter() - started
            actual = cp.asnumpy(output)
            name = properties["name"].decode() if isinstance(properties["name"], bytes) else str(properties["name"])
            runtime = str(cp.cuda.runtime.runtimeGetVersion())
            backend = "CuPy"
        else:
            import torch
            device = torch.device("cuda:0")
            a, b = torch.from_numpy(first).to(device), torch.from_numpy(second).to(device)
            torch.cuda.synchronize(device)
            started = time.perf_counter()
            output = torch.tanh(a * b + a)
            torch.cuda.synchronize(device)
            kernel_seconds = time.perf_counter() - started
            actual = output.cpu().numpy()
            name = torch.cuda.get_device_name(device)
            runtime = str(torch.version.cuda)
            backend = "PyTorch"
        error = vector_relative_error(actual.astype(np.float64), expected.astype(np.float64))
        status = ExecutionStatus.PASS if error <= self.tolerances.relative and telemetry.get("uuid") else ExecutionStatus.FAIL
        return GPUReceipt(status, backend, name, telemetry.get("uuid"), telemetry.get("driver_version"), runtime, elements, kernel_seconds, cpu_seconds, error, cpu_seconds / max(kernel_seconds, 1e-30), telemetry)

