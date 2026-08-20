#!/usr/bin/env python3
"""Measure a selected additive test pattern over the complete source universe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon36.coverage_runtime import discover_sources, measure


def main() -> int:
    parser = argparse.ArgumentParser()
    for version in (34, 35, 36): parser.add_argument(f"--sm{version}-src", type=Path, required=True)
    parser.add_argument("--tests", type=Path, required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = [getattr(args, f"sm{version}_src").resolve() for version in (34, 35, 36)]
    sys.path[:0] = [str(path) for path in reversed(sources)]
    models = discover_sources(tuple(path / f"supermoon{version}" for path, version in zip(sources, (34, 35, 36))))
    def runner() -> bool:
        for name in tuple(sys.modules):
            if any(name == f"supermoon{version}" or name.startswith(f"supermoon{version}.") for version in (34, 35, 36)):
                del sys.modules[name]
        suite = unittest.TestLoader().discover(str(args.tests.resolve()), pattern=args.pattern)
        runner.result = unittest.TextTestRunner(verbosity=2).run(suite)
        return runner.result.wasSuccessful()
    passed, payload = measure(models, runner); result = runner.result
    payload["tests"] = {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "passed": passed, "pattern": args.pattern}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if passed else 2


if __name__ == "__main__": raise SystemExit(main())
