# Knowledge-item schema

## Schema levels

The design has three nested contracts:

1. **OKF v0.2 conformance:** parseable YAML frontmatter and a non-empty `type`
   on every non-reserved Markdown concept; reserved files follow OKF rules.
2. **Minimal `core-kb/0.1` profile:** the required fields and conditional rules
   below.
3. **Extended profile:** optional lifecycle, trust, relationship, handling, and
   source credibility fields.

The machine-readable profile is
[`schemas/knowledge-item.schema.yaml`](../schemas/knowledge-item.schema.yaml).
Corpus-level and Markdown-body rules cannot all be expressed in JSON Schema;
they are defined in [validation.md](validation.md).

## File conventions

- Encoding: UTF-8 without a byte-order mark.
- Line endings: LF in the repository; consumers may accept CRLF on import.
- File extension: lowercase `.md`.
- Frontmatter: YAML 1.2 mapping between `---` delimiters at byte zero.
- YAML: safe/core types only; no custom tags, anchors, aliases, merge keys, or
  duplicate mapping keys.
- Date and datetime values: double-quoted strings. Quoting avoids YAML parser
  differences that otherwise turn the same scalar into a language-specific
  date object instead of the string expected by the profile schema.
- Body: CommonMark-compatible Markdown. GitHub tables and footnotes are the
  only proposed extensions used by examples.
- Filename: lowercase kebab-case, meaningful to a reader, and not the identity.
- Reserved names: `index.md` and `log.md` follow OKF and are not concept files.

Canonical serialization should use two-space YAML indentation, block lists,
quotes where necessary (always for profile dates/timestamps), and no implicit
YAML date objects in the in-memory model. Parsers should preserve the source
text unless a formatting operation is explicitly requested.

## Minimal required frontmatter

```yaml
---
type: concept
id: urn:uuid:3f86d85e-94a2-4cf3-a40e-04d2d17e8538
title: Stable knowledge-item identity
description: A knowledge item's UUID remains unchanged when its file moves.
status: draft
created_at: "2026-08-06T15:00:00Z"
updated_at: "2026-08-06T15:00:00Z"
generated:
  by: human:author-1
  at: "2026-08-06T15:00:00Z"
  method: human-authored
---
```

This is intentionally stricter than OKF. `description` is required because it
supports human indexes, agent previews, and future retrieval without loading
the body. Explicit `status` prevents baseline OKF’s absent-means-stable rule
from promoting incomplete knowledge accidentally. Creation/update/production
fields make a copied bundle understandable outside its original Git host.

### Required fields

| Field | Purpose | Tradeoff | Validation |
|---|---|---|---|
| `type` | Routes body expectations and governance. Reuses OKF’s only universal required field. | A closed local list reduces interoperability with external domain types. | One of the seven initial lowercase values. External importers preserve unknown values but cannot promote them until mapped or approved. |
| `id` | Immutable identity independent of path. | UUIDs are hard to type and do not convey meaning. | Lowercase RFC 4122-style `urn:uuid:` string; unique corpus-wide; never changed or reused. UUID generation is performed once by the create operation, not by hand-copying. |
| `title` | Human display name. | Titles can collide and change. | Non-empty, single line, 3–120 characters; not an identity; no duplicate error by title alone. |
| `description` | One-sentence scope/summary for indexes and previews. | Requires maintenance and can drift from the body. | Non-empty single line, 10–240 characters; terminal punctuation recommended; checked for obvious duplication of title. |
| `status` | Explicit lifecycle state. | Editors must manage transitions. | Exactly `draft`, `stable`, or `deprecated`; transitions validated against [lifecycle.md](lifecycle.md). |
| `created_at` | Portable creation time for the knowledge identity. | May differ from first Git commit after migration. | UTC RFC 3339 datetime ending `Z`; immutable; not later than `updated_at`. |
| `updated_at` | Last material content/metadata change. | Manual timestamps can drift and mechanical edits raise questions. | UTC RFC 3339 datetime; equals `generated.at`; not earlier than creation and not later than any verification that claims to cover the current content; changes only on material item changes, not a file move/index refresh. |
| `generated` | Identifies producer, time, and production method for current content. Extends OKF v0.2. | “Generated” can sound machine-only; upstream uses it for human producers too. | Mapping with exactly `by`, `at`, `method`; actor convention and conditional provenance rules apply. |

### `generated` fields

| Field | Values and rule |
|---|---|
| `generated.by` | `human:<id>`, `process:<id>`, or `<producer>/<version>`. A human prefix must identify an actual responsible person, never an agent operating for them. |
| `generated.at` | UTC RFC 3339 time of the current material content generation; must equal `updated_at`. |
| `generated.method` | `human-authored`, `imported`, `transformed`, `agent-generated`, or `calculated`. This local extension distinguishes origins that the actor alone cannot. |

