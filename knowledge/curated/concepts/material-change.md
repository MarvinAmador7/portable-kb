---
type: concept
id: urn:uuid:7d657931-1613-4ff9-945b-5048617d7659
title: Material change
description: A material change alters what a reader may believe or do and therefore invalidates prior verification.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:52:16Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:52:16Z"
  method: agent-generated
sources:
  - id: lifecycle-design
    resource: urn:core-kb:design:lifecycle:material-change
confidence:
  level: high
  basis: The lifecycle model enumerates material fields and the transition validator checks their effects.
tags:
  - lifecycle
  - verification
related:
  - urn:uuid:3052cfa1-4270-45e1-8399-90ba1a02fe86
sensitivity: internal
---

# Material change

## Definition

A material change can alter what a reader believes or does: substantive claims,
steps, requirements, scope, evidence, lifecycle, sensitivity, or authoritative
relationships.[^lifecycle-design]

## Context

Material changes update production metadata and remove verification for the
prior snapshot. Authoritative content returns to draft until the corrected
snapshot is reviewed. This follows the rule that
[verification is snapshot evidence](verification-is-evidence.md).

## Examples

Changing a procedure step is material. Correcting punctuation or moving a file
while repairing every link is normally non-material.

## Boundaries

Mechanical versus material is not always determinable from syntax. When in
doubt, treat the change as material and request review.

[^lifecycle-design]: The local lifecycle design defines material and non-material changes.
