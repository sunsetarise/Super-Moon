"""Real-wall-clock endurance, telemetry, atomic checkpoint, and restart logic."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Callable, Mapping

try:
    import resource as _resource
except ImportError:  # Windows does not provide the POSIX resource module.
    _resource = None

try:
    import psutil as _psutil
except ImportError:  # The Studio profile installs psutil; keep runtime importable without it.
    _psutil = None

from .contracts import ExecutionStatus, InvalidInput
from .evidence import canonical_json, sha256_file


def _max_rss_kib() -> int:
    """Return peak/current resident memory in KiB on Unix, macOS, and Windows."""
    if _resource is not None:
        value = int(_resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss)
        # macOS reports bytes; Linux and other supported Unix targets report KiB.
        return max(0, value // 1024 if sys.platform == "darwin" else value)
    if _psutil is not None:
        try:
            return max(0, int(_psutil.Process(os.getpid()).memory_info().rss) // 1024)
        except Exception:
            return 0
    return 0


def _fsync_directory(directory: Path) -> None:
    """Persist a directory entry where supported; Windows has no directory fsync."""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        directory_fd = os.open(directory, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(directory_fd)
        except OSError:
            pass
    finally:
        os.close(directory_fd)


@dataclass(frozen=True, slots=True)
class Heartbeat:
    sequence: int
    elapsed_seconds: float
    wall_utc: str
    max_rss_kib: int
    work_digest: str


@dataclass(frozen=True, slots=True)
class EnduranceReceipt:
    status: ExecutionStatus
    requested_seconds: float
    elapsed_seconds: float
    heartbeat_count: int
    checkpoint_sha256: str
    telemetry_sha256: str
    qualified_profile: str | None
    failures: tuple[str, ...]


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json(payload) + b"\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class EnduranceRunner:
    def run(
        self,
        duration_seconds: float,
        work: Callable[[int], bytes],
        *,
        checkpoint: Path,
        telemetry: Path,
        heartbeat_seconds: float = 60.0,
    ) -> EnduranceReceipt:
        if duration_seconds <= 0 or heartbeat_seconds <= 0:
            raise InvalidInput("durations must be positive")
        if heartbeat_seconds > duration_seconds:
            heartbeat_seconds = duration_seconds
        started = time.monotonic()
        sequence = 0
        previous = ""
        heartbeats: list[Heartbeat] = []
        failures: list[str] = []
        while True:
            payload = work(sequence)
            if not isinstance(payload, bytes):
                raise InvalidInput("endurance work callback must return bytes")
            previous = hashlib.sha256(previous.encode("ascii") + payload).hexdigest()
            elapsed = time.monotonic() - started
            heartbeat = Heartbeat(
                sequence,
                elapsed,
                datetime.now(timezone.utc).isoformat(),
                _max_rss_kib(),
                previous,
            )
            heartbeats.append(heartbeat)
            _atomic_json(checkpoint, {"format": "SM34_CHECKPOINT_V1", "heartbeat": asdict(heartbeat), "chain": previous})
            _atomic_json(telemetry, {"format": "SM34_ENDURANCE_TELEMETRY_V1", "requested_seconds": duration_seconds, "heartbeats": [asdict(item) for item in heartbeats]})
            sequence += 1
            if elapsed >= duration_seconds:
                break
            time.sleep(min(heartbeat_seconds, duration_seconds - elapsed))
        elapsed = time.monotonic() - started
        profile = "ENDURANCE_72H" if duration_seconds >= 72 * 3600 and elapsed >= 72 * 3600 else ("ENDURANCE_24H" if duration_seconds >= 24 * 3600 and elapsed >= 24 * 3600 else None)
        status = ExecutionStatus.PASS if profile is not None and not failures else ExecutionStatus.PASS_WITH_LIMITATIONS
        return EnduranceReceipt(status, duration_seconds, elapsed, len(heartbeats), sha256_file(checkpoint), sha256_file(telemetry), profile, tuple(failures))

    @staticmethod
    def load_checkpoint(path: Path) -> Mapping[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format") != "SM34_CHECKPOINT_V1" or "chain" not in payload:
            raise InvalidInput("invalid SM34 checkpoint")
        return payload
