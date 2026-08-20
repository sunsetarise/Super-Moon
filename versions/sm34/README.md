# Super Moon 34 New Universe Prompt Studio — Audited Python 3.14 Build

Local Windows research interface integrating the complete **SUPER MOON 34 NEW UNIVERSE OMEGA** corpus, its additive `supermoon34` runtime, the inherited SM31/SM32 runtime, a Python/FastAPI backend, and Babylon.js 9 visualization.

The canonical SM34 `.txt.gz` is retained intact under `knowledge/`. Its length-prefixed New Universe layer is reconstructed under `supermoon_runtime/` with all 62 embedded files verified by size and SHA-256. Prompt analysis now routes directly to the 16 P01-P11/A01-A05 capability tracks, backend probes, and W01-W08 qualification gates.

## Required Python installation

This release is intentionally bound to the Python installation already configured on this workstation:

```text
C:\Users\zero\AppData\Local\Programs\Python\Python314\python.exe
```

The setup does **not** silently substitute a Windows Store Python, `py.exe`, another PATH entry, or another Python 3.14 installation. It verifies that the file above exists, is 64-bit CPython 3.14, and then creates/validates `.venv` from that exact base executable.

If a `.venv` exists but its `sys._base_executable` points to another Python installation, setup discards the generated environment and rebuilds it from the required path. Set `SM34_KEEP_OLD_VENV=1` before setup only if you explicitly want the rejected venv preserved as a timestamped backup. Legacy `SM32_*` overrides remain accepted for compatibility.

## Clean Windows setup

1. Extract the package to a normal writable folder.
2. Double-click **`SETUP_WINDOWS.bat`**.
3. When setup reports success, double-click **`START_SUPERMOON.bat`**.
4. Optional: run **`RUN_FULL_AUDIT.bat`** for the complete application + embedded SuperMoon regression suite.
5. Optional: run **`CHECK_INSTALLATION.bat`** at any time for a non-destructive installation diagnosis.

### What SETUP_WINDOWS.bat does

The BAT first checks the exact Python path above, then delegates to `tools/windows_bootstrap.py`, which performs the authoritative setup:

- verifies CPython **3.14 x64** and the exact executable path;
- verifies the canonical SM34 knowledge archive size and SHA-256 plus the reconstructed SM34 source manifest before building/using derived caches;
- diagnoses `python.exe` / `py.exe` on PATH for visibility, but does not use a different interpreter;
- verifies or recreates `.venv` and checks its **base-interpreter provenance**;
- repairs `pip` with `ensurepip` if the selected Python installation lacks it;
- upgrades `pip`, `setuptools`, and `wheel` inside the venv;
- installs the Python 3.14 dependency profile with `pip --isolated --only-binary=:all:`;
- refuses native source-build fallback, preventing the previous `pydantic-core` Rust/MSVC / `link.exe` failure mode;
- runs `pip check` and imports every required runtime package;
- attempts to cache the pinned Babylon.js **9.21.2** bundle locally; if that network step is unavailable, the browser retains a pinned CDN fallback;
- builds the local seekable SM34 knowledge cache from the canonical `.txt.gz` corpus;
- runs the integrated Studio self-test, core tests, and SM34 local validation suite;
- writes `runtime/setup-state.json` and `runtime/setup.log`.

The Python 3.14 dependency profile is pinned in `requirements-py314.txt` and mirrored in `requirements.txt` so an accidental generic install cannot pull the old incompatible profile.

## Dependency policy

The audited Python 3.14 profile pins:

```text
fastapi==0.140.8
uvicorn==0.39.0
python-multipart==0.0.32
pydantic==2.12.5
pydantic-core==2.41.5
reportlab==5.0.0
numpy==2.5.1
scipy==1.17.0
psutil==7.2.2
pytest==9.0.2
httpx==0.28.1
```

For Python 3.14 the installer uses **binary wheels only**. If the configured package index cannot provide a compatible wheel, setup stops with a clear error and pip tag diagnostics instead of trying to compile Rust/C/C++ code locally. The default package index is PyPI. An intentional alternate mirror can be set before setup with `SM34_PIP_INDEX_URL`.

## How START_SUPERMOON.bat works

Every start is preflighted. The launcher:

1. checks the exact configured Python installation;
2. verifies that `.venv` is still based on that exact Python;
3. verifies required dependency imports and `pip check`;
4. automatically reruns audited setup if the environment is missing or damaged;
5. builds the knowledge index if it is missing;
6. starts FastAPI on `127.0.0.1` using a free port beginning at **8892**;
7. performs the local health probe and opens the interface in the default browser.

