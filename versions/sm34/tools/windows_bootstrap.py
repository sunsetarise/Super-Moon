from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sqlite3
import struct
import subprocess
import sys
import sysconfig
import time
import urllib.request
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)
LOG = RUNTIME / "setup.log"
STATE = RUNTIME / "setup-state.json"
VENV = ROOT / ".venv"
REQ = ROOT / "requirements-py314.txt"
BABYLON_VERSION = "9.21.2"
BABYLON = ROOT / "static" / "vendor" / f"babylon-{BABYLON_VERSION}.js"
KNOWLEDGE_GZ = ROOT / "knowledge" / "SUPER_MOON_34_NEW_UNIVERSE_OMEGA_FULLY_IMPLEMENTED_FULL_MERGED.txt.gz"
SM34_PORTABILITY_OVERLAY = ROOT / "supermoon_runtime" / "evidence" / "SM34_WINDOWS_PORTABILITY_OVERLAY.json"
DEFAULT_REQUIRED_PYTHON = r"C:\Users\zero\AppData\Local\Programs\Python\Python314\python.exe"
EXPECTED_KNOWLEDGE_GZIP_BYTES = 108689607
EXPECTED_KNOWLEDGE_GZIP_SHA256 = "0e077a7237b2bbaea1343cc73b6f025562b6a00d7a0469be78fba0ac72436a64"
EXPECTED_KNOWLEDGE_DECOMPRESSED_SHA256 = "8d96f961541706dc8fbe419a332bace0f14648807e60eccd48dabb6a0b1330ac"
EXPECTED_KNOWLEDGE_DECOMPRESSED_BYTES = 721679960

REQUIRED_IMPORTS = (
    "fastapi",
    "uvicorn",
    "multipart",
    "pydantic",
    "pydantic_core",
    "reportlab",
    "numpy",
    "scipy",
    "psutil",
    "pytest",
    "httpx",
)
REQUIRED_DISTRIBUTIONS = (
    "fastapi",
    "uvicorn",
    "python-multipart",
    "pydantic",
    "pydantic-core",
    "reportlab",
    "numpy",
    "scipy",
    "psutil",
    "pytest",
    "httpx",
)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log(message: str = "") -> None:
    print(message, flush=True)
    try:
        with LOG.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(message + "\n")
    except OSError:
        pass


def norm_win_path(value: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(value).strip('"')))


def required_python() -> str:
    # The exact path confirmed by the user is authoritative. An override is
    # available only when deliberately set by the user before launching.
    raw = os.environ.get("SM34_REQUIRED_PYTHON", os.environ.get("SM32_REQUIRED_PYTHON", DEFAULT_REQUIRED_PYTHON)).strip().strip('"')
    if os.path.isdir(raw):
        raw = os.path.join(raw, "python.exe")
    return raw