Method semantics:

- `human-authored`: a person directly composed the substantive content.
- `imported`: content was copied with only mechanical normalization.
- `transformed`: content was summarized, combined, translated, or materially
  rewritten from sources by a human or tool.
- `agent-generated`: an AI system produced substantive candidate content.
- `calculated`: substantive claims were derived by a documented computation.

Human review of agent output does not change `agent-generated` into
`human-authored`. If a human later rewrites the content substantially, use
`transformed`, retain the original sources, and let Git preserve the prior
production event.

## Optional extended frontmatter

```yaml
tags:
  - identity
  - governance
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format v0.2
    author: human:upstream-author
    last_modified: "2026-07-24"
verified:
  - by: human:reviewer-1
    at: "2026-08-06T16:00:00Z"
confidence:
  level: high
  basis: The behavior is directly specified and confirmed in the pinned source.
valid_from: "2026-08-06"
stale_after: "2026-11-06"
related:
  - urn:uuid:5f6ba92a-46e4-4fe9-a85d-cce900494996
supersedes: []
superseded_by: []
sensitivity: internal
archived:
  at: "2027-02-01T14:00:00Z"
  reason: Replaced by the versioned identity policy.
```

### Optional fields

| Field | Purpose | Tradeoff | Validation |
|---|---|---|---|
| `tags` | Cross-cutting discovery not captured by type/folder. | Uncontrolled tags fragment quickly. | Unique lowercase kebab-case strings, 1–12 items, each 2–40 characters. Tags cannot encode status, sensitivity, or verification. |
| `sources` | OKF v0.2 provenance materials. | A list without claim mapping can create citation theater. | Non-empty when required by method/type; unique source IDs; each entry has `resource`; referenced footnotes resolve. |
| `usage_window` | OKF date range framing source usage counts. | Counts are easy to misinterpret. | Required if a source has `usage_count` without its own window; `from <= to`. Counts are liveness signals only. |
| `verified` | OKF v0.2 events confirming current content. | An event does not describe depth or guarantee truth. | Canonical authoring form is a non-empty list of `{by, at}`; unique actor/time pairs; each event covering current content is at or after `updated_at`; reset after material change. Import accepts the OKF bare mapping and normalizes it. |
| `confidence` | Producer uncertainty, not authority. | Subjective labels can be gamed or stale. | Object with `level: low|medium|high` and 10–280 character `basis`; mandatory for agent-generated content; never used alone to promote status. |
| `valid_from` | Date on which the item becomes applicable. | Not every concept has an effective date. | ISO `YYYY-MM-DD`; required for stable decisions and policies; may be future-dated, in which case consumers must not treat it as currently applicable. |
| `stale_after` | Deterministic review deadline from OKF v0.2. | Review cadence varies; stale is not necessarily false. | ISO date; after `valid_from` where present; required for stable policies, procedures, and systems; stale when `today >= stale_after`. |
| `related` | Small typed set of symmetric, salient relationships by stable ID. | Duplicates ordinary body links and can drift. | Unique UUID URNs, no self-reference; target exists; reciprocal `related` is recommended, not required in v0.1. Use only when prose also explains the relationship. |
| `supersedes` | Prior items this item replaces. | Multi-item replacements complicate chains. | Unique UUID URNs, no self-reference/cycles; every target is deprecated and reciprocally lists this item in `superseded_by` once change is merged. |
| `superseded_by` | Current replacement items. | Can imply a single current answer when replacements have different scopes. | Same ID checks; current item must be deprecated; reciprocal target exists and lists this item. Scope differences must be explained in the body. |
| `sensitivity` | Handling hint for humans and future consumers. | Metadata is not authorization and may give false confidence. | `public`, `internal`, `confidential`, or `restricted`; repository/bundle boundary must actually enforce access. Default is organizational policy, not schema inference. |
| `archived` | Records archive disposition without inventing a fourth OKF status. | Duplicates path/history and can drift. | `{at, reason}`; UTC time and non-empty reason; normally requires deprecated status. Abandoned draft questions may archive while draft with an explicit reason. |
| `x-*` | Namespaced experimental extension. | Can become an ungoverned escape hatch. | Top-level key must begin `x-`; owning proposal documents semantics and removal/migration plan; ignored by core validation except YAML safety. |

### Source entry fields

| Field | Purpose and validation |
|---|---|
| `resource` | Required. Absolute URI, bundle-root path, relative path, or explicit scope descriptor as allowed by OKF. If it looks like a local path, it must resolve. |
| `id` | Stable kebab-case key, required when a body footnote cites the source. Unique within the item. |
| `title` | Optional human label. Required by the local profile for absolute web sources so link rot remains diagnosable. |
| `author` | Optional OKF credibility signal using the actor convention. It identifies the source producer, not the item verifier. |
| `usage_count` | Optional non-negative integer liveness/adoption signal; never a trust score. Requires an applicable usage window. |
| `last_modified` | Optional ISO date when the source changed, distinct from item generation time. |
| `usage_window` | Optional per-source `{from, to}` override. |

