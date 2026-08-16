---
type: question
id: urn:uuid:8b23d72d-232b-4dd4-acf4-9b2d23c99505
title: Where will project design sources be published
description: Project-local design URNs need immutable published resources before external bundle distribution.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:34:46Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:34:46Z"
  method: agent-generated
sources:
  - id: source-inventory
    resource: urn:core-kb:design:source-inventory
confidence:
  level: high
  basis: The current source inventory explicitly marks local design URNs as temporary until a publication location exists.
tags:
  - portability
  - provenance
sensitivity: internal
---

# Where will project design sources be published

## Question

Which immutable public or bundle-contained resources will replace project-local
design URNs before external distribution?[^source-inventory]

## Why it matters

URNs preserve source identity but do not let an external reviewer open the
underlying design evidence.

## Known facts

- The pinned OKF source is independently resolvable.
- Project design documents currently sit outside the bundle boundary.
- Copying those documents into the bundle would turn them into concepts unless
  placed as lawful referenced artifacts.

## Competing hypotheses

- Publish the repository and cite immutable Git blob URLs.
- Mirror approved design artifacts under `knowledge/references/`.

## Resolution criteria

Choose a lawful, immutable, accessible source that survives bundle exchange and
does not create two competing canonical copies.

## Outcome

Pending repository publication policy.

[^source-inventory]: The representative source inventory records temporary project design URNs.
