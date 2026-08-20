# Independent second-machine procedure

Use a distinct physical machine and independent operator. Start from an empty
workspace, verify the published release hash, reconstruct, install only locked
dependencies, run all local tests and coverage gates, then execute every backend
available to that machine. Record privacy-preserving machine/operator hashes and
compare exact deterministic outputs or prespecified numerical tolerances. Do not
use unpublished repair instructions; release any repair as a new version first.
