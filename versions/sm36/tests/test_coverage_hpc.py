from __future__ import annotations

import math
import unittest

from supermoon36.contracts import ValidationError
from supermoon36.coverage import (
    CoverageCounters, aggregate_coverage, decide_coverage, validate_exclusions, validate_mcdc,
)
from supermoon36.hpc import RankReceipt, assess_scaling, validate_rank_matrix


def rank_receipt(ranks: int, nodes: int = 1):
    total = 80; base = total // ranks; start = 0; ranges = []
    for index in range(ranks):
        end = total if index == ranks - 1 else start + base; ranges.append((start, end)); start = end
    hosts = tuple(f"host-{index}" for index in range(nodes))
    return RankReceipt(ranks, nodes, hosts, tuple(ranges), ("PASS",) * ranks, 1e-12, 20, 10 / ranks, (f"e:{ranks}",))


class CoverageTests(unittest.TestCase):
    def test_counters_and_aggregate(self):
        counter = CoverageCounters(95, 100, 90, 100)
        self.assertEqual(counter.statement_percent, 95); self.assertEqual(counter.branch_percent, 90)
        self.assertEqual(CoverageCounters(0, 0, 0, 0).statement_percent, 100)
        payload = {"files": {"/supermoon35/a.py": {"summary": {"covered_lines": 9, "num_statements": 10, "covered_branches": 8, "num_branches": 10}}, "/supermoon36/b.py": {"summary": {"covered_lines": 10, "num_statements": 10, "covered_branches": 10, "num_branches": 10}}}}
        self.assertEqual(aggregate_coverage(payload).statements, 20)
        self.assertEqual(aggregate_coverage(payload, ("supermoon36",)).covered_statements, 10)
        invalid = (CoverageCounters(-1, 1, 0, 0), CoverageCounters(2, 1, 0, 0))
        for row in invalid:
            with self.assertRaises(ValidationError): row.validate()
        for value in ({}, {"files": {}}, {"files": {1: {}}}, {"files": {"a": {}}}):
            with self.assertRaises(ValidationError): aggregate_coverage(value)
        with self.assertRaises(ValidationError): aggregate_coverage(payload, ("missing",))

    def test_exclusion_governance(self):
        row = {"id": "X1", "path": "a.py", "classification": "provably_unreachable", "reason": "proof", "owner": "o", "independent_reviewer": "r", "expiry_utc": "2027", "impact": "none"}
        self.assertTrue(validate_exclusions((row,)))
        for invalid in ({}, {**row, "extra": "x"}, {**row, "reason": ""}, {**row, "classification": "convenience"}):
            with self.assertRaises(ValidationError): validate_exclusions((invalid,))
        with self.assertRaises(ValidationError): validate_exclusions((row, row))

    def test_mcdc(self):
        vectors = ((False, False), (True, False), (False, True))
        outcomes = (False, True, True)
        self.assertTrue(validate_mcdc(vectors, outcomes))
        self.assertFalse(validate_mcdc(((False, False), (True, True)), (False, True)))
        for vectors, outcomes in (((), ()), (((True,),), (True,)), (((True,), (True, False)), (True, False))):
            with self.assertRaises(ValidationError): validate_mcdc(vectors, outcomes)

    def test_coverage_decision(self):
        passed = decide_coverage(CoverageCounters(95, 100, 90, 100), CoverageCounters(98, 100, 95, 100), mutation_killed=9, mutation_total=10, fuzz_failures=0, exclusions_valid=True)
        self.assertTrue(passed.passed)
        failed = decide_coverage(CoverageCounters(94, 100, 90, 100), CoverageCounters(98, 100, 95, 100), mutation_killed=8, mutation_total=10, fuzz_failures=1, exclusions_valid=False)
        self.assertFalse(failed.passed)
        for args in ((11, 10, 0), (0, 0, 0), (1, 1, -1)):
            with self.assertRaises(ValidationError): decide_coverage(CoverageCounters(1, 1, 1, 1), CoverageCounters(1, 1, 1, 1), mutation_killed=args[0], mutation_total=args[1], fuzz_failures=args[2], exclusions_valid=True)


class HPCTests(unittest.TestCase):
    def test_rank_matrix(self):
        rows = [rank_receipt(rank, 2 if rank == 8 else 1) for rank in (1, 2, 3, 4, 8)]
        self.assertTrue(validate_rank_matrix(rows))
        with self.assertRaises(ValidationError): validate_rank_matrix(rows[:-1])
        with self.assertRaises(ValidationError): validate_rank_matrix([rank_receipt(rank) for rank in (1, 2, 3, 4, 8)])

    def test_rank_receipt_negative_cases(self):
        base = rank_receipt(2)
        invalid = (
            RankReceipt(5, 1, ("h",), ((0, 1),) * 5, ("PASS",) * 5, 0, 1, 1, ("e",)),
            RankReceipt(2, 2, ("h",), base.ownership_ranges, base.terminal_states, 0, 1, 1, ("e",)),
            RankReceipt(2, 1, ("h",), ((1, 2), (3, 4)), base.terminal_states, 0, 1, 1, ("e",)),
            RankReceipt(2, 1, ("h",), base.ownership_ranges, ("PASS", "FAIL"), 0, 1, 1, ("e",)),
            RankReceipt(2, 1, ("h",), base.ownership_ranges, base.terminal_states, 1, 1, 1, ("e",)),
            RankReceipt(2, 1, ("h",), base.ownership_ranges, base.terminal_states, 0, 0, 1, ("e",)),
            RankReceipt(2, 1, ("h",), base.ownership_ranges, base.terminal_states, 0, 1, 1, ()),
        )
        for row in invalid:
            with self.assertRaises(ValidationError): row.validate()

    def test_scaling_pass_and_fail(self):
        rows = [rank_receipt(rank, 2 if rank == 8 else 1) for rank in (1, 2, 3, 4, 8)]
        strong = {rank: [80 / rank] * 3 for rank in (1, 2, 3, 4, 8)}
        weak = {rank: [80.0] * 3 for rank in (1, 2, 3, 4, 8)}
        scheduler = {"scheduler": "slurm", "job_id": "1", "accounting_record": "sacct", "node_list": "h1,h2", "exit_code": 0, "submitted_utc": "t1", "ended_utc": "t2"}
        decision = assess_scaling(rows, strong, weak, scheduler); self.assertTrue(decision.passed)
        self.assertFalse(assess_scaling(rows, {**strong, 8: [40.0] * 3}, weak, scheduler).passed)
        self.assertFalse(assess_scaling(rows, strong, weak, {**scheduler, "exit_code": 1}).passed)
        with self.assertRaises(ValidationError): assess_scaling(rows, {1: [1, 2]}, weak, scheduler)
        with self.assertRaises(ValidationError): assess_scaling(rows, {**strong, 8: [1, math.nan, 2]}, weak, scheduler)


if __name__ == "__main__": unittest.main()

