# OpenFOAM case contract

Generate three systematically refined meshes from the neutral NACA0012 schema,
run `checkMesh` before `foamRun`, and retain dictionaries, mesh metrics, residuals,
conservation, coefficients, sampled fields, wall time, memory, and parallel-domain
mapping. No case result is embedded because OpenFOAM did not execute here.
