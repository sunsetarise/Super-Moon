"""Six-degree-of-freedom rigid-body dynamics, trim residuals, and LQR."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import scipy.linalg

from ..contracts import InvalidInput


@dataclass(frozen=True, slots=True)
class RigidBodyState:
    position_ned_m: np.ndarray
    velocity_body_m_s: np.ndarray
    quaternion_body_to_ned: np.ndarray
    rates_body_rad_s: np.ndarray


@dataclass(frozen=True, slots=True)
class StateDerivative:
    position_dot_ned_m_s: np.ndarray
    velocity_dot_body_m_s2: np.ndarray
    quaternion_dot: np.ndarray
    rates_dot_body_rad_s2: np.ndarray


def _vector(value: object, length: int, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (length,) or not np.all(np.isfinite(array)):
        raise InvalidInput(f"{name} must be a finite {length}-vector")
    return array


def quaternion_rotation(quaternion: object) -> np.ndarray:
    q = _vector(quaternion, 4, "quaternion")
    norm = np.linalg.norm(q)
    if norm <= 0:
        raise InvalidInput("quaternion norm must be positive")
    w, x, y, z = q / norm
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


@dataclass(slots=True)
class FlightDynamicsModel:
    mass_kg: float
    inertia_body_kg_m2: np.ndarray

    def __post_init__(self) -> None:
        self.inertia_body_kg_m2 = np.asarray(self.inertia_body_kg_m2, dtype=float)
        if self.mass_kg <= 0 or self.inertia_body_kg_m2.shape != (3, 3) or not np.allclose(self.inertia_body_kg_m2, self.inertia_body_kg_m2.T):
            raise InvalidInput("mass and symmetric 3x3 inertia are required")
        if np.min(np.linalg.eigvalsh(self.inertia_body_kg_m2)) <= 0:
            raise InvalidInput("inertia must be positive definite")

    def derivative(self, state: RigidBodyState, force_body_n: object, moment_body_nm: object, gravity_m_s2: float = 9.80665) -> StateDerivative:
        position = _vector(state.position_ned_m, 3, "position")
        velocity = _vector(state.velocity_body_m_s, 3, "velocity")
        quaternion = _vector(state.quaternion_body_to_ned, 4, "quaternion")
        rates = _vector(state.rates_body_rad_s, 3, "rates")
        force = _vector(force_body_n, 3, "force")
        moment = _vector(moment_body_nm, 3, "moment")
        rotation = quaternion_rotation(quaternion)
        gravity_body = rotation.T @ np.array([0.0, 0.0, gravity_m_s2])
        position_dot = rotation @ velocity
        velocity_dot = force / self.mass_kg + gravity_body - np.cross(rates, velocity)
        w, x, y, z = quaternion / np.linalg.norm(quaternion)
        p, q, r = rates
        quaternion_dot = 0.5 * np.array([-x * p - y * q - z * r, w * p + y * r - z * q, w * q + z * p - x * r, w * r + x * q - y * p])
        angular_momentum = self.inertia_body_kg_m2 @ rates
        rates_dot = np.linalg.solve(self.inertia_body_kg_m2, moment - np.cross(rates, angular_momentum))
        return StateDerivative(position_dot, velocity_dot, quaternion_dot, rates_dot)

    @staticmethod
    def trim_residual(forces_body_n: object, moments_body_nm: object, weight_n: float, flight_path_angle_rad: float = 0.0) -> np.ndarray:
        forces = _vector(forces_body_n, 3, "forces")
        moments = _vector(moments_body_nm, 3, "moments")
        if weight_n <= 0:
            raise InvalidInput("weight must be positive")
        target = np.array([-weight_n * math.sin(flight_path_angle_rad), 0.0, -weight_n * math.cos(flight_path_angle_rad)])
        return np.concatenate((forces - target, moments))

    @staticmethod
    def continuous_lqr(a: object, b: object, q: object, r: object) -> np.ndarray:
        a_m, b_m, q_m, r_m = (np.asarray(item, dtype=float) for item in (a, b, q, r))
        if a_m.ndim != 2 or a_m.shape[0] != a_m.shape[1] or b_m.shape[0] != a_m.shape[0] or q_m.shape != a_m.shape or r_m.shape != (b_m.shape[1], b_m.shape[1]):
            raise InvalidInput("incompatible LQR matrices")
        solution = scipy.linalg.solve_continuous_are(a_m, b_m, q_m, r_m)
        return np.linalg.solve(r_m, b_m.T @ solution)

