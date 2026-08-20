"""SM35 qualification-candidate command line interface."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from typing import Sequence

from . import RELEASE_NAME, RELEASE_STATE, VERSION
from .physical import capability_matrix
from .qualification import candidate_decision


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="supermoon35")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("capabilities")
    sub.add_parser("score")
    args = parser.parse_args(argv)
    if args.command == "status":
        payload = {"name": RELEASE_NAME, "state": RELEASE_STATE, "version": VERSION}
    elif args.command == "capabilities":
        payload = [asdict(item) for item in capability_matrix()]
    else:
        decision = candidate_decision()
        payload = {**asdict(decision), "status": decision.status.value}
    print(json.dumps(payload, sort_keys=True, default=str))
    return 0
