# Example corpus

This directory is a design-time test corpus, not the future production OKF
bundle.

## Positive fixtures

Files under `valid/` pass the draft JSON Schema and deterministic corpus checks.
Two groups intentionally produce non-error health findings:

- `stale-system.md` is structurally valid but stale on and after 2026-08-01.
- `conflicting-policy-90-days.md` and
  `conflicting-policy-180-days.md` are each structurally valid but express
  incompatible obligations in the same synthetic scope. The semantic quality
  check warns and requires human resolution.

`agent-generated-draft.md` demonstrates that agent output stays explicitly
labeled, sourced, uncertain, and draft.

## Negative fixtures

Files under `invalid/` must not be repaired as normal content:

- `missing-provenance.md` fails JSON Schema conditional source requirements.
- `invalid-timestamp.md` fails strict UTC schema validation and corpus ordering.
- `self-supersession.md` passes structural schema validation but fails the
  corpus-level no-self-reference rule.

The test runner selects these directories explicitly. It must not
scan `examples/` as one OKF bundle because `README.md` is project documentation
and negative fixtures are intentionally malformed.

## Heuristic evaluation

`heuristics/` is a separately valid bundle containing a duplicate-candidate
pair. Its `labels.yaml` also points to the conflicting policy pair under
`valid/`. Tests assert the expected evidence-bearing warnings without treating
either label as an automatic merge or authority decision.
