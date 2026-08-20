"""Dependency-free statement and branch-arc measurement for SM36."""

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


def analyze_source(path: Path) -> SourceModel:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    statements = {
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.stmt)
        and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
    }
    continuations: dict[ast.stmt, int] = {}
    def map_block(items: list[ast.stmt], continuation: int) -> None:
        for index, item in enumerate(items):
            next_line = items[index + 1].lineno if index + 1 < len(items) else continuation
            continuations[item] = next_line
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.With, ast.AsyncWith)):
                map_block(item.body, 0 if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else next_line)
            elif isinstance(item, ast.If):
                map_block(item.body, next_line); map_block(item.orelse, next_line)
            elif isinstance(item, (ast.For, ast.AsyncFor, ast.While)):
                map_block(item.body, item.lineno); map_block(item.orelse, next_line)
            elif isinstance(item, (ast.Try, ast.TryStar)):
                map_block(item.body, next_line)
                for handler in item.handlers: map_block(handler.body, next_line)
                map_block(item.orelse, next_line); map_block(item.finalbody, next_line)
            elif isinstance(item, ast.Match):
                for case in item.cases: map_block(case.body, next_line)
    map_block(tree.body, 0)
    branches: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            branches.add((node.lineno, node.body[0].lineno))
            branches.add((node.lineno, node.orelse[0].lineno if node.orelse else continuations[node]))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            branches.add((node.lineno, node.body[0].lineno))
            branches.add((node.lineno, node.orelse[0].lineno if node.orelse else continuations[node]))
        elif isinstance(node, ast.Match):
            for case in node.cases:
                if case.body: branches.add((node.lineno, case.body[0].lineno))
    branches.discard((0, 0))
    return SourceModel(path.resolve(), frozenset(statements), frozenset(branches))


@dataclass(slots=True)
class Collector:
    sources: frozenset[Path]
    lines: dict[Path, set[int]] = field(default_factory=dict)
    arcs: dict[Path, set[tuple[int, int]]] = field(default_factory=dict)
    previous: dict[int, tuple[Path, int]] = field(default_factory=dict)
    resolved_filenames: dict[str, Path] = field(default_factory=dict)

    def trace(self, frame: FrameType, event: str, argument: object) -> Callable | None:
        filename = frame.f_code.co_filename
        path = self.resolved_filenames.get(filename)
        if path is None:
            path = Path(filename).resolve(); self.resolved_filenames[filename] = path
        identity = id(frame)
        if event == "call":
            if path in self.sources:
                self.previous[identity] = (path, 0); return self.trace
            return None
        if path not in self.sources:
            return None
        if event == "line":
            line = frame.f_lineno; self.lines.setdefault(path, set()).add(line)
            previous = self.previous.get(identity)
            if previous and previous[1]: self.arcs.setdefault(path, set()).add((previous[1], line))
            self.previous[identity] = (path, line)
        elif event == "return":
            previous = self.previous.pop(identity, None)
            if previous and previous[1]:
                self.arcs.setdefault(path, set()).add((previous[1], 0))
        return self.trace


def discover_sources(roots: Iterable[Path]) -> tuple[SourceModel, ...]:
    paths = sorted({path.resolve() for root in roots for path in root.rglob("*.py") if "__pycache__" not in path.parts})
    return tuple(analyze_source(path) for path in paths)


def measure(models: Iterable[SourceModel], runner: Callable[[], bool]) -> tuple[bool, dict[str, object]]:
    rows = tuple(models); collector = Collector(frozenset(row.path for row in rows)); previous = sys.gettrace()
    sys.settrace(collector.trace)
    try:
        passed = runner()
    finally:
        sys.settrace(previous)
    files = {}
    for model in rows:
        executed = collector.lines.get(model.path, set()) & set(model.statements)
        observed = collector.arcs.get(model.path, set()) & set(model.branches)
        files[str(model.path)] = {
            "executed_lines": sorted(executed),
            "missing_lines": sorted(set(model.statements) - executed),
            "executed_branches": [list(item) for item in sorted(observed)],
            "missing_branches": [list(item) for item in sorted(set(model.branches) - observed)],
            "summary": {
                "covered_lines": len(executed), "num_statements": len(model.statements),
                "covered_branches": len(observed), "num_branches": len(model.branches),
            },
        }
    return passed, {"meta": {"tool": "SM36_STDLIB_BRANCH_COVERAGE", "version": "1.0"}, "files": files}
