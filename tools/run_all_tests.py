#!/usr/bin/env python3
"""Run version-isolated test suites to avoid historical package collisions."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(label: str, test_paths: list[str], python_paths: list[Path], cwd: Path | None = None) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in python_paths)
    command = [sys.executable, "-m", "pytest", "-q", *test_paths]
    print(f"== {label} ==", flush=True)
    subprocess.run(command, cwd=cwd or ROOT, env=env, check=True)


def main() -> int:
    sm34 = ROOT / "versions" / "sm34"
    sm35 = ROOT / "versions" / "sm35"
    sm36 = ROOT / "versions" / "sm36"
    run(
        "SM34 Prompt Studio",
        ["tests", "supermoon_runtime/tests"],
        [sm34, sm34 / "supermoon_runtime" / "src"],
        sm34,
    )
    run("SM35", ["tests/sm35"], [sm35 / "src"], sm35)
    run(
        "SM36",
        ["tests"],
        [sm36 / "src", sm35 / "src", sm34 / "supermoon_runtime" / "src"],
        sm36,
    )
    print("all_version_suites=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

