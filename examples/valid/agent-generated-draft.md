---
type: question
id: urn:uuid:d81e4806-8702-4805-b1bb-baba8e910bda
title: Which actor identifiers should the bundle use
description: The bundle needs durable human, process, and agent actor identifiers before the profile is finalized.
status: draft
created_at: "2026-08-06T14:30:00Z"
updated_at: "2026-08-06T15:30:00Z"
generated:
  by: research-agent/model-1
  at: "2026-08-06T15:30:00Z"
  method: agent-generated
sources:
  - id: okf-actors
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format v0.2 actor convention
confidence:
  level: medium
  basis: The required prefixes are specified, but the organization-specific identity and privacy policy is unresolved.
tags:
  - actors
  - open-question
---

# Which actor identifiers should the bundle use

## Question

Which durable, non-secret identifier should appear after `human:` and
`process:`, and which producer/version string should identify agents?

## Why it matters

OKF consumers use the `human:` prefix when deriving a human-reviewed trust
tier.[^okf-actors] The identifier also appears in portable files and Git
history, so privacy and durability matter.

## Known facts

- Human, process, and producer/version actor classes have defined prefix
  conventions.[^okf-actors]
- Metadata cannot prove that the claimed actor performed the action.

## Competing hypotheses

- Use organization email addresses for readability.
- Use stable directory IDs to reduce rename drift.
- Use opaque knowledge-governance IDs to minimize personal data.

## Resolution criteria

Identity, privacy, audit, portability, and offboarding owners must approve one
mapping and its retention behavior.

## Outcome

Unresolved. This agent-authored item must remain draft until a human decision is
recorded.

[^okf-actors]: Open Knowledge Format v0.2 specification, actor convention.
