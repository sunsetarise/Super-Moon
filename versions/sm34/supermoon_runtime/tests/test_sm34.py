from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from supermoon34.aerospace.design import AircraftDesignModel, MissionSegment, isa_troposphere
from supermoon34.aerospace.digital_thread import DigitalThread, Requirement, RequirementState
from supermoon34.aerospace.flight import FlightDynamicsModel, RigidBodyState, quaternion_rotation
from supermoon34.aerospace.structures import StructuralAssessment
from supermoon34.aerospace.systems import BudgetItem, SystemArchitecture
from supermoon34.backends import probe_all
from supermoon34.capabilities import TRACKS, validate_registry
from supermoon34.cad import CadQualificationRunner, probe_cad
from supermoon34.cfd import compare_solvers, parse_openfoam_residuals
from supermoon34.contracts import BackendUnavailable, EvidenceError, ExecutionStatus, GateDecision, InvalidInput, TolerancePolicy
from supermoon34.endurance import EnduranceRunner
from supermoon34.evidence import EvidenceGraph, append_hash_chain, canonical_json
from supermoon34.gpu import GPUQualification, probe_gpu
from supermoon34.hpc import render_slurm_script
from supermoon34.math_metrics import (
    amdahl_speedup,
    availability,
    backward_error,
    deterministic_repeat_rate,
    effective_sample_size,
    grid_convergence_index,
    hausdorff_distance,
    relative_residual,
    roofline,
    strong_scaling,
)
from supermoon34.orchestration import QualificationOrchestrator, TrackTask
from supermoon34.performance import BenchmarkSuite
from supermoon34.petsc_mpi import PetscDistributedSolver, probe_petsc_mpi
from supermoon34.qualification import conservative_gate, evaluate_release, gate, unexecuted_release
from supermoon34.reproduction import MachineReceipt, ReproductionVerifier
from supermoon34.validation import ValidationSuite, manufactured_poisson


class ContractsTests(unittest.TestCase):
    def test_tolerance(self):
        policy = TolerancePolicy(absolute=1e-6, relative=1e-6)
        self.assertTrue(policy.close(1.0, 1.0 + 1e-7))
        self.assertFalse(policy.close(1.0, 1.01))

    def test_gate_rejects_evidence_free_pass(self):
        with self.assertRaises(EvidenceError):
            GateDecision("W01", 20, 1.0, ExecutionStatus.PASS, "B01")

    def test_registry(self):
        self.assertTrue(validate_registry())
        self.assertEqual(len(TRACKS), 16)


class MathTests(unittest.TestCase):
    def test_residuals(self):
        a = np.array([[4.0, 1.0], [1.0, 3.0]])
        b = np.array([1.0, 2.0])
        x = np.linalg.solve(a, b)
        self.assertLess(relative_residual(a, x, b), 1e-14)
        self.assertLess(backward_error(a, x, b), 1e-14)

    def test_scaling_metrics(self):
        self.assertEqual(strong_scaling(10.0, 2.5, 4), (4.0, 1.0))
        self.assertAlmostEqual(amdahl_speedup(0.1, 10), 1 / 0.19)
        self.assertEqual(roofline(100.0, 10.0, 2.0), 20.0)

    def test_statistics_and_geometry(self):
        self.assertEqual(effective_sample_size([1, 1, 1, 1]), 4.0)
        self.assertEqual(deterministic_repeat_rate(["a", "a", "b"]), 2 / 3)
        self.assertAlmostEqual(availability(99, 1), 0.99)
        self.assertAlmostEqual(hausdorff_distance([[0, 0], [1, 0]], [[0, 0], [2, 0]]), 1.0)
        self.assertGreater(grid_convergence_index(1.0, 1.1, 2.0, 2.0), 0)


