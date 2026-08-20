from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from supermoon36.contracts import ResultState, ValidationError
from supermoon36.registry import parse_master_prompt
from supermoon36.workitems import pending_work_item, read_work_items, validate_work_items, write_work_items


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "spec/SUPER_MOON_35_TO_36_15000_ADVANCED_QUALIFICATION_METHODOLOGIES_MASTER_PROMPT.txt"


class WorkItemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = parse_master_prompt(PROMPT)
        cls.rows = tuple(pending_work_item(row, prompt_sha256="a" * 64, registry_sha256="b" * 64, completion_timestamp="2026-08-20T00:00:00+00:00") for row in cls.records)

    def test_complete_schema_and_cardinality(self):
        self.assertTrue(validate_work_items(self.rows)); self.assertEqual(len(self.rows), 15000)
        self.assertEqual(self.rows[0].result_state, ResultState.BLOCKED)
        self.assertEqual(self.rows[2500].result_state, ResultState.NOT_EXECUTED)
        self.assertEqual(set(self.rows[0].payload()) - {"format"}, {
            "methodology_id", "phase_id", "technique_kernel", "qualification_lens", "objective",
            "prerequisites", "commands_or_procedure", "configuration_id", "hardware_and_environment_id",
            "input_artifact_ids_and_hashes", "raw_evidence_ids_and_hashes", "quantitative_metrics",
            "pre_registered_acceptance_criteria", "result_state", "deviations", "problem_report_ids",
            "blocker_ids", "responsible_owner", "independent_reviewer", "review_signature", "completion_timestamp",
        })

    def test_roundtrip_and_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "items.jsonl.gz"; write_work_items(path, self.rows)
            restored = read_work_items(path); self.assertEqual(restored[0], self.rows[0])
            path.write_bytes(b"bad")
            with self.assertRaises(ValidationError): read_work_items(path)
        with self.assertRaises(ValidationError): validate_work_items(self.rows[:-1])
        with self.assertRaises(ValidationError): replace(self.rows[0], blocker_ids=()).validate()
        with self.assertRaises(ValidationError): replace(self.rows[0], result_state=ResultState.PASS).validate()


if __name__ == "__main__": unittest.main()
