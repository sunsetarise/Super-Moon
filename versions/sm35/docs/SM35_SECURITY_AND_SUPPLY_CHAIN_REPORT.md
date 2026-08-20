# SM35 security and supply-chain report

The layer rejects unsafe frame paths, duplicate paths, corrupt hashes, length
mismatch, malformed framing, non-finite evidence, unknown receipt fields,
duplicate evidence/artifact IDs, unsupported status promotion, and release-gate
bypass. External execution uses executable/work-root allowlists, exact argv,
`shell=False`, bounded time/output, and a sanitized environment. No credentials
are collected or embedded.

The release includes source and frame manifests, a CycloneDX SBOM, dependency
locks, threat model, reference snapshot, append-only evidence DAG, mutation/fuzz
results, and known-limitations/discrepancy ledgers. The content hash chain is
explicitly not represented as a digital signature.
