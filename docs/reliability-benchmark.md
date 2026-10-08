# Reliability and CLI read costs

The [Atlas Logistics baseline](logistics-benchmark.md) gave both approaches
8/8 successful tasks, with the wiki faster. This follow-up uses the same frozen
220-page world and adds **16 fresh agent trials**: four failure/recovery tasks,
two repetitions each, for wiki + skill and the actual Portable KB CLI + skill.
It also measures read costs and tests a focused recovery fix separately.

The wiki completed **8/8** tasks with constraints preserved. The original
Portable KB executable completed **6/8**, safely blocking both interrupted
moves after the agents restored the authoring files. A fixed executable then
completed **2/2 fresh Portable KB interruption trials**. Those candidate trials
do not replace the two original failures or constitute a new full paired run.

[Machine-readable results](../evals/reliability/results/2026-10-08-atlas-reliability-v1.json)
include per-case checks, hashes, original failures, candidate coverage, and profiles.
The implementation is development-only under `evals/reliability/`. The
[production lock fix](https://github.com/MarvinAmador7/portable-kb/pull/14)
is a separate change.

## Matched tasks

| Task | Injected condition and expected behavior |
| --- | --- |
| Concurrent update | Agent reads the original 7-day account and prepares a 14-day amendment. A checkpoint saves a collaborator's contact window. Agent must inspect the new snapshot, preserve that edit and both sources, retain 7 days as history, and verify searchability. |
| Stale citation | Agent receives a cached complete 7-day lookup; the current account has already been revised to 21 days. It must reject the cached answer as current, distinguish historical 7 days, and cite a fresh complete read without editing knowledge. |
| Interrupted move | A real process is killed after its destination-file rename. Both arms receive a trusted Git backup and permission for targeted authoring recovery. They must preserve the runbook, complete its move, repair ten callers, and reread callers and navigation/logs. |
| Rollback amendment | Restore mistaken 21-day retention to 7 days as a new draft revision, preserving identity, metadata, sources and the mistake as history; reread and search the saved account. |

The concurrent-update checkpoint **announces the collaborator's save** and
explicitly requires a reread. It tests a cooperative agent workflow, not a
blind simultaneous-writer race or automatic conflict prevention. The rollback
is a new revision, not erasure of the earlier commit. Native grading verifies
that the mistaken revision remains an ancestor.

The interruption uses a Linux libc interposer, compiled from
`evals/reliability/stop_rename.c`. After the selected successful rename, it
records the actual PID and stops the process; the controller sends `SIGKILL`
to the actual CLI/file-operation process group. Product success is not mocked,
and production binaries are not modified. This boundary is a destination-file
rename, rather than an identical percentage of each workflow: the native move
had already written several callers, while the wiki's ordinary rename left
its callers unrepaired. Hard kills bypass normal Python rollback.

Both arms can inspect Git status/diffs and restore only affected authoring
paths from the same pre-fault backup tag. Native agents then use a fresh
supported move plan/apply; they may not edit the managed consumer checkout or
manually remove product locks. The partially written native authoring tree
coexisted with an intact published consumer snapshot. Neither approach has
been shown to complete this operation without an agent doing recovery.

## Observed baseline: 2026-10-08

| Result | Wiki + skill | Portable KB + skill |
| --- | ---: | ---: |
| Completed with constraints | 8/8 | 6/8 |
| Safely blocked | 0 | 2 |
| Constraint passes | 8/8 | 8/8 |
| Grounded accurate task facts | 16/16 | 14/16 |
| Recorded CLI errors | 0 | 2 |
| Recorded shell errors | 4 | 2 |

The native blocked agents accurately reported 120 units at the surviving old
path. The fact rubric requires the completed destination path, so those two
facts do not pass the requested final-state grounding check. They are not
fabricated answers or destructive failures. Error columns overlap: CLI errors
can also make their enclosing shell action fail.

In both native interruption runs, the agents restored clean authoring files
and inspected valid fresh plans. Apply then timed out waiting for the old
operation lock. Linux retained the killed standalone child as a zombie under
this container's process supervisor. `os.kill(pid, 0)` still succeeds for a
zombie, so the CLI incorrectly classified the exited owner as alive. This is
an environment-dependent process-recovery defect, not evidence that every
interrupted operation fails on all machines.

The separate fix recognizes Linux `/proc/<pid>/stat` `Z`/`X` states as exited
owners. Unknown, inaccessible, live and foreign-host ownership stays protected.
A real unreaped-child regression exercises this condition. A new standalone
artifact was built and smoke-tested; **two fresh native agents completed the
same interrupted-move task**, preserving the runbook, all ten callers,
metadata, navigation and history. The candidate changed production lock
handling only. It used the same corpus, oracle, skills and compiled fault
library. Its prompts include the documented interface clarification below.
Only these two native candidate trials ran; prepared wiki candidate cases
were not executed or counted.

## Independent stale-draft probe

A separate deterministic probe used the **actual original CLI**:

1. Preview an update using a 14-day body prepared from the original account.
2. Save a collaborator's new contact window through the actual CLI.
3. Apply the old body file in a new CLI invocation.
4. Read the actual final saved account.

The apply succeeded and retained the collaborator's source record, but
**overwrote its contact-window body change**. The existing in-process commit
check does not bind a later CLI invocation to an earlier reviewed preview;
the later invocation replans against the latest commit. Thus the passing
checkpoint trials do not demonstrate automatic stale-draft protection.

This gap remains open. A useful next change is an explicit expected-commit
precondition, or replaying a reviewed plan bound to its source commit, with
an actual competing-writer regression. The probe is native-only and is not
counted as an additional matched agent trial. No wiki race-safety claim follows
from it. Retaining a source record is insufficient to preserve its body facts.

## Read-cost profile

Three samples per operation used fresh processes of the original standalone
CLI against the unchanged 220-page baseline. Medians include the recording
shim and JSON handling. Warm, unmodified Python core operations were measured
separately; their complete path/UUID payloads were checked against the actual
executable. Instrumented profile timings include profiling overhead and are
not the normal-operation medians.

| Operation | Standalone median | Warm core median | Concept parses per profiled core call |
| --- | ---: | ---: | ---: |
| Help | 676 ms | — | — |
| Brain status | 2,448 ms | 1,437 ms | 220 |
| Get by path | 2,403 ms | 1,490 ms | 221 |
| Get by UUID | 2,550 ms | 1,491 ms | 354 |
| Get reserved index | 2,212 ms | 1,115 ms | 220 |
| Keyword query | 2,222 ms | — | — |

Complete reads repeatedly validate and parse the entire bundle. Path retrieval
then parses its target again. UUID retrieval also scans parsed concepts until
it finds the ID. YAML accounts for roughly 46–54% of exclusive profiled time;
these percentages do not add overlapping cumulative call times. The result
points to repeated validation/parsing as a substantial cost before ranking.
Help provides a startup control, not a precise way to subtract boot time.

A promising follow-up is to reuse validation for an unchanged pinned snapshot,
provide direct UUID lookup, and amortize validated reads across a batch. Such
work must preserve dirty/unhealthy checkout detection and canonical citations.
No production performance cache or batch API was introduced in this experiment.

## Method and grading corrections

Trials used fresh Codex chat subagents through the existing recorded-shell
observer. Model identity is inherited/unknown. All task actions and real CLI
outputs are retained locally; controller/grader activity is excluded from
agent metrics. This run does not claim that `codex exec` backend execution
worked in this environment. Raw traces remain private because they include
the supplied wiki skill. Only synthetic outcomes and fingerprints are public.

One wiki interruption agent asked whether the phrase “native final authoring”
required a separate wiki CLI. It received a narrow interface clarification:
CLI move plan/apply applies only to the Portable KB arm. Remaining fresh
agents received that same clarification. A rollback agent received a narrow
clarification that `kb-fault checkpoint` is only requested by concurrent-update;
it did not invoke the controller. Future preparation states both points
explicitly. No task facts or recovery solution were supplied by the evaluator.

Initial grading reused a single-input raw-copy allowance and therefore
misclassified authorized copies of incoming evidence as unrelated edits.
One wiki also gave those unchanged raw copies descriptive new filenames,
which the old exact-filename source check missed. The reliability rubric now
allows **new, byte-identical incoming evidence copies under `raw/`**, including
renamed copies cited in source metadata. Existing raw files and unrelated or
modified new documents remain protected. Original grades are retained locally;
no agent was rerun or edited to improve a score. Regression tests cover these
cases, current versus historical durations, stale citations/index ordering,
and an actual rename-boundary hard kill.

A first preparation attempt failed on a fixture footnote/source-ID mismatch
before any agent started. It is retained as a preparation failure; the matched
baseline was prepared afresh after correcting the controller fixture.

Local verification passed 459 evaluation tests at 87.10% coverage and 438
production-fix tests at 87.07%, including real Tantivy and QMD. GitHub Linux CI
also exposed an inherited reserved-document fixture that relied on a global Git
author; its helper now supplies a synthetic test identity. The affected tests
pass with global/system Git configuration disabled. This test-only correction
does not change the measured executables or agent outcomes.

This is one mostly templated synthetic world, two repetitions, one Linux host
and its process supervisor. Execution order was not randomized, and agents
shared the host. Completed-task medians have different coverage because two
native tasks blocked; compare matched successful tasks instead of treating
unequal totals as a speed verdict. The results establish concrete workflow
behavior and defects, not statistical reliability or a universal winner.

## Reproduce

Use a development checkout, a real standalone executable, and your wiki skill.
Fault preparation requires Linux and a C compiler; it creates only fresh
synthetic cases. It does not inject faults into an existing user brain.

```bash
python -m evals.logistics generate --output /tmp/atlas-corpus --seed 20261008
python -m evals.reliability prepare \
  --output /tmp/atlas-recovery \
  --corpus /tmp/atlas-corpus \
  --cli /absolute/path/to/pkb \
  --wiki-skill /absolute/path/to/wiki-skill.md --repetitions 2

# Explicit agent/model opt-in; an authenticated runner is required.
python -m evals.reliability run --output /tmp/atlas-recovery/trials/wiki --jobs 2
python -m evals.reliability run --output /tmp/atlas-recovery/trials/portable-kb --jobs 2
python -m evals.reliability grade --output /tmp/atlas-recovery/trials/wiki
python -m evals.reliability grade --output /tmp/atlas-recovery/trials/portable-kb
python -m evals.reliability compare \
  /tmp/atlas-recovery/trials/wiki/report.json \
  /tmp/atlas-recovery/trials/portable-kb/report.json \
  --output /tmp/atlas-recovery/comparison.json

python -m evals.reliability profile \
  --case /tmp/atlas-recovery/trials/fixtures/consumer \
  --output /tmp/atlas-read-profile --samples 3
```

Repeated `prepare --scenario TASK` selects a subset. Use separate fresh outputs
for candidates, never retry an existing trial in place. Candidate-only coverage
must be reported separately when an arm or task was not run. Keep copied skills
and raw traces private; share the sanitized outcomes and inputs you are authorized
to publish.
