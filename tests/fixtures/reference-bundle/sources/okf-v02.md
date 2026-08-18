---
type: source-summary
id: urn:uuid:cfc6bf19-7640-4c01-9508-eb9db7cd67c6
title: Open Knowledge Format v0.2
description: OKF v0.2 defines a permissive Markdown bundle with optional provenance, trust, freshness, lifecycle, and attestation signals.
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
  basis: The summary is bounded to the pinned primary specification and distinguishes upstream rules from local requirements.
tags:
  - okf
  - provenance
  - trust
related:
  - urn:uuid:31f5f4b3-0f8e-405a-a097-3e818ef67c99
sensitivity: internal
---

# Open Knowledge Format v0.2

## Summary

OKF v0.2 represents a bundle as Markdown concepts with YAML frontmatter and
ordinary Markdown links. Only a non-empty `type` is universally required;
provenance, generation, verification, freshness, lifecycle, and attestation
families are optional.[^okf-spec]

## Key claims

- `index.md` and `log.md` are reserved documents with defined structures.[^okf-spec]
- Consumers tolerate unknown types and fields and preserve extensions.[^okf-spec]
- Broken concept links do not alone make a baseline bundle malformed.[^okf-spec]
- Trust tiers are derived from verification actors rather than stored as a
  portable truth score.[^okf-spec]

## Limitations

This summary covers the pinned commit. It is not a substitute for the normative
specification and does not make stricter local rules upstream requirements.

## Relevance

`core-kb/0.1` reuses OKF vocabulary and adds deterministic authoring gates for
identity, provenance, lifecycle, and relationships. The
[compatibility decision](../decisions/pin-okf-v02.md) records the exact
revision used by the implementation.

## Follow-up

Compare later upstream versions explicitly before changing compatibility code.

[^okf-spec]: Open Knowledge Format v0.2 at the pinned upstream commit.
