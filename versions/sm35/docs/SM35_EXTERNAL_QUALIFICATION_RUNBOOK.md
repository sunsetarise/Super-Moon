# SM35 external qualification runbook

1. Verify the release with `tools/verify_sm35_release.py` and reconstruct into a
   new empty workspace.
2. Establish an authorized, credential-free runtime and record exact software,
   compiler, library, machine, and scheduler versions.
3. Run PETSc at 1/2/3/4/8 ranks, with a 4- or 8-rank job across at least two
   physical nodes. Preserve rank-local ownership, residual, host, and terminal
   agreement evidence.
4. Run three-mesh OpenFOAM and SU2 families, SU2 adjoint directional-gradient
   checks, and solver-neutral coefficient/field comparisons.
5. Run CadQuery/OCCT STEP plus direct-OCCT IGES matrices with BRep checks and
   prespecified drift thresholds.
6. Submit scheduler-managed CPU/MPI, checkpoint/restart, stage-out, and permitted
   failure jobs; retain `sacct`/equivalent accounting.
7. Run real CUDA parity, synchronized timing, profiler, and telemetry tracks.
8. Run separate continuous 24-hour and 72-hour profiles without clock or loop
   substitution.
9. Reproduce from the published release on a distinct physical machine under an
   independent operator.
10. Rebuild the evidence DAG and score. Do not rename the release to QUALIFIED
    unless every blocker closes and the score is at least 95.
