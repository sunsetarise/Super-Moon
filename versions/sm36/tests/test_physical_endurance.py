from __future__ import annotations

from dataclasses import replace
import hashlib
import math
import unittest

from supermoon36.contracts import ValidationError, canonical_json
from supermoon36.endurance import Heartbeat, ReproductionReceipt, assess_endurance, heartbeat_from_mapping, validate_heartbeat_chain
from supermoon36.physical import (
    CADReceipt, CUDAReceipt, GridPoint, capability_matrix, conservation_balance,
    cross_solver_discrepancy, detect_capability, grid_convergence, validate_cad_matrix,
)


def heartbeat(sequence, elapsed, memory=1000, handles=5, progress=None, previous="0" * 64):
    body = {"sequence": sequence, "elapsed_monotonic_seconds": elapsed, "resident_bytes": memory, "open_handles": handles, "progress_counter": sequence + 1 if progress is None else progress, "previous_sha256": previous}
    return Heartbeat(**body, chain_sha256=hashlib.sha256(canonical_json(body)).hexdigest())


def heartbeat_chain(hours):
    rows = []; previous = "0" * 64
    for sequence, elapsed in enumerate(range(0, hours * 3600 + 1, 60)):
        row = heartbeat(sequence, elapsed, previous=previous); rows.append(row); previous = row.chain_sha256
    return tuple(rows)


def cad(route, **changes):
    values = dict(translator_done=True, brep_valid=True, solids=1, shells=1, faces=6, edges=12, vertices=8, volume_relative_drift=1e-10, area_relative_drift=1e-10, centroid_drift_m=1e-10, units_preserved=True, metadata_preserved=True, evidence_ids=("e",))
    values.update(changes); return CADReceipt(route, **values)


class PhysicalTests(unittest.TestCase):
    def test_capability_probe(self):
        rows = capability_matrix(); self.assertEqual({row.track_id for row in rows}, {"cad", "cuda", "openfoam", "petsc_mpi", "slurm", "su2"})
        self.assertTrue(all(row.reason for row in rows))
        with self.assertRaises(ValidationError): detect_capability("invented")

    def test_grid_convergence(self):
        result = grid_convergence((GridPoint(0.25, 1.0625), GridPoint(0.5, 1.25), GridPoint(1.0, 2.0)))
        self.assertAlmostEqual(result.observed_order, 2.0)
        invalid = (
            ((GridPoint(1, 1),), 1.25),
            ((GridPoint(0.25, 1), GridPoint(0.5, 1), GridPoint(1, 2)), 1.25),
            ((GridPoint(0.25, 1), GridPoint(0.5, 2), GridPoint(1, 1)), 1.25),
            ((GridPoint(0, 1), GridPoint(0.5, 2), GridPoint(1, 3)), 1.25),
        )
        for points, safety in invalid:
            with self.assertRaises(ValidationError): grid_convergence(points, safety)
        with self.assertRaises(ValidationError): grid_convergence((GridPoint(0.25, 1), GridPoint(0.5, 2), GridPoint(1, 3)), 1)

    def test_conservation_and_cross_solver(self):
        self.assertEqual(conservation_balance(10, 9, 1, 0, 10), 0)
        with self.assertRaises(ValidationError): conservation_balance(1, 1, 0, 0, 0)
        result = cross_solver_discrepancy({"CL": .5, "CD": .02}, {"CL": .51, "CD": .021}, ("CL", "CD"), .1)
        self.assertIn("CL", result)
        with self.assertRaises(ValidationError): cross_solver_discrepancy({}, {}, (), .1)
        with self.assertRaises(ValidationError): cross_solver_discrepancy({"CL": 1}, {}, ("CL",), .1)
        with self.assertRaises(ValidationError): cross_solver_discrepancy({"CL": math.nan}, {"CL": 1}, ("CL",), .1)

    def test_cad_matrix(self):
        rows = [cad(route) for route in ("STEP", "IGES", "ASSEMBLY_STEP", "TESSELLATION")]
        self.assertTrue(validate_cad_matrix(rows)); self.assertTrue(all(row.passes() for row in rows))
        self.assertFalse(cad("STEP", volume_relative_drift=1e-3).passes())
        with self.assertRaises(ValidationError): cad("BAD").passes()
        with self.assertRaises(ValidationError): cad("STEP", faces=-1).passes()
        with self.assertRaises(ValidationError): validate_cad_matrix(rows[:-1])

    def test_cuda_receipt(self):
        row = CUDAReceipt("uuid", "gpu", "driver", "runtime", "8.0", 10, False, 1e-12, 0, (1.0, 1.0, 1.0), 70, False, ("e",))
        self.assertTrue(row.passes())
        self.assertFalse(replace(row, cpu_fallback_detected=True).passes())
        self.assertFalse(replace(row, sanitizer_errors=1).passes())
        self.assertFalse(replace(row, timing_samples_ms=(1.0, 2.0, 10.0)).passes())
        with self.assertRaises(ValidationError): replace(row, device_uuid="").passes()
        with self.assertRaises(ValidationError): replace(row, timing_samples_ms=(1.0,)).passes()


class EnduranceTests(unittest.TestCase):
    def test_heartbeat_and_profiles(self):
        rows = heartbeat_chain(24); self.assertTrue(validate_heartbeat_chain(rows))
        self.assertTrue(assess_endurance(rows, 24, 1).passed)
        self.assertTrue(assess_endurance(heartbeat_chain(72), 72, 2).passed)
        self.assertFalse(assess_endurance(heartbeat_chain(23), 24, 1).passed)
        growing = list(heartbeat_chain(24)); last = growing[-1]
        growing[-1] = heartbeat(last.sequence, last.elapsed_monotonic_seconds, memory=2000, previous=last.previous_sha256)
        self.assertFalse(assess_endurance(tuple(growing), 24, 1).passed)
        with self.assertRaises(ValidationError): assess_endurance(rows, 1, 1)
        with self.assertRaises(ValidationError): validate_heartbeat_chain((rows[0],))

    def test_heartbeat_rejections_and_mapping(self):
        row = heartbeat(0, 0); self.assertEqual(heartbeat_from_mapping(row.body() | {"chain_sha256": row.chain_sha256}), row)
        for bad in (replace(row, sequence=-1), replace(row, elapsed_monotonic_seconds=math.nan), replace(row, resident_bytes=-1), replace(row, chain_sha256="0" * 64)):
            with self.assertRaises(ValidationError): bad.validate()
        with self.assertRaises(ValidationError): heartbeat_from_mapping({})
        second = heartbeat(1, 0, previous=row.chain_sha256)
        with self.assertRaises(ValidationError): validate_heartbeat_chain((row, second))

    def test_reproduction(self):
        row = ReproductionReceipt("m1", "m2", "o1", "o2", "l1", "l2", True, True, True, True, ("e",))
        self.assertTrue(row.passes())
        self.assertFalse(replace(row, second_machine_fingerprint="m1").passes())
        self.assertFalse(replace(row, second_operator_fingerprint="o1").passes())
        self.assertFalse(replace(row, clean_workspace=False).passes())
        with self.assertRaises(ValidationError): replace(row, first_machine_fingerprint="").passes()


if __name__ == "__main__": unittest.main()
