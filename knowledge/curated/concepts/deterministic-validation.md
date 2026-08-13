---
type: concept
id: urn:uuid:eff7f704-a5a9-4086-9ffb-824556ef2142
title: Deterministic validation
description: Deterministic validation reports the same ordered governance findings for the same bundle, schema, date, and base.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:34:46Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:34:46Z"
  method: agent-generated
sources:
  - id: validation-design
    resource: urn:core-kb:design:validation
confidence:
  level: high
  basis: The implemented validator fixes discovery and finding order and receives freshness time as an explicit input.
tags:
  - governance
  - validation
sensitivity: internal
---

# Deterministic validation

## Definition

Deterministic validation produces the same findings in the same order when the
bundle, profile schema, explicit review date, and optional Git base are the
same.[^validation-design]

## Context

The validator separates permissive OKF conformance from stricter profile
governance and never mutates input. Network checks and semantic truth judgments
are outside the deterministic gate.

## Examples

Duplicate UUIDs and supersession cycles are errors. Staleness is a dated
warning. Similar titles are candidates for human review, not proof of identity.

## Boundaries

Passing validation proves structural consistency, not correctness or approval.

[^validation-design]: The local validation catalog defines stable rule codes and deterministic ordering.
