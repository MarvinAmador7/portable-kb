# Phased implementation roadmap

The phases stabilize the canonical files before adding operations and only then
describe retrieval/integrations. Phases are gates, not calendar estimates.

## Implementation status

| Phase | Status | Evidence |
|---|---|---|
| 0 — Research and decisions | Implemented | The upstream revision and local decisions are pinned in `docs/profile-decisions.md`; deployment reviewer identities remain safely empty until real people configure them. |
| 1 — Core file model | Implemented | The isolated reference fixture exercises fourteen representative concepts across five active types, indexes, a log, and bundle configuration. Production brains are created in separate repositories with `pkb brain init`. |
| 2 — Validation | Implemented | `portable_kb.validate_bundle()` covers the rule catalog with stable structured findings and offline explicit-date behavior. |
| 3 — Lifecycle operations | Implemented | Reviewable planners cover create, update, promote, reverify, move, supersede, and archive with base/proposed validation and optimistic application. The CLI exposes plan-first create, update, and mechanical move. |
| 4 — Test corpus | Implemented | Focused fixtures and transition/operation tests assert every catalog rule; time and network behavior are deterministic. |
| 5 — Retrieval and CLI consumers | In progress | Inline/non-interactive setup, checksum-verified standalone CLI releases, local-first brain initialization with optional GitHub publication, plan-first draft creation and material update, explicit validated fast-forward push/sync, brain distribution, QMD BM25 search, complete-item retrieval, read-only links/backlinks and derived Markdown views, and setup-integrated Codex/Claude skill installation are implemented. The keyword provider boundary, labeled evaluation harness, normalized section records, SQLite/Tantivy prototypes, initial shared-corpus benchmarks, and native atomic rebuild/recovery with concurrent readers and reader-safe generation cleanup are implemented. Tantivy is integrated as the builtin provider, and native distribution is wired into the 0.2.0 release gate. Remote release validation, representative domain evaluations, semantic/hybrid retrieval, and trust filtering remain pending. |
| 6+ — Applications and integrations | Deferred | MCP, native UI, authentication/authorization, and connectors remain outside the current implementation. |

Technical implementation does not substitute for human governance. When a
deployment chooses to promote authoritative content, a real authorized person
must review the final snapshot, provide a scope record, and record their own
configured identifier. That is an ongoing content lifecycle action, not a
missing core implementation phase.

## Phase 0 — Research and decisions

**Goal:** agree on terminology, scope, OKF target, profile rules, and governance
owners.

**Deliverables:**

- approved versions of the design documents in this repository;
- pinned OKF v0.2 tag/commit and documented upgrade policy;
- decisions on actor IDs, verification authority, bundle boundary, freshness
  defaults, sensitivity boundaries, and policy inclusion;
- profile name/version (`core-kb/0.1`); and
- representative source/content inventory without importing it.

**Dependencies:** access to domain owners, records/privacy/security reviewers,
and the current OKF specification.

**Acceptance criteria:**

- researched facts and local recommendations are distinguishable;
- open questions blocking schema behavior are resolved or explicitly deferred;
- every proposed required field has a purpose and validation rule;
- no integration/runtime design has leaked into core scope; and
- an owner accepts the lifecycle and approval matrix.

**Risks:** designing from hypothetical use cases, upstream OKF changes, too many
required fields, and absent organizational authority definitions.

**Not included:** working bundle, validator, CLI, search, integrations, or
production governance automation.

## Phase 1 — Core file model

**Goal:** create a small, manually usable OKF bundle and prove authoring,
reading, linking, and Git review.

**Deliverables:**

- `knowledge/` with root/directory `index.md` and `log.md` conventions;
- finalized profile schema and metadata reference;
- templates for seven initial types;
- 10–20 curated, real representative items across at least four types;
- author/reviewer handbook and pull-request checklist;
- source citation and file-move conventions; and
- deterministic formatting policy (documented, not necessarily automated).

**Dependencies:** Phase 0 decisions, initial authors/reviewers, lawful source
access, and Git repository governance.

**Acceptance criteria:**

