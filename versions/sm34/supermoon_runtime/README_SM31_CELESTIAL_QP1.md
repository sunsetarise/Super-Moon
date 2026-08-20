# SUPER MOON 31.0 OMEGA CELESTIAL — QUALIFICATION PATCH 1

This successor layer is the authoritative patched Celestial payload embedded at the end of the merged SUPER MOON 31.0 text artifact. It preserves the historical SM31 and Celestial payloads and adds a full patched source snapshot plus qualification evidence.

Key QP1 changes:
- Repairs the second-order Euler MUSCL interface flux off-by-one error.
- Replaces deprecated NumPy 2-D cross-product usage in B-spline curvature.
- Alternates first/second-order Euler execution in the endurance kernel.
- Adds QP1 regression, numerical validation, coverage, diff, warning, and endurance evidence.

Status: PASS WITH DURATION / COVERAGE LIMITATIONS.
