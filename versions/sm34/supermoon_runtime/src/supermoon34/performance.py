"""Statistically explicit microbenchmark and regression contracts."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
import time
from typing import Callable

import numpy as np

from .contracts import ExecutionStatus, InvalidInput
from .math_metrics import median_absolute_deviation


@dataclass(frozen=True, slots=True)
class BenchmarkReceipt:
    status: ExecutionStatus
    samples_seconds: tuple[float, ...]
    median_seconds: float
    mad_seconds: float
    ci95_seconds: tuple[float, float]
    work_units: int
    warmups: int
    repetitions: int


class BenchmarkSuite:
    def measure(
        self,
        function: Callable[[], object],
        *,
        work_units: int,
        warmups: int = 3,
        repetitions: int = 15,
        seed: int = 34,
    ) -> BenchmarkReceipt:
        if work_units <= 0 or warmups < 0 or repetitions < 5:
            raise InvalidInput("invalid benchmark plan")
        for _ in range(warmups):
            function()
        samples: list[float] = []
        for _ in range(repetitions):
            started = time.perf_counter_ns()
            function()
            elapsed = (time.perf_counter_ns() - started) / 1e9
            if elapsed <= 0 or not math.isfinite(elapsed):
                raise InvalidInput("nonpositive benchmark duration")
            samples.append(elapsed)
        center = float(median(samples))
        spread = median_absolute_deviation(samples)
        rng = np.random.default_rng(seed)
        bootstrap = np.median(rng.choice(np.asarray(samples), size=(2000, repetitions), replace=True), axis=1)
        ci = (float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975)))
        return BenchmarkReceipt(ExecutionStatus.PASS, tuple(samples), center, spread, ci, work_units, warmups, repetitions)

    @staticmethod
    def regression(current: BenchmarkReceipt, baseline: BenchmarkReceipt, *, allowed_fraction: float = 0.10) -> bool:
        if allowed_fraction < 0:
            raise InvalidInput("allowed regression must be nonnegative")
        if current.work_units != baseline.work_units:
            raise InvalidInput("benchmark work definitions differ")
        return current.median_seconds <= baseline.median_seconds * (1.0 + allowed_fraction)

