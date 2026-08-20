# SM34 Qualification Threat Model

Protected assets are inherited source bytes, requirement/evidence integrity,
solver inputs and outputs, scheduler jobs, device identity, checkpoints,
reviewer decisions, and release claims.

Primary threats include path traversal in reconstruction, archive truncation,
binary substitution, shell injection, inherited environment secrets, unbounded
output, stale or fabricated logs, serial/MPI confusion, CPU/GPU fallback,
same-machine reproduction presented as independent, shortened endurance time,
post-hoc tolerance widening, corrupt checkpoints, missing evidence parents, and
regulatory overclaim.

Controls include length-prefix plus SHA-256 verification, confined paths,
shell-free argv execution, executable allowlists and hashes, sanitized
environment, output/time budgets, explicit rank/device/scheduler receipts,
monotonic wall-clock measurement, atomic fsync checkpoints, content-addressed
evidence DAGs, fixed weights/blockers, and non-success states that cannot be
coerced to PASS.

Residual risks include compromised hosts, malicious privileged operators,
colluding external reviewers, hash-algorithm failure, vendor/backend defects,
and invalid engineering assumptions. These require organizational controls,
independent review, protected signing infrastructure, physical access controls,
and qualified laboratory or certification processes outside this software.

