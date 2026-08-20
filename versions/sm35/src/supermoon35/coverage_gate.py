"""Independent statement/branch threshold verification for coverage JSON."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .contracts import ValidationError


@dataclass(frozen=True, slots=True)
class CoverageDecision:
    statement_percent: float
    branch_percent: float
    statement_threshold: float
    branch_threshold: float
    measured_files: int
    passed: bool


def _percent(covered: object, total: object, name: str) -> float:
    if not isinstance(covered, int) or not isinstance(total, int) or covered < 0 or total < 0 or covered > total:
        raise ValidationError(f"invalid {name} counters")
    return 100.0 if total == 0 else 100.0 * covered / total


def verify_coverage(payload: Mapping[str, Any], *, statement_threshold: float = 95.0, branch_threshold: float = 90.0) -> CoverageDecision:
    if not all(isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 100 for value in (statement_threshold, branch_threshold)):
        raise ValidationError("coverage thresholds must be finite percentages")
    files = payload.get("files")
    if not isinstance(files, Mapping) or not files:
        raise ValidationError("coverage JSON requires measured files")
    statements_covered = statements_total = branches_covered = branches_total = 0
    for path, row in files.items():
        if not isinstance(path, str) or not path or not isinstance(row, Mapping):
            raise ValidationError("malformed file coverage row")
        summary = row.get("summary")
        if not isinstance(summary, Mapping):
            raise ValidationError("file coverage row lacks summary")
        statements_covered += int(summary.get("covered_lines", -1))
        statements_total += int(summary.get("num_statements", -1))
        branches_covered += int(summary.get("covered_branches", -1))
        branches_total += int(summary.get("num_branches", -1))
    statement_percent = _percent(statements_covered, statements_total, "statement")
    branch_percent = _percent(branches_covered, branches_total, "branch")
    return CoverageDecision(
        round(statement_percent, 6), round(branch_percent, 6), float(statement_threshold),
        float(branch_threshold), len(files), statement_percent >= statement_threshold and branch_percent >= branch_threshold,
    )
