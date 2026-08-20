# SM35 CFD cross-validation report

The neutral case schema fixes SI units, X-forward/Y-right/Z-down axes, reference
area and length, moment center, fluid and freestream state, boundary semantics,
quantities of interest, and a prespecified discrepancy threshold. The comparison
code rejects missing or non-finite quantities and reports every open quantity.

OpenFOAM and SU2 executables are unavailable in this environment. No residual,
conservation, grid-convergence, adjoint, field, or cross-solver result is claimed.
The OpenFOAM, SU2, and material-discrepancy blockers remain open.
