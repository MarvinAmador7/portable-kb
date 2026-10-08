# Validation strategy

## Goals

Validation should make syntax, structure, identity, references, dates, and
lifecycle deterministic while clearly separating semantic judgment. It is a
local quality profile layered on OKF v0.2, not a redefinition of upstream
conformance.

Every finding should include:

- stable rule code, such as `KB-E121`;
- severity: error, warning, or information;
- file and precise field/line where possible;
- concise explanation;
- safe remediation guidance; and
- whether the rule is baseline OKF or `core-kb/0.1`.

The validator is implemented by the `portable_kb` Python API. It is read-only,
offline, and deterministic for an explicit bundle, schema, date, and optional
base tree.

## Severity policy

- **Error:** deterministic violation that prevents profile-safe merge or makes
  the intended corpus inconsistent. Exit non-zero.
- **Warning:** likely quality/governance problem requiring review or explicit
  acknowledgment; does not fail a draft-only local check by default, but may be
  promoted to error for release branches.
- **Information:** health signal or suggestion with no implied defect.

Report baseline OKF conformance separately:

```text
OKF v0.2: pass | fail
core-kb/0.1: pass | fail-with-errors | pass-with-warnings
```

An unknown key, broken link, or unknown type may be acceptable baseline OKF but
an error under the local authoring profile. The message must state that
difference.

## Validation pipeline

Run deterministic checks in this order so later checks can assume earlier
structure:

1. discover bundle boundary and reserved files;
2. check UTF-8, filenames, delimiters, and safe YAML syntax;
3. validate each frontmatter object against the draft schema;
4. build maps for path, immutable ID, title, source resource, and indexes;
5. resolve links, source footnotes, and relationship targets;
6. validate lifecycle, timestamps, staleness, and supersession graph;
7. validate type/body/index/log conventions;
8. compare Git base for transitions and immutable-field changes when available;
9. emit health notices for orphans, likely duplicates, and review cadence.

The same input, validation date, schema version, and Git base must produce the
same ordered findings. Network access is off by default; external URL
availability is a separate, opt-in future check and cannot determine truth.

## Rules and severities

### Files and YAML

| Code | Check | Severity |
|---|---|---|
| `KB-E001` | Concept is not valid UTF-8 or has a byte-order mark. | Error |
| `KB-E002` | Non-reserved `.md` lacks a frontmatter block at byte zero. | Error; baseline OKF failure |
| `KB-E003` | YAML is not a mapping, is syntactically invalid, contains duplicate keys, unsafe tags, anchors/aliases, or merge keys. | Error |
| `KB-E004` | Frontmatter delimiter is missing/ambiguous. | Error |
| `KB-E005` | Filename is not lowercase kebab-case `.md`, or misuses reserved `index.md`/`log.md`. | Error for reserved misuse; warning for style |
| `KB-W006` | CRLF or trailing whitespace differs from canonical format. | Warning; formatter may fix only with explicit request |
| `KB-E007` | A concept is a symbolic link and may escape or alias the bundle boundary. | Error |

### Required fields and vocabulary

| Code | Check | Severity |
|---|---|---|
| `KB-E100` | `type` missing/empty. | Error; baseline OKF failure |
| `KB-E101` | Any minimal profile field is missing or wrong type. | Error; profile only |
| `KB-E102` | Type is unsupported locally. | Error for new authored/promoted content; warning for preserved external import |
| `KB-E103` | Unknown non-`x-` top-level field. | Error profile-only; importer must preserve it and request mapping rather than drop it |
| `KB-W104` | `x-` field lacks a documented owning proposal. | Warning |
| `KB-E105` | Legacy aliases (`source`, `generated_by`, `verified_by`, top-level `author`) are used. | Error with migration guidance |
| `KB-E106` | Tag syntax/uniqueness/count invalid. | Error |

### Identity and timestamps

| Code | Check | Severity |
|---|---|---|
| `KB-E120` | `id` is not a lowercase UUID URN. | Error |
| `KB-E121` | Duplicate immutable ID. | Error |
| `KB-E122` | ID changed relative to Git base. | Error |
| `KB-E123` | `created_at` changed or is after `updated_at`. | Error |
| `KB-E124` | Timestamp is not strict UTC RFC 3339 ending `Z`. | Error |
| `KB-E124A` | Profile date or datetime is not serialized as a quoted YAML string. | Error |
| `KB-E125` | `updated_at` differs from `generated.at`. | Error in first profile |
| `KB-W126` | Material Git diff without updated production metadata, or metadata update on a clearly mechanical move. | Warning; materiality may need human judgment |
| `KB-E127` | Current verification predates the content `updated_at` it claims to cover. | Error |

