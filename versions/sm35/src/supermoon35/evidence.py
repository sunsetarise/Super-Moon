"""Content-addressed append-only evidence DAG with terminal closure."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .contracts import ValidationError, canonical_json, sha256_json


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    node_id: str
    kind: str
    payload: Mapping[str, Any]
    parents: tuple[str, ...]
    created_utc: str


@dataclass(slots=True)
class EvidenceDAG:
    nodes: dict[str, EvidenceNode] = field(default_factory=dict)

    def add(self, kind: str, payload: Mapping[str, Any], parents: Iterable[str] = (), *, created_utc: str | None = None) -> EvidenceNode:
        if not kind:
            raise ValidationError("evidence kind must be nonempty")
        parent_ids = tuple(sorted(set(parents)))
        missing = tuple(item for item in parent_ids if item not in self.nodes)
        if missing:
            raise ValidationError(f"missing evidence parents: {missing}")
        timestamp = created_utc or datetime.now(timezone.utc).isoformat()
        body = {"kind": kind, "payload": dict(payload), "parents": parent_ids, "created_utc": timestamp}
        node_id = f"sha256:{sha256_json(body)}"
        node = EvidenceNode(node_id, kind, dict(payload), parent_ids, timestamp)
        existing = self.nodes.get(node_id)
        if existing is not None and existing != node:
            raise ValidationError("evidence node ID collision")
        self.nodes[node_id] = node
        return node

    def verify(self) -> bool:
        for node_id, node in self.nodes.items():
            if any(parent not in self.nodes for parent in node.parents):
                raise ValidationError(f"missing parent for {node_id}")
            body = {"kind": node.kind, "payload": node.payload, "parents": node.parents, "created_utc": node.created_utc}
            if node_id != f"sha256:{sha256_json(body)}":
                raise ValidationError(f"node hash mismatch for {node_id}")
        return True

    def terminal_closure(self, terminal_id: str) -> tuple[str, ...]:
        if terminal_id not in self.nodes:
            raise ValidationError("unknown terminal node")
        visited: set[str] = set()
        stack = [terminal_id]
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            stack.extend(self.nodes[node_id].parents)
        return tuple(sorted(visited))

    def encode(self) -> bytes:
        self.verify()
        rows = [asdict(self.nodes[key]) for key in sorted(self.nodes)]
        return canonical_json({"format": "SM35_EVIDENCE_DAG_V1", "nodes": rows}) + b"\n"
