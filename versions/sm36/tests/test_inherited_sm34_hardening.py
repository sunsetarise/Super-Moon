from __future__ import annotations

from contextlib import redirect_stdout
import gzip
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np

from supermoon34 import cli as cli34
from supermoon34.cad import CadQualificationRunner
from supermoon34.cfd import OpenFOAMRunner, SU2Runner, compare_solvers, parse_openfoam_residuals
from supermoon34.contracts import BackendUnavailable, ExecutionStatus, InvalidInput, TolerancePolicy
from supermoon34.evidence import (
    EvidenceGraph, ManifestEntry, append_hash_chain, artifact_from_file, build_manifest,
    canonical_json, json_value, sha256_file, verify_manifest,
)
from supermoon34.execution import CommandPolicy, CommandReceipt, CommandRunner
from supermoon34.gpu import GPUQualification, _nvidia_telemetry, probe_gpu
from supermoon34.hpc import SlurmQualification, render_slurm_script
from supermoon34.math_metrics import *
from supermoon34.math_metrics import _array
from supermoon34.petsc_mpi import PetscDistributedSolver
from supermoon34.requirements import _record, compile_prompt, iter_records, open_prompt
from supermoon34.aerospace.design import AircraftDesignModel, MissionSegment, isa_troposphere
from supermoon34.aerospace.digital_thread import DigitalThread, Interface, Requirement, RequirementState
from supermoon34.aerospace.flight import FlightDynamicsModel, RigidBodyState, quaternion_rotation
from supermoon34.aerospace.structures import StructuralAssessment
from supermoon34.aerospace.systems import BudgetItem, SystemArchitecture


class RequirementCompilerHardening(unittest.TestCase):
    def test_full_cardinality_compile_and_grammar(self):
        generic = "REQ-000001 | P01=PETSC_MPI_DISTRIBUTED_NUMERICS | obligation\n"
        aerospace = "AERO-REQ-00001 | A01=AEROSPACE_SYSTEMS_ARCHITECTURE_MBSE | obligation\n"
        policy = "GATE policy line\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); prompt = root / "prompt.txt"; output = root / "matrix.jsonl.gz"
            with prompt.open("w", encoding="utf-8", newline="") as stream:
                for _ in range(149_600): stream.write(generic)
                for _ in range(50_000): stream.write(aerospace)
                for _ in range(400): stream.write(policy)
            summary = compile_prompt(prompt, output)
            self.assertEqual(summary["matrix_records"], 200_000)
            self.assertTrue(output.is_file())
            with gzip.open(output, "rt", encoding="utf-8") as stream:
                self.assertEqual(json.loads(next(stream))["record_type"], "HPC_REQUIREMENT")
            gz = root / "single.gz"
            with gzip.open(gz, "wt", encoding="utf-8", newline="") as stream: stream.write(policy)
            with open_prompt(gz) as stream: self.assertEqual(tuple(iter_records(stream))[0].record_type, "POLICY")

    def test_grammar_rejections_and_crlf(self):
        self.assertEqual(_record(1, "GATE x").record_type, "POLICY")
        rows = tuple(iter_records(StringIO("GATE one\r\nGATE two\n"))); self.assertEqual(len(rows), 2)
        for line in (
            "unknown", "REQ-000001 | P99=NOPE | x",
            "REQ-000001 | P01=WRONG_NAME | x",
        ):
            with self.assertRaises(InvalidInput): _record(1, line)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); prompt = root / "short.txt"; prompt.write_text("GATE short\n", encoding="utf-8")
            with self.assertRaises(InvalidInput): compile_prompt(prompt, root / "out.gz")


