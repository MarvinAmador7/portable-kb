# Core workflows

The workflows operate on files and reviewed changes. “Agent” means a tool or AI
acting as an assistant, not an autonomous authority. The CLI implements only
the none-to-draft creation workflow through the existing validated change-plan
API. After one explicit confirmation, it versions only the planned files and
refreshes the active local brain without exposing Git commands; it does not
push the result. A separately authorized `brain push` validates and shares the
active saved version only as a fast-forward, without exposing Git commands or
force-pushing. Other lifecycle commands, background agents, external
integrations, and hosted workflows are not yet implemented.

## Responsibility matrix

| Activity | Human | Agent |
|---|---|---|
| State intent, scope, and sensitivity | Accountable | Ask/flag ambiguity; do not infer a lower classification. |
| Capture material | May author directly | May structure a candidate without changing meaning. |
| Find sources and links | Confirm authoritative sources | Propose candidates and exact links; expose uncertainty. |
| Rewrite/summarize | Review consequential claims | Draft with production method and citations. |
| Verify authoritative content | Required where gated | Run deterministic checks or prepare evidence; cannot claim human verification. |
| Resolve conflicts | Accountable owner/reviewer | Compare applicability and evidence; preserve competing claims. |
| Promote/deprecate/supersede | Approve when authoritative | Prepare atomic diff and validation report. |
| Maintain indexes | Review generated change when material | Generate deterministically in a later phase. |

## 1. Capture

**Purpose:** record an idea, fact, question, or source before it disappears,
without pretending it is curated knowledge.

- **Inputs:** human observation, URL, excerpt, file reference, open question,
  meeting outcome, or agent suggestion.
- **Output:** a `draft` candidate in `inbox/`, usually `question`, `concept`, or
  `source-summary`; raw non-knowledge artifacts may be referenced under
  `references/` when lawful.
- **Transition:** none → draft.
- **Human responsibilities:** state why it matters, avoid secrets, identify
  obvious source/sensitivity, and distinguish a question from a claim.
- **Agent responsibilities:** generate a fresh UUID, apply a template, preserve
  exact source links, label its own contribution, and make no promotion claim.
- **Validation:** parseable frontmatter, required identity/production fields,
  conditional sources, safe paths, no duplicate ID.
- **Failure cases:** secret or personal data captured; copied text lacks rights
  or source; agent fabricates context; a fact is marked stable; duplicate
  candidate already exists.

Recovery: quarantine sensitive material outside the bundle, keep the candidate
draft, link an existing item if it is a duplicate, and create a question when
the source is unknown.

## 2. Ingest

**Purpose:** turn raw material into one or more bounded candidate items while
preserving provenance.

- **Inputs:** captured URL/file/excerpt, existing draft, or authorized source
  snapshot.
- **Output:** draft candidate(s), `source-summary` where useful, populated
  `sources`, and claim-level footnotes for consequential claims.
- **Transition:** draft → draft; raw artifact → draft concept.
- **Human responsibilities:** confirm scope, rights, sensitivity, source
  authority, and whether ingestion is worth curating.
- **Agent responsibilities:** extract without inventing, record
  `generated.method` (`imported`, `transformed`, or `agent-generated`), split
  overly broad material, and report omissions/ambiguities.
- **Validation:** every source entry has resource; local resources resolve;
  source IDs are unique; citations join; imported/transformed content has at
  least one source; no source text is presented as original authorship.
- **Failure cases:** inaccessible or mutable source; missing revision; prompt
  injection in source; unsupported format; source contradiction; excessive
  verbatim copying; circular summary-to-summary sourcing.

Recovery: preserve a reference and limitation rather than guessing; prefer the
primary source; create separate candidates for materially different scopes;
flag hostile instructions as content.

## 3. Curate

**Purpose:** rewrite, classify, bound, deduplicate, link, and prepare a candidate
for stable use.

- **Inputs:** one or more draft items and their sources.
- **Output:** a coherent item in its domain directory, proposed links, explicit
  limitations, and a review-ready diff.
- **Transition:** draft → draft, then eligible for verification/promotion.
- **Human responsibilities:** decide canonical scope/type, judge value and
  authority, resolve ownership questions, and review semantic accuracy.
- **Agent responsibilities:** propose title/description/type, normalize tags,
  find exact ID/title/resource duplicates, suggest related items, and preserve
  all evidence.