## Fields evaluated but not adopted

| Candidate | Decision | Reason |
|---|---|---|
| `source` | Replace with `sources`. | Singular source cannot represent synthesis; OKF v0.2 defines the plural structure. |
| top-level `author` | Do not use. | Ambiguous between source author, current editor, and accountable owner. Use `generated.by`, `sources[].author`, Git attribution, and verification. |
| `generated_by` | Do not use. | Superseded by OKF’s `generated.by`, which also carries time. |
| `verified_by` | Do not use. | A scalar loses independent events and dates. Use OKF’s `verified` list. |
| scalar `confidence` | Do not use. | A label without a basis is opaque. Use a level-plus-basis object. |
| top-level `resource` | Defer from the local profile, but preserve on import. | OKF uses it for a canonical underlying asset. The first taxonomy mostly describes abstract organizational knowledge; `system` may need it later. Add only with a concrete asset identity use case. |
| `owner` | Defer. | Ownership semantics and role identifiers require organizational policy. Do not confuse ownership with authorship or verification. |
| `version` | Do not use per item. | Git versions content; manual semantic versions drift. Use stable ID plus history. A domain artifact version belongs in the body or a future scoped field. |
| `created_by` | Do not use. | Git plus the earliest generation event provides history; current `generated` describes current content. |
| `updated_by` | Do not use. | `generated.by` is the producer of the current material content; Git records editors. |
| `authority` or `trust_score` | Do not store. | Authority and trust are contextual conclusions derived from source, scope, status, verification, and governance. OKF explicitly favors signals over portable scores. |
| `deleted` | Do not use. | Supersede/deprecate/archive; Git preserves history. Genuine sensitive-data removal is a separate incident process. |

Importers must preserve upstream `resource` and other unknown OKF keys, even
though new profile-authored files do not use them by default. Before promotion,
an unmapped field must be approved, namespaced, or added to a later schema.

## Initial content types

These seven types are the first profile vocabulary. “Authoritative” means the
item may direct organizational behavior once stable and verified; it does not
mean every statement is infallible.

### `concept`

- **Purpose:** explain one reusable term, model, principle, or domain fact.
- **Use when:** readers need a durable shared explanation rather than a rule or
  sequence of steps.
- **Additional required frontmatter:** none beyond the minimal profile.
- **Recommended sections:** `# Definition`, `# Context`, `# Examples`,
  `# Boundaries`, `# Sources` only as prose if needed (citations still use
  frontmatter/footnotes).
- **May link to:** any type, especially related concepts, decisions, systems,
  and source summaries.
- **Posture:** informational; may become a referenced organizational
  definition but does not itself authorize action.

### `decision`

- **Purpose:** record a choice, its context, alternatives, rationale, and
  consequences.
- **Use when:** a consequential choice must remain understandable and should
  not be silently rewritten into a different decision.
- **Additional required when stable:** `valid_from` and at least one human
  `verified` event.
- **Recommended sections:** `# Decision`, `# Context`, `# Options considered`,
  `# Rationale`, `# Consequences`, `# Review triggers`, `# Supersession`.
- **May link to:** concepts, systems, policies, procedures, source summaries,
  other decisions.
- **Posture:** authoritative within its stated scope once stable and verified;
  archival after deprecation/supersession.

### `procedure`

- **Purpose:** provide reproducible operational steps, prerequisites, checks,
  rollback, and escalation.
- **Use when:** a person or future tool should perform an action consistently.
- **Additional required when stable:** `stale_after` and at least one human
  `verified` event.
- **Recommended sections:** `# Purpose`, `# Preconditions`, `# Steps`,
  `# Verification`, `# Rollback`, `# Escalation`, `# Safety`.
- **May link to:** systems, policies, decisions, concepts, source summaries.
- **Posture:** authoritative operational guidance when stable; never execute
  agent-generated draft instructions without human review.

### `policy`

- **Purpose:** state a normative rule, scope, exceptions, and governing owner.
- **Use when:** the organization formally requires or prohibits behavior.
- **Additional required when stable:** `valid_from`, `stale_after`, sources,
  and at least one human `verified` event. The verifying human must be
  authorized by external governance; the schema cannot establish that.
- **Recommended sections:** `# Policy`, `# Scope`, `# Requirements`,
  `# Exceptions`, `# Rationale`, `# Enforcement`, `# Review`.