### Provenance and generation

| Code | Check | Severity |
|---|---|---|
| `KB-E200` | Imported/transformed/agent-generated/calculated item lacks sources. | Error |
| `KB-E201` | `source-summary` or stable policy lacks sources. | Error |
| `KB-E202` | Source entry lacks resource or a local resource path is invalid. | Error |
| `KB-E203` | Duplicate `sources[].id`. | Error |
| `KB-E204` | Body source footnote has no matching source ID, or cited source lacks ID. | Error |
| `KB-W205` | Source is listed but never cited in a body that makes consequential sourced claims. | Warning |
| `KB-E206` | `usage_count` lacks a valid shared/per-source usage window. | Error |
| `KB-W207` | Source appears to be a summary when a primary source is known/expected. | Warning; semantic heuristic |
| `KB-E208` | Actor syntax invalid or agent/process uses `human:`. | Error when determinable; otherwise governance warning |
| `KB-E209` | Agent-generated content lacks confidence level/basis. | Error |

### Lifecycle, trust, and freshness

| Code | Check | Severity |
|---|---|---|
| `KB-E300` | Status is not `draft`, `stable`, or `deprecated`. | Error |
| `KB-E301` | Git-detected status transition is disallowed. | Error |
| `KB-E302` | Stable decision lacks `valid_from` or current human verification. | Error |
| `KB-E303` | Stable procedure lacks `stale_after` or current human verification. | Error |
| `KB-E304` | Stable policy lacks `valid_from`, `stale_after`, sources, or human verification. | Error |
| `KB-E305` | Stable system lacks `stale_after`. | Error |
| `KB-E306` | Stable agent-generated content lacks human verification. | Error |
| `KB-W307` | Stable operational system claims lack human verification. | Warning |
| `KB-W308` | Item is stale on the validator’s explicit `--as-of` date. | Warning; error in an authoritative-release policy if configured |
| `KB-W309` | A source reports a modification date after the latest item verification. | Warning |
| `KB-I309` | Item is not yet effective. | Information; warning if linked as currently applicable |
| `KB-E310` | `stale_after <= valid_from`. | Error |
| `KB-E311` | Material change retains verification from the prior snapshot. | Error when Git comparison proves it; otherwise warning |
| `KB-W312` | Deprecated item lacks a deprecation/supersession explanation in body. | Warning |
| `KB-E313` | Archived stable item or archive metadata without reason/time. | Error; documented abandoned-draft exception allowed |
| `KB-E314` | An existing immutable identity is deleted from a proposed tree. | Error |

### Relationships and links

| Code | Check | Severity |
|---|---|---|
| `KB-E400` | Typed relation has malformed, duplicate, missing, or self target. | Error |
| `KB-E401` | Supersession relation is not reciprocal. | Error |
| `KB-E402` | Supersession graph contains a cycle. | Error |
| `KB-E403` | Superseded predecessor is not deprecated or replacement is not stable/effective. | Error |
| `KB-E404` | Internal Markdown link in curated/stable content is broken. | Error profile-only; baseline OKF permits it |
| `KB-W405` | Internal Markdown link in inbox/draft content is broken. | Warning |
| `KB-W406` | Typed relationship has no explanatory body link, or salient body supersession lacks typed relation. | Warning |
| `KB-W407` | Wikilink is missing, ambiguous, escaping, or targets a missing heading. Resolved links pass. | Warning for drafts/inbox, error for stable curated content |
| `KB-I408` | Stable item has no inbound concept links. | Information (orphan candidate, not automatically a defect) |

### Indexes, logs, and body

| Code | Check | Severity |
|---|---|---|
| `KB-E500` | Reserved `index.md` has disallowed/malformed frontmatter or entry structure. | Error; may be baseline OKF failure |
| `KB-E501` | `log.md` date headings are invalid/not newest-first. | Error; baseline OKF structure failure |
| `KB-E502` | Index entry points to missing target. | Error |
| `KB-W503` | Expected current item is missing from its directory index, or deprecated item appears as current. | Warning |
| `KB-W504` | Index description differs from target frontmatter. | Warning; generated index should be refreshed |
| `KB-W505` | Recommended type body section missing. | Warning; configurable per type/status |
| `KB-E506` | Embedded script/iframe/unsafe HTML is present. | Error |
| `KB-W507` | Placeholder markers such as `TODO`, `TBD`, or template brackets remain in a stable item. | Warning or error for policy/procedure |

### Consistency and quality

