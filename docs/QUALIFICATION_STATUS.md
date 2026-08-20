# Qualification status

Current release state: **`BLOCKED_PENDING_REAL_EXECUTION`**.

Locally demonstrated in the assembled release:

- 136 combined deterministic regression tests previously passed across SM34,
  SM35, and SM36 qualification suites;
- 96.8766404199475% combined statement coverage;
- 90.40492957746478% combined branch coverage;
- 99.229152067274% SM36 statement coverage;
- 95.2% SM36 branch coverage;
- 13/13 controlled mutations killed;
- 20,000 fuzz trials with zero recorded failures;
- 212 framed files reconstructed with declared byte counts and SHA-256 hashes.

Not demonstrated in the local qualification environment:

- real PETSc/MPI multi-rank and multi-node execution;
- external Slurm accounting on actual multi-node hardware;
- real OpenFOAM and SU2 cross-validation;
- complete CadQuery/OCCT STEP and IGES qualification;
- real CUDA GPU execution;
- continuous 24-hour and 72-hour endurance;
- independent reproduction on a second physical machine;
- industrial or aerospace certification.

Architecture, adapters, scripts, simulated paths, or unavailable-backend
receipts are never substitutes for physical evidence.

