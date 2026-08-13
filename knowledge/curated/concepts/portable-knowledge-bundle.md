---
type: concept
id: urn:uuid:17c36cb0-9c37-4122-8240-ee02d31e696d
title: Portable knowledge bundle
description: A portable knowledge bundle keeps canonical knowledge in readable files independent of its consumers.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:52:16Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:52:16Z"
  method: agent-generated
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/374e0bc4c644310ff56cdf9c0fe81eccdec862b0/okf/SPEC.md
    title: Open Knowledge Format v0.2 specification at the pinned commit
confidence:
  level: high
  basis: The bundle boundary and file representation are directly defined by the pinned upstream specification.
tags:
  - architecture
  - portability
related:
  - urn:uuid:7d657931-1613-4ff9-945b-5048617d7659
sensitivity: internal
---

# Portable knowledge bundle

## Definition

A portable knowledge bundle is a directory tree of Markdown concepts with YAML
frontmatter, readable links, reserved indexes and logs, and no required hosted
service.[^okf-spec]

## Context

The bundle under `knowledge/` is canonical. Validation and lifecycle code
govern it, while [consumer capabilities](../../decisions/separate-core-from-consumers.md)
can be replaced without changing the knowledge format. Every
[material bundle change](material-change.md) still follows snapshot governance.

## Examples

This repository's `knowledge/` directory is both a working bundle and the first
representative corpus for the profile.

## Boundaries

Portability does not provide access control, semantic search, or proof that a
claim is correct.

[^okf-spec]: OKF v0.2 sections 2 through 4 define bundles and concept documents.
