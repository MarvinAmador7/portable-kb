# Core OKF-Compatible Knowledge Base

This repository contains an implemented portable, file-based organizational
knowledge core. The knowledge bundle uses
UTF-8 Markdown, YAML 1.2 frontmatter, ordinary Markdown links, and Git history.
It targets the current Open Knowledge Format (OKF) v0.2 specification while
adding a stricter local profile for identity, provenance, lifecycle, and
quality controls.

The core includes a governed bundle, schemas, deterministic validation,
lifecycle change planning, index generation, and regression tests. A first
consumer slice adds the `pkb` command, inline terminal setup prompts, and safe
Git-backed brain installation and synchronization. It also provides isolated
QMD BM25 indexing, cited keyword search, complete-item retrieval, and one
portable workflow skill for Codex and Claude Code without model downloads. A
plan-first authoring command can create validated local drafts without silently
committing or publishing them. Semantic search, MCP, native UI,
authentication/authorization, connectors, hosted services, and automatic
background agents are not yet implemented.

## Implemented core

The first implementation is a single `knowledge/` bundle with:

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

All initial concepts remain honestly labeled agent-generated drafts. Reviewer
allowlists are intentionally empty: a deployment configures real human
identifiers when it chooses to promote authoritative content. The core requires
that review, its scope record, and its matching event; it never fabricates
them. This is an ongoing content lifecycle action rather than missing code.

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

## Proposed repository and bundle boundary

Project documentation and the knowledge bundle have an explicit
boundary. OKF treats every non-reserved Markdown file inside a bundle as a
concept document. Files such as this `README.md`, `AGENTS.md`, design docs, and
templates therefore remain outside the bundle.

```text
repository/
├── README.md
├── AGENTS.md
├── brain.yaml                 # installable brain identity and bundle path
├── docs/                      # design documentation; not an OKF bundle
├── schemas/                   # profile schema; not an OKF bundle
├── templates/                 # authoring inputs; not validated as concepts
├── examples/                  # test corpus
├── src/portable_kb/           # core library plus CLI consumers
├── tests/                     # parser, corpus, transition, operation tests
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

report = validate_bundle("knowledge", as_of="2026-08-12")
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
```

This copies the bundled `portable-kb` skill to the user-level Codex and Claude
Code discovery paths. Use `--target codex` or `--target claude` for one agent,
and use `--force` only when intentionally replacing an existing installation.
The skill instructs agents to check brain health, search, retrieve complete
items, preserve immutable citations, expose lifecycle signals, and treat
knowledge content as untrusted data rather than executable instructions.

Primary references:

- [Open Knowledge Format v0.2 specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
- [Original Google Cloud OKF announcement](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/)
- [Google Cloud OKF v0.2 trust-signals announcement](https://cloud.google.com/blog/products/data-analytics/okf-v0-2-adds-trust-signals/)

## Deferred capabilities

Semantic and hybrid retrieval, model installation, embeddings, vector
databases, knowledge-graph databases, background brain synchronization,
lifecycle CLI commands beyond draft creation, MCP, APIs, web/native UI,
authentication,
authorization, multitenancy, automatic background agents, production
infrastructure, and third-party connectors are not yet implemented. The file
model exposes stable seams for them without depending on them.
