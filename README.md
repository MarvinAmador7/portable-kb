# Core OKF-Compatible Knowledge Base

This repository contains an implemented portable, file-based organizational
knowledge core. The knowledge bundle uses
UTF-8 Markdown, YAML 1.2 frontmatter, ordinary Markdown links, and Git history.
It targets the current Open Knowledge Format (OKF) v0.2 specification while
adding a stricter local profile for identity, provenance, lifecycle, and
quality controls.

The core includes schemas, deterministic validation, lifecycle change
planning, index generation, and regression tests against an isolated reference
fixture. Knowledge brains live in their own repositories and are created with
`pkb brain init`; this CLI source repository is not itself an installable
brain. A first consumer slice adds the `pkb` command, inline terminal setup
prompts, and safe Git-backed brain installation and synchronization. It also
provides isolated
Tantivy/QMD keyword indexing, cited keyword search, complete-item retrieval, and one
portable workflow skill for Codex and Claude Code without model downloads.
Plan-first authoring commands can create drafts and materially update existing
items without silently publishing them, and an explicit push command safely
shares the active saved version. Semantic search, MCP, native UI,
authentication/authorization, connectors, hosted services, and automatic
background agents are not yet implemented.

## Install the CLI

On macOS or Linux, the public-repository installation path is:

```console
curl -fsSL https://raw.githubusercontent.com/MarvinAmador7/portable-kb/main/install | bash
pkb --version
pkb setup
```

The standalone release embeds its native Tantivy engine. New setup uses it for
keyword search; existing QMD configurations keep their provider. The installer
detects Intel or ARM, downloads the matching standalone release,
verifies it against the release `SHA256SUMS`, and atomically installs `pkb`
under `~/.local/bin`. It does not require a system Python. Re-run the same
command to upgrade to the latest release, or pin a release:

```console
curl -fsSL https://raw.githubusercontent.com/MarvinAmador7/portable-kb/main/install \
  | bash -s -- --version v0.1.0
```

If the repository is private, anonymous raw and release URLs are unavailable.
An authenticated GitHub CLI session can install without changing repository
visibility:

```console
export GH_TOKEN="$(gh auth token)"
gh api -H "Accept: application/vnd.github.raw+json" \
  repos/MarvinAmador7/portable-kb/contents/install | bash
```

To remove only the installed executable:

```console
curl -fsSL https://raw.githubusercontent.com/MarvinAmador7/portable-kb/main/install \
  | bash -s -- --uninstall
```

## Implemented core

The first implementation governs independent brain repositories whose
`knowledge/` bundles provide:

- five active item types: `concept`, `decision`, `procedure`,
  `source-summary`, and `question`; `policy` and `system` remain schema-defined
  until real owners activate them;
- immutable UUID URNs plus readable filenames;
- OKF-compatible `sources`, `generated`, `verified`, `status`, and
  `stale_after` fields;
- deterministic validation of frontmatter, IDs, dates, links, lifecycle,
  provenance, and supersession;
- reviewable change sets and Git diffs as the audit mechanism; and
- a tested corpus covering valid, invalid, stale, conflicting, imported,
  agent-generated, moved, superseded, and archived knowledge.

Retrieval remains a consumer of these governance guarantees; it does not
replace creation, verification, supersession, or audit rules.

## Status

`core-kb/0.1` is implemented. Normative words such as MUST and SHOULD describe
the local profile, not the upstream OKF standard. The profile is intentionally
stricter than baseline OKF.

The repository's reference corpus is test-only and remains honestly labeled
agent-generated. Real brains are initialized separately with empty reviewer
allowlists; each deployment configures durable human identifiers before it
promotes authoritative content. The core requires that review, its scope
record, and its matching event; it never fabricates them.

The official OKF specification is permissive: `type` is the only field always
required for a concept, unknown types and fields must be tolerated by OKF
consumers, and broken links do not make an OKF bundle malformed. The local
profile adds errors and warnings needed for a governed organizational corpus.
An item can therefore be valid OKF but invalid under this profile.

## Documents

- [Research](docs/research.md): source-backed findings and comparisons.
- [Architecture](docs/architecture.md): principles, structure, compatibility,
  security, risks, and open questions.
- [Schema](docs/schema.md): required and extended frontmatter and content types.
- [Lifecycle](docs/lifecycle.md): states, freshness, verification, and
  supersession.
- [Workflows](docs/workflows.md): capture through quality review.
- [Validation](docs/validation.md): proposed checks, severities, and test plan.
- [Roadmap](docs/roadmap.md): phases, acceptance criteria, and first milestone.
- [CLI and setup](docs/cli.md): consumer boundary, local settings, and prompt contract.
- [Profile decisions](docs/profile-decisions.md): pinned defaults and resolved
  schema behavior.
