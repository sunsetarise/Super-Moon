# Repository layout

The repository keeps historical implementations in version folders so package
names, tests, evidence paths, and relative file assumptions remain intact.

- `versions/sm34/` is the fully extracted SM34 New Universe Prompt Studio. Its
  numerical source is under `supermoon_runtime/src`; its web application is
  under `supermoon_studio`; its original knowledge/runtime assets are retained.
- `versions/sm35/` is the additive SM35 qualification candidate with its own
  source, tests, cases, deployment definitions, evidence, and prompt.
- `versions/sm36/` is the additive SM36 layer with its own source, tests,
  registry, work-item ledger, evidence, deployment definitions, and prompt.
- `assets/` contains the exact full merged release and is not a working source
  directory.

No version source was flattened into another package. This avoids import-name
collisions and preserves reproducible relative paths.

