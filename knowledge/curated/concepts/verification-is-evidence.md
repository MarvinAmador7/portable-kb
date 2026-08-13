---
type: concept
id: urn:uuid:3052cfa1-4270-45e1-8399-90ba1a02fe86
title: Verification is evidence
description: Verification records a scoped check of one snapshot rather than declaring permanent truth.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:52:16Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:52:16Z"
  method: agent-generated
sources:
  - id: lifecycle-design
    resource: urn:core-kb:design:lifecycle:verification
confidence:
  level: high
  basis: The local lifecycle model distinguishes verification events from authority, confidence, and permanent truth.
tags:
  - governance
  - verification
related:
  - urn:uuid:31f5f4b3-0f8e-405a-a097-3e818ef67c99
sensitivity: internal
---

# Verification is evidence

## Definition

A verification event records that an identified actor checked the current
snapshot at a stated time.[^lifecycle-design] It does not make the content true
forever or prove that the actor was authorized.

## Context

Human review, producer confidence, source authority, freshness, and lifecycle
status answer different questions. Keeping them separate prevents metadata from
laundering an attractive draft into organizational authority. The
[pinned-format decision](../../decisions/pin-okf-v02.md) keeps the upstream
meaning of those signals reviewable.

## Examples

A process can confirm schema structure. A configured human may verify a
procedure against a test execution. Those events communicate different trust
signals.

## Boundaries

A material change creates a new snapshot and invalidates prior verification.

[^lifecycle-design]: The local lifecycle design specifies snapshot-scoped verification.
