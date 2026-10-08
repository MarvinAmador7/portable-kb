# Saved navigation and history retrieval

`pkb get` now retrieves complete reserved index/log documents by explicit bundle
path. This closes the read limitation observed in the [move follow-up](knowledge-move-results.md).
For example:

```console
pkb get index.md --brain team --json
pkb get log.md --brain team --json
pkb get inbox/procedures/index.md --brain team --json
```

The response uses `document: {kind, path, content}` and a brain/path/commit
citation. Content comes from the pinned UTF-8 Git blob, including generated
regions and authored prose. Reserved documents receive no invented concept UUID,
producer or lifecycle fields. The concept response and strict concept-only
Python retrieval API remain unchanged. See [the CLI contract](cli.md#complete-item-retrieval).

On 2026-10-08, two fresh Portable KB foreground agents ran the runbook-move task
with the new standalone executable and installed skill. Both completed with all
observed constraints and factual checks passing. Both retrieved the changed
procedure index and log after applying the move, at its exact saved commit.
Independent observation compared each complete document response with canonical
saved content and its pinned citation. Both runs recorded **zero failed CLI or
shell commands**; neither was rerun to improve its score.

The [sanitized verification report](../evals/wiki_compare/results/2026-10-08-document-retrieval-v1.json)
includes per-case checks, document paths, metrics and artifact/skill/grader
fingerprints. Only the two Portable KB cases were executed. The harness also
prepared two wiki cases, which remain unrun. This is targeted verification of
the new read capability, not a fresh matched comparison or a speed claim. Prior
reports retain their original scores and grading fingerprints. Raw traces and
the supplied wiki skill remain outside the public repository.

The updated skill tells agents how to distinguish document responses from
concepts and requires complete saved reads of changed index/log paths after a
move. The move evaluator independently enforces those reads and rejects preview
content, pre-save reads, stale citations, missing documents and wrong brain
scope. Unit/integration checks also cover scoped isolation, read-only behavior,
unsafe and hidden paths, symlinks, dirty/unpinned checkouts and a working-file
change after the health check.

Validation: **434 Linux tests passed with 87.06% coverage**, including real
Tantivy and QMD. Lint, installer syntax, wheel build and standalone packaging
smoke checks passed. The inherited chat model was not identified, the two trials
overlapped, and token/cost telemetry is unavailable. No knowledge was published.
