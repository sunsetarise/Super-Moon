from __future__ import annotations

from dataclasses import asdict
import json
import math
import unittest

from supermoon35.contracts import ExecutionStatus, ValidationError
from supermoon35.coverage_gate import verify_coverage
from supermoon35.evidence import EvidenceDAG
from supermoon35.qualification import BLOCKERS, WEIGHTS, candidate_decision, score_release


class EvidenceQualificationTests(unittest.TestCase):
    def test_evidence_dag_and_closure(self):
        graph = EvidenceDAG()
        source = graph.add("source", {"sha256": "a" * 64}, created_utc="2026-08-20T00:00:00+00:00")
        test = graph.add("test", {"passed": True}, (source.node_id,), created_utc="2026-08-20T00:00:01+00:00")
        terminal = graph.add("decision", {"state": "BLOCKED"}, (test.node_id,), created_utc="2026-08-20T00:00:02+00:00")
        self.assertTrue(graph.verify())
        self.assertEqual(len(graph.terminal_closure(terminal.node_id)), 3)
        self.assertEqual(json.loads(graph.encode())["format"], "SM35_EVIDENCE_DAG_V1")
        self.assertEqual(graph.add("source", {"sha256": "a" * 64}, created_utc="2026-08-20T00:00:00+00:00"), source)

    def test_evidence_rejects_invalid_graph(self):
        graph = EvidenceDAG()
        with self.assertRaises(ValidationError):
            graph.add("", {})
        with self.assertRaises(ValidationError):
            graph.add("test", {}, ("missing",))
        with self.assertRaises(ValidationError):
            graph.terminal_closure("missing")
        node = graph.add("source", {"value": 1}, created_utc="2026-08-20T00:00:00+00:00")
        graph.nodes[node.node_id].payload["value"] = 2
        with self.assertRaises(ValidationError):
            graph.verify()

    def test_score_pass_block_and_fail(self):
        complete = {key: 1.0 for key in WEIGHTS}
        closed = {key: False for key in BLOCKERS}
        passed = score_release(complete, closed, True)
        self.assertTrue(passed.passed)
        self.assertEqual(passed.score, 100)
        self.assertEqual(passed.status, ExecutionStatus.PASS)
        blocked = score_release({**complete, "Q01": 0.5}, {**closed, "B01": True}, True)
        self.assertEqual(blocked.status, ExecutionStatus.BLOCKED)
        blocker_only = score_release(complete, {**closed, "B01": True}, True)
        self.assertFalse(blocker_only.passed)
        self.assertEqual(blocker_only.status, ExecutionStatus.BLOCKED)
        failed = score_release(complete, closed, False)
        self.assertEqual(failed.status, ExecutionStatus.FAIL)

    def test_score_rejects_bypass_inputs(self):
        complete = {key: 1.0 for key in WEIGHTS}
        closed = {key: False for key in BLOCKERS}
        bad_calls = (
            ({}, closed), (complete, {}), ({**complete, "Q01": math.nan}, closed),
            ({**complete, "Q01": -0.1}, closed), ({**complete, "Q01": 1.1}, closed),
            (complete, {**closed, "B01": 0}),
        )
        for completion, blockers in bad_calls:
            with self.assertRaises(ValidationError):
                score_release(completion, blockers, True)

    def test_candidate_keeps_physical_blockers(self):
        result = candidate_decision(1.0, 1.0, 1.0)
        self.assertFalse(result.passed)
        self.assertIn("B05", result.open_blockers)
        self.assertNotIn("B17", result.open_blockers)

    def test_coverage_gate(self):
        payload = {"files": {"a.py": {"summary": {"covered_lines": 95, "num_statements": 100, "covered_branches": 90, "num_branches": 100}}}}
        self.assertTrue(verify_coverage(payload).passed)
        zero = {"files": {"empty.py": {"summary": {"covered_lines": 0, "num_statements": 0, "covered_branches": 0, "num_branches": 0}}}}
        self.assertTrue(verify_coverage(zero).passed)
        payload["files"]["a.py"]["summary"]["covered_branches"] = 89
        self.assertFalse(verify_coverage(payload).passed)

    def test_coverage_rejects_malformed_inputs(self):
        invalid = (
            ({}, 95.0, 90.0), ({"files": {}}, 95.0, 90.0),
            ({"files": {1: {}}}, 95.0, 90.0),
            ({"files": {"a": {}}}, 95.0, 90.0),
            ({"files": {"a": {"summary": {"covered_lines": 2, "num_statements": 1, "covered_branches": 0, "num_branches": 0}}}}, 95.0, 90.0),
            ({"files": {"a": {"summary": {"covered_lines": 0, "num_statements": 1, "covered_branches": 0, "num_branches": 0}}}}, math.nan, 90.0),
        )
        for payload, statement, branch in invalid:
            with self.assertRaises((ValidationError, TypeError)):
                verify_coverage(payload, statement_threshold=statement, branch_threshold=branch)


if __name__ == "__main__":
    unittest.main()
