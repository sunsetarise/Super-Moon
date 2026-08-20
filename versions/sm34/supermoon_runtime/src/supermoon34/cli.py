"""Command-line control surface for Super Moon 34 New Universe."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Sequence

from . import RELEASE_NAME, __version__
from .backends import probe_all
from .capabilities import TRACKS, validate_registry
from .qualification import decision_payload, unexecuted_release
from .requirements import compile_prompt
from .validation import ValidationSuite


def _encode(value: object) -> str:
    def default(item):
        if hasattr(item, "value"):
            return item.value
        if hasattr(item, "__dataclass_fields__"):
            return asdict(item)
        raise TypeError(type(item).__name__)
    return json.dumps(value, indent=2, sort_keys=True, default=default)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="supermoon34", description=RELEASE_NAME)
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("backends")
    subparsers.add_parser("capabilities")
    subparsers.add_parser("qualification")
    subparsers.add_parser("selftest")
    compile_parser = subparsers.add_parser("compile-requirements")
    compile_parser.add_argument("prompt", type=Path)
    compile_parser.add_argument("output", type=Path)
    arguments = parser.parse_args(argv)

    if arguments.command == "backends":
        print(_encode({"release": RELEASE_NAME, "probes": probe_all()}))
        return 0
    if arguments.command == "capabilities":
        validate_registry()
        print(_encode({"release": RELEASE_NAME, "tracks": TRACKS}))
        return 0
    if arguments.command == "qualification":
        decision = unexecuted_release()
        print(_encode(decision_payload(decision)))
        return 0 if decision.passed else 2
    if arguments.command == "compile-requirements":
        summary = compile_prompt(arguments.prompt, arguments.output)
        print(_encode(summary))
        return 0
    validation = ValidationSuite().run()
    passed = validation.status.value == "PASS"
    print(_encode({"release": RELEASE_NAME, "version": __version__, "selftest": "PASS" if passed else "FAIL", "validation": validation, "release_qualification": "BLOCKED_PENDING_REAL_EXECUTION"}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

