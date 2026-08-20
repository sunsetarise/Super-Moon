# SM35 coverage report

The release contains a dependency-free branch-aware tracer because coverage.py
is unavailable in the execution environment. It records executed statement
lines and source-to-destination arcs and produces a coverage.py-compatible
summary shape plus XML, LCOV, terminal, and HTML forms.

The active SM35 internal scope excludes only the tracer's self-instrumentation
module and the subprocess-only `__main__` adapter; both are recorded in the
machine-readable exclusion ledger. No `pragma: no cover`, global omit rule, or
empty-import test is used. The combined inherited threshold is intentionally
separate from the SM35-new-code threshold and cannot be bypassed by the latter.
