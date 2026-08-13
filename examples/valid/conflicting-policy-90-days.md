---
type: policy
id: urn:uuid:ecb183ae-ecf9-4017-a0e5-f7adcb77228a
title: Synthetic operational knowledge review policy A
description: A synthetic fixture requires operational procedures to be reviewed every ninety days.
status: stable
created_at: "2026-08-01T09:00:00Z"
updated_at: "2026-08-01T09:00:00Z"
generated:
  by: human:fixture-author
  at: "2026-08-01T09:00:00Z"
  method: transformed
sources:
  - id: fixture-policy-a
    resource: https://example.invalid/fixture-policy-a
    title: Synthetic policy source A
verified:
  - by: human:fixture-reviewer-a
    at: "2026-08-01T10:00:00Z"
valid_from: "2026-08-01"
stale_after: "2027-02-01"
tags:
  - conflict-fixture
  - freshness
---

# Synthetic operational knowledge review policy A

## Policy

All operational procedures in the synthetic example scope must be reviewed at
least every 90 days.[^fixture-policy-a]

## Scope

All teams and operational procedures in the synthetic example organization.

## Requirements

Set `stale_after` no later than 90 days after verification.

## Exceptions

None are defined in this fixture.

## Rationale

The fixture intentionally conflicts with
[policy B](./conflicting-policy-180-days.md).

## Enforcement

Do not enforce this synthetic content outside tests.

## Review

The conflict must be surfaced for human resolution, not ranked away.

[^fixture-policy-a]: Synthetic policy source A; the domain is intentionally non-resolving.

## Verification record

The fixture reviewer confirmed this policy matches its synthetic source.

<!-- core-kb-verification: human:fixture-reviewer-a at 2026-08-01T10:00:00Z -->
