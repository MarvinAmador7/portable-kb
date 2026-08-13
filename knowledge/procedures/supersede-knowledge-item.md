---
type: procedure
id: urn:uuid:b9b75824-018d-40a3-864b-fdc0943e0b53
title: Supersede a knowledge item
description: Replace historical knowledge using reciprocal relationships and one atomic reviewed change.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:34:46Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:34:46Z"
  method: agent-generated
sources:
  - id: lifecycle-design
    resource: urn:core-kb:design:lifecycle:supersession
confidence:
  level: high
  basis: The lifecycle model specifies reciprocal status, relationship, link, index, and graph invariants.
tags:
  - lifecycle
  - supersession
sensitivity: internal
---

# Supersede a knowledge item

## Purpose

Replace knowledge without erasing the historically meaningful predecessor or
guessing that a conflict is true supersession.[^lifecycle-design]

## Preconditions

- An authorized human has confirmed replacement scope.
- The replacement is reviewed and eligible to become stable.
- Every predecessor and inbound link is known.

## Steps

1. Promote the replacement to stable and add predecessor IDs to `supersedes`.
2. Deprecate each predecessor and add the replacement ID to `superseded_by`.
3. Add readable links and scope explanations on both sides.
4. Update indexes and the bundle log.
5. Validate reciprocity, status, current effectiveness, and graph acyclicity.
6. Apply all files as one reviewed change.

## Verification

Confirm that partial application fails transition validation and that consumers
can locate the replacement from every predecessor.

## Rollback

Revert the complete atomic commit. Do not toggle a deprecated identity through
ordinary editing.

## Escalation

Create a question if both items may remain valid in different scopes.

## Safety

Never infer supersession from title similarity or silently delete the old item.

[^lifecycle-design]: The lifecycle model defines atomic, reciprocal, acyclic supersession.
