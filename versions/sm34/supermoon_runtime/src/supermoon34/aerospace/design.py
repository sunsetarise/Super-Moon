"""Auditable low-order atmosphere, aerodynamics, propulsion, and mission model."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from ..contracts import InvalidInput


@dataclass(frozen=True, slots=True)
class AtmosphereState:
    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float


def isa_troposphere(altitude_m: float) -> AtmosphereState:
    if not -500.0 <= altitude_m <= 11_000.0:
        raise InvalidInput("this ISA implementation is limited to -500..11000 m")
    t0, p0, lapse, gravity, gas = 288.15, 101325.0, -0.0065, 9.80665, 287.05287
    temperature = t0 + lapse * altitude_m
    pressure = p0 * (temperature / t0) ** (-gravity / (lapse * gas))
    density = pressure / (gas * temperature)
    sound = math.sqrt(1.4 * gas * temperature)
    return AtmosphereState(altitude_m, temperature, pressure, density, sound)


@dataclass(frozen=True, slots=True)
class MissionSegment:
    name: str
    duration_s: float
    speed_m_s: float
    altitude_m: float
    lift_to_drag: float
    specific_fuel_consumption_per_s: float

    def __post_init__(self) -> None:
        if not self.name or min(self.duration_s, self.speed_m_s, self.lift_to_drag) <= 0 or self.specific_fuel_consumption_per_s < 0:
            raise InvalidInput("invalid mission segment")


@dataclass(frozen=True, slots=True)
class PerformancePoint:
    speed_m_s: float
    dynamic_pressure_pa: float
    lift_coefficient: float
    drag_coefficient: float
    drag_n: float
    power_required_w: float


@dataclass(slots=True)
class AircraftDesignModel:
    mass_kg: float
    wing_area_m2: float
    cd0: float
    induced_factor: float
    cl_max: float
    propulsive_efficiency: float = 0.82

    def __post_init__(self) -> None:
        values = (self.mass_kg, self.wing_area_m2, self.cd0, self.induced_factor, self.cl_max, self.propulsive_efficiency)
        if any(value <= 0 or not math.isfinite(value) for value in values) or self.propulsive_efficiency > 1:
            raise InvalidInput("aircraft design inputs must be finite and physical")

    @property
    def weight_n(self) -> float:
        return self.mass_kg * 9.80665

    def performance_point(self, speed_m_s: float, altitude_m: float = 0.0, load_factor: float = 1.0) -> PerformancePoint:
        if speed_m_s <= 0 or load_factor <= 0:
            raise InvalidInput("speed and load factor must be positive")
        atmosphere = isa_troposphere(altitude_m)
        q = 0.5 * atmosphere.density_kg_m3 * speed_m_s**2
        cl = load_factor * self.weight_n / (q * self.wing_area_m2)
        cd = self.cd0 + self.induced_factor * cl**2
        drag = q * self.wing_area_m2 * cd
        return PerformancePoint(speed_m_s, q, cl, cd, drag, drag * speed_m_s / self.propulsive_efficiency)

    def stall_speed(self, altitude_m: float = 0.0, load_factor: float = 1.0) -> float:
        atmosphere = isa_troposphere(altitude_m)
        return math.sqrt(2 * load_factor * self.weight_n / (atmosphere.density_kg_m3 * self.wing_area_m2 * self.cl_max))

    def mission_fuel_fraction(self, segments: Iterable[MissionSegment]) -> float:
        mass_fraction = 1.0
        count = 0
        for segment in segments:
            count += 1
            exponent = -segment.specific_fuel_consumption_per_s * segment.speed_m_s * segment.duration_s / max(segment.lift_to_drag * segment.speed_m_s, 1e-30)
            mass_fraction *= math.exp(exponent)
        if count == 0:
            raise InvalidInput("mission requires at least one segment")
        return 1.0 - mass_fraction

