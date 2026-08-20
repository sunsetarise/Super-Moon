"""Command-line interface for registry, methodology, capability, and release status."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Sequence

from . import RELEASE_NAME, RELEASE_STATE, VERSION
from .methodology import ExecutionContext, MethodologyExecutor
from .physical import capability_matrix
from .qualification import candidate_decision
from .registry import MethodologyRegistry


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="supermoon36")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("capabilities")
    commands.add_parser("score")
    registry_command = commands.add_parser("registry")
    registry_command.add_argument("registry", type=Path)
    method_command = commands.add_parser("methodology")
    method_command.add_argument("registry", type=Path)
    method_command.add_argument("methodology_id")
    method_command.add_argument("--evidence", type=Path)
    method_command.add_argument("--physical-execution", action="store_true")
    method_command.add_argument("--authorize", action="store_true")
    method_command.add_argument("--reviewer")
    args = parser.parse_args(argv)
    if args.command == "status":
        _json({"name": RELEASE_NAME, "state": RELEASE_STATE, "version": VERSION, "methodologies": 15000})
    elif args.command == "capabilities":
        _json([asdict(item) for item in capability_matrix()])
    elif args.command == "score":
        decision = candidate_decision(); _json({**asdict(decision), "state": decision.state.value})
    elif args.command == "registry":
        _json(MethodologyRegistry.read_jsonl_gz(args.registry).summary())
    else:
        registry = MethodologyRegistry.read_jsonl_gz(args.registry)
        evidence = json.loads(args.evidence.read_text(encoding="utf-8")) if args.evidence else {}
        context = ExecutionContext(
            evidence,
            physical_execution=args.physical_execution,
            independent_review=bool(args.reviewer),
            reviewer=args.reviewer,
            authorized=args.authorize,
        )
        result = MethodologyExecutor().execute(registry.get(args.methodology_id), context)
        _json(result.payload())
    return 0
