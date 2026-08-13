---
type: decision
id: urn:uuid:52c4e691-a978-460f-9376-f976ec75f6ba
title: Self-superseding decision
description: This negative fixture points its supersession relationship back to its own immutable identity.
status: deprecated
created_at: "2026-08-06T17:10:00Z"
updated_at: "2026-08-06T17:10:00Z"
generated:
  by: human:fixture-author
  at: "2026-08-06T17:10:00Z"
  method: human-authored
supersedes:
  - urn:uuid:52c4e691-a978-460f-9376-f976ec75f6ba
---

# Self-superseding decision

This file is intentionally invalid under corpus rule `KB-E400`. JSON Schema
cannot detect equality between `id` and a relationship item, so corpus
validation must reject it.
