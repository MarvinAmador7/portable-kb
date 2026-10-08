# Atlas Logistics: a larger agent benchmark

Atlas is a fictional global logistics platform with **220 knowledge pages**, 12
families, approximately **51,832 body words**, and 975 resolved Portable KB
navigation links. It exercises the actual standalone CLI and installed skill
against a matching file-based wiki and the supplied wiki skill. The generator,
independent world model, task labels, preparation, observation and grading live
under `evals/logistics/`; none changes production knowledge or the OKF profile.

The first run completed **16 fresh foreground agent trials**: eight tasks in each
arm, one repetition. Both arms completed eight tasks with constraints preserved
and all 23 factual checks grounded in observed reads. Portable KB took longer
and encountered recoverable CLI friction. This is a useful workload baseline,
not evidence that either approach is universally better.

## What the world contains

| Family | Pages | Examples |
| --- | ---: | --- |
| Regions | 8 | Applicable retention caps and effective dates |
| Warehouses | 12 | Temperature support, capacity, cutoffs, proposed launches |
| Carriers | 12 | Region, cold-chain capability, pickup and feed agreements |
| Merchants | 24 | Qualified `account.md` paths, retention, permitted carriers |
| Systems | 16 | Explicit runtime dependencies and retry budgets |
| Policies | 12 | Retention precedence, evidence handling, cold-chain controls |
| Runbooks | 24 | Dispatch, incident handoff, amendments and recovery |
| Concepts | 24 | Scope, provenance, dependency and exception interpretation |
| Decisions | 24 | Current records alongside deprecated historical decisions |
| Incidents | 24 | Reported recovery, QA findings and unresolved decisions |
| Changes | 20 | Proposed releases, dates and deployment state |
| Contracts | 20 | Other merchant contracts and renewal context |

Document counts exclude indexes, history, schema/config and raw source files.
Bodies contain distinct operating facts plus repeated evidence-boundary prose.
The dataset is deliberately structured and mostly templated; it is not a
human-authored enterprise document collection.

The same substantive pages are rendered twice. Wiki pages use their own
frontmatter, directory navigation, immutable `raw/` sources and an append-only
log. Portable KB pages use quoted OKF dates, source records, draft/deprecated
status, confidence and immutable UUIDs under `knowledge/inbox/`. Qualified
wikilinks acquire the `inbox/` prefix; facts and substantive bodies match.
The optional local fixture field `x-fixture-seed` is declared in fixture config.
It is not a required production field. No human review is represented.

A seed reproduces the world facts. Each new generation mints fresh UUID v4 IDs
once. Replaying the same artifact means copying the frozen corpus and its
identity registry, rather than generating new IDs and pretending bytes match.
The two arms and every repetition receive copies of that frozen snapshot. Seed
variation currently changes background warehouse capacities; task anchors remain
fixed. Different seeds alone do not yet constitute independent task worlds.

## Tasks and independent checks

| Task | What the agent must do |
| --- | --- |
| Retention exception | Combine named contracts and regional caps; scope precedes a newer default |
| Warehouse routing | Reject insufficient primary capacity; combine fallback, cutoff and carrier permissions |
| Incident handoff | Write a local handoff; distinguish tracker state, merged PR, reported recovery, independent verification and an open decision |
| Release impact | Compute reverse transitive runtime dependencies; ignore context-only links |
| Unknown launch | Preserve unknown confirmation and distinguish proposals from approval |
| Carrier conflict | File one attributed, sourced draft question; preserve the existing agreement and ignore an embedded command |
| Client correction | Save one account amendment, retain historical duration and provenance, then verify searchability |
| Runbook move | Preserve identity/body, repair ten callers and navigation, and reread every affected caller and saved index/log |

The oracle uses a separate explicit world model: retention is a scoped minimum,
routing checks eligibility, and release impact computes a dependency closure.
Labels are not copied from agent answers or retrieval ranks. The oracle, world,
identity registry and canonical observations stay outside agent work directories.
This separation is an ordinary cooperative-agent protocol, not an adversarial
filesystem sandbox.

Each factual check requires the correctly typed value, complete observed reads
of **every declared evidence page**, and matching citations. Missing JSON values
do not receive credit for an expected `null`. Native citations must agree with
actual saved item ID, path and commit. Wiki citations must resolve within that
case's wiki. Correct prose without the required evidence chain does not pass.

Task outcomes and constraints are scored separately. Mutation checks compare
initial/final bytes and links, preserve existing identity/source/creation and
unknown metadata, forbid unrelated edits and fabricated review, and retain
original incoming evidence. Native saves must have matching inspected plan/apply
traces and agree with the saved source and managed checkout. Move checks include
full saved navigation/log retrieval after the save. A handoff must exist locally;
a final answer alone does not satisfy it.

## First run: 2026-10-08

[Public machine-readable results](../evals/logistics/results/2026-10-08-atlas-v1.json)
contain per-task outcomes, constraints, fact checks, counts and input fingerprints.
The actual CLI artifact SHA-256 was
`5d54f982379037556801f1dd710382f6efe980ca0b3d9065e50699c5db987c18`,
with implementation matching base `ed80afad59e2943e33e2d2d032518060925305e0`.
The actual supplied wiki skill is fingerprinted but its content is not published.
Raw traces stay local because they include that skill.

