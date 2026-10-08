# Lifecycle model

## State model

The profile uses OKF v0.2’s three explicit states:

```text
capture/candidate
      │
      ▼
    draft ───────────────► deprecated
      │                         ▲
      ▼                         │
    stable ─────────────────────┘
```

Archive is not a fourth state. It is a file disposition recorded by path and,
optionally, an `archived` object. Superseded is not a state either: it is a
deprecated item with reciprocal `supersedes` / `superseded_by` relationships.

## State definitions

### `draft`

The item is incomplete, unreviewed, under revision, imported, agent-generated,
or otherwise not ready for normal authoritative consumption.

- May live in `inbox/` or its eventual domain directory.
- May have no verification.
- Must not be treated as approved policy, decision, or procedure.
- Can be indexed later, but future consumers should exclude it from default
  authoritative results.

### `stable`

The current content is ready for ordinary use within its stated scope.

- Required fields and type-specific promotion gates are satisfied.
- “Stable” does not imply true forever, publicly accessible, or human-reviewed
  unless the type rules require a human verification.
- Future consumers should still consider validity dates, staleness,
  sensitivity, source quality, and conflicts.

### `deprecated`

The item is retained for history and link integrity but should not guide new
work.

- The body explains why and, where applicable, links to replacements.
- The item may remain in place for link stability or move to `archive/`.
- It is excluded from default current-knowledge views.
- Deprecation is terminal in the first profile. A mistaken deprecation is fixed
  through a reviewed corrective commit; ordinary workflow creates a new item
  rather than toggling historical authority.

## Allowed transitions

| From | To | Allowed? | Gate |
|---|---|---|---|
| none | `draft` | Yes | Minimal profile valid; source rules satisfied. |
| none | `stable` | Discouraged; only controlled migrations | All stable gates and explicit reviewer approval. Normal authoring starts draft. |
| `draft` | `stable` | Yes | Curation complete, validation clean, required human verification present, effective/freshness dates set. |
| `draft` | `deprecated` | Yes | Candidate abandoned or duplicate; reason documented. Usually archive it. |
| `stable` | `draft` | Yes, on a review branch | A material revision invalidates current verification. The default branch remains stable until the reviewed change merges. |
| `stable` | `stable` | Yes | Non-authoritative material change reviewed as required; timestamps/producer updated; verification refreshed if invalidated. |
| `stable` | `deprecated` | Yes | Human approval for authoritative items; reason and replacement/conflict links complete. |
| `deprecated` | `stable` | No normal transition | Create or restore through an exceptional corrective review with explicit audit note. |
| `deprecated` | `draft` | No | Create a new item with a new ID if knowledge must be reintroduced. |

The validator compares the proposed file to the merge-base/current default
branch in Phase 3. Phase 2 can validate only the resulting state and internal
conditions.

## Material versus non-material change

A material change can alter what a reader believes or does. It includes:

- substantive body claims, steps, requirements, scope, exceptions, formula,
  or consequences;
- source additions/removals that change evidence;
- type, status, validity, freshness, sensitivity, or supersession;
- producer method or identity; or
- changing a link whose target supplies authority or operational context.

Material changes update `updated_at` and `generated`, and invalidate current
`verified` events unless the verification occurs after the change as part of
the same reviewed transition.

Non-material changes include a pure file move with links updated, spelling or
formatting that does not change meaning, and generated index maintenance.
They need Git history but need not change item timestamps or verification. When
in doubt, treat a change as material and ask a reviewer.

## Verification model

Verification means an identified actor checked the current item against its
sources, underlying system, or governing authority at a time. It is not a
truth seal.

The body or review record should state the verification scope, for example:

- sources opened and claims compared;
- procedure executed safely in a named non-production environment;
- policy text approved by the governing role;
- system boundaries confirmed against configuration; or
- calculation inputs/formula independently reproduced.

Rules:

1. `verified` events apply only to the current material content.
2. A human event uses `human:<id>`; a process cannot impersonate a human.
3. Machine verification may establish `machine-confirmed`, not human review.
4. A verification that covers the current content cannot predate the item’s
   `updated_at`/`generated.at`. If review causes corrections, update the
   production time to the corrected revision and verify that revision at the
   same time or later.
5. The first profile requires a human event for stable decisions, procedures,
   and policies and for stable agent-generated content.
6. An authorized reviewer is an organizational rule outside the file schema.

The committed file therefore represents generation followed by confirmation.
Examples may use equal timestamps for a single review-integrated commit, while
separate verification events naturally occur later as OKF permits.

## Validity and freshness

`valid_from` answers “when does this apply?” `stale_after` answers “when must it
be reviewed?” They are independent.

At a date `D`:

- not-yet-effective when `valid_from > D`;
- current freshness window when no stale date is required/present or
  `D < stale_after`;
- stale when `D >= stale_after`;
- deprecated whenever `status: deprecated`, regardless of dates.

Stale knowledge is preserved and flagged. It does not automatically transition
to deprecated and it must not be silently deleted. High-impact consumers
should refuse unattended use of stale policies/procedures; informational views
may show them with a warning.

Review outcomes:

- still correct: update the final generation/update time, add current
  verification, and choose a new `stale_after`;
- materially changed: revise on a branch, clear prior verification, then
  re-promote;
- no longer current: deprecate or supersede;
- cannot verify: keep stable but stale only if governance permits, otherwise
  move through a reviewed deprecation; always expose the unresolved condition.

## Supersession

Supersession preserves historical knowledge and makes the current replacement
discoverable.

Atomic change requirements:

1. Replacement item is created or promoted to `stable`.
2. Replacement lists old IDs in `supersedes`.
3. Old items change to `deprecated` and list replacement IDs in
   `superseded_by`.
4. Each body explains scope and links to the other file(s).
5. All links resolve, relationships are reciprocal, and the directed graph is
   acyclic.
6. Index and log changes occur in the same review.

Multiple replacements are allowed only when the old scope splits. Multiple
predecessors are allowed when knowledge consolidates. Prose must explain which
replacement applies; consumers must not simply choose the first ID.

Conflicting items are not automatically supersession. If both claims might be
applicable, create a `question` and state the scopes until an authorized
decision resolves them.

## Archive

Archive removes low-value/deprecated material from normal navigation while
retaining it.

- Normally set `status: deprecated`, add `archived.at/reason`, and move under
  `archive/` in one commit.
- Preserve `id`, `created_at`, provenance, and body.
- Update inbound Markdown links and wikilinks through the reviewed move planner,
  or deliberately leave a documented
  redirect concept if link stability requires it. The first milestone prefers
  updating links.
- An abandoned draft question/candidate may archive without becoming stable;
  it remains `draft` and must have an explicit abandonment reason.
- Do not archive solely because an item is old. Archive based on current value,
  lifecycle, and review outcome.
- Do not use archive for sensitive-data erasure. Git history remains.

## Lifecycle invariants

- IDs never change, even through moves, promotion, deprecation, or archive.
- The current file never claims verification that predates a later material
  change.
- A deprecated item cannot supersede a stable item as the current answer.
- Supersession is reciprocal and acyclic.
- Staleness never silently changes status.
- Confidence never changes status automatically.
- Agent generation never implies human verification.
- Git preserves prior states; current frontmatter describes only current
  content.
