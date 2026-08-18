---
type: procedure
id: urn:uuid:b789bfab-271e-462d-bf06-ae61af138dee
title: Move a knowledge item
description: Move a concept without changing its identity while updating paths and navigation atomically.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:47:33Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:47:33Z"
  method: agent-generated
sources:
  - id: workflow-design
    resource: urn:core-kb:design:workflow:move
confidence:
  level: high
  basis: The workflow and identity invariants define all required parts of an atomic move.
tags:
  - identity
  - maintenance
related:
  - urn:uuid:aa555295-27ee-438d-9e1f-e4d4ba2feed0
sensitivity: internal
---

# Move a knowledge item

## Purpose

Change a readable path without changing knowledge identity or leaving broken
navigation.[^workflow-design]

## Preconditions

- The destination is inside the bundle and is not reserved.
- No concept already occupies the destination.
- Inbound links and directory indexes have been inventoried.
- The [immutable identity rule](../curated/concepts/immutable-knowledge-identity.md)
  remains applicable to the move.

## Steps

1. Preserve `id`, `type`, `created_at`, production metadata, and verification.
2. Move the file to a lowercase kebab-case path.
3. Update inbound and outbound Markdown paths.
4. Regenerate affected directory indexes.
5. Record a notable move in the scoped log when useful.
6. Run base-versus-proposed validation.

## Verification

Confirm that the identity exists exactly once, all links resolve, and the diff
contains no unintended material content change.

## Rollback

Reverse the move and link edits in one Git revert.

## Escalation

Request review when the move also changes scope, sensitivity, or meaning.

## Safety

Never copy and delete as separate published changes; partial moves break path
identity and navigation.

[^workflow-design]: The update workflow and lifecycle invariants define safe file moves.
