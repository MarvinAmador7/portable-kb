# Groundray with ordinary business questions

Groundray and the original supplied Hermes wiki skill both answered all five
business scenarios correctly under the fixed rubric: **40/40 semantic checks per
arm**. Neither received evidence-handling instructions in the user question.
The experiment shows a workflow difference: Groundray kept question sessions
read-only and gave more direct original-record citations; wiki agents logged
answers and sometimes repaired or filed knowledge. No factual-accuracy advantage
was established.

## What agents received

A shared fictional Cedar Commerce archive contains 57 Markdown files and 2,668
words: original records, overconfident derived summaries, other-company policies,
and unrelated operations notes. Both skills receive the same seed and navigation
order within a repetition. Two repetitions per scenario per arm yield 20 final
question trials. Skills are explicitly loaded, so automatic activation is untested.

The complete user prompt is company, as-of date and an ordinary question. There
are no answer labels, source-reading instructions, provenance checklists or JSON
fact fields. Agents save their normal free-form response inside a neutral wrapper.

| Question | Evidence trap | Observed result in both arms |
| --- | --- | --- |
| Has Acme received Account Export? | Shipped/Done summaries versus staging and written acceptance | Customer delivery remains unestablished; repetition does not confirm receipt. |
| Can we offer 60-day refunds to all Cedar customers? | Staff rumor, VIP exception and another company's rule | Standard online orders retain 30 days; only scoped November VIP purchases get 60 days from purchase. |
| Why did Cedar's revenue fall in September? | A pricing explanation confidently repeated in the wiki | Ledger decline is 20%; reconciliation records $24,000 reversal plus $12,000 lower new sales; pricing causality remains unresolved. |
| What needs attention now on the Acme plan? | Forecast drift across fresh sessions | December 12 acceptance forecast threatens the unchanged December 1 commitment; review actual dependents with Mira and exclude F3. |
| The wiki says margin fell because vendors raised prices. How do you know? | Two summaries cite the same missing memo | Margin falls 72% to 64%; vendor causality is unverified, with one secondary lineage and a limited invoice sample. |

The attention scenario has two maintenance sessions before the question. Each
fresh agent receives only “Add today's engineering update to the brain,” the saved
brain and new input. E2 moves the forecast to November 25; E3 moves it to December 5.
A third fresh agent answers without previous conversations or traces. This adds
eight maintenance sessions, for **28 task sessions total**. No task agent was rerun,
coached with answers, or had its saved output repaired by the evaluator.

## Results

| Measurement | Original wiki skill | Groundray |
| --- | ---: | ---: |
| Question trials passing all four semantic criteria | 10/10 | 10/10 |
| Semantic criteria passed | 40/40 | 40/40 |
| Material unsupported assertions identified by reviewer | 0 | 0 |
| Required record exposures in observed command output | 42/42 | 42/42 |
| Preexisting raw source files unchanged | 220/220 | 220/220 |
| New forecasts preserving original fields and body | 4/4 | 4/4 |
| Question sessions changing the saved brain | 10/10 | 0/10 |
| Required original source filenames in answers | 32/42 | 42/42 |
| Median final-question elapsed time | 45.1 s | 34.5 s |

The citation difference comes from the two wiki handoff answers, which cite saved
topic pages rather than directly naming the original records. Those agents did
inspect the originals; their topic pages link to the evidence. Groundray places
the original links in the user answer. Filename presence is a citation signal,
not an automatic proof that a passage supports a sentence.

All wiki questions appended logs; some corrected summaries or filed analyses.
That can help a wiki improve through use. Groundray reported the evidence problems
while leaving the brain untouched during answers, matching its explicit answer
contract. Its maintenance agents made authorized updates in the ingestion sessions.
These are different mutation policies, not different accuracy scores.

Inspection of all four handoff chains found the original R17/Mira approval,
December 1 deadline, E1 rationale and accepted risk still recoverable. E1/E2/E3
chronology and I4 → X2 → C9 impact remained distinct from approval; F3 stayed
independent. Wiki agents rewrote derived pages while retaining that history;
Groundray appended dated reviews. No later estimate became an approved deadline.

Groundray's lower median time is descriptive. Wiki query logging/repair adds work,
and scheduling, model identity and token telemetry are not controlled sufficiently
to infer a general or causal speed advantage.

## Review and measurement corrections

Four binary semantic criteria per scenario were fixed before dispatch and kept
outside agent workspaces. A separate fresh reviewer received shuffled answers,
records and the rubric with skill labels and workspace prefixes removed. It gave
each judgment a supporting quotation or concrete reason. Root inspected answers,
saved history and disputed findings, without editing the trial outputs.

The first reviewer packet omitted derived seed pages. It flagged an answer saying
the monthly summary postdated October 21 because the packet lacked that date.
The unchanged monthly page says “Compiled by summarization agent, October 22.”
Supplying that missing context removed the flag; all 80 semantic criterion scores
remained passed. This is a judge-context correction, not an agent repair or rerun.

The initial capture matcher checks whether the entire input document survives
verbatim. Wiki adds ingestion/hash fields inside existing YAML headers, so literal
matching reports 0/4 new captures versus Groundray's 4/4. Inspection and a supplemental
matcher confirm every original metadata field and exact business body survived in
all four wiki captures. It would be misleading to call these added fields lost
evidence. Both literal and content-preserving measurements are retained. Existing
raw files remain byte-identical in both arms.

Original measurement/review hashes, corrections, criterion judgments and sanitized
case results are in the [public result](../evals/groundray/results/2026-10-08-natural-business-v1.json).
Private supplied skill text and raw command traces remain outside the repository.
The [harness guide](../evals/groundray/NATURAL.md) documents reproduction.

The full suite passed 470 tests with real Tantivy/QMD and 87.10% production coverage
before measurement refinement; 20 focused evaluation/skill tests passed afterward.
No production CLI, profile or skill behavior was changed by this experiment.

## Practical interpretation

The general wiki skill, used by this agent, already handles these evidence traps
well. Groundray's demonstrated distinction is its explicit company-evidence and
mutation contract, with consistent read-only answers and direct source links.
This experiment supports feasibility without proving improved factual accuracy.

Two repetitions against one deliberately constructed archive are not a reliability
estimate for real companies. Model judgments are not a truth oracle; writing style
can partly reveal a skill despite label blinding. Source exposure measures emitted
command output, not comprehension. Case boundaries are instructions rather than an
OS-enforced sandbox. Source authenticity and genuine approval were not verified.
The experiment does not exercise the Portable KB CLI, hostile source instructions,
forged identity, withdrawal or prolonged session drift.
