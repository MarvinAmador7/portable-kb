---
type: concept
id: urn:uuid:aa555295-27ee-438d-9e1f-e4d4ba2feed0
title: Immutable knowledge identity
description: A knowledge item's UUID remains constant while its readable path may change.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:34:46Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:34:46Z"
  method: agent-generated
sources:
  - id: identity-design
    resource: urn:core-kb:design:schema:identity
confidence:
  level: high
  basis: The local profile schema directly requires UUID v4 URNs and the transition validator enforces immutability.
tags:
  - identity
  - portability
related:
  - urn:uuid:b789bfab-271e-462d-bf06-ae61af138dee
sensitivity: internal
---

# Immutable knowledge identity

## Definition

Every profile item receives one lowercase UUID v4 URN that survives moves,
renames, lifecycle transitions, and archive operations.[^identity-design]

## Context

Baseline OKF path identity remains readable and interoperable. The UUID is a
compatible local extension used by typed relationships and transition checks.
The [move procedure](../../procedures/move-knowledge-item.md) changes paths but
never IDs.

## Examples

Moving `procedures/review.md` to `procedures/quality/review.md` updates links
and indexes while retaining the same `id`.

## Boundaries

Titles and filenames can collide or change. Neither is immutable identity.

[^identity-design]: The `core-kb/0.1` schema defines identity and UUID invariants.
