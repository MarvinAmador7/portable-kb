# First workplace workflow comparison

On 2026-10-08 (America/Costa_Rica), 24 fresh foreground agent trials ran six
fictional workplace workflows twice against each interface. The wiki completed
12/12 tasks. Portable KB completed 10/12 and truthfully blocked the two runbook
moves because its CLI has no supported move operation. Both arms passed all
observed constraints and answered 40/40 factual checks accurately with complete,
scoped evidence. Unsupported operations received no completion credit.

| Workflow | Wiki completed | Portable KB completed | Portable KB blocked |
| --- | ---: | ---: | ---: |
| Incident handoff | 2/2 | 2/2 | 0 |
| Requirements correction | 2/2 | 2/2 | 0 |
| Conflicting evidence | 2/2 | 2/2 | 0 |
| Client isolation | 2/2 | 2/2 | 0 |
| Untrusted notes | 2/2 | 2/2 | 0 |
| Runbook move | 2/2 | 0/2 | 2 |

For the ten paired trials that both interfaces completed with constraints,
median foreground elapsed time was **66.0 seconds for wiki** and **82.1 seconds
for Portable KB**. Preparation, indexing the initial fixtures and independent
grading were outside that timing. Runs overlapped, used the inherited chat model
without reported model identity, and had only two repetitions per workflow.
These measurements do not establish a general performance ranking or token/cost
advantage. The blocked moves' roughly 41-second runtimes are excluded.

The machine-readable, sanitized checks and per-case metrics are in
[`2026-10-08-agentic-v1.json`](../evals/wiki_compare/results/2026-10-08-agentic-v1.json).
Its fingerprints identify the suite, both fictional worlds, supplied wiki skill,
actual CLI and grading/observation implementation. Private original wiki content,
raw agent traces, installed skill copies and local brain paths are not committed.
See [the workflow guide](agentic-workflows.md) to reproduce new trials.

## What the traces showed

- Wiki agents made **five failed shell reads** while guessing directories such
  as `entities/`, `concepts/` or the wiki root before reading the actual listed
  paths. They recovered without losing task completion. Native wiki navigation
  could make full relative paths easier to discover.
- Portable KB agents made **zero failed CLI or shell calls** in the matched run.
  They used inspected previews/applies, rebuilt stale search after corrections,
  and cited complete saved items. This result applies to these isolated fixtures.
- Both approaches retained old provenance, preserved creation metadata, kept the
  client's proposed CSV and unknown date qualified, and captured conflicting
  evidence without rewriting the established requirement.
- The client test used the same native item UUID in two brains. Both repetitions
  changed Northstar to 45 days, kept Harbor at 7, preserved the alternate corpus
  and left active selection unchanged. The wiki used the same relative filename
  in two isolated roots.
- The embedded notes instruction did not execute its marker command or cause
  a human-verification claim. The resulting local summaries stayed drafts and
  left established pages unchanged. This is a bounded observed test, not a claim
  of general prompt-injection immunity.
- Wiki agents completed both moves while retaining the substantive runbook body,
  creation/source history and inbound display labels. Portable KB's missing CLI
  move is a concrete capability gap. A future move workflow needs identity
  preservation and atomic repair of inbound links/navigation before it can
  receive completion credit here.

## Pilot and grading corrections

Before the matched run, twelve pilot trials executed: six wiki and six Portable
KB. The wiki completed all six. Portable KB completed three, safely blocked its
move, and failed two tasks after treating incoming `evidence/` documents as
missing CLI knowledge references. Twelve further prepared pilot cases were not
run. The pilot traces and failures remain retained outside the repository and
are excluded from the matched score.

The matched run clarified that incoming evidence files live outside the managed
brain and are readable with ordinary file tools. It also aligned all alternate
world bodies before creating fresh copies and agents. This is a protocol change,
not evidence that the skill alone improved. Real agent instructions should make
that source-document boundary clear.

Grading was corrected to accept valid absolute paths within the exact wiki case,
native wiki summary types, and links to existing raw-source files. The source
files remain immutable and byte checked. These corrections accommodate the wiki's
own conventions instead of applying Portable KB's profile to it. Original prompts,
answers and traces were preserved; no failed matched trial was rerun to improve
its score. The report also fingerprints the grader and observation code, so
reports from different rubrics must be regraded before comparison.

The supported workflows tied on completion in this small sample. Wiki also
covered a move that the current CLI cannot perform; Portable KB offered explicit
scope, governed saved drafts, stable identity and executable citation/navigation
commands. Choosing between them needs the workflows an organization actually
requires, plus larger and noisier evidence sets, rather than a single combined
score that hides missing capabilities or safe blocking.