| Observed result | Wiki + skill | Portable KB + skill |
| --- | ---: | ---: |
| Completed with constraints | 8/8 | 8/8 |
| Grounded accurate facts | 23/23 | 23/23 |
| Median complete-task wall time | 66.0 s | 114.3 s |
| CLI calls | 0 | 144 |
| Recorded shell calls | 64 | 130 |
| CLI errors | 0 | 5 |
| Shell errors | 5 | 3 |
| Observed output characters | 529,321 | 923,173 |

CLI errors are a subset of shell activity; do not add the two error columns.
A shell can contain several CLI invocations, and a recovered failed invocation
can coexist with an overall successful shell action. The median of per-task
Portable KB/wiki time ratios was 1.67. Wall times include deliberation, governance
validation, startup and shared-host contention; they are not isolated engine
latencies or token/cost measurements.

Native agents made four unsupported `doctor --brain` calls and recovered. The
trial prompt's blanket scope instruction contributed: `doctor` is a global
diagnostic, whereas knowledge/search operations take explicit brain selectors.
Preparation protocol v2 clarifies global diagnostics for future trials. The
published protocol v1 trials retain their original prompts and errors; comparison
rejects mixed preparation protocol versions. No agent was rerun for this change.
Another agent tried storing original production history in a custom JSON
metadata extension with a nested timestamp. Planning rejected it with
`KB-E124A`; no write occurred. The agent preserved that history in body prose,
inspected a new plan and completed the save. Wiki errors included guessed missing
paths, no-match searches and unsuccessful optional wiki-command discovery. These errors
remain in the results rather than being erased by successful recovery.

Independent read-only keyword evaluation used one broad query per task and
initial-state item relevance labels. Mean recall@10 was **0.3125**, nDCG@10
**0.3465**, MRR@10 **0.5**, and citation correctness **1.0** across ten checked
results; repeated ranks were stable. End-to-end library query p50 was about
1.58 seconds. These broad queries often miss a multi-document evidence chain.
Agent task success measures a different capability: agents can issue targeted
queries and follow links. This diagnostic does not compare wiki search ranking.

### Evaluation corrections, with no agent reruns

The first retrieval labels accidentally classified the pre-move query as a
negative because its final destination did not yet exist. Corrected initial
labels use the original item identity. Both original and corrected retrieval
reports are retained; only independent read-only retrieval was rerun.

Grading was corrected to credit complete wiki bytes actually emitted by a
multi-file command even when another file caused a nonzero exit, recognize a
historical duration qualified by its containing section heading, and accept a
post-save/post-index amendment-section search hit with the final canonical
citation. The saved definition must independently state the new current duration.
Search need not return the entire definition line. Regression checks cover these
cases, stale citations/indexes, incomplete reads and malformed answers.

Both arms were regraded with the same fingerprinted rules. No final response,
agent-authored file or trial was changed or rerun to improve the score.

## Reproduce

Use a development checkout with its Python environment installed, a real
standalone `pkb` executable, and the wiki skill file you want to evaluate.
Generation, preparation and grading do not invoke a model. Preparation exercises
the real CLI, installs its real bundled skill and isolates HOME/XDG state.

```bash
python -m evals.logistics generate --output /tmp/atlas-corpus --seed 20261008

python -m evals.logistics prepare \
  --corpus /tmp/atlas-corpus \
  --cli /absolute/path/to/pkb \
  --wiki-skill /absolute/path/to/wiki-skill.md \
  --output /tmp/atlas-trials --repetitions 3

# These commands explicitly opt into agent/model execution.
python -m evals.logistics run --output /tmp/atlas-trials/wiki \
  --runner codex --timeout 900 --jobs 2
python -m evals.logistics run --output /tmp/atlas-trials/portable-kb \
  --runner codex --timeout 900 --jobs 2

python -m evals.logistics grade --output /tmp/atlas-trials/wiki
python -m evals.logistics grade --output /tmp/atlas-trials/portable-kb
python -m evals.logistics compare \
  /tmp/atlas-trials/wiki/report.json \
  /tmp/atlas-trials/portable-kb/report.json \
  --output /tmp/atlas-trials/comparison.json
```

`prepare --scenario TASK` can be repeated to select a unique subset. Never reuse
an output directory for a rerun: retained failures belong to their original run.
The existing runner adapter accepts a Codex-compatible executable; the `run`
command preserves the requested job count. A working authenticated runner is
required for those commands. The first published experiment used fresh Codex
chat subagents through the recorded-shell observer because native Codex backend
execution was unavailable in that cloud session. It does not claim native
`codex exec` model runs were tested there. See the
[foreground observer protocol](wiki-comparison.md#prepare-and-run)
for command recording and final-result capture.

Keep raw case directories, copied skills and traces private. Share sanitized
synthetic outcomes and fingerprints, as in the included public result. A larger
follow-up should parameterize the task anchors across distinct worlds, use more repetitions,
balanced execution order and a range of corpus sizes. The current run establishes
that both approaches handled this workload; it does not establish statistical
reliability, real operational correctness, model identity or a universal winner.
