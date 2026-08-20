from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import types
import unittest

from supermoon36.certification import validate_assurance_case
from supermoon36.cli import main
from supermoon36.contracts import ClaimLevel, ExecutionReceipt, ResultState, ValidationError, sha256_json
from supermoon36.coverage import CoverageCounters, aggregate_coverage, validate_exclusions, validate_mcdc
from supermoon36.coverage_runtime import analyze_source, discover_sources, measure
from supermoon36.coverage_runtime import Collector
from supermoon35.coverage_runtime import TraceCollector, analyze_source as analyze_source35
from supermoon36.evidence import EvidenceLedger, EvidenceNode
from supermoon36.framing import encode_frame, parse_frames
from supermoon36.hpc import RankReceipt
from supermoon36.physical import CUDAReceipt, GridPoint, grid_convergence
from supermoon36.registry import MethodologyRegistry, parse_master_prompt
from supermoon36.workitems import MethodologyWorkItem, pending_work_item, validate_work_items


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "spec/SUPER_MOON_35_TO_36_15000_ADVANCED_QUALIFICATION_METHODOLOGIES_MASTER_PROMPT.txt"
REGISTRY = ROOT / "registry/SM36_METHODOLOGY_REGISTRY.jsonl.gz"
NOW = "2026-08-20T00:00:00+00:00"


