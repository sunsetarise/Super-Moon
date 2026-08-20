# SM31 CELESTIAL QUALIFICATION PATCH 1 — Bug Fix Report

## Confirmed CFD defect

The second-order Euler path failed for N=60 with a broadcasting mismatch of `(59,3)` versus `(60,3)`. The exact cause was an off-by-one flux-divergence slice after MUSCL/minmod reconstruction. With two copied boundary cells on each side, reconstruction produces exactly `N+1` interface fluxes. The old update incorrectly used `Fi[2:2+N] - Fi[1:1+N]`; because `Fi` has length `N+1`, the first slice contains only `N-1` rows while the second contains `N`.

QP1 establishes an explicit reconstruction shape contract and updates physical cell `i` from faces `i` and `i+1` using `Fi[1:] - Fi[:-1]`. It also checks that the reconstructed flux array is exactly `(N+1,3)`.

## B-spline / NumPy warning

The 2-D curvature branch called `np.cross(d1,d2)` on two-component vectors. QP1 replaces that operation with the mathematically identical planar scalar cross product `d1[0]*d2[1] - d1[1]*d2[0]`. The validated 2-D curvature case returns 0.999999943972 with zero warnings.

## Endurance integration

The endurance kernel now alternates first- and second-order Euler execution by seed parity, preventing the repaired branch from being excluded from soak testing. The 30-second post-patch run executed 51296 iterations: 25648 first-order and 25648 second-order, with 0 exceptions and 0 invariant failures.