class EvidenceTests(unittest.TestCase):
    def test_dag(self):
        graph = EvidenceGraph()
        first = graph.add("source", {"sha": "a"}, created_utc="2026-08-20T00:00:00+00:00")
        graph.add("test", {"passed": True}, (first.node_id,), created_utc="2026-08-20T00:00:01+00:00")
        self.assertTrue(graph.verify())
        self.assertIn(b"SM34_EVIDENCE_DAG_V1", graph.encode())

    def test_hash_chain(self):
        first = append_hash_chain(None, {"step": 1})
        second = append_hash_chain(first, {"step": 2})
        self.assertNotEqual(first, second)
        self.assertEqual(len(second), 64)


class QualificationTests(unittest.TestCase):
    def test_unexecuted_release_blocked(self):
        result = unexecuted_release()
        self.assertFalse(result.passed)
        self.assertEqual(result.status, ExecutionStatus.BLOCKED)
        self.assertEqual(result.score, 0)
        self.assertEqual(len(result.open_blockers), 8)

    def test_complete_release_passes(self):
        rows = [gate(f"W{i:02d}", ExecutionStatus.PASS, fraction=1.0, evidence_ids=(f"e{i}",)) for i in range(1, 9)]
        result = evaluate_release(rows, evidence_graph_valid=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 100)

    def test_partial_gate_fails(self):
        result = conservative_gate("W01", {"a": True, "b": False}, ("e",))
        self.assertEqual(result.status, ExecutionStatus.FAIL)
        self.assertEqual(result.fraction, 0.5)


class AdapterTests(unittest.TestCase):
    def test_backend_probes_are_explicit(self):
        probes = probe_all()
        self.assertEqual(len(probes), 9)
        self.assertTrue(any(row.backend.value == "INTERNAL" and row.available for row in probes))

    def test_missing_petsc_rejected(self):
        if not probe_petsc_mpi().available:
            with self.assertRaises(BackendUnavailable):
                PetscDistributedSolver().solve_poisson_1d(17)

    def test_missing_gpu_rejected(self):
        if not probe_gpu().available:
            with self.assertRaises(BackendUnavailable):
                GPUQualification().run(128)

    def test_missing_cad_rejected(self):
        if not probe_cad().available:
            with self.assertRaises(BackendUnavailable):
                CadQualificationRunner().run_reference()

    def test_openfoam_parser(self):
        text = "smoothSolver:  Solving for Ux, Initial residual = 0.2, Final residual = 1e-06, No Iterations 2"
        self.assertEqual(parse_openfoam_residuals(text)["Ux"], (1e-6,))

    def test_cfd_comparison(self):
        result = compare_solvers({"CL": 0.5}, {"CL": 0.5}, {"p": np.ones(3)}, {"p": np.ones(3)})
        self.assertTrue(result.accepted)

    def test_slurm_script_has_no_substitution(self):
        script = render_slurm_script(job_name="sm34", nodes=2, tasks_per_node=4, walltime="01:00:00", command=("python3", "run.py"))
        self.assertIn("#SBATCH --nodes=2", script)
        self.assertIn("srun --kill-on-bad-exit=1", script)
        with self.assertRaises(InvalidInput):
            render_slurm_script(job_name="bad;id", nodes=1, tasks_per_node=1, walltime="01:00:00", command=("x",))


