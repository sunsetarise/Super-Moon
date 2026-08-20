from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from supermoon35.contracts import ExecutionStatus, ValidationError
from supermoon35.physical import (
    ExternalCommandPolicy, PetscRankResult, capability_matrix, detect_capability,
    execute_authorized, unavailable_receipt, validate_petsc_matrix,
)


def rank_result(ranks: int, nodes: int = 1) -> PetscRankResult:
    step = 80 // ranks
    ranges = []
    start = 0
    for index in range(ranks):
        end = 80 if index == ranks - 1 else start + step
        ranges.append((start, end))
        start = end
    return PetscRankResult(ranks, nodes, ("PASS",) * ranks, tuple(ranges), 1e-12, (f"e:{ranks}",))


class PhysicalContractTests(unittest.TestCase):
    def test_capability_matrix_is_truthful(self):
        matrix = capability_matrix()
        self.assertEqual({item.track_id for item in matrix}, {"cad", "containers", "gpu", "hpc", "openfoam", "petsc_mpi", "su2"})
        self.assertTrue(all(item.reason for item in matrix))
        with self.assertRaises(ValidationError):
            detect_capability("invented")

    def test_unavailable_receipt(self):
        item = unavailable_receipt("gpu", {"nvidia_smi": None}, "No physical CUDA device", timestamp="2026-08-20T00:00:00+00:00")
        self.assertEqual(item.status, ExecutionStatus.UNAVAILABLE)
        self.assertFalse(item.checks["physical_execution_completed"])

    def test_complete_petsc_matrix_contract(self):
        rows = [rank_result(rank, 2 if rank == 8 else 1) for rank in (1, 2, 3, 4, 8)]
        self.assertTrue(validate_petsc_matrix(rows))
        with self.assertRaises(ValidationError):
            validate_petsc_matrix(rows[:-1])
        with self.assertRaises(ValidationError):
            validate_petsc_matrix([rank_result(rank) for rank in (1, 2, 3, 4, 8)])

    def test_rank_receipt_negative_cases(self):
        invalid = (
            PetscRankResult(5, 1, ("PASS",) * 5, ((0, 1),) * 5, 0, ("e",)),
            PetscRankResult(2, 1, ("PASS", "FAIL"), ((0, 1), (1, 2)), 0, ("e",)),
            PetscRankResult(2, 1, ("PASS",) * 2, ((0, 1),), 0, ("e",)),
            PetscRankResult(2, 1, ("PASS",) * 2, ((1, 2), (3, 4)), 0, ("e",)),
            PetscRankResult(2, 1, ("PASS",) * 2, ((0, 1), (1, 2)), 1, ("e",)),
            PetscRankResult(2, 1, ("PASS",) * 2, ((0, 1), (1, 2)), 0, ()),
        )
        for item in invalid:
            with self.assertRaises(ValidationError):
                item.validate()

    def test_external_command_requires_authorization_and_allowlists(self):
        echo = Path("/bin/echo")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = ExternalCommandPolicy((echo,), (root,), timeout_seconds=2, output_limit_bytes=100)
            result = execute_authorized(policy, echo, ("sm35",), root, authorized=True)
            self.assertEqual(result.stdout.strip(), b"sm35")
            with self.assertRaises(ValidationError):
                execute_authorized(policy, echo, (), root, authorized=False)
            with self.assertRaises(ValidationError):
                execute_authorized(policy, Path("/bin/true"), (), root, authorized=True)
            with tempfile.TemporaryDirectory() as other:
                with self.assertRaises(ValidationError):
                    execute_authorized(policy, echo, (), Path(other), authorized=True)

    def test_external_policy_limits_and_output_cap(self):
        with self.assertRaises(ValidationError):
            ExternalCommandPolicy((), (), 0, 0).validate()
        with self.assertRaises(ValidationError):
            ExternalCommandPolicy((Path("/bin/echo"),), (Path("/tmp"),), 0, 1).validate()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = ExternalCommandPolicy((Path("/bin/echo"),), (root,), output_limit_bytes=1)
            with self.assertRaises(ValidationError):
                execute_authorized(policy, Path("/bin/echo"), ("too-long",), root, authorized=True)


if __name__ == "__main__":
    unittest.main()