class MathMetricHardening(unittest.TestCase):
    def test_success_matrix(self):
        self.assertEqual(weak_scaling(2, 4), .5)
        self.assertGreater(gustafson_speedup(.1, 8), 1)
        self.assertGreater(karp_flatt(4, 8), 0)
        self.assertEqual(arithmetic_intensity(10, 2), 5)
        self.assertGreaterEqual(coefficient_of_variation([1, 2, 3]), 0)
        self.assertEqual(median_absolute_deviation([1, 2, 100]), 1)
        self.assertAlmostEqual(observed_order(.25, .0625, 2), 2)
        self.assertTrue(np.isfinite(richardson_extrapolate(1, 1.2, 2, 2)))
        self.assertEqual(normalized_discrepancy(1, 1), 0)
        self.assertEqual(weighted_field_l2([1, 2], [1, 2], [1, 2]), 0)
        self.assertEqual(conservation_defect(10, 8, 1, 1, 10), 0)
        self.assertEqual(gradient_inconsistency(1, 1), 0)
        self.assertEqual(robust_linear_slope([0, 1, 2], [0, 2, 4]), 2)
        self.assertEqual(relative_overhead(12, 10), .2)
        self.assertEqual(vector_relative_error([1, 2], [1, 2]), 0)
        self.assertGreater(monte_carlo_standard_error([1, 2, 3]), 0)
        self.assertAlmostEqual(reproducibility_z(1, 2, 1, 0), 1)
        self.assertEqual(evidence_closure(2, 4), .5)
        self.assertEqual(weighted_score(((40, .5), (60, 1))), 80)
        self.assertTrue(tolerance_compare(1, 1, TolerancePolicy()))

    def test_invalid_matrix(self):
        invalid_calls = (
            lambda: relative_residual([[1]], [1, 2], [1]), lambda: _array([], "x"),
            lambda: _array([np.nan], "x"), lambda: _array([object()], "x"),
            lambda: strong_scaling(0, 1, 1), lambda: weak_scaling(0, 1),
            lambda: amdahl_speedup(-1, 1), lambda: gustafson_speedup(2, 1),
            lambda: karp_flatt(0, 1), lambda: arithmetic_intensity(-1, 1),
            lambda: roofline(0, 1, 1), lambda: observed_order(0, 1, 2),
            lambda: richardson_extrapolate(1, 2, 1, 1), lambda: grid_convergence_index(0, 1, 2, 2),
            lambda: weighted_field_l2([1], [1, 2]), lambda: weighted_field_l2([1], [1], [-1]),
            lambda: hausdorff_distance([1], [[1]]), lambda: robust_linear_slope([1], [1]),
            lambda: availability(0, 1), lambda: relative_overhead(1, 0),
            lambda: vector_relative_error([1], [1, 2]), lambda: effective_sample_size([-1, 1]),
            lambda: monte_carlo_standard_error([1]), lambda: reproducibility_z(1, 2, 0, 0),
            lambda: deterministic_repeat_rate([]), lambda: evidence_closure(2, 1),
            lambda: weighted_score(((1, 2),)),
        )
        for call in invalid_calls:
            with self.assertRaises(InvalidInput): call()