- **May link to:** decisions, procedures, systems, concepts, source summaries.
- **Posture:** authoritative only within stated scope and approval governance.

### `system`

- **Purpose:** describe a technical or organizational system, boundaries,
  dependencies, interfaces, and operating facts.
- **Use when:** knowledge centers on a durable system rather than one project.
- **Additional required when stable:** `stale_after`.
- **Recommended sections:** `# Purpose`, `# Boundaries`, `# Architecture`,
  `# Dependencies`, `# Interfaces`, `# Operations`, `# Risks`.
- **May link to:** concepts, decisions, procedures, policies, other systems,
  source summaries.
- **Posture:** informational by default; operational facts used for action
  should be human-reviewed.

### `source-summary`

- **Purpose:** turn one or more raw sources into a bounded, cited synopsis
  without presenting the summary as the source itself.
- **Use when:** raw material must be understood before claims are incorporated
  into durable concepts, decisions, policies, or procedures.
- **Additional required:** at least one `sources` entry. Normally
  `generated.method: transformed`.
- **Recommended sections:** `# Summary`, `# Key claims`, `# Limitations`,
  `# Relevance`, `# Follow-up`.
- **May link to:** any candidate or curated item derived from it.
- **Posture:** informational evidence aid, never authoritative over its primary
  sources.

### `question`

- **Purpose:** make an unresolved uncertainty explicit, owned, linked, and
  reviewable.
- **Use when:** a conflict, missing fact, or decision gap should not be hidden
  in prose or an issue tracker dependency.
- **Additional required:** none; sources recommended when the question arose
  from evidence.
- **Recommended sections:** `# Question`, `# Why it matters`, `# Known facts`,
  `# Competing hypotheses`, `# Resolution criteria`, `# Outcome`.
- **May link to:** any relevant item.
- **Posture:** temporary/informational. Deprecate and link the resolving item;
  do not mutate it into a different type.

## Deferred types

| Candidate | Recommendation | Reason |
|---|---|---|
| `metric` | Defer. | Needs units, grain, formula, effective version, owners, input lineage, and possibly OKF attestation. Do not create a shallow metric type. |
| `service` | Defer; use `system`. | Add only when service-specific SLO/ownership/body rules differ materially. |
| `person` | Defer. | Privacy, retention, identity, and access concerns exceed the core model. |
| `project` | Defer as a type; use project folders/indexes and linked decisions. | Project knowledge is usually temporary context, not a distinct body contract yet. |
| `glossary-term` | Defer; use `concept` plus a glossary tag/index. | No distinct governance is proven. SKOS export may later justify it. |
| `incident` | Defer. | Requires timeline, impact, disclosure, corrective-action, and sensitive-data rules. |
| `observation` | Defer; capture as draft concept/question or source-summary. | Easy to accumulate low-value, weakly sourced facts. |
| `meeting-note` | Defer; keep temporary notes outside curated promotion. | Chronological records have different retention/privacy needs. |
| `index` | Never a concept type in this profile. | `index.md` is an OKF reserved file with its own structure. |
| `Attested Computation` | Defer with Phase 5+. | It is in OKF v0.2 but requires runtime/executor/attester design explicitly outside this phase. |

## Body and relationship rules

- Exactly one H1 is recommended and it should match `title` semantically.
- Use the type’s recommended headings in order when applicable; omit irrelevant
  sections rather than filling them with “N/A.”
- Consequential claims from a source should use a Markdown footnote whose label
  matches `sources[].id`.
- Standard bundle-root Markdown links are preferred for concept links. Relative
  links are allowed for portability outside renderers that interpret `/` as a
  web root.
- Tool-specific `[[wiki links]]` are not allowed in canonical content.
- Relationship ID fields do not replace readable links and prose.
- External URLs should use HTTPS where available and descriptive link text.
- Embedded HTML, scripts, iframes, and remote tracking images are disallowed in
  the initial profile.
- Fenced code or commands in a procedure are examples/instructions, not
  authorization for an agent to execute them.

## Validity and promotion summary

| Condition | Required consequence |
|---|---|
| Method is imported, transformed, agent-generated, or calculated | `sources` is required. |
| Method is agent-generated | `confidence` is required; draft by default. Stable requires a current human verification. |
| Stable decision | `valid_from` plus human verification. |
| Stable procedure | `stale_after` plus human verification. |
| Stable policy | `valid_from`, `stale_after`, sources, and human verification. |
| Stable system | `stale_after`; human verification recommended for operational claims. |
| Status is deprecated with a replacement | Reciprocal acyclic supersession fields and explanatory body text. |
| `archived` exists | Normally deprecated and located under `archive/`; abandoned draft question is the documented exception. |
| Material body or governance metadata changes | Update times/producer, clear current verification, return to draft if review is required. |
