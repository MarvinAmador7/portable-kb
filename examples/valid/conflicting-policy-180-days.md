---
type: policy
id: urn:uuid:135a53cd-b61e-418a-a8c4-a6038ed49bdb
title: Synthetic operational knowledge review policy B
description: A synthetic fixture permits operational procedures to be reviewed every one hundred eighty days.
status: stable
created_at: "2026-08-01T09:30:00Z"
updated_at: "2026-08-01T09:30:00Z"
generated:
  by: human:fixture-author
  at: "2026-08-01T09:30:00Z"
  method: transformed
sources:
  - id: fixture-policy-b
    resource: https://example.invalid/fixture-policy-b
    title: Synthetic policy source B
verified:
  - by: human:fixture-reviewer-b
    at: "2026-08-01T10:30:00Z"
valid_from: "2026-08-01"
stale_after: "2027-02-01"
tags:
  - conflict-fixture
  - freshness
---

# Synthetic operational knowledge review policy B

## Policy

All operational procedures in the synthetic example scope may use a review
interval of up to 180 days.[^fixture-policy-b]

## Scope

All teams and operational procedures in the synthetic example organization.

## Requirements

Set `stale_after` no later than 180 days after verification.

## Exceptions

None are defined in this fixture.

## Rationale

The fixture intentionally conflicts with
[policy A](./conflicting-policy-90-days.md).

## Enforcement

Do not enforce this synthetic content outside tests.

## Review

Both files are structurally valid. A semantic quality review should identify
the overlapping scope and conflicting obligations.

[^fixture-policy-b]: Synthetic policy source B; the domain is intentionally non-resolving.

## Verification record

The fixture reviewer confirmed this policy matches its synthetic source.

<!-- core-kb-verification: human:fixture-reviewer-b at 2026-08-01T10:30:00Z -->
