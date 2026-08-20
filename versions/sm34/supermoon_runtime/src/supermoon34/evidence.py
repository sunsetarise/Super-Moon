"""Content-addressed evidence, immutable manifests, and hash-chain receipts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import ArtifactRef, EvidenceError, InvalidInput


def json_value(value: Any) -> Any:
    if is_dataclass(value):
        return {key: json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [json_value(item) for item in value]
    if isinstance(value, float) and not (value == value and abs(value) != float("inf")):
        raise InvalidInput("non-finite numbers are forbidden in canonical evidence")
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(json_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path, *, limit_bytes: int | None = None) -> str:
    digest = hashlib.sha256()
    remaining = limit_bytes
    with path.open("rb") as stream:
        while remaining is None or remaining > 0:
            chunk = stream.read(1024 * 1024 if remaining is None else min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    if remaining not in (None, 0):
        raise EvidenceError(f"file shorter than required prefix: {path}")
    return digest.hexdigest()


def artifact_from_file(path: Path, kind: str, *, logical_path: str | None = None) -> ArtifactRef:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise InvalidInput(f"artifact is not a file: {path}")
    digest = sha256_file(resolved)
    return ArtifactRef(f"sha256:{digest}", digest, resolved.stat().st_size, kind, logical_path or str(path))


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    node_id: str
    kind: str
    payload: Mapping[str, Any]
    parents: tuple[str, ...]
    created_utc: str


@dataclass(slots=True)
class EvidenceGraph:
    """Append-only DAG whose node IDs commit to the complete node content."""

    nodes: dict[str, EvidenceNode] = field(default_factory=dict)

    def add(
        self,
        kind: str,
        payload: Mapping[str, Any],
        parents: Iterable[str] = (),
        *,
        created_utc: str | None = None,
    ) -> EvidenceNode:
        if not kind:
            raise InvalidInput("evidence kind must be nonempty")
        parent_tuple = tuple(sorted(set(parents)))
        missing = tuple(parent for parent in parent_tuple if parent not in self.nodes)
        if missing:
            raise EvidenceError(f"missing evidence parents: {missing}")
        timestamp = created_utc or datetime.now(timezone.utc).isoformat()
        body = {"kind": kind, "payload": dict(payload), "parents": parent_tuple, "created_utc": timestamp}
        node_id = f"sha256:{sha256_bytes(canonical_json(body))}"
        node = EvidenceNode(node_id, kind, dict(payload), parent_tuple, timestamp)
        self.nodes.setdefault(node_id, node)
        return self.nodes[node_id]

    def verify(self) -> bool:
        for node_id, node in self.nodes.items():
            if any(parent not in self.nodes for parent in node.parents):
                raise EvidenceError(f"missing parent for {node_id}")
            body = {"kind": node.kind, "payload": node.payload, "parents": node.parents, "created_utc": node.created_utc}
            expected = f"sha256:{sha256_bytes(canonical_json(body))}"
            if expected != node_id:
                raise EvidenceError(f"hash mismatch for evidence node {node_id}")
        return True

    def encode(self) -> bytes:
        self.verify()
        return canonical_json({"format": "SM34_EVIDENCE_DAG_V1", "nodes": [self.nodes[key] for key in sorted(self.nodes)]}) + b"\n"


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    path: str
    size_bytes: int
    sha256: str


def build_manifest(root: Path, *, exclude: Iterable[str] = ()) -> tuple[ManifestEntry, ...]:
    resolved = root.resolve(strict=True)
    excluded = set(exclude)
    rows: list[ManifestEntry] = []
    for path in sorted(item for item in resolved.rglob("*") if item.is_file()):
        relative = path.relative_to(resolved).as_posix()
        if relative in excluded:
            continue
        rows.append(ManifestEntry(relative, path.stat().st_size, sha256_file(path)))
    return tuple(rows)


def verify_manifest(root: Path, rows: Iterable[ManifestEntry]) -> bool:
    resolved = root.resolve(strict=True)
    for row in rows:
        target = (resolved / row.path).resolve(strict=True)
        if resolved != target and resolved not in target.parents:
            raise EvidenceError(f"manifest path escapes root: {row.path}")
        if target.stat().st_size != row.size_bytes or sha256_file(target) != row.sha256:
            raise EvidenceError(f"manifest mismatch: {row.path}")
    return True


def append_hash_chain(previous: str | None, payload: Mapping[str, Any]) -> str:
    """Create a tamper-evident chain link without pretending it is a signature."""

    if previous is not None and (len(previous) != 64 or any(c not in "0123456789abcdef" for c in previous)):
        raise InvalidInput("previous link must be a SHA-256 hex digest")
    return sha256_bytes(canonical_json({"previous": previous, "payload": payload}))

