"""Qualification mathematics corresponding to SM34 M001-M040."""

from __future__ import annotations

import math
from statistics import median
from typing import Iterable, Sequence

import numpy as np
import numpy.typing as npt

from .contracts import InvalidInput, TolerancePolicy

Array = npt.NDArray[np.float64]


def _array(values: object, name: str) -> Array:
    try:
        result = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidInput(f"{name} must be numeric") from exc
    if result.size == 0 or not np.all(np.isfinite(result)):
        raise InvalidInput(f"{name} must be nonempty and finite")
    return result


def relative_residual(matrix: object, solution: object, rhs: object, *, epsilon: float = 1e-30) -> float:
    a, x, b = _array(matrix, "matrix"), _array(solution, "solution"), _array(rhs, "rhs")
    if a.ndim != 2 or x.ndim != 1 or b.ndim != 1 or a.shape != (b.size, x.size):
        raise InvalidInput("incompatible linear-system dimensions")
    return float(np.linalg.norm(b - a @ x) / max(float(np.linalg.norm(b)), epsilon))


def backward_error(matrix: object, solution: object, rhs: object, *, epsilon: float = 1e-30) -> float:
    a, x, b = _array(matrix, "matrix"), _array(solution, "solution"), _array(rhs, "rhs")
    residual = float(np.linalg.norm(b - a @ x))
    denominator = float(np.linalg.norm(a, 2) * np.linalg.norm(x) + np.linalg.norm(b))
    return residual / max(denominator, epsilon)


def strong_scaling(serial_time: float, parallel_time: float, ranks: int) -> tuple[float, float]:
    if serial_time <= 0 or parallel_time <= 0 or ranks <= 0:
        raise InvalidInput("times and ranks must be positive")
    speedup = serial_time / parallel_time
    return speedup, speedup / ranks


def weak_scaling(single_rank_time: float, parallel_time: float) -> float:
    if single_rank_time <= 0 or parallel_time <= 0:
        raise InvalidInput("times must be positive")
    return single_rank_time / parallel_time


def amdahl_speedup(serial_fraction: float, ranks: int) -> float:
    if not 0.0 <= serial_fraction <= 1.0 or ranks <= 0:
        raise InvalidInput("invalid serial fraction or rank count")
    return 1.0 / (serial_fraction + (1.0 - serial_fraction) / ranks)


def gustafson_speedup(serial_fraction: float, ranks: int) -> float:
    if not 0.0 <= serial_fraction <= 1.0 or ranks <= 0:
        raise InvalidInput("invalid serial fraction or rank count")
    return ranks - serial_fraction * (ranks - 1)


def karp_flatt(speedup: float, ranks: int) -> float:
    if speedup <= 0.0 or ranks <= 1:
        raise InvalidInput("speedup must be positive and ranks > 1")
    return (1.0 / speedup - 1.0 / ranks) / (1.0 - 1.0 / ranks)


def arithmetic_intensity(flops: float, bytes_transferred: float) -> float:
    if flops < 0.0 or bytes_transferred <= 0.0:
        raise InvalidInput("invalid operation or byte count")
    return flops / bytes_transferred


def roofline(peak: float, bandwidth: float, intensity: float) -> float:
    if peak <= 0.0 or bandwidth <= 0.0 or intensity < 0.0:
        raise InvalidInput("invalid roofline input")
    return min(peak, bandwidth * intensity)


def coefficient_of_variation(values: object, *, epsilon: float = 1e-30) -> float:
    samples = _array(values, "values").ravel()
    return float(np.std(samples, ddof=1 if samples.size > 1 else 0) / max(abs(float(np.mean(samples))), epsilon))


def median_absolute_deviation(values: object) -> float:
    samples = [float(item) for item in _array(values, "values").ravel()]
    center = median(samples)
    return float(median(abs(item - center) for item in samples))


def observed_order(error_coarse: float, error_fine: float, refinement_ratio: float) -> float:
    if error_coarse <= 0 or error_fine <= 0 or refinement_ratio <= 1:
        raise InvalidInput("errors must be positive and refinement ratio > 1")
    return math.log(error_coarse / error_fine) / math.log(refinement_ratio)


def richardson_extrapolate(phi_fine: float, phi_coarse: float, ratio: float, order: float) -> float:
    denominator = ratio**order - 1.0
    if ratio <= 1.0 or order <= 0.0 or denominator == 0.0:
        raise InvalidInput("invalid Richardson parameters")
    return phi_fine + (phi_fine - phi_coarse) / denominator


def grid_convergence_index(phi_fine: float, phi_coarse: float, ratio: float, order: float, safety: float = 1.25) -> float:
    denominator = abs(phi_fine) * (ratio**order - 1.0)
    if denominator <= 0.0 or safety <= 0.0:
        raise InvalidInput("invalid GCI parameters")
    return safety * abs(phi_fine - phi_coarse) / denominator


