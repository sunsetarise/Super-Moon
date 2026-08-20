"""Mass, power, thermal, data, reliability, and interface budget closure."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping

from ..contracts import InvalidInput


@dataclass(frozen=True, slots=True)
class BudgetItem:
    item_id: str
    expected: float
    uncertainty: float
    growth: float = 0.0

    def __post_init__(self) -> None:
        if not self.item_id or self.expected < 0 or self.uncertainty < 0 or self.growth < 0:
            raise InvalidInput("invalid budget item")

    @property
    def conservative(self) -> float:
        return self.expected * (1.0 + self.growth) + self.uncertainty


@dataclass(frozen=True, slots=True)
class BudgetClosure:
    limit: float
    expected_total: float
    conservative_total: float
    margin: float
    closed: bool


@dataclass(slots=True)
class SystemArchitecture:
    budgets: dict[str, dict[str, BudgetItem]] = field(default_factory=dict)
    limits: dict[str, float] = field(default_factory=dict)
    failure_probabilities: dict[str, float] = field(default_factory=dict)

    def set_limit(self, budget: str, value: float) -> None:
        if not budget or value <= 0 or not math.isfinite(value):
            raise InvalidInput("budget limit must be finite and positive")
        self.limits[budget] = value

    def add_item(self, budget: str, item: BudgetItem) -> None:
        if budget not in self.limits:
            raise InvalidInput(f"budget limit is undefined: {budget}")
        rows = self.budgets.setdefault(budget, {})
        if item.item_id in rows:
            raise InvalidInput(f"duplicate budget item {item.item_id}")
        rows[item.item_id] = item

    def close_budget(self, budget: str) -> BudgetClosure:
        limit = self.limits[budget]
        rows = self.budgets.get(budget, {})
        expected = sum(item.expected for item in rows.values())
        conservative = sum(item.conservative for item in rows.values())
        margin = (limit - conservative) / limit
        return BudgetClosure(limit, expected, conservative, margin, conservative <= limit)

    def set_failure_probability(self, failure_id: str, probability: float) -> None:
        if not failure_id or not 0.0 <= probability <= 1.0:
            raise InvalidInput("failure probability must lie in [0,1]")
        self.failure_probabilities[failure_id] = probability

    def independent_union_probability(self, failure_ids: tuple[str, ...]) -> float:
        if not failure_ids:
            raise InvalidInput("at least one failure is required")
        survival = math.prod(1.0 - self.failure_probabilities[item] for item in failure_ids)
        return 1.0 - survival

    def closure_report(self) -> Mapping[str, BudgetClosure]:
        return {name: self.close_budget(name) for name in sorted(self.limits)}

