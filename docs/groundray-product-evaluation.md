# Building company brains from messy records

The intensive experiment completed **108 fresh-agent tasks across 18 chains**,
starting from empty brains for three different businesses. The original supplied
Hermes wiki skill, the same skill plus a 64-word grounding policy, and Groundray
all retained useful scoped knowledge, incorporated corrections and handed it to
new operators. **This run establishes no clear accuracy advantage for Groundray.**

Reviewers identified no material unsupported assertions. One original-wiki briefing
omitted two parts of the selected coverage checklist; one grounded-wiki saved
handoff page used ten absolute workspace links. Groundray consistently answered
without changing the brain, while both wiki arms filed every query. Groundray
also produced larger archives and used more recorded shell commands.

These findings extend the [180-task continuity study](groundray-longitudinal-evaluation.md).
The [public result](../evals/groundray/results/2026-10-09-company-brain-product-v1.json)
contains delivered answers, all 576 facet judgments, owner routes, source/evaluator
hashes, mechanical observations and explicit grading corrections.

## What was tested

| Fictional business | Records and decisions |
| --- | --- |
| Kestrel Cloud | Subscription/setup reconciliation, recurring versus signed deal value, production acceptance, scoped renewal credit, unlike onboarding samples and launch dependencies. Kestrel Labs shares names but is a separate company. |
| Mosaic Studio | Retainer versus ad-hoc rates, fees versus invoices/tax/pipeline, suspected versus posted cost reversal, mockup acceptance versus launch, accessibility gates and independent Tint work. Mosaic Events is separate. |
| Vale Supply | Each/carton and company boundaries, stock reservations and quarantine, price versus allocation authority, deposits versus earned revenue, partial receipt/release and fulfillment risk. Vale Service is separate. |

Each business supplies **54 initial Markdown, text and CSV records**, including
36 ordinary operations notes across 12 topics and three batches. Initial payloads
are approximately 23–24 KB per business. No brain, authority register or canonical
company metric is seeded. Missing rules, unavailable originals, genuine scoped
approvals, estimates and derivative sales reports coexist.

Three arms × three businesses × two repetitions produce 18 chains. Each chain
uses six distinct agents, with no inherited parent context:

1. Build a portable brain and optionally ask up to six owner questions.
2. Integrate only the replies to questions actually asked.
3. Deliver an ordinary operating briefing.
4. Apply owner corrections and reconciled records.
5. Ingest new operational evidence and stale copied summaries.
6. Let a fresh operator take over from the saved brain and frozen skill.

Only the brain and skill carry forward. Question-time filing is permitted and
carried where the arm chooses it. The final brain is measured **after phase 6**,
including any final query filing, rather than immediately before the handoff.
Source ordering is shuffled per repetition and identical across arms; agents may
ignore that ordering. Skills, tasks, source fixtures and review rules stayed frozen.

## Coverage and usefulness

Each cell below gives **supported / qualified / unsupported / missing** judgments
out of 48 facets: six items × eight selected material issues. Qualified means a
real unresolved evidence or authority issue remains honestly scoped. More supported
statuses are not inherently better: cases receive different owner replies and
separate model reviewers can draw that boundary differently.

| Snapshot | Original wiki | Wiki + grounding | Groundray |
| --- | ---: | ---: | ---: |
| Initial compiled brain | 26 / 22 / 0 / 0 | 28 / 20 / 0 / 0 | 25 / 23 / 0 / 0 |
| First delivered briefing | 33 / 13 / 0 / 2 | 38 / 10 / 0 / 0 | 30 / 18 / 0 / 0 |
| Final compiled brain | 40 / 8 / 0 / 0 | 43 / 5 / 0 / 0 | 37 / 11 / 0 / 0 |
| Final delivered briefing | 40 / 8 / 0 / 0 | 43 / 5 / 0 / 0 | 37 / 11 / 0 / 0 |

Supported provenance was judged present for **48/48 expressed facets in every
stage and arm**. Applied usefulness judgments also total 48/48 per stage/arm.
These are separate judgments about expressed content, not a claim of complete
coverage: the two missing wiki facets retain useful and supported partial content.
The Mosaic/wiki repetition-1 first briefing separates Studio from Events and
correctly describes the Lumen launch gate, but omits Tint and PHOTO-8 independence.
Its compiled brain retains those details; saved pages do not repair an omission
in a delivered answer. Both final snapshots cover them.

