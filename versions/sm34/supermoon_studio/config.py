from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    static_dir: Path = ROOT / "static"
    runtime_dir: Path = ROOT / "runtime"
    output_dir: Path = ROOT / "output"
    knowledge_dir: Path = ROOT / "knowledge"
    supermoon_runtime_dir: Path = ROOT / "supermoon_runtime"
    sm32_runtime_dir: Path = ROOT / "supermoon_runtime"
    knowledge_gz: Path = ROOT / "knowledge" / "SUPER_MOON_34_NEW_UNIVERSE_OMEGA_FULLY_IMPLEMENTED_FULL_MERGED.txt.gz"
    knowledge_db: Path = ROOT / "runtime" / "knowledge_index.sqlite3"
    knowledge_chunks: Path = ROOT / "runtime" / "knowledge_chunks.bin"
    host: str = os.getenv("SM34_HOST", os.getenv("SM32_HOST", "127.0.0.1"))
    port: int = int(os.getenv("SM34_PORT", os.getenv("SM32_PORT", "8892")))
    babylon_version: str = "9.21.2"

settings = Settings()
for p in (settings.runtime_dir, settings.output_dir):
    p.mkdir(parents=True, exist_ok=True)
