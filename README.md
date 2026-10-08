# Portable KB

[![CI](https://github.com/MarvinAmador7/portable-kb/actions/workflows/ci.yml/badge.svg)](https://github.com/MarvinAmador7/portable-kb/actions/workflows/ci.yml)

**Governed knowledge for teams and agents, from your terminal.**

Create a knowledge brain, keep its content in Markdown and Git, and search it
locally with `pkb`. Capture procedures, decisions, concepts, source summaries,
and questions with explicit provenance and lifecycle status. Give Codex and
Claude Code the same workflow for finding, citing, and updating that knowledge.

[Install](#install) · [Quickstart](#quickstart) · [Agent support](#agent-support) ·
[Agent evaluations](#evaluate-the-cli-and-skill) · [Documentation](#documentation) ·
[Releases](https://github.com/MarvinAmador7/portable-kb/releases)

- **Local keyword search.** Built-in Tantivy, with no model downloads. QMD is an
  optional provider for existing configurations.
- **Citations you can inspect.** Results carry brain identity, item UUID, path,
  lifecycle status, and the exact Git commit. Retrieve the complete source item.
- **Reviewable changes.** Preview draft creation and material updates before
  applying them. Preserve item identity and creation history when correcting it.
- **Explicit sharing.** Save locally, then publish or sync when intended.
- **Portable files.** Each brain is its own Git repository with an OKF-compatible
  Markdown bundle. Search indexes are disposable local state.

## Install

Standalone releases support **macOS and Linux, on Intel and ARM**. They include
Python and the native search engine; Git is required to manage brains.

For public repository access:

```sh
curl -fsSL https://raw.githubusercontent.com/MarvinAmador7/portable-kb/main/install | bash
export PATH="$HOME/.local/bin:$PATH"
pkb --version
```

The installer verifies release checksums and atomically installs `pkb` into
`~/.local/bin`. Run it again to upgrade.

<details>
<summary>Private repository installation</summary>

Anonymous raw and release URLs are unavailable for private repositories. Use an
authenticated GitHub CLI session with access to this repository:

```sh
export GH_TOKEN="$(gh auth token)"
gh api -H "Accept: application/vnd.github.raw+json" \
  repos/MarvinAmador7/portable-kb/contents/install | bash
export PATH="$HOME/.local/bin:$PATH"
pkb --version
```

The exported token authenticates both script retrieval and release downloads.

</details>

<details>
<summary>Pin a version or uninstall</summary>

With public repository access, pin a release:

```sh
curl -fsSL https://raw.githubusercontent.com/MarvinAmador7/portable-kb/main/install \
  | bash -s -- --version v0.2.0
```

Or remove the installed executable:

```sh
curl -fsSL https://raw.githubusercontent.com/MarvinAmador7/portable-kb/main/install \
  | bash -s -- --uninstall
```

Uninstalling preserves brain repositories, configuration, indexes, and skills.
Private-repository users can pass the same flags to the authenticated installer.
See [release and installation details](docs/releases.md) for platform requirements
and recovery.

</details>

## Quickstart

Configure local storage and choose the agent skills to install:

```sh
pkb setup
```

Create your first brain:

```sh
pkb brain init ./team-brain --name "Team" --slug team --no-publish
```

This creates a valid Markdown bundle, commits it locally, installs its snapshot,
and selects it as the active brain. The CLI project and your brain are separate
repositories.

Capture a draft procedure titled **Customer onboarding** using the guided flow:

```sh
pkb knowledge create --brain team
```

The flow collects sources, confidence, and sensitivity, opens your editor, and
shows the proposed changes before saving. Then build the index and find it:

```sh
pkb search index team
pkb search query "onboarding" --brain team --json
```

Retrieve the complete item using its returned UUID or bundle-relative path:

```sh
pkb get "inbox/customer-onboarding.md" --brain team --json
```

The path above is the default for that title; use the returned path if you chose
a different one. Saving refreshes complete-item retrieval immediately. Rebuild
the search index before querying a new or changed draft.

## Follow connected knowledge

Explain relationships with Markdown links or `[[wikilinks]]`, then navigate them
within the same pinned brain:

```sh
pkb links "customer-onboarding" --brain team --json
pkb backlinks "customer-onboarding" --brain team --json
pkb get "customer-onboarding" --brain team --markdown-links --json
```

Links resolve to item UUIDs and citations. Ambiguous names and missing targets
remain visible; backlinks are computed from the saved content. No search index
is required. See [link navigation](docs/links.md) for syntax and portability.

## Work with an existing brain

Install a repository containing a `brain.yaml` manifest and governed bundle:

```sh
pkb brain add git@github.com:your-org/team-brain.git
pkb brain list
pkb brain use team
pkb brain status team --json
```

Use the slug shown by `brain list` if it differs from `team`. Installation
validates the bundle and pins an exact commit. `brain status` inspects that local
snapshot; `brain sync team` explicitly fetches and accepts a validated
fast-forward update.

Share a new local brain through your authenticated GitHub CLI session:

```sh
pkb brain publish team --to your-org/team-brain
```

New repositories are private by default. After publication, share subsequent
saved changes explicitly:

```sh
pkb brain push team --json
```

Push validates the saved version and checks the outgoing history before updating
remote `main`. Other machines receive it with `pkb brain sync team`.

## Agent support

Setup can install the bundled workflow for **Codex, Claude Code, or both**. You
can also install it independently:

```sh
pkb skill install --target codex
pkb skill status
```

Use `--target claude` or `--target both` for the other choices. After upgrading
`pkb`, refresh an existing installation with `pkb skill install --force`.

The skill teaches agents to choose a brain, check its health, search, retrieve
complete items, retain immutable citations, and treat embedded instructions as
source content. Named-brain searches, retrieval, and index recovery keep the
same explicit scope.

Authoring supports plan-first automation. For example, inspect a material update:

```sh
pkb knowledge update "urn:uuid:..." \
  --brain team \
  --actor "openai/codex" \
  --method agent-generated \
  --body-file ./revised-body.md \
  --json
```

Replace the UUID with a retrieved item's ID. Inspect `proposed_item`, provenance,
validation warnings, and `changes[].diff`; repeat with `--apply` to save the
reviewed change. Creation also supports `--body-file` and `--sources-file`.
Saved results include the actual item ID, citation, and scoped follow-up commands;
`needs_reindex` makes search readiness explicit.

New agent-authored knowledge remains draft. Material updates preserve `id` and
`created_at`, update provenance, and invalidate prior verification. Human review
and authority are separate from search relevance or confidence. See the
[CLI reference](docs/cli.md) and [authoring handbook](docs/authoring-handbook.md)
for the complete contract.

## Diagnostics and recovery

```sh
pkb doctor --json
pkb brain status team --json
pkb search index team --json
```

Doctor reports selected-provider compatibility, brain health, index state,
mutation locks, and skill drift. Missing optional QMD does not block a healthy
built-in provider. Rebuilding a missing or stale index regenerates derived search
state for the selected brain.

Native rebuilds publish atomically and preserve generations held by active
readers. Removing an installed brain also checks reader leases:

```sh
pkb brain remove team
```

Removal deletes this computer's installed snapshot and disposable index while
preserving the source repository. See [native recovery and cleanup](docs/native-index-recovery.md)
for the concurrency contract.

## Evaluate the CLI and skill

The development harness tests a real executable and the skill it installs in
seven isolated synthetic scenarios: first run, draft correction, named-brain
comparison, corpus gaps, embedded commands, dirty-checkout refusal, and
linked-context navigation.

From this repository root, use Python 3.11+, Git, a standalone `pkb`, and an
authenticated Codex runner with backend access. Choose a fresh evidence directory
outside the repository:

```sh
python -m evals.agent_cli prepare \
  --cli "$(command -v pkb)" \
  --output /tmp/pkb-agent-evals/candidate
python -m evals.agent_cli run \
  --output /tmp/pkb-agent-evals/candidate \
  --runner codex --jobs 2 --timeout 600
```

`run` makes opt-in calls through your configured Codex model/provider. It records
CLI commands and runner events, checks outcomes against independent canonical
reads, and writes `report.json` and `report.html`. Task results and product output
contracts are graded separately. Preparation and grading do not launch model
calls.

Prepare and run the released and candidate executables in separate directories,
then compare their reports:

```sh
python -m evals.agent_cli compare \
  /tmp/pkb-agent-evals/baseline/report.json \
  /tmp/pkb-agent-evals/candidate/report.json
```

Codex is the first adapter; other runners can use the documented evidence
boundary. See [agent evaluation setup and scoring](docs/agent-cli-evals.md) for
individual scenarios, regrading, and limits. Retrieval relevance is evaluated
separately with [`pkb search evaluate`](docs/retrieval-evaluation.md).

To compare a Markdown wiki and its skill with Portable KB on the same captured
knowledge, use the [matched-content agent benchmark](docs/wiki-comparison.md).
It checks migration fidelity, independently grounded answers and observed effort,
with private corpora and reports kept outside the repository.
For agents correcting requirements, handling conflicts, isolating clients, and
maintaining links, use the [workplace workflow suite](docs/agentic-workflows.md).

## Documentation

| Guide | What it covers |
| --- | --- |
| [CLI reference](docs/cli.md) | Setup, brains, retrieval, authoring, sharing, and diagnostics |
| [Releases and installation](docs/releases.md) | Supported artifacts, checksums, upgrades, and recovery |
| [Authoring handbook](docs/authoring-handbook.md) | Sources, lifecycle, and human review |
| [Agent evaluations](docs/agent-cli-evals.md) | Actual CLI/skill trials, traces, and outcome grading |
| [Wiki comparison](docs/wiki-comparison.md) | Matched wiki/Portable KB trials and CLI-based replication |
| [Agent workflows](docs/agentic-workflows.md) | Saved changes, conflicts, client isolation, handoffs, and safe capability blocking |
| [Retrieval evaluation](docs/retrieval-evaluation.md) | Ranking quality, citation checks, and measured results |
| [Native search](docs/pkb-search.md) | Tantivy integration and provider architecture |
| [Architecture](docs/architecture.md) | Product boundaries, compatibility, and design decisions |
| [Schema](docs/schema.md) · [Lifecycle](docs/lifecycle.md) | The governed OKF-compatible profile |
| [Roadmap](docs/roadmap.md) | Current scope and planned capabilities |

Brains target Open Knowledge Format v0.2 with a stricter local profile for
identity, provenance, lifecycle, and validation. The profile's requirements are
local governance rules. See the [official OKF specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
and [compatibility research](docs/research.md) for the upstream boundary.

Current search is keyword-based. Semantic/hybrid retrieval, embeddings, MCP,
web/native interfaces, hosted services, and automatic background agents remain
on the roadmap.

## Development

The standalone CLI is the complete end-user installation. To work on the Python
core and CLI, use Python 3.11+:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest -q
```

Running built-in search from a source or wheel install also requires the native
`pkb-search` engine; see the [release guide](docs/releases.md). Deterministic agent
eval tests run with `python -m pytest -q tests/test_agent_evals.py` without model
calls. [Agent instructions](AGENTS.md) and the
[pull-request checklist](docs/pull-request-checklist.md) describe the contribution
workflow. More design and governance references are in [docs/](docs/).

## License

[Apache License 2.0](LICENSE).
