---
type: question
id: urn:uuid:fe68dca6-0ad4-4769-9042-005e89d202b7
title: Which people may verify authoritative knowledge
description: Deployment owners must map real durable human identifiers to authoritative review responsibilities.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:34:46Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:34:46Z"
  method: agent-generated
sources:
  - id: governance-decision
    resource: urn:core-kb:profile-decisions:verification
confidence:
  level: high
  basis: The technical rule is resolved, while the deployment-specific people cannot be inferred by an agent.
tags:
  - governance
  - verification
sensitivity: internal
---

# Which people may verify authoritative knowledge

## Question

Which real people and durable opaque identifiers should populate each
authoritative type's reviewer allowlist?[^governance-decision]

## Why it matters

The validator can confirm that a verification event uses an allowed identifier,
but it cannot invent the organization or prove that a role assignment exists.

## Known facts

- Actor IDs must identify people rather than roles or agents.
- Empty allowlists safely prevent authoritative promotion.
- Repository governance must bind identifiers to actual control.

## Competing hypotheses

- Use existing internal directory IDs.
- Issue knowledge-governance-specific opaque IDs.

## Resolution criteria

Privacy, offboarding, audit, and knowledge owners approve a durable mapping and
populate the configuration themselves.

## Outcome

Unassigned. No human verification event is fabricated in this bundle.

[^governance-decision]: The profile decisions require configured real-human reviewer identities.
