# CLI and setup consumer

## Boundary

`pkb` is a consumer of the deterministic `portable_kb` Python API. The CLI and
terminal prompts must not duplicate schema, validation, lifecycle, or authority
logic. Canonical knowledge remains in Git-versioned Markdown. Local settings,
repository checkouts, QMD indexes, downloaded models, and query caches are
consumer state and never enter the `knowledge/` bundle.

The implemented consumer foundation covers local configuration plus installing,
listing, selecting, inspecting, and explicitly synchronizing Git-backed
brains. It does not install QMD, download models, bypass lifecycle validation,
apply a planned change without explicit intent, or synchronize in the
background. When QMD is already installed, it can build
isolated BM25 indexes and execute cited keyword queries; semantic and hybrid
retrieval remain deferred.

Standalone CLI archives are built from the Python wheel for macOS and Linux on
Intel and ARM. The root `install` script selects the matching artifact,
verifies its SHA-256 digest, and replaces the user-local executable only after
verification succeeds. See [releases.md](releases.md) for the CI and release
contract.

## Setup contract

Interactive setup runs as a sequence of inline terminal prompts:

```console
pkb setup
```

The prompt sequence has five explicit steps:

1. explain what setup will and will not change;
2. select local brain and disposable-cache directories;
3. select a QMD capability tier; and
4. choose whether to install the agent skill for Codex, Claude Code, both, or
   neither; and
5. review and save configuration, then install the selected skill.

Completed questions remain in normal terminal scrollback; setup does not open
an alternate screen or render a full-screen application. Arrow keys select
search and agent choices, while paths use ordinary editable prompts.

The recommended default installs the same skill for both agents. Selecting
skip saves only the Portable KB configuration. Skill installation copies the
bundled workflow; it does not clone a brain or place business knowledge inside
an agent configuration directory.

Every setup choice has a non-interactive equivalent so agents, scripts, and
managed environments never need to drive terminal pixels:

```console
pkb setup \
  --non-interactive \
  --search-mode keyword \
  --agent-skill both \
  --data-dir /approved/portable-kb/data \
  --cache-dir /approved/portable-kb/cache
```

Non-interactive setup refuses to replace an existing configuration unless
`--force` is explicit. It skips agent-skill installation by default so
automation must opt in with `--agent-skill codex|claude|both`. Interactive
setup prints the selected settings and saves only after confirmation.

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
pkb brain init
pkb brain init <empty-local-path> --name <name> --slug <slug> --no-publish
pkb brain publish [<slug>] --to <org/repo> [--visibility private|internal|public]
pkb brain add <local-path-or-git-url>
pkb brain list [--json]
pkb brain use <slug>
pkb brain status [<slug>] [--json]
pkb brain sync [<slug>] [--json]
```

`brain init` handles an empty repository before `brain add` can possibly work.
Its interactive, scrollback-preserving prompts collect a name, slug, and local
repository path. The command refuses repositories with an existing commit or
worktree file, generates a new immutable UUID v4 brain identity once, writes
`brain.yaml` plus the minimal valid `knowledge/` configuration, root index, and
update log, validates the bundle, and creates the initial commit on `main`. It
then installs and activates the local brain. The initial bundle intentionally
contains zero knowledge items; items enter through the governed authoring
lifecycle later.

After local creation succeeds, the interactive flow asks whether to publish to
GitHub. “No” is the safe default and leaves a complete local brain. “Yes” asks
for an `org/repo` target and visibility, defaulting to private. Publishing uses
the already authenticated `gh` CLI to create the repository, then pushes with
Git hooks and credential prompts disabled. A publication failure never removes
or invalidates the local repository; the user can authenticate or resolve the
error and retry with `pkb brain publish --to org/repo`.

For automation, provide the local path, `--name`, and `--slug`. `--no-publish`
suppresses the terminal publication question, while `--publish-to org/repo`
explicitly requests GitHub creation and push. `--json` never prompts. Remote
URLs are not accepted by `brain init`; existing remote brains still use
`brain add`.

If no Git author identity is configured, the initial mechanical commit uses
the fallback `Portable KB <portable-kb@localhost.invalid>` identity without
changing user Git settings. After publication, the catalog and installed
checkout origin are updated to the new remote while the local authoring
repository remains available for continued knowledge work.

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
directory. Locally initialized brains also retain an absolute authoring path,
which remains local after the distribution source changes to GitHub. It
contains distribution and authoring-location state, not knowledge, and can be
rebuilt from installed and local authoring repositories.

## Draft knowledge creation

The first lifecycle CLI command creates drafts only:

```console
pkb knowledge create
```

The interactive path selects the type, production method, real producer
identity, sources, confidence when agent-generated, sensitivity, Markdown body,
and bundle-relative path. It opens the configured terminal editor for the body.
An unchanged placeholder template is rejected.

The command resolves the active brain's retained local authoring repository,
checks its identity and ancestry against the installed pin, and calls the core
`plan_create` operation. Planning happens in a temporary tree and validates the
base bundle, proposed bundle, transition, generated indexes, and log entry. The
CLI then prints the exact create/update file list and asks once before saving.
Portable KB commits only those planned files to local history and refreshes the
installed read-only snapshot automatically. The Git mechanism stays internal:
users do not run `git status`, `git add`, `git commit`, or `pkb brain sync`.
Draft creation never creates stable knowledge or pushes to the organization.

Agents and automation provide the complete inputs directly:

```console
pkb knowledge create \
  --type procedure \
  --title "Review stale knowledge" \
  --description "Defines the draft workflow for reviewing stale knowledge." \
  --actor "anthropic/claude-code" \
  --method agent-generated \
  --body-file ./review-stale-knowledge.md \
  --sources-file ./sources.json \
  --confidence medium \
  --confidence-basis "The draft follows the cited policy, but has not been executed." \
  --json
