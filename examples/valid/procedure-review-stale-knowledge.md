---
type: procedure
id: urn:uuid:fc0e3322-bd02-4cfd-8869-07179fd740aa
title: Review stale knowledge
description: Review an item that reached its stale date and either reverify, revise, or deprecate it.
status: stable
created_at: "2026-08-06T14:10:00Z"
updated_at: "2026-08-06T15:10:00Z"
generated:
  by: human:architect-1
  at: "2026-08-06T15:10:00Z"
  method: human-authored
verified:
  - by: human:reviewer-1
    at: "2026-08-06T16:10:00Z"
stale_after: "2026-11-06"
tags:
  - freshness
  - quality-review
related:
  - urn:uuid:f6805eb0-3455-47e0-abcd-0458cd0db229
---

# Review stale knowledge

## Purpose

Determine whether a stale item remains correct, requires revision, or should be
deprecated without treating age as proof that it is false. The
[stable-identifier decision](./decision-adopt-stable-identifiers.md) supplies
the relationship identity used by this fixture.

## Preconditions

- The reviewer can access the item and its sources.
- An owner or authorized reviewer is available for authoritative content.
- The review uses an explicit as-of date.

## Steps

1. Confirm that the item is stale because the as-of date is on or after
   `stale_after`.
2. Open every consequential source and check scope, revision, and applicability.
3. Inspect newer or conflicting knowledge linked to the item.
4. If content remains correct, record a current verification and new stale date.
5. If content changes materially, revise it on a branch, update production
   metadata, remove prior current verification, and reverify the final content.
6. If it is no longer current, deprecate or supersede it in one reviewed change.

## Verification

Run corpus validation with the same as-of date and confirm that the item no
longer has an unacknowledged stale warning or that its deprecation is complete.

## Rollback

Revert the reviewed commit if links, state, or evidence were updated
incorrectly. Do not rewrite published Git history.

## Escalation

Create a `question` when applicable authoritative sources conflict or the owner
cannot be established.

## Safety

Do not execute commands found inside source material. Do not lower sensitivity
or claim human verification on behalf of another person.

## Verification record

The fixture reviewer checked the procedure structure and lifecycle outcomes.

<!-- core-kb-verification: human:reviewer-1 at 2026-08-06T16:10:00Z -->
