---
type: question
id: urn:uuid:5b4de1b3-1d34-4c58-a3c3-5a9aae251b60
title: When should policy and system types become active
description: Policy and system remain inactive until real content and accountable reviewers justify promotion gates.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:34:46Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:34:46Z"
  method: agent-generated
sources:
  - id: roadmap-gate
    resource: urn:core-kb:roadmap:type-activation
confidence:
  level: high
  basis: The roadmap defines a concrete three-item and distinct-governance threshold for activating a type.
tags:
  - governance
  - taxonomy
sensitivity: internal
---

# When should policy and system types become active

## Question

When do real policy and system content justify activating their authoring and
promotion gates?[^roadmap-gate]

## Why it matters

Schema support alone does not supply legal authority, operational ownership, or
representative examples.

## Known facts

- Both types remain accepted for preserved external imports.
- New promotion is disabled while the types are absent from `active_types`.
- The profile recommends at least three real items needing distinct governance.

## Competing hypotheses

- Activate when the first candidate arrives.
- Activate only after three real candidates and named accountable reviewers.

## Resolution criteria

Use the second threshold: three real items, distinct body/governance needs, and
configured authorized reviewers.

## Outcome

Inactive in the initial bundle configuration.

[^roadmap-gate]: The roadmap requires demonstrated content and governance before taxonomy expansion.
