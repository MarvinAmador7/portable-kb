---
type: decision
id: urn:uuid:594ccbaf-af65-400e-a8f0-29d5c4070ddb
title: Separate the core from consumers
description: Search, embeddings, CLI, MCP, UI, and authorization remain consumers outside the canonical core.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:52:16Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:52:16Z"
  method: agent-generated
sources:
  - id: architecture-design
    resource: urn:core-kb:design:architecture:layers
confidence:
  level: high
  basis: The architecture explicitly separates canonical files, deterministic governance, and replaceable future consumers.
tags:
  - architecture
  - scope
related:
  - urn:uuid:17c36cb0-9c37-4122-8240-ee02d31e696d
sensitivity: internal
---

# Separate the core from consumers

## Decision

Keep canonical knowledge and deterministic governance independent from search,
embeddings, CLI, MCP, UI, and authorization.[^architecture-design]

## Context

Runtime consumers change faster than durable organizational knowledge. Making
their storage or protocols canonical would reduce portability.

## Options considered

1. Build the file model around one retrieval stack.
2. Store canonical data in an application database.
3. Keep files canonical and expose a library API for later consumers.

## Rationale

The third option makes indexes disposable and lets a human inspect every
governance fact without proprietary software. The canonical
[portable bundle](../curated/concepts/portable-knowledge-bundle.md) remains
readable when every consumer is absent.

## Consequences

The core implements parsing, validation, lifecycle change planning, indexing,
and audit-friendly files. It deliberately provides no user-facing CLI or
service.

## Review triggers

Revisit only if a consumer requirement cannot be represented without changing
canonical semantics.

## Supersession

This is the first decision for the core/consumer boundary.

[^architecture-design]: The project architecture defines three independent layers.
