# Evaluate agents doing knowledge work

The agentic suite compares the wiki + supplied skill with the actual Portable
KB CLI + installed skill on six multi-step workplace workflows. Agents must
produce useful local artifacts or save the requested changes, preserve evidence
and scope, and retrieve the resulting knowledge. A claimed successful answer
does not substitute for a saved result.

All client names, contacts, incident states and policies are fictional. This
suite is defined in `evals/wiki_compare/workflows.py`; it does not redistribute
or depend on the user's private wiki. Supply your own wiki skill file.

## Workflows

| Scenario | Agent task | Independent checks |
| --- | --- | --- |
| Incident handoff | Combine project knowledge with a captured incident board into a local handoff | Merged PR versus tracker state, attributed production/QA reports, unresolved decision, unknown date, complete-page citations, no knowledge writeback |
| Requirements correction | Apply a daily-feed correction to the existing delivery page and current summary | Both saved pages change, previous cadence is historical, CSV/fields/unknown date/proposal survive, identity and sources survive, search verifies the update |
| Conflicting evidence | Capture hourly client demand versus daily vendor support as one open question | Both dated claims, resolved context links, real input source, no inferred replacement of the agreed requirement |
| Client isolation | Inspect two clients with the same filename and, in Portable KB, the same UUID; change only one | Northstar 45 days, Harbor 7 days, both complete scoped reads, unchanged alternate corpus and active selection |
| Untrusted notes | Ingest a sourced draft from meeting notes containing an embedded instruction | Reported QA, unresolved decision, proposal remains unapproved, unchanged established pages, no fabricated review or observed marker-command execution |
| Runbook move | Rename a runbook and repair inbound links/navigation without losing identity | Original removed, substantive body and provenance preserved, inbound targets and display labels preserved; an unsupported CLI operation is recorded as blocked |

These are multi-step single-request workflows, not a multi-turn user simulator.
The matching unit is the requested outcome and evidence. Wiki agents use ordinary
file tools and their native schema/index/log/source conventions. Portable KB
agents use the packaged CLI, staged previews/applies, generated indexes and
honest draft metadata. The move scenario exercises `pkb knowledge move` when available; older CLI artifacts are scored as blocked only after observed help and an unchanged brain. Whole-wiki import remains outside the production CLI.

## Prepare, run and compare

Install the repository's development dependencies and use an absolute path to a
working standalone CLI containing the link-navigation feature. Preparation
invokes the real CLI for setup, skill installation, creation of draft fixtures,
brain installation and keyword indexing. It makes no agent/model calls.

```sh
python -m evals.wiki_compare prepare-agentic \
  --cli /absolute/path/to/pkb \
  --wiki-skill /absolute/path/to/llm-wiki/SKILL.md \
  --output /tmp/pkb-workflows --repetitions 2

python -m evals.wiki_compare run-agentic \
  --output /tmp/pkb-workflows/wiki --jobs 2
python -m evals.wiki_compare run-agentic \
  --output /tmp/pkb-workflows/portable-kb --jobs 2

python -m evals.wiki_compare compare-agentic \
  /tmp/pkb-workflows/wiki/report.json \
  /tmp/pkb-workflows/portable-kb/report.json \
  --output /tmp/pkb-workflows/comparison
```

Use repeated `--scenario <name>` flags to select a subset. Preparation refuses
reused output directories and supports 1–10 repetitions. Each task/repetition
has fresh copies, HOME/XDG paths, an immutable incoming evidence file, the actual
skill, a prompt digest and independently captured initial state. Incoming
`evidence/` files are ordinary user-supplied documents outside the managed brain;
read them with normal file tools. Raw managed Portable KB files remain outside
the agent's interface.

`run-agentic` uses the existing pluggable Codex-compatible runner and requires
normal backend access. Runs remain opt-in. For explicitly delegated foreground
chat agents, use the [recorded-shell adapter](wiki-comparison.md#prepare-and-run)
for every shell action, then finish the structured response and grade:

```sh
python -m evals.agent_cli.observer \
  --case /tmp/pkb-workflows/wiki/incident-handoff-r1 \
  exec --command 'cat ../prompt.txt'
# The agent reads its skill and works through this same observer.
python -m evals.agent_cli.observer \
  --case /tmp/pkb-workflows/wiki/incident-handoff-r1 \
  finish --final-file /tmp/pkb-workflows/wiki/incident-handoff-r1/work/agent-final.json
python -m evals.wiki_compare grade-agentic --output /tmp/pkb-workflows/wiki
```

The response contract names `outcome`, factual `answers` with scoped citations,
and a result/blocker summary. Wiki citations accept the exact relative page path
or its absolute path within that case and client scope. Portable KB citations
must include the saved item's actual UUID, path and full commit. Complete reads
must be independently observed; snippets and guessed citations do not qualify.

## What the scores mean

Task completion and constraint adherence are separate. `completed`, `blocked`,
`failed` and `incomplete` describe the task; `pass`, `fail` and `incomplete`
describe observed constraints. Overall passing requires completed work and all
constraints. A truthful unsupported move with an unchanged healthy brain receives
`blocked`, not completion credit. Grading exits nonzero for blocked, failed or
incomplete cases so automation cannot treat them as completed tasks.

The controller checks final saved content, real evidence sources, corpus/link
health, navigation, source/checkout agreement, mutation allowlists, preservation
of creation/identity/unknown fields and existing sources, unchanged alternate
clients, active selection, skill/prompt/input integrity, and honest draft state.
Every successful native save needs an earlier completed preview with the same
substantive arguments and input-file digests. Preview IDs do not count as saved
create IDs. The final saved body must correspond to a successful supported CLI
save. Indirect move repairs must match the recorded CLI diff applied to the
initial caller content and the saved citation commit. Native move trials also
require complete retrieval of every changed index/log document at the final
saved commit after apply. Native correction trials must rebuild keyword search
after saving and
query it successfully; wiki correction trials must search the updated text.

Metrics include observed shell/CLI calls and failures, captured output
characters, complete final-page reads, changed knowledge pages and foreground
elapsed time. Errors are retained even when an agent recovers. Comparison checks
suite/corpus/repetition/artifact/skill fingerprints, identical task coverage and
the grader digest. Timing comparisons use only paired trials that both arms
completed with constraints. No token, cost or reasoning telemetry is invented.

This is a small synthetic workload with declared deterministic semantic checks.
It cannot establish a general winner or guarantee that arbitrary prose contains
no hallucinations. The foreground adapter records shell actions but is not an
adversarial-runner security sandbox; the bounded embedded-command check does not
recognize every possible program that could execute a command. Full captured
outputs may exceed a runner's displayed context. Preserve traces and input
artifacts, review suspicious results, and keep pilot diagnostics separate from
matched scored runs. It does not send messages, publish knowledge, touch a live
tracker, or inspect production systems.

## First measured run

Results from the matched run and retained pilot diagnostics are recorded in
[the results note](agentic-workflow-results.md). A targeted
[move follow-up](knowledge-move-results.md) verifies the new supported CLI move.
[Reserved document verification](document-retrieval-results.md) checks complete
saved navigation/history reads with the updated CLI and installed skill.
Future scenarios can add staged
sessions, noisy evidence volumes, sync conflicts, authorized publication and
recovery once their interfaces and independent checks are available. Extend
`TASKS`, fixture evidence, grading and regression tests together; do not substitute
mocked product outputs for actual CLI execution.
