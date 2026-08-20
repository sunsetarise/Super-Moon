#!/usr/bin/env python3
"""Idempotently install the additive SM35 bridge without deleting SM34 code."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


IMPORT = "from .sm35_api import router as sm35_router\n"
INCLUDE = "app.include_router(sm35_router)\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("promptstudio_root", type=Path)
    parser.add_argument("sm35_tree", type=Path)
    args = parser.parse_args()
    studio = args.promptstudio_root / "supermoon_studio"
    runtime_src = args.promptstudio_root / "supermoon_runtime" / "src" / "supermoon35"
    shutil.copytree(args.sm35_tree / "src" / "supermoon35", runtime_src, dirs_exist_ok=True)
    for name in ("sm35_bridge.py", "sm35_api.py"):
        shutil.copy2(Path(__file__).with_name(name), studio / name)
    main_path = studio / "main.py"
    text = main_path.read_text(encoding="utf-8")
    if IMPORT not in text:
        marker = "from .sm34_bridge import overview as sm34_overview, runtime_status as sm34_runtime_status, validation as sm34_validation\n"
        text = text.replace(marker, marker + IMPORT)
    if INCLUDE not in text:
        marker = 'app=FastAPI(title=APP_NAME,version=__version__)\n'
        text = text.replace(marker, marker + INCLUDE)
    main_path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