def run(
    args: Sequence[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a child process while preserving its complete output in setup.log.

    `capture` is retained for call-site compatibility; stdout is always captured so
    dependency/build diagnostics are not lost when the console closes. Output is
    replayed to the console after the child exits and remains available on the
    returned CompletedProcess.
    """
    pretty = subprocess.list2cmdline([str(x) for x in args])
    log(f"$ {pretty}")
    proc = subprocess.run(
        [str(x) for x in args],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        errors="replace",
    )
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n", flush=True)
        try:
            with LOG.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(proc.stdout)
                if not proc.stdout.endswith("\n"):
                    fh.write("\n")
        except OSError:
            pass
    if check and proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, args, output=proc.stdout)
    return proc


def query_python(python_exe: Path | str) -> dict:
    code = (
        "import json,os,platform,struct,sys,sysconfig;"
        "print(json.dumps({"
        "'version':sys.version.split()[0],"
        "'major':sys.version_info.major,'minor':sys.version_info.minor,"
        "'implementation':sys.implementation.name,"
        "'bits':struct.calcsize('P')*8,"
        "'executable':os.path.abspath(sys.executable),"
        "'base_executable':os.path.abspath(getattr(sys,'_base_executable',sys.executable)),"
        "'prefix':os.path.abspath(sys.prefix),"
        "'base_prefix':os.path.abspath(sys.base_prefix),"
        "'soabi':str(sysconfig.get_config_var('SOABI') or ''),"
        "'machine':platform.machine()}))"
    )
    proc = subprocess.run(
        [os.fspath(python_exe), "-c", code],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        errors="replace",
    )
    if proc.returncode:
        raise RuntimeError(f"Python probe failed for {python_exe}: {proc.stdout.strip()}")
    lines = [x for x in proc.stdout.splitlines() if x.strip()]
    if not lines:
        raise RuntimeError(f"Python probe returned no data for {python_exe}")
    return json.loads(lines[-1])


def validate_base_python(*, require_exact_executable: bool = True) -> dict:
    expected = required_python()
    if os.name != "nt":
        raise RuntimeError("Windows bootstrap can only run on Windows.")
    if not os.path.isfile(expected):
        raise RuntimeError(f"Required Python was not found at: {expected}")

    actual = query_python(expected)
    errors: list[str] = []
    if (actual["major"], actual["minor"]) != (3, 14):
        errors.append(f"expected CPython 3.14, got {actual['version']}")
    if actual["implementation"] != "cpython":
        errors.append(f"expected CPython, got {actual['implementation']}")
    if actual["bits"] != 64:
        errors.append(f"expected 64-bit Python, got {actual['bits']}-bit")
    if require_exact_executable and norm_win_path(actual["executable"]) != norm_win_path(expected):
        errors.append(f"Python executable resolved to {actual['executable']} instead of {expected}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return actual


def venv_python() -> Path:
    return VENV / "Scripts" / "python.exe"


def inspect_venv() -> dict | None:
    py = venv_python()
    if not py.exists():
        return None
    try:
        return query_python(py)
    except Exception as exc:
        return {"invalid": True, "error": f"{type(exc).__name__}: {exc}"}


def venv_matches_base(meta: dict | None, base: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not meta:
        return False, ["virtual environment does not exist"]
    if meta.get("invalid"):
        return False, [str(meta.get("error", "virtual environment is invalid"))]
    if (meta.get("major"), meta.get("minor")) != (3, 14):
        reasons.append(f"venv Python is {meta.get('version')}, not 3.14")
    if meta.get("implementation") != "cpython":
        reasons.append(f"venv implementation is {meta.get('implementation')}, not CPython")
    if meta.get("bits") != 64:
        reasons.append(f"venv is {meta.get('bits')}-bit, not 64-bit")
    if norm_win_path(meta.get("base_executable", "")) != norm_win_path(base["executable"]):
        reasons.append(
            "venv base interpreter mismatch: "
            f"{meta.get('base_executable')} != {base['executable']}"
        )
    return not reasons, reasons


def remove_bad_venv(meta: dict | None, reasons: Iterable[str]) -> None:
    receipt = {
        "removed_at": now_iso(),
        "venv": str(VENV),
        "previous": meta,
        "reasons": list(reasons),
    }
    (RUNTIME / "venv-rebuild-receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    keep = os.environ.get("SM34_KEEP_OLD_VENV", os.environ.get("SM32_KEEP_OLD_VENV", "0")) == "1"
    if keep:
        dst = ROOT / f".venv.old.{time.strftime('%Y%m%d_%H%M%S')}"
        log(f"[INFO] Preserving old venv as {dst.name}")
        VENV.rename(dst)
        return
    log("[INFO] Removing generated .venv because it is invalid or bound to another Python.")
    shutil.rmtree(VENV, ignore_errors=False)


def clean_pip_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "PIP_NO_BINARY",
        "PIP_ONLY_BINARY",
        "PIP_PREFER_BINARY",
        "PIP_NO_BUILD_ISOLATION",
        "PIP_EXTRA_INDEX_URL",
        "PIP_REQUIRE_VIRTUALENV",
        "PIP_CONFIG_FILE",
    ):
        env.pop(key, None)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONUTF8"] = "1"
    return env


def ensure_system_pip(base_exe: str) -> None:
    proc = subprocess.run(
        [base_exe, "-m", "pip", "--version"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    if proc.returncode == 0:
        log(f"[OK] System pip: {proc.stdout.strip()}")
        return
    log("[INFO] pip is missing from Python 3.14; running ensurepip --upgrade.")
    run([base_exe, "-m", "ensurepip", "--upgrade"])


def create_venv(base: dict) -> dict:
    ensure_system_pip(base["executable"])
    log(f"[INFO] Creating .venv from exact base Python: {base['executable']}")
    run([base["executable"], "-m", "venv", str(VENV)])
    meta = inspect_venv()
    ok, reasons = venv_matches_base(meta, base)
    if not ok:
        raise RuntimeError("Fresh venv provenance validation failed: " + "; ".join(reasons))
    return meta or {}


def requirements_hash() -> str:
    return hashlib.sha256(REQ.read_bytes()).hexdigest()


def required_distribution_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw in REQ.read_text("utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise RuntimeError(f"Dependency profile must use exact pins: {line}")
        name, version = line.split("==", 1)
        versions[name.strip().lower()] = version.strip()
    return versions


def install_dependencies() -> dict[str, str]:
    if not REQ.exists():
        raise RuntimeError(f"Missing dependency profile: {REQ}")
    py = venv_python()
    env = clean_pip_env()
    index = os.environ.get("SM34_PIP_INDEX_URL", os.environ.get("SM32_PIP_INDEX_URL", "https://pypi.org/simple")).strip()
    if not index:
        index = "https://pypi.org/simple"

    log(f"[INFO] Package index: {index}")
    log("[INFO] Native dependency policy: BINARY WHEELS ONLY (no Rust/MSVC source fallback).")

    pip = [str(py), "-m", "pip", "--isolated"]
    run(
        pip
        + [
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--only-binary=:all:",
            "--index-url",
            index,
            "--upgrade",
            "pip",
            "setuptools",
            "wheel",
        ],
        env=env,
    )

    try:
        run(
            pip
            + [
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--only-binary=:all:",
                "--index-url",
                index,
                "--upgrade",
                "--upgrade-strategy",
                "only-if-needed",
                "-r",
                str(REQ),
            ],
            env=env,
        )
    except subprocess.CalledProcessError:
        log("[ERROR] Dependency installation failed with source builds disabled.")
        log("[INFO] pip tag diagnostics:")
        run(pip + ["debug", "--verbose"], env=env, check=False)
        raise

    run(pip + ["check"], env=env)
    verify_dependency_imports(py)
    versions = {name: importlib_metadata_from(py, name) for name in REQUIRED_DISTRIBUTIONS}
    return versions


def importlib_metadata_from(python_exe: Path, dist: str) -> str:
    code = (
        "import importlib.metadata,sys;"
        f"print(importlib.metadata.version({dist!r}))"
    )
    proc = subprocess.run(
        [str(python_exe), "-c", code],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        errors="replace",
    )
    return proc.stdout.strip().splitlines()[-1] if proc.returncode == 0 and proc.stdout.strip() else "unknown"


def verify_dependency_imports(python_exe: Path, *, quiet: bool = False) -> None:
    code = (
        "import sys;"
        "assert sys.version_info[:2]==(3,14);"
        + ";".join(f"import {name}" for name in REQUIRED_IMPORTS)
        + ";print('dependency-imports-ok')"
    )
    proc = subprocess.run(
        [str(python_exe), "-c", code],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        errors="replace",
    )
    if proc.returncode:
        raise RuntimeError("Dependency import verification failed: " + proc.stdout.strip())
    if not quiet:
        log("[OK] " + (proc.stdout.strip() or "dependency-imports-ok"))


def fetch_babylon() -> dict:
    BABYLON.parent.mkdir(parents=True, exist_ok=True)
    if BABYLON.exists() and BABYLON.stat().st_size > 1_000_000:
        return {"ok": True, "cached": True, "bytes": BABYLON.stat().st_size}
    url = f"https://cdn.jsdelivr.net/npm/babylonjs@{BABYLON_VERSION}/babylon.js"
    tmp = BABYLON.with_suffix(".download")
    try:
        log(f"[INFO] Caching Babylon.js {BABYLON_VERSION} from jsDelivr...")
        req = urllib.request.Request(url, headers={"User-Agent": "SuperMoon-34-New-Universe-Prompt-Studio/34.0"})
        with urllib.request.urlopen(req, timeout=45) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out)
        size = tmp.stat().st_size
        if size < 1_000_000:
            raise RuntimeError(f"downloaded Babylon bundle is unexpectedly small ({size} bytes)")
        tmp.replace(BABYLON)
        return {"ok": True, "cached": True, "bytes": size}
    except Exception as exc:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        log(f"[WARN] Babylon.js local cache could not be downloaded: {type(exc).__name__}: {exc}")
        log("[WARN] The UI can still use the pinned jsDelivr browser fallback when online.")
        return {"ok": False, "cached": False, "error": f"{type(exc).__name__}: {exc}"}


def verify_sm34_runtime() -> dict:
    manifest_path = ROOT / "supermoon_runtime" / "evidence" / "SM34_SOURCE_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"SM34 source manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if manifest.get("format") != "SM34_SOURCE_MANIFEST_V1":
        raise RuntimeError("SM34 source manifest format is invalid")
    overlays: dict[str, dict] = {}
    if SM34_PORTABILITY_OVERLAY.is_file():
        overlay_payload = json.loads(SM34_PORTABILITY_OVERLAY.read_text("utf-8"))
        if overlay_payload.get("format") != "SM34_WINDOWS_PORTABILITY_OVERLAY_V1":
            raise RuntimeError("SM34 Windows portability overlay format is invalid")
        for row in overlay_payload.get("files", []):
            path = str(row.get("path", ""))
            if not path or path in overlays:
                raise RuntimeError("SM34 Windows portability overlay contains an invalid path")
            overlays[path] = row
    checked = 0
    applied_overlays: set[str] = set()
    for row in manifest.get("files", []):
        path = ROOT / "supermoon_runtime" / row["path"]
        if not path.is_file():
            raise RuntimeError(f"Reconstructed SM34 runtime file is missing: {path}")
        size = path.stat().st_size
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if size != int(row["size_bytes"]) or digest != row["sha256"]:
            overlay = overlays.get(row["path"])
            valid_overlay = bool(
                overlay
                and overlay.get("baseline_sha256") == row["sha256"]
                and int(overlay.get("baseline_size_bytes", -1)) == int(row["size_bytes"])
                and overlay.get("patched_sha256") == digest
                and int(overlay.get("patched_size_bytes", -1)) == size
            )
            if not valid_overlay:
                raise RuntimeError(f"Reconstructed SM34 runtime integrity mismatch: {path}")
            applied_overlays.add(row["path"])
        checked += 1
    if checked != 59:
        raise RuntimeError(f"Unexpected SM34 source-manifest cardinality: {checked}")
    unused_overlays = sorted(set(overlays) - applied_overlays)
    if unused_overlays:
        raise RuntimeError(f"Unused or stale SM34 portability overlays: {unused_overlays}")
    return {
        "format": manifest["format"],
        "verified_files": checked,
        "portability_overlays": len(applied_overlays),
    }


def verify_canonical_knowledge() -> dict:
    if not KNOWLEDGE_GZ.exists():
        raise RuntimeError(f"Canonical knowledge file is missing: {KNOWLEDGE_GZ}")
    size = KNOWLEDGE_GZ.stat().st_size
    if size != EXPECTED_KNOWLEDGE_GZIP_BYTES:
        raise RuntimeError(
            f"Canonical knowledge size mismatch: {size} != {EXPECTED_KNOWLEDGE_GZIP_BYTES}"
        )
    h = hashlib.sha256()
    with KNOWLEDGE_GZ.open("rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(block)
    digest = h.hexdigest()
    if digest != EXPECTED_KNOWLEDGE_GZIP_SHA256:
        raise RuntimeError(
            "Canonical knowledge SHA-256 mismatch: "
            f"{digest} != {EXPECTED_KNOWLEDGE_GZIP_SHA256}"
        )
    return {"bytes": size, "sha256": digest, "runtime": verify_sm34_runtime()}


def knowledge_index_status() -> dict:
    db = RUNTIME / "knowledge_index.sqlite3"
    chunks = RUNTIME / "knowledge_chunks.bin"
    if not db.exists() or not chunks.exists():
        return {"ready": False, "current": False, "reason": "index files missing"}
    try:
        con = sqlite3.connect(db)
        meta = dict(con.execute("select key,value from meta").fetchall())
        count = int(con.execute("select count(*) from chunk_meta").fetchone()[0])
        con.close()
        reasons = []
        if count <= 0:
            reasons.append("index contains no chunks")
        if meta.get("source_gzip_bytes") != str(EXPECTED_KNOWLEDGE_GZIP_BYTES):
            reasons.append("source gzip size metadata mismatch")
        if meta.get("source_name") != KNOWLEDGE_GZ.name:
            reasons.append("source filename metadata mismatch")
        if meta.get("format") != "SM34_SEEKABLE_KNOWLEDGE_INDEX_V2":
            reasons.append("index format mismatch")
        if meta.get("source_decompressed_sha256") != EXPECTED_KNOWLEDGE_DECOMPRESSED_SHA256:
            reasons.append("source decompressed SHA-256 metadata mismatch")
        if meta.get("source_decompressed_bytes") != str(EXPECTED_KNOWLEDGE_DECOMPRESSED_BYTES):
            reasons.append("source decompressed byte-count metadata mismatch")
        return {
            "ready": True,
            "current": not reasons,
            "reason": "; ".join(reasons) if reasons else "ok",
            "chunks": count,
            "meta": meta,
        }
    except Exception as exc:
        return {
            "ready": True,
            "current": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }


def run_knowledge_index(*, force: bool = False) -> dict:
    verify_canonical_knowledge()
    if os.environ.get("SM34_SKIP_INDEX", os.environ.get("SM32_SKIP_INDEX", "0")) == "1":
        log("[WARN] SM34_SKIP_INDEX=1: knowledge index build skipped.")
        return {"skipped": True}
    index_state = knowledge_index_status()
    if index_state.get("ready") and not index_state.get("current"):
        log(f"[INFO] Existing knowledge index is stale/corrupt: {index_state.get('reason')}")
        force = True
    args = [str(venv_python()), str(ROOT / "tools" / "build_knowledge_index.py")]
    if force:
        args.append("--force")
    run(args)
    code = (
        "import json;from supermoon_studio.knowledge import index;"
        "print(json.dumps(index.stats(),default=str))"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(ROOT / "supermoon_runtime" / "src"), env.get("PYTHONPATH", "")]
    )
    proc = run([str(venv_python()), "-c", code], env=env, capture=True)
    lines = [x for x in (proc.stdout or "").splitlines() if x.strip().startswith("{")]
    return json.loads(lines[-1]) if lines else {"ready": True}


def run_quick_validation() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(ROOT / "supermoon_runtime" / "src"), env.get("PYTHONPATH", "")]
    )
    run([str(venv_python()), "-m", "supermoon_studio.self_test"], env=env)
    run([str(venv_python()), "-m", "pytest", "-q", "tests"], env=env)
    run([str(venv_python()), "-m", "pytest", "-q", "supermoon_runtime/tests/test_sm34.py"], env=env)


def check_installation(*, quiet: bool = False) -> tuple[bool, dict]:
    result: dict = {"checked_at": now_iso(), "ok": False, "issues": [], "warnings": []}
    try:
        base = validate_base_python()
        result["base_python"] = base
    except Exception as exc:
        result["issues"].append(f"base-python: {type(exc).__name__}: {exc}")
        return False, result

    meta = inspect_venv()
    result["venv"] = meta
    ok, reasons = venv_matches_base(meta, result["base_python"])
    if not ok:
        result["issues"].extend(f"venv: {x}" for x in reasons)
        return False, result

    try:
        verify_dependency_imports(venv_python(), quiet=True)
        proc = subprocess.run(
            [str(venv_python()), "-m", "pip", "--isolated", "check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            errors="replace",
        )
        if proc.returncode:
            result["issues"].append("pip-check: " + proc.stdout.strip())
            return False, result
        result["dependencies"] = {
            name: importlib_metadata_from(venv_python(), name) for name in REQUIRED_DISTRIBUTIONS
        }
        expected_versions = required_distribution_versions()
        drift = {
            name: {"expected": expected_versions.get(name.lower()), "actual": actual}
            for name, actual in result["dependencies"].items()
            if expected_versions.get(name.lower()) != actual
        }
        if drift:
            result["issues"].append("dependency-version-drift: " + json.dumps(drift, sort_keys=True))
            return False, result
    except Exception as exc:
        result["issues"].append(f"dependencies: {type(exc).__name__}: {exc}")
        return False, result

    try:
        result["knowledge_source"] = verify_canonical_knowledge()
    except Exception as exc:
        result["issues"].append(f"canonical-knowledge: {type(exc).__name__}: {exc}")
        return False, result
    index_state = knowledge_index_status()
    result["knowledge_index"] = index_state
    if not index_state.get("ready"):
        result["warnings"].append("knowledge index is not built; START_SUPERMOON.bat will build it")
    elif not index_state.get("current"):
        result["issues"].append("knowledge-index: " + str(index_state.get("reason")))
        return False, result
    if not BABYLON.exists():
        result["warnings"].append("local Babylon.js bundle is not cached; browser CDN fallback will be used")

    result["ok"] = True
    if not quiet:
        log(json.dumps(result, indent=2, default=str))
    return True, result


def setup(*, force_venv: bool = False, force_index: bool = False) -> int:
    LOG.write_text("", encoding="utf-8")
    log("=" * 72)
    log("SUPER MOON 34 NEW UNIVERSE PROMPT STUDIO - AUDITED WINDOWS SETUP")
    log(f"Started: {now_iso()}")
    log(f"Required Python: {required_python()}")
    log("=" * 72)

    try:
        base = validate_base_python()
        log(
            f"[OK] Base runtime: CPython {base['version']} | {base['bits']}-bit | "
            f"SOABI={base['soabi']} | {base['executable']}"
        )
        knowledge_source = verify_canonical_knowledge()
        log(
            f"[OK] Canonical knowledge integrity: {knowledge_source['bytes']} bytes | "
            f"SHA-256={knowledge_source['sha256']}"
        )
        path_python = shutil.which("python.exe") or shutil.which("python")
        path_py = shutil.which("py.exe") or shutil.which("py")
        log(f"[INFO] PATH python: {path_python or 'not found'}")
        log(f"[INFO] Windows py launcher: {path_py or 'not found'}")
        log("[INFO] Setup uses the required exact interpreter above, not PATH ordering.")

        meta = inspect_venv()
        matches, reasons = venv_matches_base(meta, base)
        if force_venv:
            matches = False
            reasons = ["forced clean venv rebuild"]
        if not matches and VENV.exists():
            remove_bad_venv(meta, reasons)
            meta = None
        if meta is None or not VENV.exists():
            meta = create_venv(base)
        else:
            log(
                f"[OK] Existing .venv is bound to exact base interpreter: "
                f"{meta.get('base_executable')}"
            )

        versions = install_dependencies()
        log("[OK] Dependency set installed and pip check passed.")
        for name, version in versions.items():
            log(f"       {name}=={version}")

        babylon = fetch_babylon()
        knowledge = run_knowledge_index(force=force_index)
        run_quick_validation()

        state = {
            "ok": True,
            "completed_at": now_iso(),
            "required_python": required_python(),
            "base_python": base,
            "venv": inspect_venv(),
            "requirements_sha256": requirements_hash(),
            "dependencies": versions,
            "babylon": babylon,
            "knowledge_source": knowledge_source,
            "knowledge": knowledge,
        }
        STATE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        log("[OK] Setup completed successfully.")
        log(f"[INFO] Setup state: {STATE}")
        log(f"[INFO] Setup log: {LOG}")
        return 0
    except subprocess.CalledProcessError as exc:
        log(f"[ERROR] Command failed with exit code {exc.returncode}.")
    except Exception as exc:
        log(f"[ERROR] {type(exc).__name__}: {exc}")
    log("[ERROR] Setup did not complete. See runtime\\setup.log for the full trace.")
    return 1


def doctor() -> int:
    log("=" * 72)
    log("SUPER MOON 34 NEW UNIVERSE PROMPT STUDIO - INSTALLATION DOCTOR")
    log(f"Required Python: {required_python()}")
    log(f"Current launcher executable: {sys.executable}")
    log(f"Current launcher version: {sys.version.split()[0]}")
    log(f"Current architecture: {struct.calcsize('P')*8}-bit")
    log(f"SOABI: {sysconfig.get_config_var('SOABI')}")
    log(f"PATH python: {shutil.which('python.exe') or shutil.which('python') or 'not found'}")
    log(f"PATH py: {shutil.which('py.exe') or shutil.which('py') or 'not found'}")
    ok, result = check_installation(quiet=True)
    log(json.dumps(result, indent=2, default=str))
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--force-venv", action="store_true")
    s.add_argument("--force-index", action="store_true")
    sub.add_parser("check")
    sub.add_parser("doctor")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "setup":
        return setup(force_venv=args.force_venv, force_index=args.force_index)
    if args.command == "check":
        ok, result = check_installation(quiet=True)
        print(json.dumps(result, indent=2, default=str))
        return 0 if ok else 1
    if args.command == "doctor":
        return doctor()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