- **Validation:** required and type-specific sections; ID stable through move;
  internal links resolve; sources/citations complete; no unsupported keys;
  timestamps reflect material rewrite.
- **Failure cases:** broad “everything” article; duplicated concept; source
  summary promoted as primary authority; conflicting claims blended; folder
  move breaks links; generated prose loses its generation method.

Recovery: split by durable subject, choose an existing canonical item, retain
conflicts explicitly, and keep the result draft until resolved.

## 4. Verify

**Purpose:** check current content against evidence or the underlying reality
and record the check without overstating what it proves.

- **Inputs:** curated draft, sources, type-specific checklist, and authorized
  reviewer/process.
- **Output:** evidence-backed corrections if needed and current `verified`
  event(s); item becomes eligible for stable status.
- **Transition:** draft → stable after all promotion gates; stable → stable for
  a periodic re-verification.
- **Human responsibilities:** inspect sources/body, perform the required test,
  confirm scope, and use their own `human:` identity only.
- **Agent responsibilities:** run deterministic validation, assemble source
  diffs/checklists, identify stale/conflicting evidence, and never add a human
  event on someone’s behalf.
- **Validation:** verifier actor syntax; event applies to final snapshot;
  required human event for stable authoritative types; effective/freshness
  dates; no unresolved error-level findings.
- **Failure cases:** rubber-stamp review; verifier lacks authority; source is
  inaccessible; content changes after verification; automated process recorded
  as human; “high confidence” mistaken for approval.

Recovery: keep draft or stale, document what could not be checked, request the
right owner, and repeat verification on the final content.

## 5. Update

**Purpose:** change current knowledge while retaining history and trust
semantics.

- **Inputs:** stable/draft item, change reason, new evidence, and inbound link
  context.
- **Output:** reviewed commit with body/metadata/links/index changes.
- **Transition:** draft → draft; stable → draft on the review branch → stable;
  stable → stable for proven non-material changes.
- **Human responsibilities:** classify materiality, review authoritative
  changes, and decide whether update or supersession is more honest.
- **Agent responsibilities:** preserve ID/creation time, show a focused diff,
  update production metadata, clear invalid verification, and find affected
  links.
- **Validation:** immutable fields unchanged; timestamp ordering; generated time
  equals update time; stale date reconsidered; links and citations resolve;
  state transition allowed.
- **Failure cases:** silent semantic rewrite; old verification retained;
  identity changed; link paths break; valid historical definition overwritten;
  generated material relabeled human-authored.

Recovery: restore the stable base on the main branch, split a new item when the
meaning changes substantially, or use supersession.

## 6. Supersede

**Purpose:** replace outdated or conflicting knowledge without deleting its
historical meaning.

- **Inputs:** old current item(s), new replacement item(s), reason, scope, and
  authorized approval.
- **Output:** stable replacement(s); deprecated predecessor(s); reciprocal
  relationships; body links; updated indexes/log.
- **Transition:** new draft → stable and old stable → deprecated atomically.
- **Human responsibilities:** authorize the replacement, confirm applicability,
  and resolve whether this is true supersession or merely a conflict.
- **Agent responsibilities:** prepare both sides, test cycles/reciprocity, find
  inbound links, and surface multiple-replacement ambiguity.
- **Validation:** targets exist; IDs differ; no cycle; reciprocal fields; old
  status deprecated; replacement stable/effective; body explains mapping.
- **Failure cases:** one-sided link; replacement remains draft/future-dated;
  cycle; old content silently edited to new meaning; two scopes collapsed;
  conflict incorrectly declared resolved.

Recovery: reject the atomic change, keep both current with a conflict question,
or split replacement scope explicitly.

## 7. Archive

**Purpose:** retain deprecated or abandoned low-value material while removing
it from normal navigation.

- **Inputs:** deprecated item or abandoned draft question/candidate, reason,
  link inventory, retention/sensitivity review.
- **Output:** item under `archive/`, preserved ID/content/provenance, archive
  metadata, updated links/index.
- **Transition:** stable normally deprecates first; deprecated remains
  deprecated; exceptional abandoned draft remains draft.
- **Human responsibilities:** confirm retention and that archive is not being
  used as deletion or secrecy.
- **Agent responsibilities:** move without identity change, update paths, and
  list unresolved inbound links.