| Code | Check | Severity |
|---|---|---|
| `KB-W600` | Normalized titles collide in the same scope. | Warning; not proof of duplication |
| `KB-W601` | Multiple items claim the same canonical source/resource and similar scope. | Warning |
| `KB-W602` | Metadata title/description appears inconsistent with H1/body. | Warning; heuristic |
| `KB-I603` | Draft has not changed within the configured inbox review window. | Information |
| `KB-I604` | Stable item has no tags. | Information only; tags are optional |
| `KB-W605` | Two current items are explicitly marked or heuristically detected as conflicting. | Warning requiring human resolution; never auto-merge |

### Bundle configuration

| Code | Check | Severity |
|---|---|---|
| `KB-E700` | `.core-kb.yaml` is missing, unsafe, or invalid against its schema. | Error |
| `KB-E701` | Stable content uses a type that is not active in the bundle. | Error |
| `KB-E702` | A stable authoritative item lacks verification by a configured reviewer. | Error |
| `KB-E703` | A verification event has no matching body record documenting its review scope. | Error |

## Valid and invalid examples

The repository includes:

- `examples/valid/decision-adopt-stable-identifiers.md`: stable, human-verified
  decision with validity and sources.
- `examples/valid/procedure-review-stale-knowledge.md`: stable procedure with
  freshness and verification.
- `examples/valid/source-summary-okf-v02.md`: transformed, cited source summary.
- `examples/valid/agent-generated-draft.md`: clearly labeled generated draft
  with sources and uncertainty.
- `examples/invalid/missing-provenance.md`: transformed item without sources.
- `examples/invalid/self-supersession.md`: deprecated item that supersedes
  itself.
- `examples/invalid/invalid-timestamp.md`: non-UTC/misordered timestamps.

Invalid examples are expected to fail and must remain excluded from normal
bundle validation or be tagged as negative fixtures by the test runner.
Templates are also excluded because their placeholders are intentionally not
valid instances.

## Testing strategy

### Unit-level parser/schema tests

- valid/invalid YAML delimiters and duplicate keys;
- YAML implicit dates, quoted/unquoted timestamps, Unicode, and unsafe tags;
- every field boundary, enum, pattern, and conditional requirement;
- bare `verified` mapping import normalization versus canonical list authoring;
- unknown field preservation on import and rejection at profile promotion;
- actor, UUID, tag, URI/path, and timestamp edge cases.

### Corpus-level tests

- duplicate IDs across directories;
- moves that preserve IDs and update links;
- broken links at draft versus stable severity;
- missing/duplicate source IDs and footnote joins;
- reciprocal, branching, merging, and cyclic supersession graphs;
- indexes/logs with missing, duplicate, stale, or out-of-order entries;
- orphan and duplicate candidates;
- stale and future-effective items under a fixed `as_of` date.

### Transition tests

Given base and proposed trees:

- every allowed/disallowed state transition;
- immutable ID/creation time changes;
- material update that improperly retains verification;
- pure rename/formatting that should not require semantic re-verification;
- atomic supersession where only one side changes;
- agent draft promotion with and without human verification.

### Golden test corpus

The Phase 4 tests maintain focused positive/negative mutations and bundles for:

1. minimal valid draft;
2. stable informational concept;
3. stable authoritative decision/procedure/policy;
4. imported and transformed source material;
5. agent-generated candidate and approved generated item;
6. calculated item without formal attestation;
7. stale but not false content;
8. future-effective content;
9. conflicting current sources;
10. valid split/consolidated supersession;
11. archive and abandoned-draft exception;
12. every validation error class.

Golden outputs include sorted finding codes, paths, severities, and messages.
Use a fixed date and normalized paths so tests are deterministic.

### Property/invariant tests

- moving a valid item while updating all paths preserves validity and ID;
- reordering YAML mappings/lists where semantics are unordered does not change
  findings;
- adding an unrelated valid item does not change findings for existing items;
- a supersession graph accepted by the validator is acyclic and reciprocal;
- validation never mutates input files;
- parsing/serializing an imported OKF item preserves unknown fields.

### Review of heuristic rules

Duplicate/conflict/body-consistency detection cannot be a release-blocking
truth oracle. Measure precision on a labeled corpus, show supporting excerpts,
and require human decisions. Semantic similarity must never establish
authority, equivalence, or supersession.

## Governance of validation rules

- Version the profile and rule catalog.
- Every rule change includes positive/negative fixtures and migration notes.
- Do not change severity silently.
- Suppressions, if later allowed, are explicit, scoped, owned, reasoned, and
  expire; they cannot suppress baseline YAML/type failures or ID collisions.
- Pin YAML/Markdown parser behavior and the OKF target.
- Treat validator fixes as normal reviewed changes; validation itself never
  approves content.
