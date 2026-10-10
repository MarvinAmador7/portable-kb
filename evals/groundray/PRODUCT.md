# Company-brain formation and owner review

Opt-in synthetic product experiment. Compare the frozen original supplied Hermes
wiki skill, that same skill plus the existing 64-word grounding policy, and frozen
Groundray. No production CLI, profile or skill change. Do not tune any arm during
the run or silently repair/rerun outputs to improve its results.

Three independently designed businesses exercise different records and arithmetic:
Kestrel Cloud subscriptions, delivery and commercial offers; Mosaic Studio rates,
project costs and launch dependencies; Vale Supply physical stock, reservations,
unit/company boundaries, cash deposits and fulfillment. Each starts with 54 mixed
Markdown, text and CSV sources, including 36 ordinary operational records. There
is no seeded brain, authority register or predefined company metric. Some missing
rules can be established by a simulated owner; others require unavailable records
or future measurement. Genuine scoped acceptance and approval coexist with rumors.

Two repetitions per business/arm yield 18 chains and 108 fresh task sessions:

1. Create the brain and optionally ask up to six focused owner questions.
2. A new agent integrates replies to the questions actually asked.
3. A fresh colleague answers an ordinary operating-briefing request.
4. Another agent applies owner corrections and reconciled source versions.
5. Another ingests new operational evidence and stale copied summaries.
6. A new colleague takes over using only the portable saved brain and skill.

Only the saved brain and unchanged skill carry between sessions. Original intake
ordering is shuffled within each repetition and identical across arms. The model
may ignore that order. Question-time filing is permitted where the skill chooses
it. Case boundaries are protocol instructions, not OS-enforced isolation. Record
all task shell actions through the observer, including failed commands. Timing
starts at the first observer call, not at dispatch. Model identity is inherited
and may be unknown; no token/cost or human-time claims.

The final brain is captured after phase 6, including question-time filing if that
arm chooses it. It is not a measurement of the phase-5 brain before the operator
arrives. The [completed product experiment](../../docs/groundray-product-evaluation.md)
records results, routing/review corrections and execution limitations.

## Preparation and dispatch

```bash
python -m evals.groundray.product prepare --root /tmp/product-eval \
  --groundray .agents/skills/groundray --wiki-skill /private/wiki-skill.md
```

Dispatch each `session-01` to a separate agent with no parent context or rubric.
Agent writes its brain, ordinary response, and optional `owner-questions.json` as
`{"questions": ["natural question", ...]}`. Observer finish records the ordinary
answer from `agent-final.json`, with the same normal answer saved in `answer.md`.
No business fact fields or scoring checklist are given to agents.

After all six builds for a business finish:

```bash
python -m evals.groundray.product owner-packet --root /tmp/product-eval --world kestrel
```

A separate arm-blinded router reads that packet's natural questions, initial
records and six frozen owner cards. For every ID, select at most one card that
answers the question's actual primary issue, or `null` if none does. Do not give
extra cards for generic requests to approve everything, infer the skill arm, or
rewrite questions. Identify redundancy against supplied records. Save
`owner-route-kestrel.json` as `{"items": [{"id": "...", "card": "authority",
"reason": "specific routing rationale", "redundant_with_records": false}]}`.
Repeat for the other businesses. Malformed question artifacts receive no invented
questions; over-budget artifacts preserve the violation and answer only the first
six. Root checks routing consistency without supplying unasked cards.
Each match returns the whole frozen card, which can contain adjacent details;
it does not guarantee that the requested original evidence or every part of the
question is available. Preserve original and applied routing decisions when a
consistency check changes a match.

```bash
python -m evals.groundray.product advance --root /tmp/product-eval \
  --case kestrel-groundray-1 --phase 2
```

Advance through phase 6 with a distinct fresh agent each time. Owner replies are
simulated fixtures, not real people contacted or authenticated. A routing model's
interpretation may affect which information each case receives; preserve its
original decisions and assess that limitation. Owner questions, word counts,
redundancy and distinct requested topics are effort proxies, not measured human
review time or a requirement to spend all six questions.
The report's `owner_questions_answered` counts replies, including unmatched/negative
replies; `distinct_owner_cards_requested` counts distinct matched cards per case,
not all topics raised in natural language.

## Blinded review

```bash
python -m evals.groundray.product audit --root /tmp/product-eval --output /tmp/audit.json
python -m evals.groundray.product blind-packets --root /tmp/product-eval
```

Eighteen separate fresh reviewers each inspect one arm-blinded chain: the initial
brain, first briefing, final brain and final briefing. Each item includes only
records supplied by its phase, its actual archive and eight private material
facets. Later facts must not repair initial knowledge in the review. Initial
brain is before any owner reply; first briefing only has the cards actually
requested. Do not demand unprovided definitions or independently authenticated
real-world signatures. Inspect meaningful synthesis and explicit unresolved
questions; merely copying all raw sources is not compiling company knowledge.
The four snapshots share one reviewer context, so the phase-boundary instruction
reduces but cannot eliminate hindsight. Absolute-path masking can also hide a
portability defect; root must inspect the actual saved link targets separately.

For each facet record `status` (`supported`, `qualified`, `unsupported`, `missing`),
boolean `provenance_supported`, boolean `useful_for_next_operator`, actual `paths`,
verbatim `quote` and specific `reason`. Correct known facts should remain usable;
qualification without a real gap and blanket uncertainty should not count as
useful. A clearly scoped derivation with its formula can be supported without an
invented claim that it is the company's canonical metric. A question can compile
an unresolved issue but must identify the actual gap and relevant evidence.

List material unsupported assertions separately with a verbatim quote and reason;
attributed original rumors are not agent overclaims. Source links should support
the actual scoped claim, not just exist. For the final brain additionally grade
four boolean continuity checks: `correction_effect`, `history`, `scope_dependencies`
and `portability`, each with a concrete reason. These cover current reconciliation,
recoverable original records/reasoning, actual affected work and exclusions, and
usable relative navigation/evidence from the relocated saved folder. Do not award
correctness merely for obeying a template or marking everything uncertain.

Save `review-product-01.json` etc as `{"items": [{"id": "product-01-1-brain",
"facets": {"company": {"status": "supported", "provenance_supported": true,
"useful_for_next_operator": true, "paths": ["brain.md"], "quote": "...",
"reason": "..."}}, "material_unsupported_claims": [], "continuity": {}}]}` with
all eight exact facet keys and all four packet items. Final brain has all four
continuity keys. Root checks quotes, disputed judgments and actual saved artifacts;
any review corrections must preserve original judgments and be published explicitly.

```bash
python -m evals.groundray.product_report --root /tmp/product-eval --output /tmp/result.json
```

Report initial/final coverage, calibration, source-adjacent provenance, usable
knowledge, consequential overclaims, correction/history/dependency preservation,
question burden, source captures, query mutations, file growth and time separately.
There is no combined winner score. Compare within paired business/repetition and
inspect disagreements. Private supplied skill text and full command traces stay
outside the public repository; sanitized judgments and synthetic fixtures may be
published. Six chains per arm across three businesses still cannot establish real
company reliability or that a CLI/specification is necessary.
