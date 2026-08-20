"""Preliminary stress, buckling, fatigue, and margin calculations."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from ..contracts import InvalidInput


@dataclass(frozen=True, slots=True)
class MarginResult:
    allowable: float
    applied: float
    factor_of_safety: float
    margin_of_safety: float
    positive: bool


@dataclass(slots=True)
class StructuralAssessment:
    yield_strength_pa: float
    ultimate_strength_pa: float
    elastic_modulus_pa: float
    density_kg_m3: float

    def __post_init__(self) -> None:
        if min(self.yield_strength_pa, self.ultimate_strength_pa, self.elastic_modulus_pa, self.density_kg_m3) <= 0:
            raise InvalidInput("material properties must be positive")

    @staticmethod
    def bending_stress(moment_nm: float, distance_m: float, second_moment_m4: float) -> float:
        if distance_m < 0 or second_moment_m4 <= 0:
            raise InvalidInput("invalid section geometry")
        return abs(moment_nm) * distance_m / second_moment_m4

    def yield_margin(self, applied_stress_pa: float, factor_of_safety: float = 1.5) -> MarginResult:
        if applied_stress_pa < 0 or factor_of_safety <= 0:
            raise InvalidInput("invalid stress or factor of safety")
        allowable = self.yield_strength_pa / factor_of_safety
        margin = allowable / max(applied_stress_pa, 1e-30) - 1.0
        return MarginResult(allowable, applied_stress_pa, factor_of_safety, margin, margin >= 0)

    def euler_buckling(self, length_m: float, second_moment_m4: float, effective_length_factor: float = 1.0) -> float:
        if min(length_m, second_moment_m4, effective_length_factor) <= 0:
            raise InvalidInput("invalid buckling inputs")
        return math.pi**2 * self.elastic_modulus_pa * second_moment_m4 / (effective_length_factor * length_m) ** 2

    @staticmethod
    def miner_damage(cycles: Iterable[tuple[float, float]]) -> float:
        damage = 0.0
        count = 0
        for applied, allowable in cycles:
            if applied < 0 or allowable <= 0:
                raise InvalidInput("fatigue cycle counts are invalid")
            damage += applied / allowable
            count += 1
        if count == 0:
            raise InvalidInput("fatigue spectrum is empty")
        return damage

    @staticmethod
    def thermal_stress(elastic_modulus_pa: float, expansion_per_k: float, delta_temperature_k: float, poisson: float = 0.3) -> float:
        if elastic_modulus_pa <= 0 or expansion_per_k < 0 or not -1.0 < poisson < 0.5:
            raise InvalidInput("invalid thermoelastic inputs")
        return abs(elastic_modulus_pa * expansion_per_k * delta_temperature_k / (1.0 - poisson))