The original blind reviews marked six Groundray cash facets less useful. Root
adjudication restored those six flags after checking the available records;
the original aggregate is **186/192 useful Groundray facets**, versus 192/192
for each wiki arm. Applied Groundray utility is 192/192. The explanation and full
original/applied judgments are published below; this is not an unqualified blind
192/192 result.

No material unsupported assertions were identified in any of the 24 reviewed
items per arm. This is an observed model-review result for eight selected issues,
not certification of the entire archive or real-world business truth.

## Correction and handoff continuity

| Final-brain check | Original wiki | Wiki + grounding | Groundray |
| --- | ---: | ---: | ---: |
| Corrected values reflected in current knowledge | 6/6 | 6/6 | 6/6 |
| Original records and prior reasoning recoverable | 6/6 | 6/6 | 6/6 |
| Affected work and unrelated exclusions preserved | 6/6 | 6/6 | 6/6 |
| Portable navigation and evidence | 6/6 | 5/6 | 6/6 |

Paired business/repetition comparisons found no consequential overclaim in any
arm. Kestrel has no selected coverage omission in either repetition. Mosaic has
the two first-briefing omissions in original-wiki repetition 1 and the saved-page
portability defect in grounded-wiki repetition 2. Vale has no selected coverage
omission; its cash utility disagreement is specifically documented. These isolated
differences do not establish a general winner.

Concrete recovered reasoning includes:

- Kestrel's corrected Birch split is USD7,200 annual subscription plus USD2,400
  setup. The current supplied calculation becomes USD1,800/month, while the
  former conditional USD2,000 remains history. This is a same-snapshot correction,
  not measured churn. Production export acceptance does not prove the earlier
  launch call happened or authorize a blanket renewal-credit offer.
- Mosaic's posted USD500 reversal changes Lumen cost from USD2,000 to USD1,500
  and scoped margin from 50% to 62.5%. The suspected duplicate remains historical;
  the improvement is not evidence that redesign caused profit. The November 23
  accessibility forecast threatens the November 17 gate/conditional November 20
  reservation without creating an approved new launch date or cancelling Tint.
- Vale's confirmed A90 correction and N receipt with only 40 of 100 saleable
  support 90 free each and a 30-each River shortage under the supplied reservation
  interpretation. Cases without the allocation reply can legitimately preserve
  conditional Gate-overlap scenarios: the initial copied instruction does not
  itself state that its 60 units are already included. Receipt is not dispatch,
  the USD1,800 deposit is not the USD4,800 quote as earned revenue, and O802 remains
  independent.

Grounded-wiki Mosaic repetition 2 archives ten absolute links in
`queries/ops-lead-handoff.md`, targeting the original session workspace. They
include commercial, owner, finance, QA and history pages and will not follow
relocation. Other local navigation and all sources survive; this is a defect in
that saved page rather than loss of the whole brain. The actual-path audit found
it after blind masking had replaced the private prefix with `brain/`. Four
unresolved `[[wikilinks]]` syntax examples in Kestrel schema pages are descriptive
examples, not operating citation failures. The static audit checks file targets,
not headings or ambiguous-name resolution.

## Work and owner-question burden

All 18 builders used six questions after the common prompt explicitly invited
owner clarification. This does not demonstrate spontaneous discovery. A separate
arm-blinded router selects at most one primary frozen card per question and returns
its whole text; adjacent details can be supplied, and partial replies need not
provide the requested original evidence.

| Observation, totals across six chains per arm | Original wiki | Wiki + grounding | Groundray |
| --- | ---: | ---: | ---: |
| Completed sessions / unchanged skill sessions | 36 / 36 | 36 / 36 | 36 / 36 |
| Owner questions submitted and replied to | 36 | 36 | 36 |
| Questions without a matching card | 10 | 9 | 10 |
| Questions redundant with supplied records | 1 | 0 | 1 |
| Distinct matched cards, summed per case | 25 | 25 | 21 |
| Question words | 511 | 588 | 538 |
| Initial source payload copies retained | 324/324 | 324/324 | 324/324 |
| Final source payload copies retained | 366/366 | 366/366 | 366/366 |
| Initial files / bytes | 455 / 518,582 | 533 / 569,923 | 750 / 821,040 |
| Final files / bytes | 512 / 828,630 | 600 / 963,902 | 859 / 1,208,818 |
| Query sessions changing the brain | 12/12 | 12/12 | 0/12 |
| Recorded shell commands | 317 | 323 | 379 |
| Nonzero recorded shell exits | 16 | 11 | 1 |