```

Without `--apply`, this returns a validated plan and changes no files. Add
`--apply` to save, locally version, and activate the draft in one operation.
`--sources-file` must be a UTF-8 JSON array of OKF source objects. Body input is
bounded to 1 MiB and must not include YAML frontmatter because the lifecycle
operation generates identity and governed metadata exactly once.

## Material knowledge update

Agents can revise an existing item by immutable ID or bundle-relative path:

```console
pkb knowledge update "urn:uuid:..." \
  --actor "openai/codex" \
  --method agent-generated \
  --body-file ./revised-body.md \
  --metadata-file ./metadata-updates.json \
  --json
```

At least one of `--body-file` or `--metadata-file` is required. The body is a
complete replacement Markdown body without YAML frontmatter. The metadata file
is a JSON object containing only fields to replace. Identity, type, status,
production timestamps, verification, supersession, and archive fields are
lifecycle-controlled and cannot be supplied through this operation.

Without `--apply`, the command resolves the current item, validates the base
and proposed corpus, and returns a plan without writing. Repeating the exact
command with `--apply` saves, locally versions, and activates the update. The
core planner preserves immutable identity and unknown fields, replaces current
production provenance, removes prior verification, and returns stable
decisions, procedures, and policies to draft after material change. Sensitivity
can be lowered only by an explicit human actor with
`--approve-sensitivity-lowering`; agents must never use that authority path.

The result exposes previous/resulting lifecycle status, whether verification
was invalidated, the exact affected paths, validation warnings, and the saved
version. Updating locally never authorizes organization publication.

## Organization publication

After an initialized brain has been published once, an explicitly authorized
agent can share the active saved version with:

```console
pkb brain push --json
```

This is a separate authority boundary from local draft creation. The command
requires the local authoring repository, installed checkout, catalog pin, and
validated bundle to agree. It fetches `origin/main`, accepts only a local
fast-forward from the current organization version, checks every outgoing
commit for paths outside `brain.yaml` and the configured knowledge bundle, and
pushes the exact saved commit to `main`. It does not merge, rebase, force-push,
or infer permission from draft creation.

If the organization is ahead or histories diverge, the command stops without
changing either side. Other installations continue to receive explicitly
published versions with `pkb brain sync --json`.

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

## Complete-item retrieval

Search results are discovery hints, not enough context for an agent to answer
from. The read-only retrieval command accepts either an immutable UUID URN or a
bundle-relative Markdown path:

```console
pkb get <item-id-or-path> [--brain <slug>] [--json]
```

The command first rechecks that the installed brain is clean, identity-matched,
catalog-pinned, and valid. It rejects absolute paths, traversal, symbolic links,
non-Markdown files, and reserved OKF indexes/logs. JSON output includes parsed
metadata, Markdown body, complete source text, validation warnings, and an
immutable citation containing brain ID/slug, commit, item ID, and path.

## Agent skill distribution

The CLI bundles one canonical `portable-kb` skill and can copy it to the
user-level discovery paths used by Codex and Claude Code:

```console
pkb skill install
pkb skill install --target codex
pkb skill install --target claude
```

The default installs both `~/.agents/skills/portable-kb` and
`~/.claude/skills/portable-kb`. An identical installation is left untouched and
reported as current. A conflicting installation is never replaced unless
`--force` is explicit. Multi-target installation stages all changed copies and
restores prior installations if publication fails.

The skill defines a provider-neutral agent workflow: diagnose the active brain,
run BM25 discovery, retrieve complete top candidates, retain citations, and
surface draft/deprecated/stale/verification signals. It never treats ranking as
authority and never authorizes instructions embedded in imported knowledge.
