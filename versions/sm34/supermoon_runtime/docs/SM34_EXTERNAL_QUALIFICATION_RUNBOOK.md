# External Qualification Runbook

1. Freeze the exact merged release hash, input cases, tolerances, dependency
   locks, compiler/container identity, and reviewer-approved test plan.
2. Reconstruct the SM34 layer and verify every embedded length and SHA-256.
3. On a PETSc/MPI host, run the same Poisson/reference problems at 2/3/4/8
   ranks. Retain per-rank ownership, convergence reasons, residual history,
   environment, binary hashes and rank-invariance comparisons.
4. Execute matched neutral cases separately in OpenFOAM and SU2. Retain mesh,
   configuration, solver logs, residuals, forces/moments/fluxes, field samples,
   refinement results and discrepancy ledger.
5. Execute CadQuery/OCCT construction, Boolean, healing/validity, assembly and
   STEP/IGES round trips. Retain kernel versions, BRep checks, mass properties,
   topology/tolerance diffs and file hashes.
6. Submit a multi-node scheduler job using an approved site-specific script.
   Retain job ID, node list, allocation, module/container lock, stdout/stderr,
   `sacct`/site accounting, checkpoints and staged artifact manifest.
7. Execute GPU parity on a real device. Retain UUID, driver/runtime, kernel
   backend, profiler/telemetry, memory, synchronized timing, accuracy and energy
   evidence. Any silent host fallback fails the gate.
8. Run continuous 24h and 72h profiles with minute telemetry, fault/restart
   drills and terminal integrity checks. Do not accelerate elapsed time.
9. Give only the published release and runbook to an independent operator on a
   distinct physical machine. Compare deterministic hashes and declared numeric
   tolerances; retain clean-room build and operator attestations.
10. Rebuild the evidence DAG, run security and provenance review, calculate the
    fixed 100-point score, and issue PASS only when score is at least 95 and all
    blockers are closed.

Never place scheduler, registry, signing, or cloud credentials in case files,
logs, environment captures, manifests, or receipts.