class AerospaceTests(unittest.TestCase):
    def test_atmosphere(self):
        sea = isa_troposphere(0)
        self.assertAlmostEqual(sea.temperature_k, 288.15)
        self.assertAlmostEqual(sea.pressure_pa, 101325)

    def test_design(self):
        design = AircraftDesignModel(1000, 16, 0.025, 0.045, 1.5)
        self.assertGreater(design.stall_speed(), 0)
        point = design.performance_point(60)
        self.assertGreater(point.drag_n, 0)
        fraction = design.mission_fuel_fraction((MissionSegment("cruise", 3600, 60, 1000, 12, 2e-5),))
        self.assertTrue(0 < fraction < 1)

    def test_structures(self):
        model = StructuralAssessment(300e6, 450e6, 70e9, 2700)
        stress = model.bending_stress(1000, 0.05, 1e-5)
        self.assertGreater(stress, 0)
        self.assertTrue(model.yield_margin(stress).positive)
        self.assertAlmostEqual(model.miner_damage(((100, 1000), (50, 1000))), 0.15)

    def test_system_budgets(self):
        system = SystemArchitecture()
        system.set_limit("mass", 100)
        system.add_item("mass", BudgetItem("wing", 40, 2, 0.1))
        system.add_item("mass", BudgetItem("fuselage", 30, 3, 0.1))
        self.assertTrue(system.close_budget("mass").closed)
        system.set_failure_probability("a", 0.1)
        system.set_failure_probability("b", 0.2)
        self.assertAlmostEqual(system.independent_union_probability(("a", "b")), 0.28)

    def test_digital_thread(self):
        thread = DigitalThread()
        thread.add_requirement(Requirement("ROOT", "Civil research aircraft", "stakeholder", "review", allocation_ids=("SYS",)))
        thread.add_requirement(Requirement("R1", "Mass below limit", "performance", "analysis", parent_ids=("ROOT",), allocation_ids=("AIRFRAME",)))
        thread.revise("R1", state=RequirementState.VERIFIED, evidence_ids=("sha256:e",))
        report = thread.traceability()
        self.assertEqual(report["requirements"], 2)
        self.assertEqual(report["verified_fraction"], 0.5)

    def test_flight_dynamics(self):
        model = FlightDynamicsModel(1000, np.diag([1000, 1200, 1500]))
        state = RigidBodyState(np.zeros(3), np.array([50.0, 0, 0]), np.array([1.0, 0, 0, 0]), np.zeros(3))
        derivative = model.derivative(state, [0, 0, -1000 * 9.80665], [0, 0, 0])
        self.assertTrue(np.allclose(derivative.velocity_dot_body_m_s2, 0))
        self.assertTrue(np.allclose(quaternion_rotation([1, 0, 0, 0]), np.eye(3)))
        gain = model.continuous_lqr([[0, 1], [0, 0]], [[0], [1]], np.eye(2), np.eye(1))
        self.assertEqual(gain.shape, (1, 2))


class ValidationPerformanceTests(unittest.TestCase):
    def test_manufactured_order(self):
        errors, orders = manufactured_poisson()
        self.assertEqual(len(errors), 4)
        self.assertGreater(min(orders), 1.9)

    def test_validation_suite(self):
        self.assertEqual(ValidationSuite().run().status, ExecutionStatus.PASS)

    def test_benchmark(self):
        receipt = BenchmarkSuite().measure(lambda: sum(range(100)), work_units=100, repetitions=5, warmups=1)
        self.assertEqual(receipt.status, ExecutionStatus.PASS)
        self.assertGreater(receipt.median_seconds, 0)


class EnduranceOrchestrationTests(unittest.TestCase):
    def test_short_endurance_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = EnduranceRunner().run(0.01, lambda i: str(i).encode(), checkpoint=root / "checkpoint.json", telemetry=root / "telemetry.json", heartbeat_seconds=0.005)
            self.assertEqual(receipt.status, ExecutionStatus.PASS_WITH_LIMITATIONS)
            self.assertIsNone(receipt.qualified_profile)

    def test_reproduction_requires_distinct_receipts(self):
        first = MachineReceipt("m1", "o1", "r", {"a": "h"}, {"q": 1.0}, True, True, True)
        same = MachineReceipt("m1", "o1", "r", {"a": "h"}, {"q": 1.0}, True, True, True)
        self.assertFalse(ReproductionVerifier().compare(first, same).accepted)
        second = MachineReceipt("m2", "o2", "r", {"a": "h"}, {"q": 1.0}, True, True, True)
        self.assertTrue(ReproductionVerifier().compare(first, second).accepted)

    def test_async_dag(self):
        async def action():
            return {"ok": True}
        tasks = {
            "a": TrackTask("a", (), action),
            "b": TrackTask("b", ("a",), action),
        }
        results = asyncio.run(QualificationOrchestrator(2).run(tasks))
        self.assertEqual(results["b"].status, ExecutionStatus.PASS)


if __name__ == "__main__":
    unittest.main()

