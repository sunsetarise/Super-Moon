#!/usr/bin/env python3
"""Idempotently install SM36 beside SM34/SM35 without deleting inherited code."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


IMPORT = "from .sm36_api import router as sm36_router\n"
INCLUDE = "app.include_router(sm36_router)\n"


def add_after(text: str, marker: str, addition: str) -> str:
    if addition in text:
        return text
    if marker not in text:
        raise RuntimeError(f"required additive insertion marker not found: {marker!r}")
    return text.replace(marker, marker + addition, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("promptstudio_root", type=Path)
    parser.add_argument("sm36_tree", type=Path)
    args = parser.parse_args()
    studio = (args.promptstudio_root / "supermoon_studio").resolve(strict=True)
    main_path = (studio / "main.py").resolve(strict=True)
    runtime_src = args.promptstudio_root / "supermoon_runtime" / "src" / "supermoon36"
    source = (args.sm36_tree / "src" / "supermoon36").resolve(strict=True)
    shutil.copytree(source, runtime_src, dirs_exist_ok=True)
    for name in ("sm36_bridge.py", "sm36_api.py"):
        shutil.copy2(Path(__file__).with_name(name), studio / name)
    original = main_path.read_text(encoding="utf-8")
    changed = add_after(original, "from .sm35_api import router as sm35_router\n", IMPORT)
    changed = add_after(changed, "app.include_router(sm35_router)\n", INCLUDE)
    if changed != original:
        backup = main_path.with_suffix(".py.pre-sm36")
        if not backup.exists():
            shutil.copy2(main_path, backup)
        main_path.write_text(changed, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
