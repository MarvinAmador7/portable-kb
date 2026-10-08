# Groundray decision continuity pilot

Groundray and the original supplied Hermes wiki skill both recovered a saved
business decision and correctly assessed a changed forecast. Groundray passed
38/38 fixed answer checks; wiki passed 37/38. The difference is one decision-ID
classification, with ambiguity in the task wording. This is evidence that the
workflow is feasible, not evidence of a general winner or a CLI advantage.

## Case and method

All records and companies are fictional. Cedar Commerce accepts an Account Export
delivery promise for Acme by December 1. Its local definition requires production
deployment **and** written customer acceptance. R17 records the approval and
explicitly relies on an engineering estimate, E1. Acme's intention to sign is a
customer condition, not an executed contract. A sales comment repeated in two
summaries supplies one origin, not three independent confirmations.

An initial agent creates a portable brain from eight records, including the
decision, definition, forecast, commitment and work dependencies. A different
fresh agent receives that saved brain and three new records, without the prior
chat or final response. A revised forecast moves integration completion to
December 5, retaining seven calendar days for acceptance. The acceptance forecast
therefore becomes December 12: eleven days after the unchanged December 1 promise.
As of October 21, this establishes risk, not an observed failed commitment.

The dashboard's “Done” label means merged code; another company's “Delivered”
definition also means merged code. Neither satisfies Cedar's customer commitment.
Integration I4 affects dependent acceptance X2, commitment C9 and R17's schedule
reasoning. Refund FAQ F3 is context only and has no dependency on them.

Two repetitions per skill produce **four complete chains and eight sessions**.
Both arms receive identical records, tasks, output vocabulary and ordinary file
tools. Skills are frozen per case. Actions use the recorded-shell observer, with
no answer coaching or repaired agent outputs. Agents are instructed to avoid
evaluator files and other cases; this is a trial protocol, not an OS-enforced
filesystem sandbox. Recorded commands show no evaluator or cross-case reads.
The fixed answer labels were specified before dispatch. Chat model identity is
inherited/unknown; reasoning, token and cost telemetry are unavailable.

## Results

| Measurement | Original wiki skill | Groundray |
| --- | ---: | ---: |
| Capture sessions passing all checks | 2/2 | 2/2 |
| Strict complete chains passing all checks | 1/2 | 2/2 |
| Fixed answer checks | 37/38 | 38/38 |
| Final original source captures unchanged | 22/22 | 22/22 |
| Original decision history preserved | 2/2 | 2/2 |
| Fresh sessions observed recovering prior reasoning | 2/2 | 2/2 |
| Mean combined session elapsed time per chain | 301 s | 303 s |

Both skills returned the right forecast, preserved the approved deadline, rejected
merged-code delivery claims, kept signing unestablished, retained one report
origin, excluded F3, and identified Mira as the approver within the supplied rule.
Neither authenticated real-world approval or issued a new one.

One wiki follow-up lists I4/X2/C9 as affected IDs and treats R17 as the historical
decision, while the key also requires R17. Its review does recover R17's rationale
and preserve the original approval. The task asks for “register IDs,” although R17
is a decision referenced in the register, so the omission can reflect classification
rather than failed reasoning. Do not interpret the strict 1/2 versus 2/2 as proof
that Groundray prevents a business error the wiki skill cannot prevent.

Manual inspection also found one Groundray capture describing R17 as responding
to Acme's condition without explicitly labelling that sentence as inference. The
record states reliance on E1; Acme provides plausible commercial context, not a
recorded motive. It remains in the trial artifact and is a wording defect worth
testing further. The other Groundray capture labels that interpretation explicitly.

## Measurement correction and validation

The initial navigation checker wrongly treated basename wikilinks as file-relative
paths. Correcting it to accept unique page names and root-based wiki paths changes
one wiki session's navigation flag from failure to pass. Ambiguous page names remain
uncredited. The original report and grader are retained privately with hashes in
the [public synthetic result](../evals/groundray/results/2026-10-08-cedar-decision-v1.json).
No agents were rerun and strict chain outcomes remain unchanged. The public result
separates original recorded evaluator fingerprints from the corrected grader.

Negative controls cover correct-looking answers without observed source exposure,
rewritten originals, approval/forecast promotion, company leakage, duplicate
report origins, unrelated work, missing history, escaping paths, fresh-session
copies and wiki navigation. The full suite passed 464 tests at 87.10% production
coverage; 14 focused evaluation/skill tests passed after the navigation correction.
Repository lint and whitespace checks pass. Astra found no actionable issues in
read-only inspection of the updated skill; that review is not behavioral validation.

## What this establishes

A company brain can preserve definitions and decision reasoning in ordinary
Markdown, then help a fresh agent trace changed assumptions to dependent work.
Groundray specifies that behavior explicitly. The original wiki skill can also
perform it when the task requests it, at similar elapsed time in this pilot.

Source exposure is a reading proxy, not comprehension. Mechanical link checks
establish discoverability, not meaningful dependency prose; the qualitative review
is by the root assistant and is not blinded or independently scored. Shared tasks
request provenance and history, so this does not test spontaneous behavior on
brief business questions. One scenario and two repetitions per arm cannot establish
reliability across companies. Missing originals, genuine authority conflicts,
causal explanations, source withdrawal and hostile imported instructions remain
future cases. No real company records or Portable KB CLI operations were tested.

Reproduction instructions and the fictional corpus are in
[the development harness](../evals/groundray/README.md). Private supplied skill
text and raw agent traces are excluded from the repository.
