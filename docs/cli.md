# CLI and setup consumer

## Boundary

`pkb` is a consumer of the deterministic `portable_kb` Python API. The CLI and
terminal UI must not duplicate schema, validation, lifecycle, or authority
logic. Canonical knowledge remains in Git-versioned Markdown. Local settings,
repository checkouts, QMD indexes, downloaded models, and query caches are
consumer state and never enter the `knowledge/` bundle.

The implemented consumer foundation covers local configuration plus installing,
listing, selecting, inspecting, and explicitly synchronizing Git-backed
brains. It does not install QMD, download models, execute lifecycle changes, or
synchronize in the background. When QMD is already installed, it can build
isolated BM25 indexes and execute cited keyword queries; semantic and hybrid
retrieval remain deferred.

## Setup contract

Interactive setup runs as a Textual terminal wizard:

```console
pkb setup
```

The wizard has four explicit steps:

1. explain what setup will and will not change;
2. select local brain and disposable-cache directories;
3. select a QMD capability tier; and
4. review and save configuration.

Every setup choice has a non-interactive equivalent so agents, scripts, and
managed environments never need to drive terminal pixels:

```console
pkb setup \
  --non-interactive \
  --search-mode keyword \
  --data-dir /approved/portable-kb/data \
  --cache-dir /approved/portable-kb/cache
```

Non-interactive setup refuses to replace an existing configuration unless
`--force` is explicit. Interactive setup shows the current settings and saves
only after confirmation.

## Search tiers

QMD is the selected local provider. Its documented commands separate BM25
keyword search, vector search, and full hybrid search. Portable KB exposes
those capabilities as product tiers rather than forcing the maximum footprint
on every user.

| Tier | QMD capability | Model download during setup |
|---|---|---|
| `keyword` | BM25 full-text search | None |
| `semantic` | Vector similarity | None; a later explicit install step will fetch the embedding model |
| `full` | Query expansion, BM25/vector fusion, and reranking | None; a later explicit install step will show and confirm the full footprint |

