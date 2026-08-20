#!/usr/bin/env python3
"""Run inherited and successor unittest suites under the SM35 coverage engine."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import unittest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sm34-src", type=Path, required=True)
    parser.add_argument("--sm34-tests", type=Path, required=True)
    parser.add_argument("--sm35-src", type=Path, required=True)
    parser.add_argument("--sm35-tests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(args.sm35_src.resolve()), str(args.sm34_src.resolve())]
    runtime_path = args.sm35_src.resolve() / "supermoon35" / "coverage_runtime.py"
    spec = importlib.util.spec_from_file_location("_sm35_coverage_runtime", runtime_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load SM35 coverage runtime")
    runtime = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runtime
    spec.loader.exec_module(runtime)
    discover_sources = runtime.discover_sources
    measure = runtime.measure

    models = discover_sources((args.sm34_src / "supermoon34", args.sm35_src / "supermoon35"))

    def runner() -> bool:
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        suite.addTests(loader.discover(str(args.sm34_tests.resolve()), pattern="test*.py"))
        suite.addTests(loader.discover(str(args.sm35_tests.resolve()), pattern="test*.py"))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        runner.result = result
        return result.wasSuccessful()

    passed, payload = measure(models, runner)
    result = runner.result
    payload["tests"] = {
        "run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "passed": passed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
