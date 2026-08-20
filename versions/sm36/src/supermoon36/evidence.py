"""Append-only content-addressed evidence ledger with hash-chain verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import Artifact, ValidationError, canonical_json, safe_logical_path, sha256_json, timestamp


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    node_id: str
    sequence: int
    kind: str
    payload: Mapping[str, Any]
    parents: tuple[str, ...]
    previous_chain_sha256: str
    chain_sha256: str
    created_utc: str

    def validate(self) -> None:
        if not self.node_id.startswith("sha256:") or len(self.node_id) != 71:
            raise ValidationError("invalid evidence node ID")
        if not isinstance(self.sequence, int) or self.sequence < 0 or not self.kind:
            raise ValidationError("invalid evidence sequence or kind")
        timestamp(self.created_utc, "created_utc")
        body = {
            "sequence": self.sequence,
            "kind": self.kind,
            "payload": self.payload,
            "parents": self.parents,
            "created_utc": self.created_utc,
        }
        if self.node_id != f"sha256:{sha256_json(body)}":
            raise ValidationError("evidence node content hash mismatch")
        chain_body = {"node_id": self.node_id, "previous_chain_sha256": self.previous_chain_sha256}
        if self.chain_sha256 != sha256_json(chain_body):
            raise ValidationError("evidence chain hash mismatch")


@dataclass(slots=True)
class EvidenceLedger:
    nodes: list[EvidenceNode] = field(default_factory=list)

    @property
    def by_id(self) -> dict[str, EvidenceNode]:
        return {node.node_id: node for node in self.nodes}

    def add(
        self,
        kind: str,
        payload: Mapping[str, Any],
        parents: Iterable[str] = (),
        *,
        created_utc: str | None = None,
    ) -> EvidenceNode:
        if not isinstance(kind, str) or not kind.strip():
            raise ValidationError("evidence kind must be nonempty")
        parent_ids = tuple(sorted(set(parents)))
        known = self.by_id
        missing = [item for item in parent_ids if item not in known]
        if missing:
            raise ValidationError(f"missing evidence parents: {missing}")
        created = created_utc or datetime.now(timezone.utc).isoformat()
        timestamp(created, "created_utc")
        sequence = len(self.nodes)
        body = {"sequence": sequence, "kind": kind, "payload": dict(payload), "parents": parent_ids, "created_utc": created}
        node_id = f"sha256:{sha256_json(body)}"
        previous = self.nodes[-1].chain_sha256 if self.nodes else "0" * 64
        chain = sha256_json({"node_id": node_id, "previous_chain_sha256": previous})
        node = EvidenceNode(node_id, sequence, kind, dict(payload), parent_ids, previous, chain, created)
        node.validate()
        if node_id in known:
            raise ValidationError("duplicate evidence node")
        self.nodes.append(node)
        return node

    def add_artifact(self, path: Path, root: Path, *, parents: Iterable[str] = (), created_utc: str | None = None) -> EvidenceNode:
        try:
            resolved = path.resolve(strict=True)
            base = root.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValidationError("artifact or evidence root does not exist") from exc
        if resolved != base and base not in resolved.parents:
            raise ValidationError("artifact is outside evidence root")
        logical = resolved.relative_to(base).as_posix()
        safe_logical_path(logical)
        digest = hashlib.sha256(); total = 0
        with resolved.open("rb") as stream:
            while chunk := stream.read(4 * 1024 * 1024):
                total += len(chunk); digest.update(chunk)
        artifact = Artifact(f"artifact:{digest.hexdigest()[:24]}", logical, total, digest.hexdigest())
        artifact.validate()
        return self.add("artifact", asdict(artifact), parents, created_utc=created_utc)

    def verify(self) -> bool:
        known: set[str] = set()
        previous = "0" * 64
        for index, node in enumerate(self.nodes):
            node.validate()
            if node.sequence != index or node.previous_chain_sha256 != previous:
                raise ValidationError("evidence chain sequence discontinuity")
            if any(parent not in known for parent in node.parents):
                raise ValidationError("evidence parent is not antecedent")
            if node.node_id in known:
                raise ValidationError("duplicate evidence node ID")
            known.add(node.node_id)
            previous = node.chain_sha256
        return True

    def closure(self, terminal_id: str) -> tuple[str, ...]:
        lookup = self.by_id
        if terminal_id not in lookup:
            raise ValidationError("unknown terminal evidence node")
        visited: set[str] = set(); stack = [terminal_id]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current); stack.extend(lookup[current].parents)
        return tuple(sorted(visited))

    def encode(self) -> bytes:
        self.verify()
        return canonical_json({"format": "SM36_EVIDENCE_LEDGER_V1", "nodes": [asdict(node) for node in self.nodes]}) + b"\n"

    @classmethod
    def decode(cls, payload: bytes) -> "EvidenceLedger":
        try:
            value = json.loads(payload)
            if value.get("format") != "SM36_EVIDENCE_LEDGER_V1" or not isinstance(value.get("nodes"), list):
                raise ValidationError("invalid evidence ledger envelope")
            ledger = cls([EvidenceNode(**{**row, "parents": tuple(row["parents"])}) for row in value["nodes"]])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("malformed evidence ledger") from exc
        ledger.verify()
        return ledger


def write_ledger(path: Path, ledger: EvidenceLedger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(ledger.encode())
    temporary.replace(path)
