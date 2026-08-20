# SM34 New Universe Architecture

## Additive boundary

SM34 never edits inherited paths. Its code lives under `src/supermoon34`, its
metadata is `SM34_pyproject.toml`, and its artifacts use `SM34_` prefixes. The
outer release is a concatenated gzip stream: the original SM33 gzip member is
copied unchanged, followed by a deterministic gzip member containing the
length-prefixed SM34 layer. Therefore both compressed SM33 bytes and the full
decompressed SM33 prefix are independently verifiable.

## Claim and gate model

Implementation maturity and execution evidence are separate. A real adapter
may be `IMPLEMENTED` while its environment-specific run is `NOT_EXECUTED`.
`PASS` requires linked evidence. Missing executables produce `UNAVAILABLE`.
Short test loops remain `PASS_WITH_LIMITATIONS` and cannot satisfy 24h/72h
profiles. Same-machine repeats cannot satisfy second-machine reproduction.

The release decision is

\[
S=\sum_{i=1}^{8} w_i g_i,\qquad
Release=(S\ge95)\land\bigwedge_i \neg B_i\land EvidenceDAGValid.
\]

All eight gates must be present exactly once. Each blocker remains open unless
its associated gate is a fully evidenced `PASS`. A partial fraction contributes
diagnostic score only and is still a failing gate.

## Execution boundary

External tools are invoked without a shell, from confined work roots, with an
executable allowlist, a sanitized environment, timeout, bounded output, binary
hash, exact argv, return code, stdout/stderr, and wall-time receipt. Scheduler
submission additionally requires an explicit authorization flag.

## Numerical qualification

Tolerances are declared before evaluation. Validation contains analytic and
manufactured references, grid-order calculation, independent directional
gradient checks, conservation closure, uncertainty coverage, repeated timing,
median/MAD and confidence intervals. Discrepancies are reported, not hidden by
post-hoc threshold widening.

## Aerospace architecture

The digital thread stores atomic versioned requirements, parent/allocation
edges, interfaces, verification states, artifact links, and a canonical hash.
Systems budgets carry expected value, uncertainty and growth. Preliminary
aerodynamics, mission, structures and flight dynamics expose units and validity
limits. Every aerospace capability is explicitly research-only and requires
competent independent review for regulated decisions.

