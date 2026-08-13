---
type: decision
id: urn:uuid:31f5f4b3-0f8e-405a-a097-3e818ef67c99
title: Pin OKF v0.2 for the core profile
description: The core profile targets one immutable OKF v0.2 revision and reviews upstream changes explicitly.
status: draft
created_at: "2026-08-13T01:34:46Z"
updated_at: "2026-08-13T01:34:46Z"
generated:
  by: openai-codex/gpt-5
  at: "2026-08-13T01:34:46Z"
  method: agent-generated
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/374e0bc4c644310ff56cdf9c0fe81eccdec862b0/okf/SPEC.md
    title: Open Knowledge Format v0.2 specification at the pinned commit
confidence:
  level: high
  basis: The upstream file declares v0.2 and the chosen commit was read directly before implementation.
tags:
  - compatibility
  - okf
related:
  - urn:uuid:cfc6bf19-7640-4c01-9508-eb9db7cd67c6
sensitivity: internal
---

# Pin OKF v0.2 for the core profile

## Decision

Target OKF v0.2 at commit
`374e0bc4c644310ff56cdf9c0fe81eccdec862b0`.[^okf-spec] Later upstream
changes enter through an explicit compatibility review and profile release.

## Context

The upstream `main` branch is mutable. Deterministic conformance requires a
fixed normative input.

## Options considered

1. Follow upstream `main` continuously.
2. Copy the specification without revision identity.
3. Pin an immutable commit and record the version in the bundle.

## Rationale

The pinned commit keeps validation reproducible while the root index exposes
the portable `okf_version: "0.2"` declaration.

## Consequences

Maintainers must compare and review later upstream changes. Baseline OKF and
local-profile results remain separate.

## Review triggers

Review when upstream publishes a new version or a relevant v0.2 correction.

## Supersession

This is the first bundle-level compatibility decision.

See the [upstream source summary](../sources/okf-v02.md).

[^okf-spec]: OKF v0.2 sections 11 and 12 define conformance and versioning.
