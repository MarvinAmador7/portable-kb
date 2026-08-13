---
type: decision
id: urn:uuid:f6805eb0-3455-47e0-abcd-0458cd0db229
title: Adopt immutable UUIDs for knowledge items
description: Each knowledge item receives a UUID URN that remains unchanged when its file moves.
status: stable
created_at: "2026-08-06T14:00:00Z"
updated_at: "2026-08-06T15:00:00Z"
generated:
  by: human:architect-1
  at: "2026-08-06T15:00:00Z"
  method: transformed
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format v0.2 specification
verified:
  - by: human:reviewer-1
    at: "2026-08-06T16:00:00Z"
valid_from: "2026-08-06"
tags:
  - identity
  - portability
related:
  - urn:uuid:fc0e3322-bd02-4cfd-8869-07179fd740aa
---

# Adopt immutable UUIDs for knowledge items

## Decision

Assign every profile-authored item a lowercase UUID v4 URN. Preserve it across
renames, moves, lifecycle transitions, and archive operations.

## Context

Baseline OKF identifies a concept by its bundle-relative path without the
`.md` suffix.[^okf-spec] Paths are readable but change when the bundle is
reorganized.

## Options considered

1. Use only OKF path identity.
2. Use a readable organization/slug identifier.
3. Retain OKF path identity and add an immutable UUID extension.

## Rationale

Option 3 preserves baseline OKF navigation and supplies a collision-resistant
identity for typed relationships and future cross-system exchange.

## Consequences

Authors need UUID generation support. Validators must detect collisions and
reject ID changes. Filenames remain readable and ordinary Markdown links still
need maintenance after moves.

## Review triggers

Revisit if OKF standardizes a stable identity independent of path.

## Supersession

This is the first decision for profile identity.

See the [stale-knowledge review procedure](./procedure-review-stale-knowledge.md)
for an example of a relationship that survives path changes through IDs.

[^okf-spec]: Open Knowledge Format v0.2 specification, sections 2 and 6.

## Verification record

The fixture reviewer compared the decision with the cited specification.

<!-- core-kb-verification: human:reviewer-1 at 2026-08-06T16:00:00Z -->
