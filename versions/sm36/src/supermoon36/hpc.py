"""PETSc/MPI rank, partition, scaling, scheduler, and topology qualification."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean, stdev
from typing import Mapping, Sequence

from .contracts import ValidationError


@dataclass(frozen=True, slots=True)
class RankReceipt:
    ranks: int
    nodes: int
    physical_hosts: tuple[str, ...]
    ownership_ranges: tuple[tuple[int, int], ...]
    terminal_states: tuple[str, ...]
    relative_residual: float
    iterations: int
    elapsed_seconds: float
    evidence_ids: tuple[str, ...]

    def validate(self) -> None:
        if self.ranks not in {1, 2, 3, 4, 8} or not isinstance(self.nodes, int) or self.nodes < 1:
            raise ValidationError("invalid rank/node count")
        if len(self.physical_hosts) != self.nodes or len(set(self.physical_hosts)) != self.nodes:
            raise ValidationError("physical host attestation does not match node count")
        if len(self.ownership_ranges) != self.ranks or len(self.terminal_states) != self.ranks or set(self.terminal_states) != {"PASS"}:
            raise ValidationError("rank state or partition row missing")
        ordered = sorted(self.ownership_ranges)
        if ordered[0][0] != 0 or any(left[1] != right[0] for left, right in zip(ordered, ordered[1:])):
            raise ValidationError("ownership ranges are not contiguous")
        if any(start < 0 or end <= start for start, end in ordered):
            raise ValidationError("invalid ownership range")
        if not math.isfinite(self.relative_residual) or not 0 <= self.relative_residual <= 1e-8:
            raise ValidationError("residual requirement failed")
        if not isinstance(self.iterations, int) or self.iterations <= 0 or not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds <= 0:
            raise ValidationError("iteration or timing evidence invalid")
        if not self.evidence_ids:
            raise ValidationError("rank receipt requires evidence")


@dataclass(frozen=True, slots=True)
class ScalingDecision:
    strong_efficiency_at_max: float
    weak_efficiency_at_max: float
    coefficient_of_variation: float
    rank_matrix_valid: bool
    multi_node_valid: bool
    scheduler_valid: bool
    passed: bool


def _positive_samples(samples: Mapping[int, Sequence[float]], required: set[int]) -> None:
    if set(samples) != required:
        raise ValidationError("scaling sample rank set mismatch")
    for rank, rows in samples.items():
        if len(rows) < 3 or any(not math.isfinite(value) or value <= 0 for value in rows):
            raise ValidationError(f"rank {rank} requires at least three positive samples")


def validate_rank_matrix(receipts: Sequence[RankReceipt]) -> bool:
    rows = tuple(receipts)
    if len(rows) != 5 or {row.ranks for row in rows} != {1, 2, 3, 4, 8}:
        raise ValidationError("rank matrix requires exactly 1/2/3/4/8")
    for row in rows:
        row.validate()
    if not any(row.ranks in {4, 8} and row.nodes >= 2 for row in rows):
        raise ValidationError("rank matrix lacks mandatory multi-node 4/8-rank execution")
    return True


def assess_scaling(
    receipts: Sequence[RankReceipt],
    strong_samples: Mapping[int, Sequence[float]],
    weak_samples: Mapping[int, Sequence[float]],
    scheduler: Mapping[str, object],
) -> ScalingDecision:
    required = {1, 2, 3, 4, 8}
    _positive_samples(strong_samples, required); _positive_samples(weak_samples, required)
    rank_valid = validate_rank_matrix(receipts)
    strong_means = {rank: mean(values) for rank, values in strong_samples.items()}
    weak_means = {rank: mean(values) for rank, values in weak_samples.items()}
    max_rank = max(required)
    strong_efficiency = strong_means[1] / (max_rank * strong_means[max_rank])
    weak_efficiency = weak_means[1] / weak_means[max_rank]
    per_rank_cv = [stdev(values) / mean(values) if len(values) > 1 else 0.0 for values in strong_samples.values()]
    cv = max(per_rank_cv, default=0.0)
    scheduler_valid = all(
        scheduler.get(key) not in (None, "")
        for key in ("scheduler", "job_id", "accounting_record", "node_list", "submitted_utc", "ended_utc")
    ) and isinstance(scheduler.get("exit_code"), int) and not isinstance(scheduler.get("exit_code"), bool) and scheduler.get("exit_code") == 0
    multi = any(row.nodes >= 2 and len(row.physical_hosts) >= 2 for row in receipts)
    passed = rank_valid and multi and scheduler_valid and strong_efficiency >= 0.5 and weak_efficiency >= 0.7 and cv <= 0.15
    return ScalingDecision(strong_efficiency, weak_efficiency, cv, rank_valid, multi, scheduler_valid, passed)
