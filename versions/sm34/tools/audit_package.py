from __future__ import annotations

import gzip
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import py_compile
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
REPORT = RUNTIME / "FULL_AUDIT_REPORT.json"
KNOWLEDGE = ROOT / "knowledge" / "SUPER_MOON_34_NEW_UNIVERSE_OMEGA_FULLY_IMPLEMENTED_FULL_MERGED.txt.gz"
EXPECTED_KNOWLEDGE_GZIP_SHA256 = "0e077a7237b2bbaea1343cc73b6f025562b6a00d7a0469be78fba0ac72436a64"
EXPECTED_KNOWLEDGE_DECOMPRESSED_SHA256 = "8d96f961541706dc8fbe419a332bace0f14648807e60eccd48dabb6a0b1330ac"
EXPECTED_KNOWLEDGE_DECOMPRESSED_BYTES = 721679960

EXPECTED_WINDOWS_PYTHON = r"C:\Users\zero\AppData\Local\Programs\Python\Python314\python.exe"
EXPECTED_DEPS = {
    "fastapi": "0.140.8",
    "uvicorn": "0.39.0",
    "python-multipart": "0.0.32",
    "pydantic": "2.12.5",
    "pydantic-core": "2.41.5",
    "reportlab": "5.0.0",
    "numpy": "2.5.1",
    "scipy": "1.17.0",
    "psutil": "7.2.2",
    "pytest": "9.0.2",
    "httpx": "0.28.1",
}

CRITICAL = [
    "SETUP_WINDOWS.bat",
    "START_SUPERMOON.bat",
    "CHECK_INSTALLATION.bat",
    "RUN_FULL_AUDIT.bat",
    "requirements-py314.txt",
    "supermoon_runtime/evidence/SM34_WINDOWS_PORTABILITY_OVERLAY.json",
    "tools/windows_bootstrap.py",
    "tools/build_knowledge_index.py",
    "tools/reconstruct_sm34.py",
    "supermoon_studio/main.py",
    "supermoon_studio/analysis_engine.py",
    "supermoon_studio/report_engine.py",
    "supermoon_studio/sm34_bridge.py",
    "supermoon_runtime/src/supermoon34/__init__.py",
    "supermoon_runtime/src/supermoon32/__init__.py",
    "supermoon_runtime/src/supermoon32/qualified/__init__.py",
    "static/index.html",
    "static/js/app.js",
    "static/css/sm34.css",
]