class ExecutionEvidenceHardening(unittest.TestCase):
    def test_command_runner_success_limits_and_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = CommandPolicy(("python3",), (root,), timeout_seconds=2, max_output_bytes=64)
            runner = CommandRunner(policy)
            receipt = runner.run(("python3", "-c", "print('ok')"), cwd=root)
            self.assertEqual(receipt.return_code, 0); self.assertIn("ok", receipt.stdout)
            for argv in ((), ("",), ("bad\x00",)):
                with self.assertRaises(InvalidInput): runner.run(argv, cwd=root)
            with self.assertRaises(BackendUnavailable): runner.resolve("not-authorized")
            with self.assertRaises(BackendUnavailable): runner.resolve("python3/x")
            with self.assertRaises(InvalidInput): CommandPolicy((), (root,))
            with self.assertRaises(InvalidInput): CommandPolicy(("python3",), (root,), timeout_seconds=0)
            tiny = CommandRunner(CommandPolicy(("python3",), (root,), max_output_bytes=1))
            with self.assertRaises(InvalidInput): tiny.run(("python3", "-c", "print('large')"), cwd=root)
            timed = CommandRunner(CommandPolicy(("python3",), (root,), timeout_seconds=.01))
            with self.assertRaises(TimeoutError): timed.run(("python3", "-c", "import time;time.sleep(1)"), cwd=root)

    def test_evidence_manifest_graph_and_hash_edges(self):
        self.assertEqual(json_value({"x": (1, 2)}), {"x": [1, 2]})
        with self.assertRaises(InvalidInput): canonical_json({"x": float("nan")})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); file = root / "a"; file.write_bytes(b"abc")
            self.assertEqual(len(sha256_file(file)), 64); self.assertEqual(len(sha256_file(file, limit_bytes=2)), 64)
            with self.assertRaises(Exception): sha256_file(file, limit_bytes=4)
            artifact = artifact_from_file(file, "test"); self.assertEqual(artifact.size_bytes, 3)
            sub = root / "dir"; sub.mkdir()
            with self.assertRaises(InvalidInput): artifact_from_file(sub, "bad")
            manifest = build_manifest(root); self.assertTrue(verify_manifest(root, manifest))
            file.write_bytes(b"changed")
            with self.assertRaises(Exception): verify_manifest(root, manifest)
            escape = ManifestEntry("../escape", 0, "0" * 64)
            with self.assertRaises(Exception): verify_manifest(root, (escape,))
        graph = EvidenceGraph()
        with self.assertRaises(InvalidInput): graph.add("", {})
        with self.assertRaises(Exception): graph.add("x", {}, ("missing",))
        node = graph.add("x", {}, created_utc="2026-08-20T00:00:00+00:00")
        graph.nodes[node.node_id] = type(node)(node.node_id, node.kind, {"tamper": True}, node.parents, node.created_utc)
        with self.assertRaises(Exception): graph.verify()
        with self.assertRaises(InvalidInput): append_hash_chain("bad", {})


class AdapterPathHardening(unittest.TestCase):
    def command_receipt(self, stdout="", stderr="", code=0):
        return CommandReceipt(("x",), "/x", "0" * 64, "/tmp", code, stdout, stderr, .1)

    def test_cfd_runner_paths(self):
        self.assertEqual(parse_openfoam_residuals("none"), {})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "case.dat").write_text("x")
            foam = OpenFOAMRunner((root,)); foam.runner = Mock()
            foam.runner.run.side_effect = [self.command_receipt(code=1)]
            self.assertEqual(foam.run(root).status, ExecutionStatus.FAIL)
            foam.runner.run.side_effect = [self.command_receipt(), self.command_receipt("Solving for U, Initial residual = 1, Final residual = 1e-9")]
            self.assertEqual(foam.run(root, solver="simpleFoam").status, ExecutionStatus.PASS)
            config = root / "case.cfg"; config.write_text("x")
            su2 = SU2Runner((root,)); su2.runner = Mock(); su2.runner.run.return_value = self.command_receipt()
            self.assertEqual(su2.run(config).status, ExecutionStatus.FAIL)
            (root / "history.csv").write_text("Iter,RMS_DENSITY\n1,-3\n")
            self.assertEqual(su2.run(config).status, ExecutionStatus.PASS)
        with self.assertRaises(InvalidInput): compare_solvers({"a": 1}, {}, {}, {})
        failed = compare_solvers({"a": 1}, {"a": 2}, {"f": np.ones(2)}, {"f": np.zeros(2)}, tolerances=TolerancePolicy(relative=1e-9))
        self.assertFalse(failed.accepted)

    def test_slurm_render_submit_accounting_paths(self):
        self.assertIn("partition=p", render_slurm_script(job_name="a", nodes=1, tasks_per_node=1, walltime="01:00:00", command=("python3", "x"), partition="p"))
        invalid = (
            dict(job_name="bad id", nodes=1, tasks_per_node=1, walltime="01:00:00", command=("x",)),
            dict(job_name="x", nodes=0, tasks_per_node=1, walltime="01:00:00", command=("x",)),
            dict(job_name="x", nodes=1, tasks_per_node=1, walltime="bad", command=("x",)),
            dict(job_name="x", nodes=1, tasks_per_node=1, walltime="01:00:00", command=("bad;",)),
            dict(job_name="x", nodes=1, tasks_per_node=1, walltime="01:00:00", command=("x",), partition="bad id"),
        )
        for row in invalid:
            with self.assertRaises(InvalidInput): render_slurm_script(**row)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); script = root / "job.sh"; script.write_text("#!/bin/bash\n")
            slurm = SlurmQualification((root,)); slurm.runner = Mock(); slurm.runner.policy = Mock(allowed_roots=(root,))
            with self.assertRaises(InvalidInput): slurm.submit(script)
            slurm.runner.run.return_value = self.command_receipt("123;cluster\n")
            self.assertEqual(slurm.submit(script, authorized=True).job_id, "123")
            slurm.runner.run.return_value = self.command_receipt("bad", code=1)
            with self.assertRaises(BackendUnavailable): slurm.submit(script, authorized=True)
            slurm.runner.run.return_value = self.command_receipt("bad")
            with self.assertRaises(InvalidInput): slurm.submit(script, authorized=True)
            with self.assertRaises(InvalidInput): slurm.accounting("bad")
            line = "123|job|c|p|2|8|00:01|COMPLETED|0:0|1M|1\n"
            slurm.runner.run.return_value = self.command_receipt(line)
            self.assertTrue(slurm.accounting("123").successful)
            slurm.runner.run.return_value = self.command_receipt("")
            self.assertEqual(slurm.accounting("123").status, ExecutionStatus.NOT_EXECUTED)

    def test_cli_all_routes(self):
        for command, expected in (("backends", 0), ("capabilities", 0), ("qualification", 2), ("selftest", 0)):
            output = StringIO()
            with redirect_stdout(output): self.assertEqual(cli34.main((command,)), expected)
            self.assertIsInstance(json.loads(output.getvalue()), dict)
        self.assertIn("PASS", cli34._encode(ExecutionStatus.PASS))
        with self.assertRaises(TypeError): cli34._encode(object())
        with self.assertRaises(SystemExit): cli34.main(())
        with patch.object(cli34, "compile_prompt", return_value={"ok": True}):
            output = StringIO()
            with redirect_stdout(output): self.assertEqual(cli34.main(("compile-requirements", "a", "b")), 0)


