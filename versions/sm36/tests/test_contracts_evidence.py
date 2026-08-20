from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json
import math
from pathlib import Path
import tempfile
import unittest

from supermoon36.contracts import (
    Artifact, ClaimLevel, ExecutionReceipt, MethodologyResult, ResultState,
    ValidationError, canonical_json, safe_logical_path, sha256_json, timestamp,
    unique_identifiers, validate_result_mapping,
)
from supermoon36.evidence import EvidenceLedger, write_ledger


NOW = "2026-08-20T12:00:00+00:00"


def method_result(**changes):
    values = dict(
        methodology_id="P01-M0001", state=ResultState.PASS, claim_level=ClaimLevel.VERIFIED,
        started_utc=NOW, ended_utc=NOW, elapsed_monotonic_seconds=1.0,
        checks={"ok": True}, evidence_ids=("evidence:one",), reviewer="reviewer",
        reviewer_state=ResultState.PASS,
    )
    values.update(changes); return MethodologyResult(**values)


def receipt(**changes):
    environment = changes.pop("environment", {"python": "3.12"})
    values = dict(
        run_id="run:one", track_id="coverage", state=ResultState.PASS,
        claim_level=ClaimLevel.VERIFIED, started_utc=NOW, ended_utc=NOW,
        elapsed_monotonic_seconds=1.0, environment=environment,
        environment_sha256=sha256_json(environment), checks={"ok": True},
        evidence_ids=("evidence:one",), reviewer="reviewer", reviewer_state=ResultState.PASS,
    )
    values.update(changes); return ExecutionReceipt(**values)


class ContractTests(unittest.TestCase):
    def test_canonical_json_and_timestamp(self):
        self.assertEqual(canonical_json({"b": 1, "a": 2}), b'{"a":2,"b":1}')
        self.assertIsNotNone(timestamp(NOW))
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValidationError): canonical_json({"bad": value})
        with self.assertRaises(ValidationError): canonical_json({1: "bad"})
        for value in ("", "bad", "2026-01-01T00:00:00"):
            with self.assertRaises(ValidationError): timestamp(value)

    def test_paths_artifacts_and_identifiers(self):
        self.assertEqual(str(safe_logical_path("a/b.txt")), "a/b.txt")
        for value in ("", "/a", "../a", "a/../../b", "a\\b"):
            with self.assertRaises(ValidationError): safe_logical_path(value)
        good = Artifact("artifact:one", "a/b", 1, "a" * 64); good.validate()
        invalid = (
            replace(good, artifact_id="bad id"), replace(good, logical_path="../a"),
            replace(good, size_bytes=-1), replace(good, sha256="BAD"), replace(good, media_type="bad"),
        )
        for item in invalid:
            with self.assertRaises(ValidationError): item.validate()
        self.assertEqual(unique_identifiers(("a", "b"), "ids"), ("a", "b"))
        for values in (("a", "a"), ("bad id",)):
            with self.assertRaises(ValidationError): unique_identifiers(values, "ids")

    def test_methodology_result_roundtrip(self):
        item = method_result(); payload = item.payload(); rebuilt = validate_result_mapping(payload)
        self.assertEqual(rebuilt, item)
        invalid = (
            replace(item, format="bad"), replace(item, methodology_id="bad"),
            replace(item, started_utc="2027-01-01T00:00:00Z"), replace(item, elapsed_monotonic_seconds=-1),
            replace(item, elapsed_monotonic_seconds=math.nan), replace(item, checks={"x": 1}),
            replace(item, evidence_ids=("same", "same")), replace(item, evidence_ids=("bad id",)),
            replace(item, checks={}), replace(item, reviewer=None),
            replace(item, state=ResultState.NOT_EXECUTED, reviewer_state=ResultState.PASS),
        )
        for value in invalid:
            with self.assertRaises(ValidationError): value.validate()
        with self.assertRaises(ValidationError): validate_result_mapping({})
        with self.assertRaises(ValidationError): validate_result_mapping({**payload, "state": "INVENTED"})

    def test_execution_receipt_truth_contract(self):
        artifact = Artifact("a:1", "a", 0, "0" * 64)
        item = receipt(inputs=(artifact,)); self.assertEqual(item.payload()["state"], "PASS")
        invalid = (
            replace(item, format="bad"), replace(item, run_id="bad id"),
            replace(item, ended_utc="2025-01-01T00:00:00Z"), replace(item, elapsed_monotonic_seconds=-1),
            replace(item, environment_sha256="0" * 64), replace(item, outputs=(artifact,)),
            replace(item, checks={"bad": 1}), replace(item, checks={}), replace(item, reviewer=None),
            replace(item, claim_level=ClaimLevel.QUALIFIED, physical_attestation={}),
        )
        for value in invalid:
            with self.assertRaises(ValidationError): value.validate()
        qualified = replace(item, claim_level=ClaimLevel.QUALIFIED, physical_attestation={"device": "real"})
        qualified.validate()


class EvidenceTests(unittest.TestCase):
    def test_ledger_chain_closure_encode_decode(self):
        ledger = EvidenceLedger()
        source = ledger.add("source", {"sha256": "a" * 64}, created_utc=NOW)
        test = ledger.add("test", {"passed": True}, (source.node_id,), created_utc="2026-08-20T12:00:01+00:00")
        terminal = ledger.add("decision", {"state": "BLOCKED"}, (test.node_id,), created_utc="2026-08-20T12:00:02+00:00")
        self.assertTrue(ledger.verify()); self.assertEqual(len(ledger.closure(terminal.node_id)), 3)
        encoded = ledger.encode(); self.assertEqual(EvidenceLedger.decode(encoded).encode(), encoded)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            write_ledger(path, ledger); self.assertEqual(path.read_bytes(), encoded)

    def test_artifact_node_and_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); artifact = root / "a.txt"; artifact.write_text("data")
            ledger = EvidenceLedger(); node = ledger.add_artifact(artifact, root, created_utc=NOW)
            self.assertEqual(node.kind, "artifact")
            other = root.parent
            with self.assertRaises(ValidationError): ledger.add_artifact(other / "outside", root)
        ledger = EvidenceLedger()
        with self.assertRaises(ValidationError): ledger.add("", {})
        with self.assertRaises(ValidationError): ledger.add("x", {}, ("missing",))
        with self.assertRaises(ValidationError): ledger.closure("missing")
        with self.assertRaises(ValidationError): EvidenceLedger.decode(b'{}')
        with self.assertRaises(ValidationError): EvidenceLedger.decode(b'not-json')

    def test_tamper_and_order_detection(self):
        ledger = EvidenceLedger(); node = ledger.add("source", {"x": 1}, created_utc=NOW)
        object.__setattr__(node, "chain_sha256", "0" * 64)
        with self.assertRaises(ValidationError): ledger.verify()


if __name__ == "__main__": unittest.main()

