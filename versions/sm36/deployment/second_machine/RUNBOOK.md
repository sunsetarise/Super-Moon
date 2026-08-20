# Independent SM36 second-machine reproduction

Use a distinct physical host, site, and operator. Start from an empty workspace.
Verify the published full gzip SHA-256 and every split-part hash, concatenate the
parts in numeric order, run `gzip -t`, reconstruct SM36, and compare the frame
manifest. Run SM34, SM35, and SM36 regression suites from released artifacts
only, rebuild the 15,000-method registry, compare its digest, then execute every
locally available external backend. Record privacy-preserving machine, operator,
site, scheduler, GPU, compiler, MPI, PETSc, OpenFOAM, SU2, and OCCT fingerprints.

The independent reviewer must compare deterministic hashes exactly and numerical
outputs against preregistered tolerances. Any repair instruction must be released
as a new version. A first-machine rerun, VM clone, container clone, or second
account on the same host does not satisfy independent reproduction.
