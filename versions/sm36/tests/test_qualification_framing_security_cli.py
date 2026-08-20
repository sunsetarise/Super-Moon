from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
from io import BytesIO, StringIO
import ast
import json
from pathlib import Path
import tempfile
import unittest

from supermoon36.cli import main
from supermoon36.contracts import ResultState, ValidationError
from supermoon36.framing import encode_frame, parse_frames, reconstruct
from supermoon36.qualification import GATE_WEIGHTS, GateResult, candidate_decision, candidate_gates, score_release
from supermoon36.security import audit_source, call_name, validate_sbom


class QualificationTests(unittest.TestCase):
    def closed(self):
        return {gate: GateResult(gate, 1.0, ResultState.PASS, (f"e:{gate}",), (), "reviewer") for gate in GATE_WEIGHTS}

    def test_pass_block_fail(self):
        closed = self.closed(); passed = score_release(closed, True)
        self.assertTrue(passed.passed); self.assertEqual(passed.score, 100); self.assertEqual(passed.state, ResultState.QUALIFIED)
        blocked = dict(closed); blocked["G04"] = GateResult("G04", .5, ResultState.BLOCKED, (), ("b:G04",), None)
        self.assertFalse(score_release(blocked, True).passed)
        self.assertEqual(score_release(closed, False).state, ResultState.FAIL)
        candidate = candidate_decision(); self.assertFalse(candidate.passed); self.assertIn("G04", candidate.open_gates)
        self.assertEqual(set(candidate_gates()), set(GATE_WEIGHTS))

    def test_gate_rejections(self):
        row = self.closed()["G01"]
        invalid = (
            replace(row, gate_id="G99"), replace(row, completion=-1), replace(row, state=ResultState.PASS, evidence_ids=()),
            replace(row, state=ResultState.BLOCKED, blocker_ids=()),
        )
        for value in invalid:
            with self.assertRaises(ValidationError): value.validate()
        with self.assertRaises(ValidationError): score_release({}, True)
        mismatched = self.closed(); mismatched["G01"] = replace(mismatched["G01"], gate_id="G02")
        with self.assertRaises(ValidationError): score_release(mismatched, True)


class FramingTests(unittest.TestCase):
    def test_roundtrip_and_reconstruct(self):
        payload = encode_frame("a.txt", b"hello") + encode_frame("bin/a.bin", bytes(range(64)))
        rows = tuple(parse_frames(BytesIO(payload))); self.assertEqual(rows[0].data, b"hello")
        with tempfile.TemporaryDirectory() as directory:
            outputs = reconstruct(BytesIO(payload), Path(directory)); self.assertEqual(len(outputs), 2)
            with self.assertRaises(ValidationError): reconstruct(BytesIO(payload), Path(directory))

    def test_parser_rejections(self):
        valid = encode_frame("a", b"x")
        noncanonical = valid.replace(b"eA==", b"eB==")
        invalid = (
            b"garbage\n", valid.replace(b"<<<END_SM36_FILE>>>", b"BAD"),
            valid.replace(b"bytes=1", b"bytes=2"), valid + valid,
            valid.replace(b"eA==", b"!!!!"), noncanonical,
        )
        for payload in invalid:
            with self.assertRaises((ValidationError, UnicodeDecodeError)): tuple(parse_frames(BytesIO(payload)))
        with self.assertRaises(ValidationError): encode_frame("../a", b"x")


class SecurityTests(unittest.TestCase):
    def test_call_name(self):
        calls = [node for node in ast.walk(ast.parse("f(); a.b.c()")) if isinstance(node, ast.Call)]
        self.assertEqual(call_name(calls[0]), "f"); self.assertEqual(call_name(calls[1]), "a.b.c")

    def test_source_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); safe = root / "safe.py"; bad = root / "bad.py"
            safe.write_text("print('ok')\n"); bad.write_text("eval('1')\nimport subprocess\nsubprocess.run('x', shell=True)\n")
            self.assertEqual(audit_source((safe,)), ())
            findings = audit_source((bad,)); self.assertEqual({row.severity for row in findings}, {"HIGH", "CRITICAL"})

    def test_sbom(self):
        payload = {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": [{"type": "library", "name": "Python", "version": "3.12"}]}
        self.assertTrue(validate_sbom(payload))
        for invalid in ({}, {**payload, "components": [{}]}, {**payload, "components": payload["components"] * 2}):
            with self.assertRaises(ValidationError): validate_sbom(invalid)


class CLITests(unittest.TestCase):
    def test_basic_commands(self):
        for command in (("status",), ("capabilities",), ("score",)):
            output = StringIO()
            with redirect_stdout(output): self.assertEqual(main(command), 0)
            self.assertIsNotNone(json.loads(output.getvalue()))
        with self.assertRaises(SystemExit): main(())


if __name__ == "__main__": unittest.main()