class MockedExternalAdapterCoverage(unittest.TestCase):
    """Mocks exercise adapter logic only and explicitly earn no physical credit."""

    def test_gpu_adapter_logic(self):
        class Runtime:
            @staticmethod
            def getDeviceCount(): return 1
            @staticmethod
            def getDeviceProperties(device): return {"name": b"Fake GPU"}
            @staticmethod
            def runtimeGetVersion(): return 12000
        class Null:
            @staticmethod
            def synchronize(): return None
        fake_cp = types.SimpleNamespace(
            cuda=types.SimpleNamespace(runtime=Runtime, Device=lambda: types.SimpleNamespace(id=0), Stream=types.SimpleNamespace(null=Null())),
            asarray=np.asarray, tanh=np.tanh, asnumpy=np.asarray,
        )
        original = sys.modules.get("cupy"); sys.modules["cupy"] = fake_cp
        try:
            with patch("supermoon34.gpu.importlib.util.find_spec", side_effect=lambda name: object() if name == "cupy" else None), patch("supermoon34.gpu._nvidia_telemetry", return_value={"uuid": "u", "driver_version": "d"}):
                self.assertTrue(probe_gpu().available)
                receipt = GPUQualification().run(32); self.assertEqual(receipt.status, ExecutionStatus.PASS)
        finally:
            if original is None: sys.modules.pop("cupy", None)
            else: sys.modules["cupy"] = original
        with self.assertRaises(InvalidInput): GPUQualification().run(0)
        completed = types.SimpleNamespace(returncode=0, stdout="u,n,d,10,1,2,3\n")
        with patch("supermoon34.gpu.shutil.which", return_value="/bin/nvidia-smi"), patch("supermoon34.gpu.subprocess.run", return_value=completed):
            self.assertEqual(_nvidia_telemetry()["uuid"], "u")

    def test_petsc_adapter_logic(self):
        class ResidualVec:
            def axpy(self, *args): pass
            def norm(self): return 0.0
            def destroy(self): pass
        class Vec:
            def set(self, value): pass
            def setValue(self, *args): pass
            def assemblyBegin(self): pass
            def assemblyEnd(self): pass
            def duplicate(self): return ResidualVec()
            def axpy(self, *args): pass
            def norm(self): return 1.0
            def getArray(self, readonly=True): return np.array([1.0, 2.0])
            def destroy(self): pass
        class Mat:
            def createAIJ(self, **kwargs): return self
            def setUp(self): pass
            def getOwnershipRange(self): return (0, 4)
            def setValue(self, *args): pass
            def setValues(self, *args): pass
            def assemblyBegin(self): pass
            def assemblyEnd(self): pass
            def createVecs(self): return Vec(), Vec()
            def mult(self, *args): pass
            def destroy(self): pass
        class PC:
            def getType(self): return "jacobi"
        class KSP:
            def create(self, comm): return self
            def setOperators(self, matrix): pass
            def setTolerances(self, **kwargs): pass
            def setFromOptions(self): pass
            def solve(self, rhs, solution): pass
            def getConvergedReason(self): return 1
            def getIterationNumber(self): return 2
            def getResidualNorm(self): return 0.0
            def getType(self): return "cg"
            def getPC(self): return PC()
            def destroy(self): pass
        class Comm:
            def Get_size(self): return 2
            def allgather(self, value): return [value, value]
        MPI = types.SimpleNamespace(COMM_WORLD=Comm(), Get_library_version=lambda: "fake MPI")
        PETSc = types.SimpleNamespace(Mat=Mat, KSP=KSP, COMM_WORLD=object(), Sys=types.SimpleNamespace(getVersion=lambda: (3, 20, 0)))
        original_mpi, original_petsc = sys.modules.get("mpi4py"), sys.modules.get("petsc4py")
        sys.modules["mpi4py"] = types.SimpleNamespace(MPI=MPI); sys.modules["petsc4py"] = types.SimpleNamespace(PETSc=PETSc)
        try:
            with patch("supermoon34.petsc_mpi.importlib.util.find_spec", return_value=object()):
                receipt = PetscDistributedSolver().solve_poisson_1d(4, required_ranks=2)
                self.assertEqual(receipt.status, ExecutionStatus.PASS)
                with self.assertRaises(InvalidInput): PetscDistributedSolver().solve_poisson_1d(4, required_ranks=3)
        finally:
            if original_mpi is None: sys.modules.pop("mpi4py", None)
            else: sys.modules["mpi4py"] = original_mpi
            if original_petsc is None: sys.modules.pop("petsc4py", None)
            else: sys.modules["petsc4py"] = original_petsc
        with self.assertRaises(InvalidInput): PetscDistributedSolver().solve_poisson_1d(2)

    def test_cad_adapter_logic(self):
        class Shape:
            wrapped = object()
            def isValid(self): return True
            def Volume(self): return 100.0
        class Workplane:
            def __init__(self, *args): pass
            def box(self, *args): return self
            def edges(self, *args): return self
            def fillet(self, *args): return self
            def faces(self, *args): return self
            def workplane(self, *args): return self
            def hole(self, *args): return self
            def val(self): return Shape()
        def export(shape, target, exportType): Path(target).write_text(exportType)
        fake_cq = types.SimpleNamespace(
            Workplane=Workplane, exporters=types.SimpleNamespace(export=export),
            importers=types.SimpleNamespace(importStep=lambda path: Workplane()),
        )
        class Analyzer:
            def __init__(self, wrapped): pass
            def IsValid(self): return True
        modules = {
            "cadquery": fake_cq, "OCP": types.ModuleType("OCP"),
            "OCP.BRepCheck": types.SimpleNamespace(BRepCheck_Analyzer=Analyzer),
            "OCP.Standard": types.SimpleNamespace(Standard_Version=lambda: "7.8"),
        }
        originals = {name: sys.modules.get(name) for name in modules}; sys.modules.update(modules)
        try:
            with patch("supermoon34.cad.importlib.util.find_spec", return_value=object()), patch("supermoon34.cad.importlib.metadata.version", return_value="1.0"):
                with tempfile.TemporaryDirectory() as directory:
                    receipt = CadQualificationRunner().run_reference(Path(directory))
                    self.assertEqual(receipt.status, ExecutionStatus.PASS)
        finally:
            for name, value in originals.items():
                if value is None: sys.modules.pop(name, None)
                else: sys.modules[name] = value


