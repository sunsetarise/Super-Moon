from __future__ import annotations

from dataclasses import replace
import unittest

from supermoon36.certification import (
    ObjectiveEvidence, READINESS_AREAS, assess_readiness, validate_assurance_case,
)
from supermoon36.contracts import ValidationError
from supermoon36.industrial import (
    ControlEvidence, INDUSTRIAL_DOMAINS, assess_industrial_controls, validate_traceability,
)


class IndustrialTests(unittest.TestCase):
    def controls(self):
        return tuple(ControlEvidence(domain, f"P-{index}", "owner", "reviewer", (f"e:{index}",), 0, 0, True) for index, domain in enumerate(INDUSTRIAL_DOMAINS))

    def test_complete_controls(self):
        rows = self.controls(); decision = assess_industrial_controls(rows)
        self.assertTrue(decision.passed); self.assertEqual(decision.domains_complete, 50)
        failed = list(rows); failed[0] = replace(failed[0], effective=False, findings_open=1)
        self.assertFalse(assess_industrial_controls(failed).passed)
        mandatory = list(rows); mandatory[0] = replace(mandatory[0], mandatory_findings_open=1)
        self.assertFalse(assess_industrial_controls(mandatory).passed)
        with self.assertRaises(ValidationError): assess_industrial_controls(rows[:-1])

    def test_control_rejections(self):
        row = self.controls()[0]
        invalid = (replace(row, domain="bad"), replace(row, owner=""), replace(row, independent_reviewer="owner"), replace(row, evidence_ids=()), replace(row, findings_open=-1))
        for value in invalid:
            with self.assertRaises(ValidationError): value.validate()

    def test_traceability(self):
        links = {"R1": {key: (key,) for key in ("source", "test", "evidence", "risk", "release")}}
        self.assertEqual(validate_traceability(links), 1.0)
        links["R2"] = {key: (() if key == "test" else (key,)) for key in ("source", "test", "evidence", "risk", "release")}
        self.assertEqual(validate_traceability(links), 0.5)
        for value in ({}, {"R": {}}, {"": {key: ("x",) for key in ("source", "test", "evidence", "risk", "release")}}):
            with self.assertRaises(ValidationError): validate_traceability(value)


class CertificationTests(unittest.TestCase):
    def objectives(self):
        return tuple(ObjectiveEvidence(area, f"OBJ-{index}", True, (f"e:{index}",), True, "reviewer", True, ()) for index, area in enumerate(READINESS_AREAS))

    def test_readiness(self):
        rows = self.objectives(); decision = assess_readiness(rows, True)
        self.assertTrue(decision.readiness_passed); self.assertFalse(decision.certification_claim_allowed)
        self.assertFalse(assess_readiness(rows, False).readiness_passed)
        failed = list(rows); failed[0] = replace(failed[0], compliant=False, open_actions=("A1",))
        self.assertFalse(assess_readiness(failed, True).readiness_passed)
        with self.assertRaises(ValidationError): assess_readiness(rows[:-1], True)
        with self.assertRaises(ValidationError): assess_readiness(tuple(replace(row, applicable=False, evidence_ids=(), compliant=False) for row in rows), True)

    def test_objective_rejections(self):
        row = self.objectives()[0]
        invalid = (
            replace(row, area="bad"), replace(row, objective_id=""), replace(row, evidence_ids=()),
            replace(row, independent_reviewer=None), replace(row, open_actions=("A",)),
            replace(row, compliant=False, authority_accepted=True),
        )
        for value in invalid:
            with self.assertRaises(ValidationError): value.validate()

    def test_assurance_case(self):
        claims = {
            "C1": {"subclaims": ("C2",), "evidence": (), "assumptions": (), "defeaters": ()},
            "C2": {"subclaims": (), "evidence": ("E1",), "assumptions": (), "defeaters": ()},
        }
        self.assertTrue(validate_assurance_case(claims, "C1"))
        with self.assertRaises(ValidationError): validate_assurance_case(claims, "missing")
        with self.assertRaises(ValidationError): validate_assurance_case({"C": {}}, "C")
        with self.assertRaises(ValidationError): validate_assurance_case({"C": {"subclaims": (), "evidence": (), "assumptions": (), "defeaters": ()}}, "C")
        with self.assertRaises(ValidationError): validate_assurance_case({"C": {"subclaims": ("X",), "evidence": (), "assumptions": (), "defeaters": ()}}, "C")
        cyclic = {"C": {"subclaims": ("C",), "evidence": (), "assumptions": (), "defeaters": ()}}
        with self.assertRaises(ValidationError): validate_assurance_case(cyclic, "C")


if __name__ == "__main__": unittest.main()

