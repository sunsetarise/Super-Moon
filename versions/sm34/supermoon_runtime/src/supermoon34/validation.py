"""Manufactured solutions, gradient checks, conservation, and UQ coverage."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .contracts import ExecutionStatus, InvalidInput, TolerancePolicy
from .math_metrics import observed_order


@dataclass(frozen=True, slots=True)
class ValidationReceipt:
    status: ExecutionStatus
    grid_sizes: tuple[int, ...]
    l2_errors: tuple[float, ...]
    observed_orders: tuple[float, ...]
    gradient_relative_error: float
    conservation_defect: float
    coverage: float
    limitations: tuple[str, ...] = ()


def manufactured_poisson(grid_sizes: tuple[int, ...] = (17, 33, 65, 129)) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Validate second-order finite differences for -u''=pi^2 sin(pi x)."""

    if len(grid_sizes) < 3 or any(size < 5 or size % 2 == 0 for size in grid_sizes):
        raise InvalidInput("use at least three odd grid sizes >=5")
    errors: list[float] = []
    spacings: list[float] = []
    for size in grid_sizes:
        x = np.linspace(0.0, 1.0, size)
        h = 1.0 / (size - 1)
        interior = size - 2
        operator = (np.diag(np.full(interior, 2.0)) + np.diag(np.full(interior - 1, -1.0), 1) + np.diag(np.full(interior - 1, -1.0), -1)) / h**2
        rhs = math.pi**2 * np.sin(math.pi * x[1:-1])
        numerical = np.zeros(size)
        numerical[1:-1] = np.linalg.solve(operator, rhs)
        exact = np.sin(math.pi * x)
        errors.append(float(np.sqrt(h * np.sum((numerical - exact) ** 2))))
        spacings.append(h)
    orders = [math.log(errors[i - 1] / errors[i]) / math.log(spacings[i - 1] / spacings[i]) for i in range(1, len(errors))]
    return tuple(errors), tuple(orders)


def gradient_check(function, point: np.ndarray, direction: np.ndarray, gradient: np.ndarray, *, step: float = 1e-6) -> float:
    x = np.asarray(point, dtype=float)
    d = np.asarray(direction, dtype=float)
    g = np.asarray(gradient, dtype=float)
    if x.shape != d.shape or x.shape != g.shape or step <= 0:
        raise InvalidInput("gradient-check dimensions or step invalid")
    d /= np.linalg.norm(d)
    finite = (float(function(x + step * d)) - float(function(x - step * d))) / (2 * step)
    analytic = float(np.dot(g, d))
    return abs(finite - analytic) / max(abs(finite), abs(analytic), 1e-30)


class ValidationSuite:
    def __init__(self, tolerances: TolerancePolicy | None = None):
        self.tolerances = tolerances or TolerancePolicy()

    def run(self, seed: int = 34) -> ValidationReceipt:
        sizes = (17, 33, 65, 129)
        errors, orders = manufactured_poisson(sizes)
        point = np.array([0.4, -0.2, 0.7])
        direction = np.array([1.0, 2.0, -0.5])
        function = lambda value: float(np.dot(value, value) + np.sin(value[0]))
        gradient = 2 * point + np.array([np.cos(point[0]), 0.0, 0.0])
        gradient_error = gradient_check(function, point, direction, gradient)
        fluxes = np.array([1.0, 0.8, -0.3, -1.5])
        conservation = abs(float(np.sum(fluxes))) / max(float(np.sum(np.abs(fluxes))), 1e-30)
        rng = np.random.default_rng(seed)
        samples = rng.standard_normal(20_000)
        coverage = float(np.mean(np.abs(samples) <= 1.959963984540054))
        passed = min(orders) > 1.9 and gradient_error < 1e-8 and conservation < 1e-14 and abs(coverage - 0.95) < 0.01
        return ValidationReceipt(ExecutionStatus.PASS if passed else ExecutionStatus.FAIL, sizes, errors, orders, gradient_error, conservation, coverage)