- all concept files are baseline OKF v0.2 conformant by inspection;
- every item has unique ID, explicit production method, and correct sources;
- a human can navigate from indexes without specialized software;
- a fresh agent can interpret files using `AGENTS.md` without inventing trust;
- at least one item has completed capture → curate → verify → stable; and
- a move preserves identity and updates all known links in one review.

**Risks:** author friction, metadata drift, premature taxonomy growth, and
templates optimized for examples rather than real work.

**Not included:** executable validator, automated index generation, CLI, MCP,
retrieval, connectors, web UI, or access-control system.

## Phase 2 — Validation

**Goal:** implement a local, read-only-by-default validator for the file model.

**Deliverables:**

- safe YAML/frontmatter and Markdown discovery/parser;
- schema validation with stable rule codes;
- corpus maps for IDs, paths, sources, links, indexes, and relationships;
- deterministic `as_of` freshness checking;
- human-readable and machine-readable reports;
- baseline-OKF versus profile result separation; and
- unit/corpus fixtures for all Phase 2 rules.

**Dependencies:** stable Phase 1 profile, selected language/toolchain, pinned
parser versions, and negative fixtures.

**Acceptance criteria:**

- zero false passes across the known invalid corpus;
- stable ordered output for identical input/date/schema;
- no file mutation during validation;
- unknown imported fields are preserved by any normalization path;
- error/warning distinctions match `docs/validation.md`; and
- validation works offline from a clean clone.

**Risks:** unsafe YAML parsing, parser dialect differences, overly strict OKF
claims, nondeterministic time/network checks, and warning overload.

**Not included:** automatic semantic fixes, state-changing commands, remote URL
truth checking, search, or integrations.

## Phase 3 — Lifecycle operations

**Goal:** make creation, review, verification, supersession, and archive changes
safe and repeatable while retaining file/Git transparency.

**Deliverables:**

- specified operations for create, promote, reverify, update, supersede, and
  archive (interface choice deferred until this phase);
- base-versus-proposed transition validation;
- immutable-field and verification-invalidation checks;
- atomic supersession and link/index update behavior;
- reviewer checklists and failure recovery; and
- audit/log conventions exercised on real changes.

**Dependencies:** reliable Phase 2 validator, Git workflow, authorized
reviewers, and Phase 1 corpus.

**Acceptance criteria:**

- every allowed transition has a passing scenario and every disallowed one a
  failing scenario;
- interrupted/partial supersession cannot pass validation;
- operations produce ordinary inspectable file diffs;
- agent-generated content cannot become stable authoritative knowledge without
  a real human verification; and
- rollback is a normal Git revert/new review, not history rewriting.

**Risks:** treating operations as authorization, timestamp races, merge
conflicts across reciprocal files, and accidental verification laundering.

**Not included:** background agents, hosted workflow, organization-wide
identity/authorization, web UI, retrieval, or connectors.

## Phase 4 — Test corpus

**Goal:** demonstrate robustness against representative valid, invalid, stale,
conflicting, and generated knowledge.

**Deliverables:**

- golden bundles listed in `docs/validation.md`;
- transition fixtures with base/proposed trees;
- property/invariant tests;
- labeled duplicate/conflict heuristic evaluation set;
- cross-platform/path/Unicode cases; and
- regression policy for schema/rule changes.

**Dependencies:** Phases 2–3 implementation and domain examples safe for test
use.

**Acceptance criteria:**

- every validation rule has a focused negative fixture and nearby positive
  control;
- tests fix time and avoid network dependencies;
- branching/consolidating supersession and archive exceptions are covered;
- generated knowledge cannot appear human-authored in any passing fixture;
- semantic heuristics report evidence and never auto-resolve; and
- test corpus runs from a clean clone on supported platforms.

**Risks:** toy fixtures, leaking sensitive source data, brittle golden text, and
measuring heuristic recall without precision.

**Not included:** retrieval benchmarks, embedding relevance tests, connector
contract tests, production load tests.

## Phase 5 — Retrieval and CLI consumers

**Goal:** consume the stable bundle without changing the canonical file model.

**Selected approach:** QMD provides local BM25, optional semantic search, and
optional hybrid reranking. Its SQLite index and downloaded models are derived
local state, never canonical knowledge and never committed to Git. Keyword
search is the default setup tier and requires no model download.