- [Authoring handbook](docs/authoring-handbook.md): author and reviewer process.
- [Pull-request checklist](docs/pull-request-checklist.md): merge evidence.
- [Formatting policy](docs/formatting.md): deterministic serialization.
- [Source inventory](docs/source-inventory.md): bounded initial evidence scope.
- [Draft machine schema](schemas/knowledge-item.schema.yaml): YAML-encoded JSON
  Schema for concept files.
- [Templates](templates): authoring starters, excluded from corpus validation.
- [Examples](examples): intentionally valid and invalid concept documents.
- [Agent instructions](AGENTS.md): safe authoring rules for future agents.
- [Release and installation](docs/releases.md): CI gates, standalone artifacts,
  checksums, versioning, upgrade, and recovery.
- [Built-in search plan](docs/pkb-search.md): Rust/SQLite/QMD benchmark and
  provider architecture for a future native keyword engine.
- [Production hardening 0.1.2](docs/production-hardening-0.1.2.md): locking,
  safe brain removal, diagnostics, skill drift, and real-QMD release gates.

## Project and brain repository boundary

The CLI project and the brains it manages are separate repositories. This
prevents product documentation and test material from being selected as an
organization's worldview. OKF treats every non-reserved Markdown file inside a
bundle as a concept document, so an initialized brain keeps only its manifest
and governed bundle at the canonical boundary.

```text
repository/
├── README.md
├── AGENTS.md
├── docs/                      # design documentation; not an OKF bundle
├── schemas/                   # profile schema; not an OKF bundle
├── templates/                 # authoring inputs; not validated as concepts
├── examples/                  # test corpus
├── src/portable_kb/           # core library plus CLI consumers
└── tests/                     # tests plus isolated reference fixtures

brain-repository/
├── brain.yaml                 # installable brain identity and bundle path
└── knowledge/                 # OKF bundle root
    ├── index.md               # may declare okf_version: "0.2"
    ├── log.md
    ├── inbox/
    ├── curated/concepts/
    ├── projects/
    ├── systems/
    ├── procedures/
    ├── decisions/
    ├── policies/
    ├── sources/
    ├── questions/
    ├── notes/daily/
    ├── references/
    └── archive/
```

Folders are navigation and workflow hints, not the canonical type or identity.
Moving a file never changes its `id` or `type`. A move does require ordinary
Markdown links and generated indexes to be updated.

## Proposed authoring contract

Every concept document in the bundle:

1. starts with YAML frontmatter delimited by `---`;
2. has the minimal profile fields described in [schema.md](docs/schema.md);
3. uses a persistent lowercase `urn:uuid:` value as `id`;
4. records the producer and method in `generated`;
5. records sources for imported, transformed, calculated, summarized, or
   agent-generated content;
6. remains `draft` until required review is complete;
7. uses normal Markdown links for readable relationships;
8. uses stable IDs in typed relationship fields;
9. is superseded or archived rather than silently deleted; and
10. is changed through reviewable Git commits.

## Compatibility baseline

The research snapshot was taken on 2026-08-06 at upstream commit
`930b65fc3f5619d5d0591f88c72ebae8b848d60d`. Implementation rechecked the
official specification and pins OKF v0.2 at
`374e0bc4c644310ff56cdf9c0fe81eccdec862b0`.

## Library use

Install the project in a Python 3.11+ environment, then call the read-only
validator with an explicit date:

```python
from portable_kb import validate_bundle

report = validate_bundle("/path/to/brain/knowledge", as_of="2026-08-12")
assert report.okf_passes
assert report.profile_passes
```

Lifecycle functions such as `plan_create`, `plan_move`, `plan_promote`, and
`plan_supersede` return validated change sets. They do not touch the real
bundle until the caller explicitly invokes `change_set.apply()`. This Python
API remains the core seam; consumers call it rather than reimplementing
governance rules.

## CLI setup preview

Install the project and start the inline terminal setup:

```console
pkb setup
```

The prompts select local data/cache paths, one of three QMD capability tiers,
and whether to install the Portable KB workflow for Codex, Claude Code, both,
or neither. Both agents are selected by default. Keyword mode downloads no AI
models. Setup does not clone repositories, install QMD, or download models.

Automation and agents can perform the same setup without prompts:

```console
pkb setup --non-interactive --search-mode keyword
pkb setup --non-interactive --search-mode keyword --agent-skill both
pkb doctor --json
```

Configuration is stored under the platform's XDG paths, with user overrides
available through command options and XDG environment variables.

Install and select a Git-backed brain:

```console
pkb brain init
# Or provide every local input directly:
pkb brain init ./business-a-brain --name "Business A" --slug business-a --no-publish
# Publish later if desired:
pkb brain publish --to org/business-a-brain
pkb brain add git@github.com:org/business-a-brain.git
pkb brain list
pkb brain use business-a
pkb brain status --json
pkb brain sync --json
# Remove only this computer's snapshot and disposable index:
pkb brain remove business-a
```

