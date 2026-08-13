---
type: source-summary
id: urn:uuid:12614e98-57c7-4aa3-aaea-7b3dd2dd8c1e
title: Open Knowledge Format v0.2 trust metadata
description: OKF v0.2 adds optional provenance, verification, freshness, lifecycle, and attestation vocabulary.
status: stable
created_at: "2026-08-06T14:20:00Z"
updated_at: "2026-08-06T15:20:00Z"
generated:
  by: human:researcher-1
  at: "2026-08-06T15:20:00Z"
  method: transformed
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format v0.2 specification
    last_modified: "2026-07-24"
  - id: okf-trust-announcement
    resource: https://cloud.google.com/blog/products/data-analytics/okf-v0-2-adds-trust-signals/
    title: OKF v0.2 adds trust signals
tags:
  - okf
  - provenance
  - trust
confidence:
  level: high
  basis: The summary is limited to fields stated in the official specification and announcement.
---

# Open Knowledge Format v0.2 trust metadata

## Summary

OKF v0.2 keeps `type` as the only universally required concept field and adds
optional vocabulary for source provenance, generation, verification,
freshness, lifecycle, and attested computations.[^okf-spec]

## Key claims

- `sources` records materials from which a concept derives.[^okf-spec]
- `generated` and `verified` distinguish production from confirmation.[^okf-trust-announcement]
- Consumers derive trust tiers from verifier actors rather than reading a
  stored trust score.[^okf-spec]
- `stale_after` is an absolute date and `status` uses draft, stable, and
  deprecated.[^okf-spec]

## Limitations

The upstream specification is evolving. This summary reflects the source
version inspected on 2026-08-06 and is not a substitute for the normative text.

## Relevance

The local profile reuses these field names and applies additional authoring
requirements without claiming that they are baseline OKF requirements.

## Follow-up

Review later upstream revisions explicitly against the implementation pin.

[^okf-spec]: Open Knowledge Format v0.2 specification.
[^okf-trust-announcement]: Google Cloud’s v0.2 trust-signals announcement.
