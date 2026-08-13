# Author and reviewer handbook

## Authoring

1. Confirm that the subject belongs in the `knowledge/` bundle and contains no
   secret or incorrectly scoped personal data.
2. Start from the matching template and generate one new lowercase UUID v4 URN.
3. Keep the item `draft`. Record the real producer and production method.
4. Add sources for imported, transformed, calculated, summarized, and
   agent-generated content. Cite consequential claims with matching footnotes.
5. Use a readable lowercase kebab-case filename and normal Markdown links.
6. Run `portable_kb.validate_bundle()` with an explicit review date. The core
   intentionally provides a library API; a CLI is deferred.
7. Submit a focused Git change using the pull-request checklist.

## Review

Reviewers inspect meaning before metadata. Confirm scope, claims, sources,
applicability, sensitivity, lifecycle, and whether the producer label is
honest. A clean validator result is necessary but not approval.

When verification is required, review the final snapshot and add your own
configured `human:` identifier. If review causes a correction, update the
snapshot first and verify the corrected version at the same time or later.
The reviewed body must also contain the exact marker emitted by the review
workflow: `<!-- core-kb-verification: human:<id> at <timestamp> -->`. Prose
immediately around that marker describes what was checked. The marker is an
auditable assertion, not cryptographic proof.

## Updating

Preserve `id` and `created_at`. A material change updates `updated_at` and
`generated`, removes prior verification, and returns authoritative content to
draft until it is reviewed. A spelling-only edit or a move need not reset
verification, but all affected paths and indexes change together.

Lowering `sensitivity` requires a human actor and the lifecycle API's explicit
approval flag. The flag records intent in the call; repository governance still
determines whether that person had authority.

## Superseding and archiving

Use supersession when a new identity replaces a historically meaningful item.
The replacement is stable, predecessors are deprecated, both sides contain
reciprocal IDs and readable links, and indexes/logs change atomically.

Archive only deprecated items or explicitly abandoned draft questions. Git
archive is retention, not erasure or access control.

## Review outcomes

- Approve: all gates pass and any required verification was actually recorded.
- Request changes: evidence, scope, body, metadata, or link behavior is wrong.
- Keep draft: authority or evidence is not yet available.
- Deprecate/archive: the candidate is abandoned or no longer current.
- Create a question: legitimate scopes or sources conflict.