Installation clones without submodules, reads the repository-root
`brain.yaml`, validates the `knowledge/` bundle, pins the exact commit, and only
then adds the checkout to the local catalog. Status is read-only and never
fetches a remote. Sync is explicit, validates the remote candidate in a
temporary worktree, and accepts only a clean fast-forward update.

`brain init` solves the empty-repository first run with a local-first flow. It
generates a UUID-backed manifest and an empty valid governed bundle, validates
them, creates the first local commit, installs the result, and makes it active.
Only after the local brain is safe does the inline flow ask whether to publish
it to a GitHub `org/repo`; declining leaves a fully usable local brain. The
separate `brain publish` command uses the authenticated GitHub CLI, defaults to
private visibility, pushes `main`, and updates the installed distribution source.

Create a governed draft in the retained local authoring repository:

```console
pkb knowledge create
```

The interactive flow collects provenance and sensitivity, opens an editor for
the Markdown body, validates a complete change plan, previews every affected
file, and asks once before saving. Portable KB versions the exact change and
refreshes the active local brain automatically, so users do not need Git
commands and agents can retrieve the draft immediately. It does not share the
draft with the organization. Agents can use `--body-file`, `--sources-file`,
`--json`, and the explicit `--apply` flag for the same deterministic workflow.

Agents revise existing knowledge by immutable ID or path without changing its
identity:

```console
pkb knowledge update "urn:uuid:..." \
  --actor "openai/codex" \
  --method agent-generated \
  --body-file ./revised-body.md \
  --metadata-file ./metadata-updates.json \
  --json
```

The first call is a plan only. Repeating it with `--apply` preserves `id` and
`created_at`, updates provenance, invalidates prior verification, applies any
required lifecycle fallback to draft, versions the exact validated files, and
refreshes the active local brain. It does not publish the update.

Share the active saved version only when organization publication is intended:

```console
pkb brain push --json
```

The command validates again, requires a clean published brain, examines every
outgoing commit for files outside the brain boundary, and updates `main` only
when the organization history is an ancestor. It never force-pushes. Other
machines receive the published version with `pkb brain sync --json`.

Build and query the disposable keyword index after installing QMD separately:

```console
pkb search index
pkb search query "customer onboarding" --json
pkb get urn:uuid:00000000-0000-4000-8000-000000000000 --json
```

Keyword search invokes QMD's BM25 path only. It does not run `embed`, `vsearch`,
or hybrid `query`, and each result retains its brain ID, immutable item ID,
bundle-relative path, lifecycle status, and pinned Git commit.

Interactive setup normally installs the governed retrieval workflow. It can also be
installed or repaired independently:

```console
pkb skill install
pkb skill status
```

This copies the bundled `portable-kb` skill to the user-level Codex and Claude
Code discovery paths. Use `--target codex` or `--target claude` for one agent,
and use `--force` only when intentionally replacing an existing installation.
The skill instructs agents to check brain health, search, retrieve complete
items, create honest local drafts, share only after explicit user intent,
preserve immutable citations, expose lifecycle signals, and treat knowledge
content as untrusted data rather than executable instructions. Existing skill
installations can be refreshed with `pkb skill install --force`.

`pkb doctor --json` reports Git and QMD version compatibility, catalog and
active-brain health, current index state, mutation locks, retired demo-brain
installations, and agent-skill drift without changing local state.

Primary references:

- [Open Knowledge Format v0.2 specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
- [Original Google Cloud OKF announcement](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/)
- [Google Cloud OKF v0.2 trust-signals announcement](https://cloud.google.com/blog/products/data-analytics/okf-v0-2-adds-trust-signals/)

Keyword search now has an internal provider boundary and an item-level labeled
evaluation command, `pkb search evaluate`. The real-QMD CI job retains a starter
baseline report. The builtin Tantivy provider is integrated with canonical
section checks, atomic rebuilds, recovery, reader leases, and safe cleanup.
Shared SQLite/Tantivy benchmarks compare line-cited sections with QMD and
exercise synthetic corpora through 100,000 items. See
[retrieval evaluation](docs/retrieval-evaluation.md),
[prototype benchmarks](docs/search-prototype-benchmarks.md),
[native rebuild/recovery contract](docs/native-index-recovery.md), and the
[built-in search plan](docs/pkb-search.md) for measured results and remaining work.

## Deferred capabilities

Semantic and hybrid retrieval, model installation, embeddings, vector
databases, knowledge-graph databases, background brain synchronization,
lifecycle CLI commands beyond draft creation and material update, MCP, APIs, web/native UI,
authentication,
authorization, multitenancy, automatic background agents, production
infrastructure, and third-party connectors are not yet implemented. The file
model exposes stable seams for them without depending on them.