class CoverageRuntimeHardening(unittest.TestCase):
    def test_complex_ast_inventory_and_false_runner(self):
        source = '''
class C:
    def f(self, xs):
        with open(__file__) as stream:
            if xs:
                for x in xs:
                    while x:
                        x -= 1
            else:
                xs = [0]
        try:
            value = xs[0]
        except IndexError:
            value = 0
        else:
            value += 1
        finally:
            value += 0
        match value:
            case 0:
                return 0
            case _:
                return 1

async def af(source, lock):
    async with lock:
        async for item in source:
            if item:
                return item
    return None
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "complex.py"; path.write_text(source, encoding="utf-8")
            model = analyze_source(path)
            self.assertGreater(len(model.branches), 10)
            self.assertEqual(discover_sources((root,)), (model,))
            passed, payload = measure((model,), lambda: False)
            self.assertFalse(passed); self.assertEqual(payload["meta"]["version"], "1.0")

    def test_trace_collectors_and_sm35_complex_ast(self):
        source = """
class C:
    def f(self, xs):
        with open(__file__):
            if xs:
                for x in xs:
                    while x:
                        x -= 1
            else:
                xs = [0]
        try:
            return xs[0]
        except IndexError:
            return 0
        finally:
            xs = []
        match xs:
            case []:
                return 0
async def af(source, lock):
    async with lock:
        async for item in source:
            return item
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "source.py"; path.write_text(source, encoding="utf-8")
            model35 = analyze_source35(path); self.assertGreater(len(model35.branches), 8)
            inside = types.SimpleNamespace(f_code=types.SimpleNamespace(co_filename=str(path)), f_lineno=1)
            outside = types.SimpleNamespace(f_code=types.SimpleNamespace(co_filename=str(root / "outside.py")), f_lineno=1)
            for collector in (Collector(frozenset((path.resolve(),))), TraceCollector(frozenset((path.resolve(),)))):
                self.assertIsNotNone(collector.trace(inside, "call", None))
                inside.f_lineno = 2; collector.trace(inside, "line", None)
                inside.f_lineno = 3; collector.trace(inside, "line", None)
                collector.trace(inside, "return", None)
                self.assertIsNone(collector.trace(outside, "call", None))
                self.assertIsNone(collector.trace(outside, "line", None))


class CLIAndRegistryHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = MethodologyRegistry.read_jsonl_gz(REGISTRY)

    def test_registry_and_method_cli_routes(self):
        for argv in (("registry", str(REGISTRY)), ("methodology", str(REGISTRY), "P01-M0001")):
            output = StringIO()
            with redirect_stdout(output): self.assertEqual(main(argv), 0)
            self.assertIsInstance(json.loads(output.getvalue()), dict)
        row = self.registry.get("P01-M0001")
        evidence = {
            "techniques": {row.technique_binding: {"executed": True, "accepted": True, "metrics": {}}},
            "lenses": {row.lens_binding: {"executed": True, "raw_evidence_retained": True, "pre_registered_gate_used": True, "provenance_complete": True}},
            "evidence_ids": ["e:one"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "e.json"; path.write_text(json.dumps(evidence), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(("methodology", str(REGISTRY), "P01-M0001", "--evidence", str(path), "--reviewer", "reviewer")), 0)
            self.assertEqual(json.loads(output.getvalue())["state"], "PASS")

    def test_registry_parser_wrong_label_and_work_item_phase_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.txt"
            path.write_text("[P01-M0001] A x B\n  WRONG: a\n" + "  EXECUTION LENS: x\n" * 7, encoding="utf-8")
            with self.assertRaises(ValidationError): parse_master_prompt(path)
        rows = tuple(pending_work_item(row, prompt_sha256="a" * 64, registry_sha256="b" * 64, completion_timestamp=NOW) for row in self.registry.records)
        tampered = list(rows); tampered[-1] = replace(tampered[-1], phase_id="P01")
        with self.assertRaises(ValidationError): validate_work_items(tampered)


class EvidenceAndSchemaHardening(unittest.TestCase):
    def test_evidence_node_and_ledger_invariants(self):
        ledger = EvidenceLedger(); first = ledger.add("x", {}, created_utc=NOW)
        for node in (
            replace(first, node_id="bad"), replace(first, sequence=-1),
            replace(first, node_id="sha256:" + "0" * 64), replace(first, chain_sha256="0" * 64),
        ):
            with self.assertRaises(ValidationError): node.validate()
        duplicate = EvidenceLedger([first, first])
        with self.assertRaises(ValidationError): duplicate.verify()
        wrong_sequence = EvidenceLedger([replace(first, sequence=1)])
        with self.assertRaises(ValidationError): wrong_sequence.verify()
        parent = replace(first, parents=("sha256:" + "f" * 64,))
        with self.assertRaises(ValidationError): EvidenceLedger([parent]).verify()
        with self.assertRaises(ValidationError): EvidenceLedger.decode(b'{"format":"SM36_EVIDENCE_LEDGER_V1","nodes":[{}]}')

    def test_work_item_validation_edges(self):
        record = MethodologyRegistry.read_jsonl_gz(REGISTRY).get("P02-M0001")
        item = pending_work_item(record, prompt_sha256="a" * 64, registry_sha256="b" * 64, completion_timestamp=NOW)
        invalid = (
            replace(item, format="bad"), replace(item, responsible_owner=""),
            replace(item, input_artifact_ids_and_hashes={"": "x"}),
            replace(item, result_state=ResultState.PASS, blocker_ids=(), raw_evidence_ids_and_hashes={"e": "h"}, responsible_owner="o", independent_reviewer="r", review_signature="s"),
        )
        for row in invalid:
            with self.assertRaises(ValidationError): row.validate()

    def test_coverage_and_assurance_terminal_edges(self):
        self.assertEqual(CoverageCounters(0, 0, 0, 0).branch_percent, 100)
        self.assertTrue(validate_exclusions(()))
        with self.assertRaises(ValidationError): validate_assurance_case({}, "missing")
        cyclic = {"a": {"subclaims": ["a"], "evidence": ["e"], "assumptions": [], "defeaters": []}}
        with self.assertRaises(ValidationError): validate_assurance_case(cyclic, "a")

    def test_remaining_decision_edges(self):
        shared = {
            "root": {"subclaims": ["left", "right"], "evidence": ["e"], "assumptions": [], "defeaters": []},
            "left": {"subclaims": ["leaf"], "evidence": ["e"], "assumptions": [], "defeaters": []},
            "right": {"subclaims": ["leaf"], "evidence": ["e"], "assumptions": [], "defeaters": []},
            "leaf": {"subclaims": [], "evidence": ["e"], "assumptions": [], "defeaters": []},
        }
        self.assertTrue(validate_assurance_case(shared, "root"))
        environment = {"python": "3.12"}
        receipt = ExecutionReceipt(
            "run:blocked", "coverage", ResultState.BLOCKED, ClaimLevel.TESTED, NOW, NOW, 0,
            environment, sha256_json(environment), checks={}, limitations=("blocked",),
        )
        receipt.validate()
        bad_coverage = {"files": {"a": {"summary": {"covered_lines": 1.0, "num_statements": 1, "covered_branches": 0, "num_branches": 0}}}}
        with self.assertRaises(ValidationError): aggregate_coverage(bad_coverage)
        with self.assertRaises(ValidationError): validate_mcdc(((False,), (True,)), (False, 1))
        self.assertEqual(tuple(parse_frames(BytesIO(b"\n" + encode_frame("a", b"x"))))[0].data, b"x")
        self.assertEqual(tuple(parse_frames(BytesIO(b""))), ())
        invalid_rank = RankReceipt(2, 1, ("h",), ((0, 1), (1, 1)), ("PASS", "PASS"), 0, 1, 1, ("e",))
        with self.assertRaises(ValidationError): invalid_rank.validate()
        with self.assertRaises(ValidationError): grid_convergence((GridPoint(.25, 0), GridPoint(.5, 1), GridPoint(1, 1.5)))
        zero_timing = CUDAReceipt("u", "g", "d", "r", "8", 1, False, 0, 0, (0.0, 0.0, 0.0), 20, False, ("e",))
        self.assertTrue(zero_timing.passes())
        ledger = EvidenceLedger(); root = ledger.add("root", {}, created_utc=NOW)
        left = ledger.add("left", {}, (root.node_id,), created_utc="2026-08-20T00:00:01+00:00")
        right = ledger.add("right", {}, (root.node_id,), created_utc="2026-08-20T00:00:02+00:00")
        terminal = ledger.add("terminal", {}, (left.node_id, right.node_id), created_utc="2026-08-20T00:00:03+00:00")
        self.assertEqual(len(ledger.closure(terminal.node_id)), 4)
        with tempfile.TemporaryDirectory() as directory:
            root_path = Path(directory) / "root"; root_path.mkdir()
            outside = Path(directory) / "outside"; outside.write_text("x")
            with self.assertRaises(ValidationError): EvidenceLedger().add_artifact(outside, root_path)


if __name__ == "__main__": unittest.main()