class AerospaceBoundaryHardening(unittest.TestCase):
    def test_digital_thread_boundaries(self):
        with self.assertRaises(InvalidInput): Requirement("", "s", "r", "v")
        with self.assertRaises(InvalidInput): Requirement("x", "s", "r", "v", version=0)
        with self.assertRaises(Exception): Requirement("x", "s", "r", "v", state=RequirementState.VERIFIED)
        with self.assertRaises(InvalidInput): Interface("", "p", "c", "s", "u", 1, 0)
        with self.assertRaises(InvalidInput): Interface("i", "p", "c", "s", "u", 0, 0)
        thread = DigitalThread(); root = Requirement("ROOT", "s", "r", "v", allocation_ids=("a",)); thread.add_requirement(root)
        with self.assertRaises(InvalidInput): thread.add_requirement(root)
        with self.assertRaises(InvalidInput): thread.add_requirement(Requirement("x", "s", "r", "v", parent_ids=("missing",)))
        with self.assertRaises(InvalidInput): thread.revise("ROOT", version=2)
        interface = Interface("i", "p", "c", "s", "u", 1, 0); thread.add_interface(interface)
        with self.assertRaises(InvalidInput): thread.add_interface(interface)
        report = thread.traceability(); self.assertEqual(report["requirements"], 1)

    def test_structures_boundaries(self):
        with self.assertRaises(InvalidInput): StructuralAssessment(0, 1, 1, 1)
        model = StructuralAssessment(1, 1, 1, 1)
        for call in (
            lambda: model.bending_stress(1, -1, 1), lambda: model.yield_margin(-1),
            lambda: model.euler_buckling(0, 1), lambda: model.miner_damage(()),
            lambda: model.miner_damage(((-1, 1),)), lambda: model.thermal_stress(0, 1, 1),
        ):
            with self.assertRaises(InvalidInput): call()
        self.assertGreater(model.euler_buckling(1, 1), 0)
        self.assertGreaterEqual(model.thermal_stress(1, .1, -1), 0)

    def test_design_systems_flight_boundaries(self):
        with self.assertRaises(InvalidInput): isa_troposphere(20_000)
        with self.assertRaises(InvalidInput): MissionSegment("", 1, 1, 0, 1, 0)
        with self.assertRaises(InvalidInput): AircraftDesignModel(0, 1, 1, 1, 1)
        design = AircraftDesignModel(1, 1, 1, 1, 1)
        with self.assertRaises(InvalidInput): design.performance_point(0)
        with self.assertRaises(InvalidInput): design.mission_fuel_fraction(())
        with self.assertRaises(InvalidInput): BudgetItem("", 1, 1)
        system = SystemArchitecture()
        with self.assertRaises(InvalidInput): system.set_limit("", 1)
        with self.assertRaises(InvalidInput): system.add_item("missing", BudgetItem("x", 1, 1))
        system.set_limit("x", 1); item = BudgetItem("i", 1, 1); system.add_item("x", item)
        with self.assertRaises(InvalidInput): system.add_item("x", item)
        with self.assertRaises(InvalidInput): system.set_failure_probability("", .1)
        with self.assertRaises(InvalidInput): system.independent_union_probability(())
        self.assertEqual(set(system.closure_report()), {"x"})
        with self.assertRaises(InvalidInput): quaternion_rotation([0, 0, 0, 0])
        with self.assertRaises(InvalidInput): FlightDynamicsModel(0, np.eye(3))
        with self.assertRaises(InvalidInput): FlightDynamicsModel(1, np.zeros((3, 3)))
        model = FlightDynamicsModel(1, np.eye(3))
        with self.assertRaises(InvalidInput): model.trim_residual([0, 0, 0], [0, 0, 0], 0)
        with self.assertRaises(InvalidInput): model.continuous_lqr([[1]], [[1, 2]], [[1]], [[1]])


if __name__ == "__main__": unittest.main()