The application binds to localhost by default. Press **Ctrl+C** in the launch console to stop the backend.

## Full audit / troubleshooting

### `CHECK_INSTALLATION.bat`
Non-destructive doctor. It verifies the configured Python, venv provenance, dependency imports, `pip check`, knowledge source and optional local Babylon cache. Diagnostic output is also written to `runtime/setup.log`.

### `RUN_FULL_AUDIT.bat`
Runs:

- package/file/integrity audit (`tools/audit_package.py`);
- full Studio + embedded SuperMoon regression suite;
- integrated analysis/PDF/runtime self-test;
- final `pip check`.

Its machine-readable record is `runtime/FULL_AUDIT_REPORT.json`.

### `REBUILD_KNOWLEDGE_INDEX.bat`
Validates/repairs the Python environment first, then rebuilds the knowledge cache from the canonical compressed corpus.

### If setup fails
Read `runtime/setup.log`. The setup deliberately does not require Visual Studio Build Tools or Rust for the normal Python 3.14 path. A dependency resolution failure should identify a missing binary wheel or package-index problem rather than attempting a source build.

If upgrading from the earlier 34.0.0 package that stopped at `ModuleNotFoundError: No module named 'scipy'`, replace it with this corrected package and run `SETUP_WINDOWS.bat` again. Setup installs the pinned SciPy 1.17.0 CPython 3.14 wheel into the existing `.venv` and then reruns the complete SM34 validation path; deleting the virtual environment is not required.

The Windows portability update also removes the runtime dependency on the Unix-only `resource` module. Endurance memory telemetry uses `resource` on supported Unix systems and `psutil` on Windows, while atomic checkpoints retain file flush/replace guarantees without attempting the unsupported Windows directory `fsync` operation.

## Integrated application functions

- Full canonical `SUPER_MOON_34_NEW_UNIVERSE...txt.gz` corpus retained under `knowledge/`.
- All 62 SM34 additive files reconstructed and verified under `supermoon_runtime/`, alongside the inherited SM31/SM32 sources.
- Actual embedded `supermoon34`, `supermoon32`, and `supermoon32.qualified` imports.
- New Universe capability routing across PETSc/MPI, OpenFOAM, SU2, OCCT/CadQuery, external HPC, GPU, endurance, second-machine reproduction, V&V/UQ, performance, evidence governance, and aerospace A01-A05.
- Dedicated New Universe control plane showing 16 implementation tracks, nine backend probes, eight gates, blockers, and local validation.
- Seekable compressed knowledge chunk store + compact SQLite conceptual metadata index.
- Streaming fallback for exact identifier-heavy searches.
- Master-prompt analysis for structure, mathematics, verification, validation, uncertainty quantification, reproducibility, evidence, orchestration, risk governance, SM34 track alignment, backend availability, qualification gates, and reporting.
- Scientific analysis PDF and patent-style technical specification PDF generation.
- Babylon.js 9 interactive research-workflow visualization.
- Local runtime-health and output APIs.

## Truth / qualification policy

The application does **not** convert prompt text, an installed adapter, or a local test into external scientific validation. PETSc/MPI rank matrices, OpenFOAM/SU2 cross-validation, CAD-kernel round trips, external cluster execution, real GPU execution, 24/72-hour endurance, and distinct second-machine reproduction remain explicit physical gates. Patent-style output is a technical drafting artifact, not a patentability or novelty opinion.

## Project layout

```text
SETUP_WINDOWS.bat          authoritative installation / repair
START_SUPERMOON.bat        preflight + launch
CHECK_INSTALLATION.bat     non-destructive environment doctor
RUN_FULL_AUDIT.bat         full regression and package audit
REBUILD_KNOWLEDGE_INDEX.bat
requirements-py314.txt     audited CPython 3.14 profile
supermoon_studio/          API, analysis, knowledge and PDF engines
static/                    Babylon.js UI
knowledge/                 canonical SM34 corpus + inherited authoritative sections
supermoon_runtime/         additive SM34 + inherited SM31/SM32 runtime/evidence
runtime/                   generated local cache, state and logs
output/                    generated scientific/patent PDFs
tools/                     audited bootstrap, package audit and index builder
tests/                     Studio integration tests
```

## Manual commands

After successful setup:

```bat
.venv\Scripts\python.exe -m supermoon_studio.self_test
.venv\Scripts\python.exe tools\build_knowledge_index.py --force
.venv\Scripts\python.exe -m supermoon_studio.launcher
```

For normal use, prefer the BAT entry points because they validate the exact Python base and repair the environment automatically.