Matched-card counts are not all topics requested or issues resolved. Replies include
negative/unmatched responses. Words and counts are effort proxies, not human review
minutes. Payload retention allows outer archive wrappers and boundary newlines;
it measures preserved source text rather than independently verified facts.

Groundray's final archives are about **46% larger in bytes** than original wiki
and use about **20% more recorded commands**. More explicit captures, questions and
reasoning can make inspection easier, but these measurements do not demonstrate
that the extra machinery improves decisions. Wiki query filing can also be useful;
it was permitted behavior. Groundray's read-only answers provide a predictable
mutation boundary, not evidence of better accuracy.

Elapsed medians remain in the JSON for inspection, without speed rankings. The
recorded task window was October 9, 2026, **18:46:06–21:29:42 UTC**. Two coordination
transport pauses resumed the same unfinished agents with their existing contexts;
completed finals were retained. Dispatch-order adjustments filled idle slots, and
local tests ran concurrently. Timing includes these conditions. Nonzero exits
include agent-authored validation/script failures and guessed file paths; the
single Groundray exit is a guessed-file read during Mosaic correction. They are
not Portable KB CLI error rates: this study uses skills and file tools.

## Audit, corrections and limits

All 108 sessions passed recorded integrity checks, with **108 distinct assigned
task agents**. Checks cover frozen inputs/skills, empty starts or matching prior
brain snapshots, saved final/answer consistency, observer recording and no brain
symlinks. Protocol boundaries are not OS isolation. Eighteen fresh reviewers each
saw one arm-blinded chain with four snapshots; 576 exact quote/path validations
passed. Root additionally inspected disputed grades, omissions, scoped evidence
and actual link targets. This is targeted semantic review, not independent expert
adjudication of every facet.

The result explicitly preserves three kinds of correction:

- **Owner routing:** before reply dispatch or knowledge grading, Mosaic question
  10 changed from no card to the commercial card. It asks for authentic retainer
  approval evidence; scoped owner confirmation supplies a partial answer, using
  the same boundary as already-matched analogous questions. The original executed
  document remains unavailable. All other 107 route decisions stayed unchanged.
- **Portability:** one blind continuity pass changed to failure after inspecting
  the ten actual absolute saved links. Original and applied judgments are retained;
  no saved brain was repaired.
- **Cash utility:** six flags across both Vale/Groundray repetitions changed from
  false to true. The replies say no qualifying dispatch is *supplied*, not that a
  complete ledger certifies zero. Distinguishing the recorded deposit/quote,
  applying the supplied recognition rule, and identifying missing movement/ledger
  evidence is useful without a literal USD0 assertion. Qualified status and
  supported provenance stay unchanged. The same interpretation accepts the
  grounded-wiki answer that no recognized River revenue is established here.

No trial coaching, output repair, replacement trial or selective rerun occurred.
Full original/applied correction fields and reasons appear in `run_audit`, alongside
original blind aggregates, coordinator recovery records and unchanged evaluator
hashes. The private supplied skill, raw archives and full command traces remain
outside the public repository.

Reviewers see all snapshots of their chain together, so instructions cannot remove
all hindsight. Archive style can reveal the arm despite label masking. Usefulness
is model judged rather than a real owner's experience. Three fictional companies,
six chains per arm and eight selected issues cannot establish real company
reliability, source authenticity, automatic skill activation, large-corpus
retrieval or the necessity of a CLI/specification. Model identity is inherited and
unknown; no token/cost telemetry or real human review time was measured. November
case dates are fictional and separate from the October capture date.

The frozen evaluator passed **488 local tests with 87.10% coverage**, including real
QMD and native search; all six CI jobs passed at commit `5b03c9f`. This validates
repository/evaluator integration, not the truth of synthetic business assertions.
The [run instructions](../evals/groundray/PRODUCT.md) and public scenario generator
make the design inspectable. No production CLI, profile or Groundray skill changed.

The next discriminating experiment should measure owner/operator decision quality
and effort under constrained attention: larger evolving archives, unanticipated
questions, missing or conflicting company rules and independent human adjudication.
Repeating the same targeted facets with more chains would mainly repeat this
ceiling result.
