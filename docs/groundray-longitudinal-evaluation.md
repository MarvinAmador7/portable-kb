# Company brains across fresh-agent handoffs

All three approaches passed **30/30 answers and 120/120 semantic criteria**:
the original supplied Hermes wiki skill, that same skill plus a 64-word grounding
policy, and the full frozen Groundray skill. No material unsupported assertions
were identified by the reviewers. The larger experiment found **no factual-accuracy
advantage for Groundray**, including over the short-policy ablation.
It extends the [ordinary-question evaluation](groundray-natural-evaluation.md)
with repeated maintenance, prospective withdrawal and loss of a source attachment.

## Design

Five fictional company archives start with identical content across arms: 21
Markdown files each, including original records, company definitions and authority,
a derived policy page, navigation and 12 irrelevant operations notes. The domains
are Cedar refunds, Harbor warranties, Juniper subscription discounts, Quartz
first-response targets and Maple cancellation requests. They vary population,
approver, units and clock start, but share one crafted sequence of events.

| Round | New evidence | Question tests |
| --- | --- | --- |
| 1 | Staff proposal becomes an approved-policy assertion through two summaries. | Apply the approved standard; trace the assertion to its single unapproved origin. |
| 2 | Written approval grants a limited pilot, motivated by two interviews. | Preserve eligible population, entry window and units; distinguish rationale from measured benefit. |
| 3 | A different company approves broader terms; staff recommends copying them. | Keep company authority separate and refuse an unapproved blanket expansion. |
| 4 | Finance records reconcile margin decline; chat alleges vendor-price causation. | Calculate 70% to 60% as 10 percentage points, reconcile $8,000 write-off plus $2,000 freight, and avoid inferring pilot retention. |
| 5 | Prospective withdrawal protects existing terms; a newer handbook copies the old approval. | Keep November 6 qualifying terms, apply the standard to November 10 entries, revise W2 and keep W3 unchanged. |
| 6 | The original finance attachment and standalone captures disappear; summaries and repeated chat survive. | Distinguish remaining evidence from earlier inspection and avoid treating repeated rumors as corroboration. |

Each round has one ingestion session followed by one ordinary question. A separate
fresh delegated agent handles every operation: **15 chains, 180 task sessions and
90 scored answers**. Six successive maintenance handoffs per chain carry only the
saved brain and unchanged skill, without conversations or earlier agent traces.
Synthetic record dates run November 3–11, 2026; these are fictional case dates.

Prompts provide the company, as-of date and a short ingest instruction or business
question. They contain no evidence checklist, required citations or answer labels.
Skills are explicitly loaded. The original wiki behavior may log questions or
repair/file knowledge, and those edits carry into the next session. Groundray
specifies read-only question answering and permits maintenance during ingestion.
No semantic coaching, output repairs, selective reruns or trial retries occurred.
A dispatcher transport disconnect recovered on a subsequent existence check;
it did not restart a task agent or change its output.

## Results

| Measurement | Original wiki | Wiki + 64-word policy | Groundray |
| --- | ---: | ---: | ---: |
| Answers passing all criteria with no material overclaim | 30/30 | 30/30 | 30/30 |
| Semantic criteria passed | 120/120 | 120/120 | 120/120 |
| Answers with material unsupported assertions identified | 0 | 0 | 0 |
| Completed task sessions | 60/60 | 60/60 | 60/60 |
| Question sessions changing the brain | 30/30 | 30/30 | 0/30 |
| New captures preserving original fields and exact body | 63/65 | 62/65 | 65/65 |
| New captures preserved allowing only boundary newlines | 65/65 | 65/65 | 65/65 |
| Final retained supplied records, excluding removed F1 | 140/140 | 140/140 | 140/140 |
| Sessions preserving preexisting raw-directory bytes | 60/60 | 60/60 | 59/60 |
| Sessions keeping installed skill unchanged | 60/60 | 60/60 | 60/60 |
| Median question elapsed time | 42.2 s | 47.5 s | 46.6 s |
| Median ingestion elapsed time | 102.3 s | 109.6 s | 121.9 s |
| Recorded shell commands | 302 | 304 | 376 |
| Nonzero recorded shell exits | 18 | 26 | 5 |
| Total final files across five brains, from 105 initial files | 179 | 174 | 208 |
| Total final bytes across five brains, from 26,051 initial bytes | 235,637 | 275,716 | 315,939 |

Each arm passed all 20 criteria in every round across the five companies.
The 65 incoming captures and 140 final retained records per arm count copies,
not independent real-world facts verified. The exact-body differences are
boundary newlines, not lost business text; the raw-directory exception concerns
an authored capture note, explained below.

Wiki questions log the query and sometimes clarify, repair or file pages. That
maintenance can be useful. Groundray consistently follows its explicit read-only
answer contract, with authorized writes occurring during ingestion. This is the
clearest observed workflow distinction. The extra grounding policy and full skill
did not improve measured accuracy over the original wiki in these cases.

Groundray produced the largest archives and more recorded commands, with the
highest ingestion median. It did not show a question-time advantage over the
original wiki in this run. These are descriptive costs under different maintenance
and documentation conventions, not a controlled speed or efficiency comparison.
Nonzero exits include no-match searches, expected missing-source checks and four
agent self-validation assertion tracebacks; they do not count failed business
answers or Portable KB CLI failures. Agents continued within their original
sessions, without evaluator repairs or task reruns.

