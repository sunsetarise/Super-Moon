# Contributing

Contributions must preserve the additive lineage, evidence truth boundary, and
mandatory release gates.

1. Create a focused branch and explain the requirement being changed.
2. Add or update tests for every active code path.
3. Run `python tools/run_all_tests.py` and `python tools/verify_assets.py`.
4. Never convert `NOT_RUN`, `UNAVAILABLE`, `BLOCKED`, or simulated evidence into
   a passing physical-execution claim.
5. Include hashes, environment details, commands, logs, and machine identity for
   externally executed qualification evidence.
6. Update the change log and traceability records when behavior changes.

Pull requests that alter historical source bytes should explicitly identify the
version and justify why an additive overlay is insufficient.

