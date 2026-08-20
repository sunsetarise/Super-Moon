"""SM34 track, gate, backend, and source-symbol registry."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import BackendKind, ClaimLevel, InvalidInput


@dataclass(frozen=True, slots=True)
class Track:
    track_id: str
    name: str
    backend: BackendKind
    implementation_symbol: str
    claim_level: ClaimLevel
    limitation: str | None = None


TRACKS: tuple[Track, ...] = (
    Track("P01", "PETSC_MPI_DISTRIBUTED_NUMERICS", BackendKind.PETSC_MPI, "supermoon34.petsc_mpi.PetscDistributedSolver", ClaimLevel.IMPLEMENTED, "Qualification requires actual 2/3/4/8-rank and external multi-node receipts."),
    Track("P02", "OPENFOAM_CROSS_VALIDATION", BackendKind.OPENFOAM, "supermoon34.cfd.OpenFOAMRunner", ClaimLevel.IMPLEMENTED, "No OpenFOAM result exists until a real case is executed."),
    Track("P03", "SU2_CROSS_VALIDATION", BackendKind.SU2, "supermoon34.cfd.SU2Runner", ClaimLevel.IMPLEMENTED, "No SU2 result exists until a real independent case is executed."),
    Track("P04", "OCCT_CADQUERY_QUALIFICATION", BackendKind.OCCT_CADQUERY, "supermoon34.cad.CadQualificationRunner", ClaimLevel.IMPLEMENTED, "Qualification requires real BRep checks and STEP/IGES round trips."),
    Track("P05", "EXTERNAL_HPC_EXECUTION", BackendKind.EXTERNAL_HPC, "supermoon34.hpc.SlurmQualification", ClaimLevel.IMPLEMENTED, "Local process execution cannot satisfy external HPC evidence."),
    Track("P06", "GPU_ACCELERATOR_EXECUTION", BackendKind.GPU, "supermoon34.gpu.GPUQualification", ClaimLevel.IMPLEMENTED, "CPU fallback is rejected as GPU evidence."),
    Track("P07", "ENDURANCE_RESILIENCE_RECOVERY", BackendKind.ENDURANCE, "supermoon34.endurance.EnduranceRunner", ClaimLevel.IMPLEMENTED, "24h/72h claims require real uninterrupted wall-clock duration."),
    Track("P08", "SECOND_MACHINE_REPRODUCTION", BackendKind.SECOND_MACHINE, "supermoon34.reproduction.ReproductionVerifier", ClaimLevel.IMPLEMENTED, "A distinct physical machine and independent operator receipt are mandatory."),
    Track("P09", "VERIFICATION_VALIDATION_UQ", BackendKind.INTERNAL, "supermoon34.validation.ValidationSuite", ClaimLevel.TESTED),
    Track("P10", "PERFORMANCE_SCALING_ENGINEERING", BackendKind.INTERNAL, "supermoon34.performance.BenchmarkSuite", ClaimLevel.TESTED),
    Track("P11", "RELEASE_SECURITY_EVIDENCE_GOVERNANCE", BackendKind.INTERNAL, "supermoon34.qualification.QualificationEngine", ClaimLevel.TESTED),
    Track("A01", "AEROSPACE_SYSTEMS_ARCHITECTURE_MBSE", BackendKind.INTERNAL, "supermoon34.aerospace.systems.SystemArchitecture", ClaimLevel.TESTED, "Research tooling is not certification or airworthiness approval."),
    Track("A02", "AERODYNAMICS_PROPULSION_AIRCRAFT_DESIGN", BackendKind.INTERNAL, "supermoon34.aerospace.design.AircraftDesignModel", ClaimLevel.TESTED, "Low-order models require independent CFD/test correlation."),
    Track("A03", "STRUCTURES_MATERIALS_AEROELASTICITY", BackendKind.INTERNAL, "supermoon34.aerospace.structures.StructuralAssessment", ClaimLevel.TESTED, "Preliminary sizing cannot establish safe-to-fly status."),
    Track("A04", "FLIGHT_DYNAMICS_AVIONICS_CONTROL", BackendKind.INTERNAL, "supermoon34.aerospace.flight.FlightDynamicsModel", ClaimLevel.TESTED, "Simulation requires SIL/HIL and independent safety review for operational use."),
    Track("A05", "AEROSPACE_SOFTWARE_ENGINEERING_DIGITAL_THREAD", BackendKind.INTERNAL, "supermoon34.aerospace.digital_thread.DigitalThread", ClaimLevel.TESTED, "Evidence-oriented software does not itself confer regulatory compliance."),
)

TRACK_BY_ID = {track.track_id: track for track in TRACKS}

GATE_WEIGHTS: dict[str, int] = {
    "W01": 20,
    "W02": 15,
    "W03": 12,
    "W04": 12,
    "W05": 12,
    "W06": 10,
    "W07": 10,
    "W08": 9,
}

GATE_BLOCKERS: dict[str, str | None] = {
    "W01": "B01",
    "W02": "B02",
    "W03": "B03",
    "W04": "B04",
    "W05": "B05",
    "W06": "B06",
    "W07": "B07",
    "W08": "B08",
}


def validate_registry() -> bool:
    if len(TRACK_BY_ID) != len(TRACKS) or set(GATE_WEIGHTS) != set(GATE_BLOCKERS):
        raise InvalidInput("duplicate track or inconsistent gate registry")
    if sum(GATE_WEIGHTS.values()) != 100:
        raise InvalidInput("gate weights must sum to 100")
    if set(TRACK_BY_ID) != {f"P{i:02d}" for i in range(1, 12)} | {f"A{i:02d}" for i in range(1, 6)}:
        raise InvalidInput("track registry is incomplete")
    return True

