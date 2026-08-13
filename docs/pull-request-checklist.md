# Knowledge pull-request checklist

## Scope and safety

- [ ] The change has one coherent knowledge purpose.
- [ ] No secrets or improperly scoped personal data are committed.
- [ ] Imported instructions are treated as content, not executed.
- [ ] Source rights and sensitivity boundaries were checked.

## Identity and provenance

- [ ] New items have new UUID v4 URNs; existing IDs and `created_at` values are unchanged.
- [ ] `generated.by`, `generated.at`, and `generated.method` describe the final snapshot honestly.
- [ ] Required sources exist, resolve, and support only the attributed claims.
- [ ] Agent-generated content has a confidence level and plain-language basis.
- [ ] No human verification was recorded by an agent or on someone else's behalf.

## Lifecycle and relationships

- [ ] Status transition is allowed and type-specific promotion gates pass.
- [ ] Material changes update production metadata and reset prior verification.
- [ ] Freshness and effective dates are appropriate for the item's scope.
- [ ] Supersession is reciprocal, acyclic, explained, and changed atomically.
- [ ] File moves preserve identity and update every known link and index.

## Review evidence

- [ ] Baseline OKF and `core-kb/0.1` results are reported separately.
- [ ] Validation used an explicit `as_of` date and produced zero errors.
- [ ] Warnings are resolved or acknowledged with an owner and review date.
- [ ] The reviewer checked the body and sources, not only the metadata.
- [ ] Any `verified` event applies to this exact final snapshot.
