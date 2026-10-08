# CLI move follow-up

The missing CLI move identified in the [first workplace comparison](agentic-workflow-results.md)
is implemented as `pkb knowledge move`. On 2026-10-08, four fresh foreground
agent trials repeated only the runbook-move workflow: two with the standalone
Portable KB CLI and its installed skill, and two with the supplied wiki skill.
Both approaches completed **2/2** tasks with all observed constraints and factual
checks passing. Portable KB had previously blocked both moves safely.

This is a targeted capability follow-up, not a rerun of the original 24 trials.
The historical results and blocked outcomes remain unchanged. The sanitized
[follow-up report](../evals/wiki_compare/results/2026-10-08-move-followup-v1.json)
records per-case checks, errors, timings and protocol/artifact/skill fingerprints.
Raw traces, local brain paths and the supplied wiki skill remain outside the
repository.

| Runbook-move measure | Wiki + skill | Portable KB + skill |
| --- | ---: | ---: |
| Completed with constraints | 2/2 | 2/2 |
| Grounded factual checks | 2/2 | 2/2 |
| Blocked | 0 | 0 |
| Observed failed CLI calls | 0 | 5 |
| Observed failed shell calls | 0 | 5 |
| Median foreground time | 57.0 s | 92.5 s |

CLI failures also appear in shell failures; these are five failed commands,
not ten separate failures. One Portable KB agent initially omitted the fixture's
`inbox/` path prefix. Both tried `pkb get` on the procedure index and log, which
are reserved documents rather than knowledge concepts. They recovered using
move diffs, complete saved concept reads, link navigation and brain health
checks. The supported CLI does not expose complete index/log retrieval, so that
remains an observable navigation limitation. Neither trial was rerun to remove
its errors or improve its score.

The Portable KB agents used explicitly scoped move previews and applies, then
retrieved the moved UUID and all three affected callers at the saved commit.
They preserved the runbook body, creation/provenance, unknown fields and draft
status; inbound display labels and authored/generated navigation survived.
They rebuilt the selected brain's derived search index. Independent observation
confirmed source/checkout agreement, healthy links and unchanged active
selection. Indirect caller changes receive credit only when the captured move
diff reproduces the final saved content from the initial page and matches the
saved citation commit.

The command also has deterministic regression coverage for reviewed stable
snapshots, directory moves, stem collisions, literal code examples, authored
navigation, unsafe/existing destinations, stale/dirty state and partial-write
rollback. Moves that would retarget local source metadata are refused, pending
an explicit source revision. All planned repairs are versioned in one local
Git commit; file replacement has optimistic checks and best-effort rollback,
not filesystem-wide crash atomicity. See [the CLI contract](cli.md#knowledge-moves).

Validation: 411 Linux tests passed with 87.04% coverage, including real Tantivy
and QMD; lint, installer syntax, wheel build and standalone smoke checks passed.
The earlier eval PR's macOS test-path failure was corrected by locating `true`
through PATH instead of assuming `/bin/true`.

The inherited chat model was not identified, trials overlapped, and only two
repetitions per interface were run. Timings exclude preparation and independent
grading. These results establish that this bounded move workflow is now
available to agents; they do not establish a general performance winner or
measure token/cost efficiency.
