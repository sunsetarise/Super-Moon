"""Coverage, MC/DC, mutation, fuzz, and exclusion-governance gates."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping, Sequence

from .contracts import ValidationError


@dataclass(frozen=True, slots=True)
class CoverageCounters:
    covered_statements: int
    statements: int
    covered_branches: int
    branches: int

    def validate(self) -> None:
        values = (self.covered_statements, self.statements, self.covered_branches, self.branches)
        if any(not isinstance(value, int) or value < 0 for value in values):
            raise ValidationError("coverage counters must be nonnegative integers")
        if self.covered_statements > self.statements or self.covered_branches > self.branches:
            raise ValidationError("covered counter exceeds total")

    @property
    def statement_percent(self) -> float:
        self.validate()
        return 100.0 if self.statements == 0 else 100.0 * self.covered_statements / self.statements

    @property
    def branch_percent(self) -> float:
        self.validate()
        return 100.0 if self.branches == 0 else 100.0 * self.covered_branches / self.branches


@dataclass(frozen=True, slots=True)
class CoverageDecision:
    combined: CoverageCounters
    new_code: CoverageCounters
    combined_pass: bool
    new_code_pass: bool
    mutation_percent: float
    mutation_pass: bool
    fuzz_failures: int
    fuzz_pass: bool
    exclusions_valid: bool
    passed: bool


def aggregate_coverage(payload: Mapping[str, Any], path_needles: Sequence[str] = ()) -> CoverageCounters:
    files = payload.get("files")
    if not isinstance(files, Mapping) or not files:
        raise ValidationError("coverage payload requires nonempty files")
    totals = [0, 0, 0, 0]; measured = 0
    for path, row in files.items():
        if not isinstance(path, str) or not isinstance(row, Mapping):
            raise ValidationError("malformed coverage file row")
        if path_needles and not any(needle in path for needle in path_needles):
            continue
        summary = row.get("summary")
        if not isinstance(summary, Mapping):
            raise ValidationError("coverage row lacks summary")
        keys = ("covered_lines", "num_statements", "covered_branches", "num_branches")
        values = [summary.get(key) for key in keys]
        if any(not isinstance(value, int) for value in values):
            raise ValidationError("coverage summary counters must be integers")
        totals = [left + right for left, right in zip(totals, values)]; measured += 1
    if not measured:
        raise ValidationError("coverage selection matched no files")
    result = CoverageCounters(*totals); result.validate(); return result


def validate_exclusions(exclusions: Iterable[Mapping[str, Any]]) -> bool:
    required = {"id", "path", "classification", "reason", "owner", "independent_reviewer", "expiry_utc", "impact"}
    identifiers: set[str] = set()
    for row in exclusions:
        if not isinstance(row, Mapping) or set(row) != required:
            raise ValidationError("coverage exclusion schema mismatch")
        if any(not isinstance(row[key], str) or not row[key].strip() for key in required):
            raise ValidationError("coverage exclusion fields must be nonempty")
        if row["id"] in identifiers:
            raise ValidationError("duplicate coverage exclusion ID")
        identifiers.add(row["id"])
        if row["classification"] not in {"provably_unreachable", "third_party", "generated_nonexecuted", "platform_mandatory_external"}:
            raise ValidationError("unapproved exclusion classification")
    return True


def validate_mcdc(condition_vectors: Sequence[Sequence[bool]], outcomes: Sequence[bool]) -> bool:
    if len(condition_vectors) != len(outcomes) or len(condition_vectors) < 2:
        raise ValidationError("MC/DC requires aligned test vectors and outcomes")
    width = len(condition_vectors[0])
    if width == 0 or any(len(row) != width or any(not isinstance(value, bool) for value in row) for row in condition_vectors):
        raise ValidationError("invalid MC/DC condition vectors")
    if any(not isinstance(value, bool) for value in outcomes):
        raise ValidationError("invalid MC/DC outcomes")
    independently_demonstrated = set()
    for left in range(len(condition_vectors)):
        for right in range(left + 1, len(condition_vectors)):
            differences = [index for index in range(width) if condition_vectors[left][index] != condition_vectors[right][index]]
            if len(differences) == 1 and outcomes[left] != outcomes[right]:
                independently_demonstrated.add(differences[0])
    return len(independently_demonstrated) == width


def decide_coverage(
    combined: CoverageCounters,
    new_code: CoverageCounters,
    *,
    mutation_killed: int,
    mutation_total: int,
    fuzz_failures: int,
    exclusions_valid: bool,
) -> CoverageDecision:
    combined.validate(); new_code.validate()
    if not isinstance(mutation_killed, int) or not isinstance(mutation_total, int) or mutation_total <= 0 or not 0 <= mutation_killed <= mutation_total:
        raise ValidationError("invalid mutation counters")
    if not isinstance(fuzz_failures, int) or fuzz_failures < 0:
        raise ValidationError("invalid fuzz failure count")
    mutation = 100.0 * mutation_killed / mutation_total
    combined_pass = combined.statement_percent >= 95.0 and combined.branch_percent >= 90.0
    new_pass = new_code.statement_percent >= 98.0 and new_code.branch_percent >= 95.0
    mutation_pass = mutation >= 90.0
    fuzz_pass = fuzz_failures == 0
    passed = combined_pass and new_pass and mutation_pass and fuzz_pass and exclusions_valid
    return CoverageDecision(combined, new_code, combined_pass, new_pass, mutation, mutation_pass, fuzz_failures, fuzz_pass, exclusions_valid, passed)

