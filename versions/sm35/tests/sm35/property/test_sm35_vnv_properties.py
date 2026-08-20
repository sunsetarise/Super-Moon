from __future__ import annotations

import math
import unittest

from supermoon35.contracts import ValidationError
from supermoon35.vnv import (
    CadRoundTrip, NeutralCFDCase, TraceLink, compare_cfd, traceability_closure,
    validate_cad_matrix, validate_endurance, validate_reproduction,
)


def cfd_case(**changes):
    values = dict(
        case_id="naca0012", units="SI", axes=("X_FORWARD", "Y_RIGHT", "Z_DOWN"),
        reference_area_m2=1.0, reference_length_m=1.0, moment_center_m=(0.25, 0, 0),
        density_kg_m3=1.225, velocity_m_s=50.0, angle_of_attack_deg=2.0,
        boundaries={"farfield": "FARFIELD", "airfoil": "WALL"}, quantities=("CL", "CD"),
        tolerance_fraction=0.05,
    )
    values.update(changes)
    return NeutralCFDCase(**values)


def cad_row(route: str, **changes):
    values = dict(brep_valid=True, volume_drift=1e-10, area_drift=1e-10, centroid_drift_m=1e-10, topology_preserved=True, translator_status="DONE", evidence_ids=("e",))
    values.update(changes)
    return CadRoundTrip(route, **values)


class VNVPropertyTests(unittest.TestCase):
    def test_cfd_symmetry_and_threshold(self):
        case = cfd_case()
        first = {"CL": 0.5, "CD": 0.02}
        second = {"CL": 0.51, "CD": 0.0205}
        ab = compare_cfd(case, first, second)
        ba = compare_cfd(case, second, first)
        self.assertEqual(ab.normalized_discrepancies, ba.normalized_discrepancies)
        self.assertTrue(ab.accepted)
        failed = compare_cfd(case, first, {"CL": 0.7, "CD": 0.02})
        self.assertEqual(failed.open_quantities, ("CL",))

    def test_cfd_validation_failures(self):
        invalid_cases = (
            cfd_case(units="US"), cfd_case(reference_area_m2=0), cfd_case(angle_of_attack_deg=100),
            cfd_case(moment_center_m=(0, 0)), cfd_case(boundaries={}),
        )
        for case in invalid_cases:
            with self.assertRaises(ValidationError):
                case.validate()
        with self.assertRaises(ValidationError):
            compare_cfd(cfd_case(), {"CL": 1}, {"CL": 1})
        with self.assertRaises(ValidationError):
            compare_cfd(cfd_case(), {"CL": math.nan, "CD": 1}, {"CL": 1, "CD": 1})

    def test_complete_cad_matrix(self):
        routes = ("CADQUERY_OCCT_STEP_OCCT", "OCCT_IGES_OCCT", "ASSEMBLY_STEP_ASSEMBLY", "SOURCE_TESSELLATION_COMPARE")
        self.assertTrue(validate_cad_matrix([cad_row(route) for route in routes]))
        self.assertFalse(validate_cad_matrix([cad_row(route, brep_valid=False) if index == 0 else cad_row(route) for index, route in enumerate(routes)]))
        with self.assertRaises(ValidationError):
            validate_cad_matrix([cad_row(routes[0])])

    def test_cad_row_validation_and_limits(self):
        with self.assertRaises(ValidationError):
            cad_row("UNKNOWN").passes()
        with self.assertRaises(ValidationError):
            cad_row("OCCT_IGES_OCCT", volume_drift=-1).passes()
        self.assertFalse(cad_row("OCCT_IGES_OCCT", evidence_ids=()).passes())
        self.assertFalse(cad_row("OCCT_IGES_OCCT", volume_drift=1e-3).passes())

    def test_endurance_real_time_contract(self):
        self.assertTrue(validate_endurance(24 * 3600, 24, (60, 61), True, 1))
        self.assertTrue(validate_endurance(72 * 3600, 72, (60,), True, 2))
        self.assertFalse(validate_endurance(10, 24, (), True, 1))
        self.assertFalse(validate_endurance(72 * 3600, 72, (121,), True, 2))
        for args in ((1, 1, (), True, 1), (math.nan, 24, (), True, 1), (1, 24, (-1,), True, 1)):
            with self.assertRaises(ValidationError):
                validate_endurance(*args)

    def test_independent_reproduction(self):
        self.assertTrue(validate_reproduction("m1", "m2", "o1", "o2", True, True, ("e",)))
        self.assertFalse(validate_reproduction("m1", "m1", "o1", "o2", True, True, ("e",)))
        self.assertFalse(validate_reproduction("m1", "m2", "o1", "o1", True, True, ("e",)))
        self.assertFalse(validate_reproduction("m1", "m2", "o1", "o2", False, True, ("e",)))
        with self.assertRaises(ValidationError):
            validate_reproduction("", "m2", "o1", "o2", True, True, ("e",))

    def test_traceability_closure(self):
        complete = TraceLink("R1", ("m:f",), ("T1",), ("E1",), ("SYS",))
        incomplete = TraceLink("R2", (), ("T2",), ("E2",), ("SYS",))
        self.assertEqual(traceability_closure((complete, incomplete)), 0.5)
        with self.assertRaises(ValidationError):
            traceability_closure(())
        with self.assertRaises(ValidationError):
            traceability_closure((complete, complete))
        with self.assertRaises(ValidationError):
            TraceLink("", ("s",), ("t",), ("e",), ("a",)).complete()


if __name__ == "__main__":
    unittest.main()
