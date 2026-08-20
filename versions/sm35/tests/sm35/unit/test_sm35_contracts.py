from __future__ import annotations

from dataclasses import replace
import math
import unittest

from supermoon35.contracts import (
    Artifact, ClaimLevel, ExecutionStatus, PhysicalReceipt, ValidationError,
    canonical_json, sha256_json, validate_receipt_mapping,
)


NOW = "2026-08-20T12:00:00+00:00"


def receipt(**changes):
    environment = changes.pop("environment", {"python": "3.12"})
    base = dict(
        run_id="run-1", track_id="coverage", status=ExecutionStatus.PASS,
        claim_level=ClaimLevel.VERIFIED, started_utc=NOW, ended_utc=NOW,
        elapsed_monotonic_seconds=1.0, environment=environment,
        environment_sha256=sha256_json(environment),
        checks={"threshold": True}, evidence_ids=("evidence:one",),
        reviewer_decision=ExecutionStatus.PASS,
    )
    base.update(changes)
    return PhysicalReceipt(**base)


class ContractTests(unittest.TestCase):
    def test_valid_receipt_roundtrip(self):
        item = receipt(input_artifacts=(Artifact("input:one", "inputs/a.txt", 1, "a" * 64),))
        payload = item.payload()
        rebuilt = validate_receipt_mapping(payload)
        self.assertEqual(rebuilt, item)

    def test_canonical_json_rejects_nonfinite(self):
        self.assertEqual(canonical_json({"b": 1, "a": 2}), b'{"a":2,"b":1}')
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValidationError):
                canonical_json({"bad": [value]})

    def test_artifact_contract(self):
        good = Artifact("a:1", "relative/a", 0, "0" * 64)
        good.validate()
        for bad in (
            Artifact("", "a", 0, "0" * 64),
            Artifact("a", "../a", 0, "0" * 64),
            Artifact("a", "/a", 0, "0" * 64),
            Artifact("a", "a", -1, "0" * 64),
            Artifact("a", "a", 1, "BAD"),
        ):
            with self.assertRaises(ValidationError):
                bad.validate()

    def test_receipt_time_hash_and_duration_failures(self):
        invalid = (
            receipt(format="wrong"), receipt(run_id="bad id"),
            receipt(started_utc=None), receipt(started_utc="bad"),
            receipt(started_utc="2026-08-20T00:00:00"), receipt(started_utc="2026-08-21T00:00:00Z"),
            receipt(elapsed_monotonic_seconds=-1), receipt(elapsed_monotonic_seconds=math.nan),
            receipt(environment_sha256="0" * 64),
        )
        for item in invalid:
            with self.assertRaises(ValidationError):
                item.validate()

    def test_receipt_duplicate_and_truth_failures(self):
        artifact = Artifact("a:1", "a", 0, "0" * 64)
        invalid = (
            receipt(input_artifacts=(artifact,), output_artifacts=(artifact,)),
            receipt(evidence_ids=("same", "same")), receipt(evidence_ids=("bad id",)),
            receipt(checks={"bad": 1}), receipt(checks={}),
            receipt(reviewer_decision=ExecutionStatus.BLOCKED),
            receipt(status=ExecutionStatus.UNAVAILABLE, reviewer_decision=ExecutionStatus.PASS),
        )
        for item in invalid:
            with self.assertRaises(ValidationError):
                item.validate()

    def test_unavailable_receipt_is_truthful(self):
        item = receipt(status=ExecutionStatus.UNAVAILABLE, claim_level=ClaimLevel.IMPLEMENTED, checks={"ran": False}, evidence_ids=(), reviewer_decision=ExecutionStatus.BLOCKED)
        item.validate()

    def test_mapping_rejects_unknown_missing_and_malformed(self):
        payload = receipt().payload()
        with self.assertRaises(ValidationError):
            validate_receipt_mapping({**payload, "surprise": 1})
        incomplete = dict(payload)
        incomplete.pop("run_id")
        with self.assertRaises(ValidationError):
            validate_receipt_mapping(incomplete)
        malformed = {**payload, "status": "INVENTED"}
        with self.assertRaises(ValidationError):
            validate_receipt_mapping(malformed)


if __name__ == "__main__":
    unittest.main()
