"""Shared command-line support for physical qualification drivers."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon35.physical import detect_capability, unavailable_receipt


def environment() -> dict[str, object]:
    return {"python": sys.version, "platform": platform.platform(), "machine": platform.machine()}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def unavailable(track: str, output: Path, limitation: str) -> int:
    capability = detect_capability(track)
    receipt = unavailable_receipt(track, {**environment(), "capability": asdict(capability)}, limitation, timestamp=timestamp())
    write_json(output, receipt.payload())
    return 3