def main() -> int:
    started = time.time()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    result: dict = {
        "ok": True,
        "audited_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "python_base_executable": getattr(sys, "_base_executable", sys.executable),
        "platform": platform.platform(),
        "checks": {},
        "issues": [],
        "warnings": [],
    }

    missing = [x for x in CRITICAL if not (ROOT / x).exists()]
    result["checks"]["critical_files"] = {"ok": not missing, "missing": missing}
    if missing:
        result["issues"].append(f"missing critical files: {missing}")

    obsolete = [
        "APPLY_PY314_EXACT_PATH_PATCH.bat", "APPLY_PY314_LOCATION_FIX.bat",
        "APPLY_PYTHON314_PATCH.bat", "PATCH_RECEIPT.json", "README_PATCH.txt",
        "payload", "patch_backups", "tools/DETECT_PYTHON.bat",
        "tools/PY314_ZERO_PATH.bat", "tools/install_py314_deps.py",
    ]
    present_obsolete = [x for x in obsolete if (ROOT / x).exists()]
    generated_in_release = [x for x in (".venv",) if (ROOT / x).exists()]
    result["checks"]["release_hygiene"] = {
        "ok": not present_obsolete,
        "obsolete_present": present_obsolete,
        "bundled_environment_present": generated_in_release,
    }
    if present_obsolete:
        result["issues"].append("release contains obsolete patch/bootstrap artifacts")

    py_files = (
        list((ROOT / "supermoon_studio").glob("*.py"))
        + list((ROOT / "tools").glob("*.py"))
        + list((ROOT / "supermoon_runtime" / "src" / "supermoon34").rglob("*.py"))
    )
    compile_errors = []
    for path in py_files:
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:
            compile_errors.append(f"{path.relative_to(ROOT)}: {type(exc).__name__}: {exc}")
    result["checks"]["python_compile"] = {"ok": not compile_errors, "errors": compile_errors}
    if compile_errors:
        result["issues"].append("Python compilation errors")

    imports = {}
    for name in ("fastapi", "uvicorn", "pydantic", "pydantic_core", "numpy", "scipy", "psutil", "reportlab", "httpx"):
        try:
            mod = importlib.import_module(name)
            imports[name] = getattr(mod, "__version__", getattr(mod, "Version", "ok"))
        except Exception as exc:
            imports[name] = f"ERROR {type(exc).__name__}: {exc}"
            if os.name == "nt":
                result["issues"].append(f"import failed: {name}")
            else:
                result["warnings"].append(f"non-Windows audit host lacks target dependency: {name}")
    result["checks"]["imports"] = imports

    # Verify the packaged dependency contract separately from whatever versions
    # happen to exist in the build/audit environment.
    req = ROOT / "requirements-py314.txt"
    generic_req = ROOT / "requirements.txt"
    req_lines = {
        line.strip() for line in req.read_text("utf-8", errors="replace").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    } if req.exists() else set()
    expected_lines = {f"{name}=={version}" for name, version in EXPECTED_DEPS.items()}
    dependency_profile_ok = req_lines == expected_lines and generic_req.exists() and generic_req.read_bytes() == req.read_bytes()
    result["checks"]["dependency_profile"] = {
        "ok": dependency_profile_ok,
        "expected": sorted(expected_lines),
        "actual": sorted(req_lines),
        "requirements_mirrored": generic_req.exists() and generic_req.read_bytes() == req.read_bytes(),
        "binary_only_installer": "--only-binary=:all:" in (ROOT / "tools" / "windows_bootstrap.py").read_text("utf-8", errors="replace"),
    }
    if not dependency_profile_ok or not result["checks"]["dependency_profile"]["binary_only_installer"]:
        result["issues"].append("Python 3.14 dependency contract is inconsistent")

    # On the supported Windows deployment, the current venv must resolve to the
    # exact base interpreter configured by the user. On non-Windows build hosts
    # this becomes a static packaging check only.
    bats = [
        ROOT / "SETUP_WINDOWS.bat", ROOT / "START_SUPERMOON.bat",
        ROOT / "CHECK_INSTALLATION.bat", ROOT / "RUN_FULL_AUDIT.bat",
        ROOT / "REBUILD_KNOWLEDGE_INDEX.bat",
    ]
    static_exact = all(EXPECTED_WINDOWS_PYTHON.lower() in x.read_text("utf-8", errors="replace").lower() for x in bats if x.exists())
    bootstrap_text = (ROOT / "tools" / "windows_bootstrap.py").read_text("utf-8", errors="replace")
    static_exact = static_exact and EXPECTED_WINDOWS_PYTHON.lower() in bootstrap_text.lower()
    python_contract = {"ok": static_exact, "expected_base": EXPECTED_WINDOWS_PYTHON, "mode": "static-non-windows"}
    if os.name == "nt":
        import struct
        base_actual = os.path.normcase(os.path.abspath(getattr(sys, "_base_executable", sys.executable)))
        base_expected = os.path.normcase(os.path.abspath(EXPECTED_WINDOWS_PYTHON))
        python_contract.update({
            "mode": "runtime-windows",
            "current_version": sys.version.split()[0],
            "current_bits": struct.calcsize("P") * 8,
            "current_base": getattr(sys, "_base_executable", sys.executable),
        })
        python_contract["ok"] = (
            static_exact and sys.implementation.name == "cpython" and
            sys.version_info[:2] == (3, 14) and struct.calcsize("P") * 8 == 64 and
            base_actual == base_expected
        )
    result["checks"]["python314_exact_path_contract"] = python_contract
    if not python_contract["ok"]:
        result["issues"].append("exact Python 3.14 base-path contract failed")

    try:
        from supermoon_studio.sm32_bridge import runtime_status
        status = runtime_status()
        result["checks"]["embedded_sm32"] = status
        if not status.get("available"):
            result["issues"].append("embedded SM32 runtime unavailable")
    except Exception as exc:
        result["checks"]["embedded_sm32"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}
        result["issues"].append("embedded SM32 runtime import failed")

    try:
        from supermoon_studio.sm34_bridge import runtime_status as sm34_runtime_status, validation as sm34_validation
        sm34_status = sm34_runtime_status()
        sm34_local = sm34_validation()
        result["checks"]["embedded_sm34"] = {"runtime": sm34_status, "local_validation": sm34_local}
        if not sm34_status.get("available") or sm34_local.get("status") != "PASS":
            result["issues"].append("embedded SM34 runtime or local validation unavailable")
    except Exception as exc:
        result["checks"]["embedded_sm34"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}
        result["issues"].append("embedded SM34 runtime import failed")

    if not KNOWLEDGE.exists():
        result["checks"]["knowledge_gzip"] = {"ok": False, "error": "missing"}
        result["issues"].append("canonical knowledge gzip missing")
    else:
        try:
            compressed_hash = hashlib.sha256()
            with KNOWLEDGE.open("rb") as raw_fh:
                for block in iter(lambda: raw_fh.read(8 * 1024 * 1024), b""):
                    compressed_hash.update(block)
            compressed_digest = compressed_hash.hexdigest()
            h = hashlib.sha256()
            total = 0
            with gzip.open(KNOWLEDGE, "rb") as fh:
                while True:
                    block = fh.read(8 * 1024 * 1024)
                    if not block:
                        break
                    h.update(block)
                    total += len(block)
            decompressed_digest = h.hexdigest()
            knowledge_ok = (
                compressed_digest == EXPECTED_KNOWLEDGE_GZIP_SHA256 and
                decompressed_digest == EXPECTED_KNOWLEDGE_DECOMPRESSED_SHA256 and
                total == EXPECTED_KNOWLEDGE_DECOMPRESSED_BYTES
            )
            result["checks"]["knowledge_gzip"] = {
                "ok": knowledge_ok,
                "compressed_bytes": KNOWLEDGE.stat().st_size,
                "compressed_sha256": compressed_digest,
                "decompressed_bytes": total,
                "decompressed_sha256": decompressed_digest,
            }
            if not knowledge_ok:
                result["issues"].append("canonical knowledge integrity does not match release receipt")
        except Exception as exc:
            result["checks"]["knowledge_gzip"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            result["issues"].append("knowledge gzip integrity failed")

    db = RUNTIME / "knowledge_index.sqlite3"
    chunks = RUNTIME / "knowledge_chunks.bin"
    if db.exists() and chunks.exists():
        try:
            con = sqlite3.connect(db)
            meta = dict(con.execute("select key,value from meta").fetchall())
            count = con.execute("select count(*) from chunk_meta").fetchone()[0]
            con.close()
            result["checks"]["knowledge_index"] = {
                "ok": count > 0 and meta.get("source_name") == KNOWLEDGE.name and meta.get("format") == "SM34_SEEKABLE_KNOWLEDGE_INDEX_V2" and meta.get("source_decompressed_sha256") == EXPECTED_KNOWLEDGE_DECOMPRESSED_SHA256,
                "chunks": count,
                "db_bytes": db.stat().st_size,
                "chunk_store_bytes": chunks.stat().st_size,
                "meta": meta,
            }
            if not result["checks"]["knowledge_index"]["ok"]:
                result["issues"].append("knowledge index is empty or stale for SM34")
        except Exception as exc:
            result["checks"]["knowledge_index"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            result["issues"].append("knowledge index validation failed")
    else:
        result["checks"]["knowledge_index"] = {"ok": True, "ready": False, "note": "not built yet; setup/start can build it"}

    js = ROOT / "static" / "js" / "app.js"
    html = ROOT / "static" / "index.html"
    js_text = js.read_text("utf-8", errors="replace") if js.exists() else ""
    html_text = html.read_text("utf-8", errors="replace") if html.exists() else ""
    ui_tokens = ["initBabylon", "/api/health", "/api/analyze", "/api/sm34/overview", "/api/report/${kind}"]
    missing_ui = [x for x in ui_tokens if x not in js_text]
    result["checks"]["frontend_contract"] = {
        "ok": not missing_ui and 'id="renderCanvas"' in html_text and 'id="tab-universe"' in html_text,
        "missing_tokens": missing_ui,
        "render_canvas": 'id="renderCanvas"' in html_text,
    }
    if not result["checks"]["frontend_contract"]["ok"]:
        result["issues"].append("frontend API/Babylon contract incomplete")

    # Direct API contract check without opening a network socket.
    try:
        from fastapi.testclient import TestClient
        from supermoon_studio.main import app

        with TestClient(app) as client:
            health = client.get("/api/health")
            sample = (
                "Objective: analyze a reproducible CFD workflow with governing equations, "
                "verification, validation, uncertainty, evidence and a scientific PDF."
            )
            analysis = client.post("/api/analyze", json={"prompt": sample, "knowledge_limit": 0})
            result["checks"]["api_contract"] = {
                "ok": health.status_code == 200 and analysis.status_code == 200,
                "health_status": health.status_code,
                "analysis_status": analysis.status_code,
                "sm34_runtime": health.json().get("sm34_runtime", {}).get("available") if health.status_code == 200 else False,
            }
            if analysis.status_code == 200:
                body = analysis.json()
                result["checks"]["api_contract"]["analysis_id"] = body.get("analysis_id")
                result["checks"]["api_contract"]["risk_class"] = body.get("risk", {}).get("risk_class")
            result["checks"]["api_contract"]["ok"] = result["checks"]["api_contract"]["ok"] and bool(result["checks"]["api_contract"]["sm34_runtime"])
            if not result["checks"]["api_contract"]["ok"]:
                result["issues"].append("API contract check failed")
    except Exception as exc:
        result["checks"]["api_contract"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        result["issues"].append("API contract check raised an exception")

    result["ok"] = not result["issues"]
    result["elapsed_s"] = round(time.time() - started, 3)
    REPORT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
