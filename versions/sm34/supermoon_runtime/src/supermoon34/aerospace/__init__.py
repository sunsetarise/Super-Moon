"""Civil, non-weapon aerospace research architecture for SM34."""

from .design import AircraftDesignModel, AtmosphereState, MissionSegment
from .digital_thread import DigitalThread, Requirement
from .flight import FlightDynamicsModel, RigidBodyState
from .structures import StructuralAssessment
from .systems import SystemArchitecture

__all__ = [
    "AircraftDesignModel",
    "AtmosphereState",
    "DigitalThread",
    "FlightDynamicsModel",
    "MissionSegment",
    "Requirement",
    "RigidBodyState",
    "StructuralAssessment",
    "SystemArchitecture",
]

