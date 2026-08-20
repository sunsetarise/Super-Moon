#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon35.evidence import EvidenceDAG


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    graph = EvidenceDAG()
    parent = None
    for path in sorted(item for item in args.evidence_root.rglob("*") if item.is_file() and item.resolve() != args.output.resolve()):
        payload = {"path": path.relative_to(args.evidence_root).as_posix(), "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        node = graph.add("artifact", payload, () if parent is None else (parent,))
        parent = node.node_id
    if parent is None:
        raise ValueError("no evidence artifacts")
    terminal = graph.add("terminal_closure", {"artifacts": len(graph.nodes)}, (parent,))
    args.output.write_bytes(graph.encode())
    print(json.dumps({"nodes": len(graph.nodes), "terminal": terminal.node_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
