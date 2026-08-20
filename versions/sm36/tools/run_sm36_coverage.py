#!/usr/bin/env python3
"""Run SM34, SM35, and SM36 unittest suites under one branch-aware tracer."""

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
    for version in (34, 35, 36):
        parser.add_argument(f"--sm{version}-src", type=Path, required=True)
        parser.add_argument(f"--sm{version}-tests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = [getattr(args, f"sm{version}_src").resolve() for version in (34, 35, 36)]
    tests = [getattr(args, f"sm{version}_tests").resolve() for version in (34, 35, 36)]
    sys.path[:0] = [str(path) for path in reversed(sources)]
    models = discover_sources(tuple(path / f"supermoon{version}" for path, version in zip(sources, (34, 35, 36))))
    def runner() -> bool:
        # The tracer itself is imported through the supermoon36 package. Purge all
        # measured packages after tracing starts so module initialization, enum and
        # dataclass definitions, and import-time registration are measured too.
        for name in tuple(sys.modules):
            if any(name == f"supermoon{version}" or name.startswith(f"supermoon{version}.") for version in (34, 35, 36)):
                del sys.modules[name]
        suite = unittest.TestSuite(); loader = unittest.TestLoader()
        for root in tests:
            suite.addTests(loader.discover(str(root), pattern="test*.py"))
        runner.result = unittest.TextTestRunner(verbosity=2).run(suite)
        return runner.result.wasSuccessful()
    passed, payload = measure(models, runner)
    result = runner.result
    payload["tests"] = {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "passed": passed}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
