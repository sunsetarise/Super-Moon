"""Dependency-free, branch-aware source coverage measurement for SM35."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
import sys
from types import FrameType
from typing import Callable, Iterable


@dataclass(frozen=True, slots=True)
class SourceModel:
    path: Path
    statements: frozenset[int]
    branches: frozenset[tuple[int, int]]


def _statement_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        lines.add(node.lineno)
    return lines


def analyze_source(path: Path) -> SourceModel:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    statements = _statement_lines(tree)
    branches: set[tuple[int, int]] = set()
    after: dict[ast.stmt, int] = {}

    def map_block(items: list[ast.stmt], continuation: int) -> None:
        for index, item in enumerate(items):
            next_line = items[index + 1].lineno if index + 1 < len(items) else continuation
            after[item] = next_line
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                map_block(item.body, 0)
            elif isinstance(item, ast.If):
                map_block(item.body, next_line)
                map_block(item.orelse, next_line)
            elif isinstance(item, (ast.For, ast.AsyncFor, ast.While)):
                map_block(item.body, item.lineno)
                map_block(item.orelse, next_line)
            elif isinstance(item, (ast.Try, ast.TryStar)):
                map_block(item.body, next_line)
                for handler in item.handlers:
                    map_block(handler.body, next_line)
                map_block(item.orelse, next_line)
                map_block(item.finalbody, next_line)
            elif isinstance(item, (ast.With, ast.AsyncWith)):
                map_block(item.body, next_line)
            elif isinstance(item, ast.Match):
                for case in item.cases:
                    map_block(case.body, next_line)

    map_block(tree.body, 0)

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            branches.add((node.lineno, node.body[0].lineno))
            branches.add((node.lineno, node.orelse[0].lineno if node.orelse else after[node]))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            branches.add((node.lineno, node.body[0].lineno))
            branches.add((node.lineno, node.orelse[0].lineno if node.orelse else after[node]))
        elif isinstance(node, ast.Match):
            for case in node.cases:
                if case.body:
                    branches.add((node.lineno, case.body[0].lineno))
    branches.discard((0, 0))
    return SourceModel(path.resolve(), frozenset(statements), frozenset(branches))


@dataclass(slots=True)
class TraceCollector:
    source_files: frozenset[Path]
    executed: dict[Path, set[int]] = field(default_factory=dict)
    arcs: dict[Path, set[tuple[int, int]]] = field(default_factory=dict)
    previous: dict[int, tuple[Path, int]] = field(default_factory=dict)

    def trace(self, frame: FrameType, event: str, arg: object) -> Callable | None:
        path = Path(frame.f_code.co_filename).resolve()
        frame_id = id(frame)
        if event == "call":
            if path in self.source_files:
                self.previous[frame_id] = (path, 0)
                return self.trace
            return None
        if path not in self.source_files:
            return None
        if event == "line":
            line = frame.f_lineno
            self.executed.setdefault(path, set()).add(line)
            previous = self.previous.get(frame_id)
            if previous is not None and previous[1] != 0:
                self.arcs.setdefault(path, set()).add((previous[1], line))
            self.previous[frame_id] = (path, line)
        elif event == "return":
            previous = self.previous.pop(frame_id, None)
            if previous is not None and previous[1] != 0:
                self.arcs.setdefault(path, set()).add((previous[1], 0))
        return self.trace


def measure(models: Iterable[SourceModel], runner: Callable[[], bool]) -> tuple[bool, dict[str, object]]:
    model_rows = tuple(models)
    collector = TraceCollector(frozenset(model.path for model in model_rows))
    previous_trace = sys.gettrace()
    sys.settrace(collector.trace)
    try:
        tests_passed = runner()
    finally:
        sys.settrace(previous_trace)
    files: dict[str, object] = {}
    for model in model_rows:
        executed = collector.executed.get(model.path, set()) & set(model.statements)
        observed = collector.arcs.get(model.path, set()) & set(model.branches)
        missing_lines = sorted(set(model.statements) - executed)
        missing_branches = sorted(set(model.branches) - observed)
        files[str(model.path)] = {
            "executed_lines": sorted(executed),
            "missing_lines": missing_lines,
            "executed_branches": [list(item) for item in sorted(observed)],
            "missing_branches": [list(item) for item in missing_branches],
            "summary": {
                "covered_lines": len(executed),
                "num_statements": len(model.statements),
                "covered_branches": len(observed),
                "num_branches": len(model.branches),
            },
        }
    return tests_passed, {"meta": {"tool": "SM35_STDLIB_BRANCH_COVERAGE", "version": "1.0"}, "files": files}


def discover_sources(roots: Iterable[Path]) -> tuple[SourceModel, ...]:
    paths = sorted({path.resolve() for root in roots for path in root.rglob("*.py") if "__pycache__" not in path.parts})
    return tuple(analyze_source(path) for path in paths)
