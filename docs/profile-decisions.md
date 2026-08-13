# Core profile decisions

Decision date: 2026-08-12.

This document closes the schema-behavior questions for `core-kb/0.1`. It does
not fabricate organizational approval or human verification. A deployment
must replace the intentionally empty reviewer allowlists in
`knowledge/.core-kb.yaml` with durable identifiers for real authorized people
  before that deployment promotes authoritative items.

## Upstream target and bundle boundary

- The implementation targets OKF v0.2 at upstream commit
  `374e0bc4c644310ff56cdf9c0fe81eccdec862b0`.
- The implementation is reviewed against later upstream revisions explicitly;
  it never follows mutable `main` silently.
- `knowledge/` is the only OKF bundle. Repository documentation, schemas,
  templates, tests, and code are outside that boundary.
- The local profile identifier is `core-kb/0.1`.

## Identity and actors

- Knowledge identity is a lowercase UUID v4 URN and never changes.
- Human actors use `human:<durable-opaque-id>`. The suffix identifies one real
  person in the deploying organization; it is not an email address or role.
- Processes use `process:<durable-process-id>`.
- Agents and tools use `<producer>/<version>`, for example
  `openai-codex/gpt-5`.
- Role membership and authorization are deployment governance. They are not
  inferred from actor spelling.

## Verification and promotion

- A Git approval or merge does not itself create a `verified` event.
- Authoritative promotion requires an explicit event by a real human whose ID
  is present in the bundle configuration for that type.
- The portable implementation validates the event and configured allowlist;
  repository permissions remain responsible for proving control of the actor.
- Decisions and procedures are active authoritative types in the first
  milestone. Policy and system remain schema-defined but inactive until their
  reviewer lists are populated and real content justifies activation.
- Agent-generated stable content always requires configured human review,
  including informational types.

## Freshness

Default review intervals are applied only by an explicit lifecycle operation:

| Type | Default interval |
|---|---:|
| `procedure` | 180 days |
| `system` | 90 days |
| `policy` | 365 days |

An author may select a shorter interval. Choosing a longer interval requires a
review note because schema validation cannot know domain risk.

## Sources and relationships

- Consequential external sources should use immutable revisions or lawful
  snapshots. Mutable URLs remain allowed when their limitation is stated.
- The optional `related` relation remains in v0.1 for salient symmetric links;
  reciprocity is recommended rather than required.
- Supersession remains reciprocal, atomic, and acyclic.
- Imported unknown OKF fields are preserved. Promotion requires an approved
  mapping, a documented `x-` namespace, or a profile revision.

## Sensitivity

- This repository's example bundle is `internal` by default.
- `confidential` and `restricted` material require a separately controlled
  repository or bundle. Metadata never grants or denies access.
- Lowering sensitivity is always a material human-reviewed change.

## Agent change boundary

- Agents may create and revise drafts, normalize mechanically, generate
  indexes, and prepare lifecycle change sets.
- Any material change resets current verification.
- Agents never add a `human:` verification event, choose a lower sensitivity,
  resolve a semantic conflict, or apply a lifecycle change without the caller
  explicitly applying the proposed change set.