## What the answers and saved brains show

The original approval and withdrawal remain inspectable in all 15 final brains,
including their dates, applicable population, rationale and work implications.
The supplied policy standard, authority register and surviving records retain
their original metadata and business body. Derived pages can be rewritten without
erasing the original decision record. The final-record audit excludes only F1,
which the harness deliberately removes before round 6.

For Cedar, the practical distinction is an online VIP order entered November 6
retaining **60 calendar days from purchase**, while one entered November 10 uses
**30 calendar days from purchase**. P3 narrows eligibility prospectively; it does
not cancel previously granted terms or prove that the pilot failed. W2 needs new
entry instructions; W3 remains on standard terms. The newer handbook's date
does not give its copied P2 claim authority over P3.

After finance-source loss, remaining ledger totals still support the margin
calculation. The $8,000/$2,000 causal bridge survives as an attributed summary,
with reduced ability to inspect the original reconciliation. Earlier inspection
history and a digest do not restore the original bytes. The new operations
talking points repeat the staff chat and add no independent vendor-price evidence.
Loss of F1 does not make that competing claim true.

## Review and measurement

Four semantic criteria per round were frozen before dispatch. Five separate fresh
reviewers each graded 18 shuffled answers using the question, as-of date, rubric,
chronological supplied records and the actual retained archive for each answer.
Arm labels, skill names and case prefixes were removed. Reviewers were instructed
to use only evidence supplied by that round; global later records were also in
their packets, so this temporal boundary depends on reviewer compliance.
Writing style and archive conventions can partly reveal the arm.

Every judgment includes a quotation and record-specific reason. A material
unsupported assertion fails the answer even when all four criteria pass. Root
checks verbatim quotation support, withdrawal/source-loss answers, selected
earlier answers, retained records and decision history. Original reviewer files
and hashes are retained. These are model judgments, not human-reviewed accounting
verification or source authentication. All 360 quoted criterion judgments have
verbatim support in the scored answer. All 180 recorded answers match agent JSON;
13 `answer.md` copies have an extra final newline. The unchanged JSON answers are
the scored outputs, and original answer hashes remain in the public result.
All 165 handoffs match the previous saved brain after the explicitly recorded
source-loss removals.

During the run, a source matcher treated removal of the blank line immediately
after YAML frontmatter as lost content. Before any round-6 source-loss session
existed, the removal matcher was corrected to ignore only boundary newline
characters while still requiring every original metadata value and business-body
character. The strict measure remains alongside the supplemental measure.
Original and corrected harness hashes, timestamp and the zero phase-11 count at
discovery are retained. Inputs, skills and semantic rubrics did not change;
no agent was rerun or its answer repaired. Subsequent export changes added explicit
as-of dates and required complete stories before grading.

The raw-directory byte-preservation proxy includes agent-authored capture notes.
Cedar Groundray round 6 updates one such note's historical F1 locator and appends
a dated availability annotation. Its prior inspection date, digest and reported
facts remain. This is a byte-changing authored-note update, not alteration of a
supplied original. The report retains the proxy failure rather than relabeling it
as source loss or silently removing it.

## Reproduction and limits

Fixtures, rubrics and the short policy are in
[longitudinal_scenarios.py](../evals/groundray/longitudinal_scenarios.py).
The [harness guide](../evals/groundray/LONGITUDINAL.md) documents preparation,
fresh-session dispatch, auditing, blinded exports and strict aggregation.
The [public result](../evals/groundray/results/2026-10-08-longitudinal-business-v1.json)
contains sanitized answers, judgments, task dates, mechanical observations and
private-artifact hashes. Private supplied skill text and raw command traces remain
outside the repository. Hashes identify recorded artifacts; they do not authenticate
company facts or make private material publicly reproducible.

The runner is a Codex chat-host subagent with an inherited, unknown model identity.
Shell commands are recorded; reasoning, token and cost telemetry are unavailable.
Elapsed time runs from the first observer call through recorded completion;
it excludes dispatch waiting and reasoning before that first call. Host scheduling
and query-maintenance workloads differ. It supports a descriptive comparison only.
Case boundaries are instructions, not OS-enforced isolation.

There is one chain per company/arm, and the five companies are variations of one
designed event pattern. The small archives, clear authority records and narrow
questions may be too easy to distinguish these approaches. Ninety answers are
correlated within chains; 360 criterion judgments are not 360 independent facts
verified. Skills were loaded explicitly; automatic activation is untested.
No genuine approval/authorship authentication, hostile instructions, forged
records, large-corpus retrieval, production company records or Portable KB CLI
behavior was evaluated. These results cannot establish a general reliability
rate, an accuracy benefit from the KB specification, or a product winner.

The useful next challenge would vary event patterns, ambiguity and archive size
across multiple agent models and include company records with independently
checkable authority. More repetitions of this same successful pattern would
mainly increase the count without resolving those limitations.

Validation: the full suite passed 477 tests with real Tantivy/QMD and 87.10%
production coverage before three report tests were added. All nine longitudinal
harness/report tests pass after the final aggregation changes. Repository lint,
whitespace checks, result counts, all 360 quoted judgments and 11 local
documentation link targets pass. This experiment changes development evaluation
and documentation; production CLI, KB profile and Groundray skill are unchanged.
