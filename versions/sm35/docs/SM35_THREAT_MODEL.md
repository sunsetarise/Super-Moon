# SM35 threat model

Protected assets are inherited bytes, source/evidence integrity, external
execution truth, credentials, scheduler resources, and release claims. Threats
include archive traversal, duplicate-name ambiguity, decompression corruption,
hash/length forgery, evidence DAG corruption, NaN/unknown-state gate bypass,
mock/fallback promotion, command injection, executable substitution, unbounded
output/time, secret capture, endurance clock forgery, same-host reproduction,
and certification overclaim.

Controls include confined versioned frames, duplicate rejection, streaming hash
and length verification, immutable SM34 prefix checks, finite strict schemas,
fixed weights/blockers, explicit authorization, allowlisted executables and work
roots, exact argv with `shell=False`, sanitized environments, bounded resources,
real-monotonic endurance contracts, distinct machine/operator attestations, and
mandatory candidate naming while evidence is incomplete.
