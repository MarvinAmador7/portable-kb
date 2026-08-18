# Production hardening 0.1.2

## Objective

Version 0.1.2 hardens the existing agent-first CLI without expanding the
product into semantic search, background services, or hosted infrastructure.
The release focuses on recoverable local mutations, diagnosable installations,
and continuously tested compatibility with the external QMD keyword provider.

## Release scope

- Serialize CLI mutations with a bounded cross-process lock. Lock metadata
  identifies the operation, process, host, and creation time; an abandoned lock
  from a dead process on the same host can be recovered without deleting a live
  or foreign-host lock.
- Add `pkb brain remove <slug>`. It removes only the installed snapshot and its
  disposable QMD index. It never deletes the authoring repository or remote.
  Dirty installed snapshots require explicit `--force`, and the catalog change
  rolls back if staged removal cannot be published safely.
- Detect the exact retired `portable-kb-core` demo identity and provide explicit
  removal guidance. A coincidentally similar user brain is not classified from
  its name alone.
- Record managed skill-installation receipts and add `pkb skill status` to
  distinguish current, missing, outdated, modified, unmanaged, and unsafe
  Codex/Claude workflow copies.
- Expand `pkb doctor` into a read-only diagnostic for settings, Git, QMD path and
  version compatibility, catalog health, active-brain health, active-index
  freshness, operation locks, legacy demo state, and agent-skill drift.
- Require QMD `>=2.5.0,<3.0.0` before indexing or querying. CI installs the exact
  `@tobilu/qmd@2.8.3` package under Node.js 24 and exercises a real isolated
  index and cited BM25 query in addition to the deterministic adapter tests.

## Safety invariants

- Canonical knowledge remains in Git brain repositories, never in the catalog,
  operation lock, skill receipt, or search index.
- Brain removal operates only on the expected immediate checkout and cache
  children. Symbolic links and irregular targets fail closed.
- Removing the active brain leaves no active brain; the CLI does not silently
  select a different business worldview.
- Doctor is observational. It does not install, repair, synchronize, rebuild,
  unlock, or remove anything.
- Agent-skill status hashes the canonical file tree. A local modification is not
  overwritten unless the user explicitly runs `pkb skill install --force`.
- QMD remains isolated below the per-brain cache and receives no repository-owned
  update hook. The compatibility smoke test runs keyword indexing only and does
  not download embedding models.

## Release acceptance

The release is ready when:

1. lint, schema, corpus, CLI, lock, removal, skill-drift, and packaging tests
   pass on supported Python and operating-system runners;
2. the real-QMD CI job indexes the reference brain and retrieves the expected
   stale-review procedure with an exact pinned-commit citation;
3. standalone Intel/ARM artifacts build and pass the published installer smoke
   tests; and
4. a clean install reports `pkb 0.1.2`, while an existing 0.1.x install upgrades
   without changing its configured brain or search provider.

## Deferred

The built-in Rust/SQLite search work is intentionally separate and documented
in [pkb-search.md](pkb-search.md). Automatic QMD installation, semantic models,
MCP, native UI, background synchronization, and hosted services remain outside
0.1.2.
