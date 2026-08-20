from __future__ import annotations

from dataclasses import replace
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from supermoon36.contracts import ResultState, ValidationError
from supermoon36.methodology import ExecutionContext, MethodologyExecutor, phase_completion
from supermoon36.registry import MethodologyRegistry, parse_master_prompt, slug, stream_jsonl_gz, validate_registry


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "spec/SUPER_MOON_35_TO_36_15000_ADVANCED_QUALIFICATION_METHODOLOGIES_MASTER_PROMPT.txt"


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = parse_master_prompt(PROMPT)
        cls.registry = MethodologyRegistry(cls.records)

    def test_exact_factorial_registry(self):
        self.assertEqual(len(self.records), 15000)
        self.assertTrue(validate_registry(self.records))
        summary = self.registry.summary()
        self.assertEqual(summary["records"], 15000)
        self.assertEqual(summary["unique_technique_bindings"], 300)
        self.assertEqual(summary["unique_lens_bindings"], 50)
        self.assertEqual(summary["phases"], {f"P{i:02d}": 2500 for i in range(1, 7)})
        self.assertEqual(len(self.registry.techniques("P01")), 50)
        self.assertEqual(len(self.registry.lenses()), 50)

    def test_lookup_phase_and_errors(self):
        row = self.registry.get("P03-M2500"); self.assertEqual(row.phase_id, "P03")
        self.assertEqual(len(self.registry.phase("P06")), 2500)
        with self.assertRaises(ValidationError): self.registry.get("missing")
        with self.assertRaises(ValidationError): self.registry.phase("P99")
        with self.assertRaises(ValidationError): slug("!!!")

    def test_registry_roundtrip_and_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.jsonl.gz"
            self.registry.write_jsonl_gz(path)
            restored = MethodologyRegistry.read_jsonl_gz(path)
            self.assertEqual(restored.summary(), self.registry.summary())
            self.assertEqual(sum(1 for _ in stream_jsonl_gz(path)), 15000)
            path.write_bytes(b"bad")
            with self.assertRaises(ValidationError): MethodologyRegistry.read_jsonl_gz(path)

    def test_record_tamper_and_registry_rejections(self):
        row = self.records[0]
        for change in (
            {"format": "bad"}, {"methodology_id": "bad"}, {"phase_id": "P02"},
            {"technique_kernel": ""}, {"record_sha256": "0" * 64},
        ):
            with self.assertRaises(ValidationError): replace(row, **change).validate()
        with self.assertRaises(ValidationError): validate_registry(self.records[:-1])
        with self.assertRaises(ValidationError): validate_registry((*self.records[:-1], self.records[0]))

    def test_prompt_parser_rejects_truncation_and_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.txt"
            path.write_text("[P01-M0001] A x B\n  TECHNIQUE: a\n")
            with self.assertRaises(ValidationError): parse_master_prompt(path)


class MethodologyExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = MethodologyRegistry(parse_master_prompt(PROMPT))

    def evidence_for(self, row):
        return {
            "techniques": {row.technique_binding: {"executed": True, "accepted": True, "metrics": {"value": 1.0}}},
            "lenses": {row.lens_binding: {"executed": True, "raw_evidence_retained": True, "pre_registered_gate_used": True, "provenance_complete": True}},
            "evidence_ids": ["evidence:one"],
        }

    def test_local_method_passes_with_review(self):
        row = self.registry.get("P01-M0001")
        context = ExecutionContext(self.evidence_for(row), independent_review=True, reviewer="reviewer")
        result = MethodologyExecutor().execute(row, context)
        self.assertEqual(result.state, ResultState.PASS); self.assertEqual(result.blocker_ids, ())

    def test_physical_method_requires_execution_and_authorization(self):
        row = self.registry.get("P02-M0001")
        evidence = self.evidence_for(row)
        result = MethodologyExecutor().execute(row, ExecutionContext(evidence, independent_review=True, reviewer="r"))
        self.assertEqual(result.state, ResultState.NOT_EXECUTED); self.assertIn("G04", result.blocker_ids)
        passed = MethodologyExecutor().execute(row, ExecutionContext(evidence, True, True, "r", True))
        self.assertEqual(passed.state, ResultState.PASS)

    def test_missing_evidence_blocks(self):
        row = self.registry.get("P05-M0001")
        result = MethodologyExecutor().execute(row, ExecutionContext({}))
        self.assertEqual(result.state, ResultState.BLOCKED)
        self.assertTrue(result.limitations)
        with self.assertRaises(ValidationError): MethodologyExecutor().execute(row, ExecutionContext({"evidence_ids": "bad"}))

    def test_custom_handlers_and_phase_completion_validation(self):
        def technique(row, context): return {"technique": True}, {"m": 1}, ()
        def lens(row, context): return {"lens": True}, ()
        row = self.registry.get("P06-M0001")
        executor = MethodologyExecutor(technique, lens)
        result = executor.execute(row, ExecutionContext({"evidence_ids": ["e"]}, independent_review=True, reviewer="r"))
        self.assertEqual(result.state, ResultState.PASS)
        phase = self.registry.phase("P06")
        results = executor.evaluate_phase(phase, ExecutionContext({"evidence_ids": ["e"]}, independent_review=True, reviewer="r"))
        self.assertEqual(phase_completion(results), 1.0)
        with self.assertRaises(ValidationError): executor.evaluate_phase(phase[:-1], ExecutionContext({}))
        with self.assertRaises(ValidationError): phase_completion(results[:-1])


if __name__ == "__main__": unittest.main()