**Deliverables:**

- `pkb` command with inline and non-interactive setup parity;
- versioned local settings and XDG-aware data/cache locations;
- a brain manifest, local catalog, Git initialization/publication/install/sync,
  and commit lock contract (local-first empty-repository initialization,
  optional GitHub publication, manifest, install, catalog, selection, local
  status, and explicit validated fast-forward push/sync implemented);
- a QMD adapter with one disposable index per selected worldview (BM25
  indexing and keyword queries implemented), plus development-only native
  atomic rebuild/recovery, concurrent-reader validation, and reader-safe
  generation cleanup;
- visible draft/deprecated/stale handling and a trust-policy boundary;
- result citations retaining bundle, immutable item ID, path, and Git commit
  (implemented for keyword queries and complete-item retrieval);
- keyword/semantic/hybrid retrieval evaluations (item-level keyword harness,
  reference section judgments, shared QMD/SQLite/Tantivy comparison, and synthetic
  scale runs implemented; representative domain and semantic/hybrid evaluation
  pending); and
- machine-readable output for agent skills and future native clients
  (implemented for search, retrieval, and skill installation).

**Dependencies:** stable corpus, validation, lifecycle operations, test data,
and explicit retrieval requirements.

**Acceptance criteria:** setup works interactively and non-interactively; no
model is downloaded without an explicit capability choice; any derived index
can be deleted and rebuilt; results retain source item ID/path/commit and
citations; stale/deprecated/draft filters are visible; similarity never
determines authority.

**Risks:** retrieval quality mistaken for truth, chunking that loses provenance,
model-dependent embeddings, and hidden filtering.

**Still deferred from this phase:** hosted search, organization identity,
authorization, cross-organization multitenancy, background synchronization,
MCP publication, and serving APIs.

See [the built-in search plan](pkb-search.md) for the provider sequence and
[retrieval evaluation](retrieval-evaluation.md) for labels, metrics, and the
starter baseline's limits.

## Phase 6 — External integrations (high level only)

**Goal:** exchange knowledge with external systems after the canonical model is
stable.

**Potential deliverables:** connector principles for source identity,
incremental import, conflict handling, permissions, deletion, provenance, and
round-trip loss analysis.

**Dependencies:** stable lifecycle/retrieval boundaries, security architecture,
identity/authorization, and system-specific owners.

**Acceptance criteria:** no connector can silently overwrite stable knowledge;
external identity/revision is preserved; generated transformations remain
labeled; permission boundaries are enforced outside metadata; round-trip loss
is documented and tested.

**Risks:** source-of-truth ambiguity, permission leakage, destructive sync,
rate/API change, and proprietary metadata coupling.

**Intentionally not designed here:** Google Drive, Microsoft 365, Notion,
Slack, Gmail, GitHub, or any other connector; authentication, authorization,
multitenancy, hosted APIs, or production infrastructure.

## Recommended first milestone

Complete Phase 0 and a deliberately narrow slice of Phase 1:

1. Pin OKF v0.2 at an exact upstream commit.
2. Resolve actor identity, verification authority, freshness defaults, and
   bundle boundary.
3. Create `knowledge/` with indexes/log and only five actively used types at
   first: `concept`, `decision`, `procedure`, `source-summary`, and `question`.
   Keep `policy` and `system` defined but activate them only when an owner and
   real examples exist.
4. Author one trustworthy real item of each active type, including one
   agent-assisted draft and one supersession pair.
5. Review the files manually against the schema/validation catalog.
6. Run the workflows for two weeks or a representative set of changes before
   freezing `core-kb/0.1`.

Success means a human and an agent can independently locate, understand,
source, review, update, and supersede the same small set of files. It does not
mean the corpus has search, automation, or integrations.

## Decision gates before expansion

- Add a type only if at least three real items need distinct body/governance
  rules.
- Build lifecycle operations only after manual transitions expose their edge
  cases.
- Add retrieval only after zero-error validation and an agreed trust filter.
- Add a connector only after source-of-truth, permissions, identity, conflict,
  and deletion semantics are written down.
- Add automation only when its changes remain bounded, reviewable, attributable,
  and reversible through ordinary Git workflows.
