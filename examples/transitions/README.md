# Transition fixtures

Each child contains complete `base/` and `proposed/` bundles. The test runner
passes both trees to `validate_transition()`; it never scans this parent as a
bundle.

- `retained-verification/` changes a stable snapshot while retaining the old
  verification event. The proposed bundle must fail `KB-E127` and the
  base-versus-proposed comparison must fail `KB-E311`.