def normalized_discrepancy(a: float, b: float, *, reference: float | None = None, floor: float = 1e-30) -> float:
    scale = abs(b if reference is None else reference)
    return abs(a - b) / max(scale, floor)


def weighted_field_l2(actual: object, expected: object, weights: object | None = None, *, epsilon: float = 1e-30) -> float:
    a, b = _array(actual, "actual").ravel(), _array(expected, "expected").ravel()
    if a.shape != b.shape:
        raise InvalidInput("field shapes differ")
    w = np.ones_like(a) if weights is None else _array(weights, "weights").ravel()
    if w.shape != a.shape or np.any(w < 0):
        raise InvalidInput("weights must be nonnegative and match field")
    return float(np.sqrt(np.dot(w, (a - b) ** 2) / max(float(np.dot(w, b**2)), epsilon)))


def conservation_defect(inflow: float, outflow: float, accumulation: float, source: float, throughput: float, *, epsilon: float = 1e-30) -> float:
    return abs(inflow - outflow - accumulation - source) / max(abs(throughput), epsilon)


def gradient_inconsistency(first: float, second: float, *, epsilon: float = 1e-30) -> float:
    return abs(first - second) / max(abs(first), abs(second), epsilon)


def hausdorff_distance(first: object, second: object) -> float:
    a, b = _array(first, "first"), _array(second, "second")
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[1]:
        raise InvalidInput("point clouds must be two-dimensional with equal dimension")
    distances = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    return float(max(np.max(np.min(distances, axis=1)), np.max(np.min(distances, axis=0))))


def robust_linear_slope(times: object, values: object) -> float:
    x, y = _array(times, "times").ravel(), _array(values, "values").ravel()
    if x.size != y.size or x.size < 2 or np.ptp(x) <= 0:
        raise InvalidInput("at least two distinct times are required")
    slopes = [(y[j] - y[i]) / (x[j] - x[i]) for i in range(x.size) for j in range(i + 1, x.size) if x[j] != x[i]]
    return float(median(slopes))


def availability(mtbf: float, mttr: float) -> float:
    if mtbf <= 0.0 or mttr < 0.0:
        raise InvalidInput("MTBF must be positive and MTTR nonnegative")
    return mtbf / (mtbf + mttr)


def relative_overhead(with_feature: float, without_feature: float) -> float:
    if with_feature < 0.0 or without_feature <= 0.0:
        raise InvalidInput("invalid timing input")
    return (with_feature - without_feature) / without_feature


def vector_relative_error(actual: object, expected: object, *, epsilon: float = 1e-30) -> float:
    a, b = _array(actual, "actual").ravel(), _array(expected, "expected").ravel()
    if a.shape != b.shape:
        raise InvalidInput("vector shapes differ")
    return float(np.linalg.norm(a - b) / max(float(np.linalg.norm(b)), epsilon))


def effective_sample_size(weights: object) -> float:
    w = _array(weights, "weights").ravel()
    if np.any(w < 0.0) or float(np.sum(w)) <= 0.0:
        raise InvalidInput("weights must be nonnegative with positive sum")
    return float(np.sum(w) ** 2 / np.dot(w, w))


def monte_carlo_standard_error(values: object, dependence_factor: float = 1.0) -> float:
    samples = _array(values, "values").ravel()
    if samples.size < 2 or dependence_factor <= 0.0:
        raise InvalidInput("at least two samples and positive dependence factor required")
    return float(np.std(samples, ddof=1) * math.sqrt(dependence_factor / samples.size))


def reproducibility_z(first: float, second: float, first_sigma: float, second_sigma: float) -> float:
    denominator = math.hypot(first_sigma, second_sigma)
    if first_sigma < 0 or second_sigma < 0 or denominator == 0:
        raise InvalidInput("reproducibility uncertainties must define positive scale")
    return (second - first) / denominator


def deterministic_repeat_rate(hashes: Sequence[str]) -> float:
    if not hashes:
        raise InvalidInput("at least one hash is required")
    reference = hashes[0]
    return sum(item == reference for item in hashes) / len(hashes)


def evidence_closure(verified: int, implemented: int) -> float:
    if verified < 0 or implemented <= 0 or verified > implemented:
        raise InvalidInput("invalid requirement coverage counts")
    return verified / implemented


def weighted_score(weights: Iterable[tuple[float, float]]) -> float:
    total = 0.0
    for weight, fraction in weights:
        if weight < 0.0 or not 0.0 <= fraction <= 1.0:
            raise InvalidInput("invalid gate weight or fraction")
        total += weight * fraction
    return total


def tolerance_compare(actual: float, expected: float, policy: TolerancePolicy, *, scale: float = 1.0) -> bool:
    return policy.close(actual, expected, scale=scale)

