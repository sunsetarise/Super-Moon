#!/usr/bin/env python3
"""Build frozen baseline, capability, limitation, SBOM, and source receipts."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import gzip
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon34.capabilities import TRACKS, validate_registry
from supermoon34.evidence import build_manifest, sha256_file


def decompressed(path: Path) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    size = 0
    lines = 0
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
            lines += chunk.count(b"\n")
    return size, lines, digest.hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve(symbol: str) -> bool:
    module_name, attribute = symbol.rsplit(".", 1)
    return hasattr(importlib.import_module(module_name), attribute)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("sm33_gzip", type=Path)
    parser.add_argument("prompt_gzip", type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    evidence = root / "evidence"
    base_size, base_lines, base_decompressed_sha = decompressed(args.sm33_gzip)
    prompt_size, prompt_lines, prompt_decompressed_sha = decompressed(args.prompt_gzip)
    baseline = {
        "format": "SM34_FROZEN_BASELINE_V1",
        "policy": "The full SM33 decompressed stream is the immutable SM34 prefix.",
        "sm33": {
            "compressed_bytes": args.sm33_gzip.stat().st_size,
            "compressed_sha256": sha256_file(args.sm33_gzip),
            "decompressed_bytes": base_size,
            "decompressed_lines": base_lines,
            "decompressed_sha256": base_decompressed_sha,
        },
        "master_prompt": {
            "compressed_bytes": args.prompt_gzip.stat().st_size,
            "compressed_sha256": sha256_file(args.prompt_gzip),
            "decompressed_bytes": prompt_size,
            "decompressed_lines": prompt_lines,
            "decompressed_sha256": prompt_decompressed_sha,
        },
    }
    write(evidence / "SM34_BASELINE_FROZEN_RECEIPT.json", baseline)
    validate_registry()
    capabilities = []
    for track in TRACKS:
        row = asdict(track)
        row["backend"] = track.backend.value
        row["claim_level"] = track.claim_level.value
        row["symbol_resolved"] = resolve(track.implementation_symbol)
        capabilities.append(row)
    if not all(row["symbol_resolved"] for row in capabilities):
        raise RuntimeError("a capability source symbol did not resolve")
    write(evidence / "SM34_CAPABILITIES.json", {"format": "SM34_CAPABILITY_REGISTRY_V1", "tracks": capabilities})
    limitations = {
        "format": "SM34_KNOWN_LIMITATIONS_V1",
        "release_gate_state": "BLOCKED_PENDING_REAL_EXECUTION",
        "items": [
            "PETSc/mpi4py are absent from the build environment; no rank qualification executed.",
            "OpenFOAM and SU2 are absent; no CFD cross-validation executed.",
            "CadQuery/OCCT are absent; no CAD round-trip qualification executed.",
            "No external Slurm allocation or scheduler accounting receipt exists.",
            "No CUDA/ROCm device is visible; GPU execution remains unavailable.",
            "24-hour and 72-hour endurance profiles have not elapsed.",
            "No independent operator on a distinct second physical machine has reproduced the release.",
            "Aerospace models are preliminary computational research and do not constitute certification, airworthiness approval, or safe-to-fly authorization."
        ]
    }
    write(evidence / "SM34_KNOWN_LIMITATIONS.json", limitations)
    packages = []
    for name in ("numpy", "scipy", "PyYAML"):
        try:
            version = importlib.metadata.version(name)
            packages.append({"name": name, "version": version, "scope": "runtime"})
        except importlib.metadata.PackageNotFoundError:
            packages.append({"name": name, "version": None, "scope": "unavailable"})
    sbom = {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": "urn:uuid:sm34-new-universe-local", "version": 1, "metadata": {"component": {"type": "application", "name": "supermoon34-new-universe", "version": "34.0.0"}}, "components": packages}
    write(evidence / "SM34_SBOM.cdx.json", sbom)
    manifest = build_manifest(root, exclude=("evidence/SM34_SOURCE_MANIFEST.json",))
    write(evidence / "SM34_SOURCE_MANIFEST.json", {"format": "SM34_SOURCE_MANIFEST_V1", "files": [asdict(item) for item in manifest]})
    print(json.dumps({"baseline": baseline, "capabilities": len(capabilities), "manifest_files": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()

