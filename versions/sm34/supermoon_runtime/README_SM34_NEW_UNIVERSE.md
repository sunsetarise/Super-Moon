# SUPER MOON 34 NEW UNIVERSE

Version 34.0.0 is an additive qualification and civil-aerospace research layer
applied after the complete SUPER MOON 33 stream. The merged release preserves
the decompressed SM33 stream byte-for-byte and adds all SM34 files in a separate
length-prefixed namespace. No SM33 code, evidence, prompt, test, or embedded
artifact is rewritten, shadowed, truncated, or removed.

## Implemented scope

| Track | Additive production implementation |
|---|---|
| PETSc + MPI | Real `petsc4py`/`mpi4py` distributed ownership, matrix/vector assembly, KSP convergence reasons, rank agreement, residuals, and solution hashing |
| OpenFOAM + SU2 | Shell-free independent runners, case hashing, mesh/solver failure visibility, residual extraction, field/QoI comparison, and tolerance contracts |
| OCCT + CadQuery | Real construction, Boolean/fillet/hole, BRep validation, volume comparison, STEP round trip, IGES attempt, and kernel/version evidence |
| External HPC | Slurm script contract, explicit submission authorization, parsable job IDs, `sacct` resource/state/exit reconciliation, and non-local evidence requirements |
| GPU | Real CuPy/PyTorch CUDA execution, synchronization, CPU parity, device UUID/driver telemetry, speed measurement, and rejection of CPU fallback |
| Endurance | Atomic checkpoints, fsync, hash chains, wall-clock heartbeats, resource telemetry, restart parsing, and strict 24h/72h duration caps |
| Reproduction | Privacy-preserving machine/operator fingerprints, clean-workspace and independent-operator attestations, hash equality, numeric tolerance comparison |
| V&V/UQ | Manufactured Poisson solution, observed order, gradient directional check, conservation closure, coverage test, predeclared tolerances |
| Performance | Warm-up, repeated samples, median/MAD, deterministic bootstrap confidence intervals, equal-work regression contracts |
| Evidence/release | Content-addressed DAG, immutable manifests, 100-point gate model, eight non-bypassable blockers, explicit unavailable/not-executed states |
| Aerospace A01-A05 | Digital thread, traceability, interfaces, budgets, reliability, ISA atmosphere, drag polar, mission fuel, structural stress/buckling/fatigue, 6-DOF rigid body, trim and LQR |

The 200,000-line master prompt is preserved as an embedded file and compiled to
exactly 200,000 machine-readable ledger records: 149,600 HPC/qualification
requirements, 50,000 aerospace requirements, and 400 policies/controls.

## Truthful qualification state

Source implementation and local deterministic tests are complete. The build
environment does not contain PETSc/MPI, OpenFOAM, SU2, CadQuery/OCCT, Slurm, or
a real GPU, and it cannot manufacture 24/72-hour or second-machine evidence.
Accordingly, the release engine reports `BLOCKED_PENDING_REAL_EXECUTION`, not a
false 9.5 pass. The adapters and runbooks are ready for those real executions.

This software is computational research tooling. It is not an airworthiness
approval, safety certification, design approval, or safe-to-fly authorization.

## Commands

```bash
PYTHONPATH=src python -m supermoon34 selftest
PYTHONPATH=src python -m supermoon34 backends
PYTHONPATH=src python -m supermoon34 capabilities
PYTHONPATH=src python -m supermoon34 qualification
python -m unittest discover -s tests -v
```

The qualification command intentionally exits nonzero until all mandatory
real-execution evidence closes.