Setup records intent only. A later `search install` operation must report exact
downloads and obtain explicit confirmation before fetching models. The BM25
adapter was checked against QMD main at commit
`cde127ee04ab7608d2c0bd6c83e81d7e18c64b97`; upstream behavior and current
requirements are documented in the [QMD repository](https://github.com/tobi/qmd).

## Local paths and file safety

Defaults follow XDG conventions:

- configuration: `$XDG_CONFIG_HOME/portable-kb/config.yaml` or
  `~/.config/portable-kb/config.yaml`;
- brain checkouts: `$XDG_DATA_HOME/portable-kb` or
  `~/.local/share/portable-kb`; and
- disposable state: `$XDG_CACHE_HOME/portable-kb` or
  `~/.cache/portable-kb`.

The settings file is written atomically with owner-only permissions. Safe YAML
loading rejects unknown structure and executable tags. Configuration paths
that are symbolic links are rejected rather than followed during writes.

QMD configuration is generated locally. Portable KB does not execute a
repository-supplied QMD `update` command or treat imported instructions as
authorization. Git synchronization uses bounded commands owned by the CLI.

## Automation and diagnostics

`pkb doctor` performs read-only local checks. `--json` is the stable direction
for agent and future application consumption:

```console
pkb doctor --json
```

The first diagnostic checks settings structure and whether the configured QMD
command resolves. Later diagnostics may check Git, repository state, index
health, model availability, and compatibility without repairing them unless a
separate explicit command is invoked.

## Brain manifest

An installable brain repository has `brain.yaml` at its repository root,
outside the OKF bundle:

```yaml
schema_version: 1
id: urn:uuid:6e7cc12e-b3f7-49da-875d-32b714fdc1e8
slug: portable-kb-core
name: Portable KB Core
bundle: knowledge
```

The brain ID is immutable UUID v4 identity for the distribution unit. The slug
is its local command name. The bundle path is fixed to `knowledge` in schema
version 1 so repositories cannot redirect consumers to arbitrary filesystem
locations. `brain.yaml` is a product/distribution artifact, not an OKF concept.

## Installation catalog

The first Git-backed commands are:

```console
pkb brain add <local-path-or-git-url>
pkb brain list [--json]
pkb brain use <slug>
pkb brain status [<slug>] [--json]
pkb brain sync [<slug>] [--json]
```

`brain add` performs a bounded sequence:

1. clone with Git hooks disabled and recursive submodules off;
2. parse `brain.yaml` with safe YAML and validate its closed schema;
3. validate the declared `knowledge/` bundle through the core API;
4. read and pin the exact 40-character Git commit;
5. reject duplicate IDs, duplicate slugs, or occupied checkout paths;
6. atomically move the staged checkout under the local data directory; and
7. atomically update the owner-readable local catalog.

Failure before catalog publication removes only the operation-owned staging
checkout. Installation never executes repository scripts, QMD update hooks, or
submodule code. Git URLs containing inline credentials are rejected; existing
Git credential helpers and SSH configuration remain the authentication layer.

The first installed brain becomes active. `brain use` changes only the local
selection after rechecking repository identity. `brain status` is read-only:
it reports checkout availability, manifest identity, current versus pinned
commit, dirty working-tree state, and deterministic bundle validation. It does
not fetch, repair, reset, or clean anything.

`brain sync` is an explicit, foreground-only fast-forward operation. With no
slug it targets the active brain. It performs this bounded sequence:

1. recheck the installed manifest identity, catalog commit, clean working tree,
   and exact `origin` URL;
2. fetch remote refs without tags, submodules, or repository hooks;
3. reject rewritten or diverged history that cannot fast-forward;
4. check out the candidate commit in a temporary detached Git worktree;
5. recheck candidate brain identity and validate its complete bundle;
6. remove the temporary worktree, then recheck the installed checkout for a
   concurrent local change;
7. fast-forward the installed branch with hooks disabled; and
8. atomically publish the new commit and name to the catalog.

An invalid candidate leaves the installed checkout and catalog pin unchanged.
If catalog publication fails after the fast-forward, the clean checkout is
restored to its prior pinned commit and the command fails. A fetch can update
Git's remote-tracking refs, but it never changes canonical knowledge files.
The command never auto-merges, rebases, force-resets user work, or runs in the
background.

The catalog records relative checkout paths below the configured data
directory. It contains distribution state, not knowledge, and can be rebuilt
from installed repositories.

## Keyword index and search

QMD must already resolve through the configured command; Portable KB does not
install it automatically. The implemented model-free commands are:

```console
pkb search index [<slug>] [--json]
pkb search query <keywords> [--brain <slug>] [-n <limit>] [--json]
```

`search index` first requires a clean, identity-matched, catalog-pinned, valid
brain. It generates a Portable-KB-owned QMD configuration containing one
Markdown collection and no `update` hook. Reserved OKF `index.md` and `log.md`
documents are excluded because search citations require immutable concept IDs.
QMD configuration and SQLite state are isolated below
`<cache>/search/qmd/<slug>/`; inherited QMD database overrides are removed.
The command invokes `qmd update` in a staging directory and atomically publishes
the new index only after QMD produces its database. A failed rebuild preserves
the prior usable index.

`search query` invokes only QMD's BM25 `search` command. It never invokes
`embed`, `vsearch`, hybrid `query`, query expansion, or reranking. Queries fail
closed when the checkout is unhealthy, the index commit differs from the
catalog pin, QMD returns malformed output, or a result escapes the selected
bundle. Every accepted result is remapped through the core parser and includes
the brain ID/slug, immutable item ID, bundle-relative path, type, lifecycle
status, `stale_after`, and exact Git commit. Draft, deprecated, and stale
signals are visible rather than silently promoted or hidden; this first slice
does not apply an authority filter.