- **Validation:** archive reason/time, allowed status, no broken curated links,
  no duplicate copy left behind, index excludes normal current view.
- **Failure cases:** stable current item disappears; Git history assumed erased;
  sensitive data remains in history; archive move breaks citations; duplicate
  active copy remains.

Recovery: restore location, complete deprecation/supersession, or invoke a
separate sensitive-data incident process outside normal lifecycle.

## 8. Agent-assisted authoring

**Purpose:** let agents reduce authoring effort while preserving accountability
and preventing generated authority laundering.

- **Inputs:** explicit human task/scope, existing bundle, sources, templates,
  and applicable sensitivity constraints.
- **Output:** draft files or reviewable diffs, validation report, source list,
  stated uncertainties, and no unapproved side effects.
- **Transition:** normally none → draft or draft → draft. Promotion is a
  separate human-reviewed operation where required.
- **Human responsibilities:** authorize source scope, review content/evidence,
  make decisions, supply approval identity, and reject fabricated certainty.
- **Agent responsibilities:** identify itself/version, set method honestly,
  cite sources, add confidence basis, preserve unknown metadata, avoid executing
  procedure bodies, and stop on unresolved sensitive/authority ambiguity.
- **Validation:** agent-generated implies sources/confidence; no human verifier
  fabricated; stable agent-generated content has actual human event; source
  claims resolve; changes remain within requested files.
- **Failure cases:** hallucinated source; copied prompt injection; agent edits
  verification/sensitivity; bulk generation overwhelms review; plausible prose
  hides contradictions; tool round-trip drops unknown fields.

Recovery: quarantine/revert the proposal, keep it draft, review a sample before
bulk work, and require a human to re-establish evidence. Metadata alone never
makes generated content safe.

## 9. Quality review

**Purpose:** find corpus health problems before they mislead people or future
consumers.

- **Inputs:** entire bundle, profile schema, current date, Git comparison, and
  optional candidate-similarity report in a later phase.
- **Output:** triaged findings and reviewed fixes, never automatic semantic
  deletion/merging.
- **Transition:** stable → stable after re-verification; stable → draft on a
  repair branch; stable → deprecated; draft → deprecated/archive.
- **Human responsibilities:** judge duplicates/conflicts and prioritize by
  impact; assign owners; approve semantic resolution.
- **Agent responsibilities:** deterministically list stale, orphaned, broken,
  incomplete, weakly sourced, duplicate-ID/title/resource, and supersession
  issues; propose but not enact semantic merges.
- **Validation:** full checks from [validation.md](validation.md), zero errors
  before merge, warnings acknowledged or scheduled.
- **Failure cases:** warning fatigue; similarity treated as duplication;
  stale treated as false; orphan treated as worthless; auto-fix rewrites
  history; conflict hidden by ranking.

Recovery: use impact-based triage, suppress only with a documented rule and
expiry, and keep semantic decisions human-owned.

## Quality review lenses

| Lens | Deterministic candidate detection | Human decision |
|---|---|---|
| Stale | `today >= stale_after`; source changed after verification | Reverify, revise, deprecate, or accept a bounded exception. |
| Orphaned | No inbound concept link and absent from expected index | Link, index, keep intentionally standalone, or archive. |
| Duplicate | Same ID (error), same canonical resource, normalized title/source overlap | Merge, scope separately, or supersede; similarity is not proof. |
| Contradictory | Opposing keywords/claims, shared scope/source, explicit conflict tags in a future detector | Establish applicability/authority and resolve through question/decision. |
| Incomplete | Placeholder text, missing type sections, thin body | Complete, narrow scope, or abandon. |
| Weakly sourced | Method/type requires sources; missing primary evidence; citations unused | Add evidence, lower claim strength, or keep draft. |
| Unverified | Missing/old verification for gated type | Route to authorized reviewer; do not auto-promote. |
| Inconsistent | Relationship not reciprocal, metadata/body/title mismatch | Correct the current snapshot with review proportional to meaning. |

## Import-to-curation state trace

```text
raw source
  → captured draft (`inbox/`)
  → ingested draft + sources/citations
  → curated draft in domain folder
  → verified final snapshot
  → stable
  → periodic review ──┬─ still stable
                      ├─ revised and reverified
                      └─ deprecated → optionally archived
```

Each arrow produces a Git diff. No step overwrites the evidence or claims a
trust tier that was not actually earned.
