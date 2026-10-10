# Groundray, reduced to an evidence check

The [108-task experiment](../groundray-product-evaluation.md) found no clear
accuracy advantage for the full Groundray skill over an existing wiki workflow.
This candidate asks a smaller product question: **does showing why an answer is
supported make a company decision easier to inspect?**

The [experimental skill](../../.agents/skills/groundray-lite/SKILL.md) is one file.
It reads relevant originals, keeps claims scoped, shows the source or calculation,
and identifies a gap only when that gap changes the decision. It uses existing
wiki conventions, preserves history when asked to edit, and answers read-only
by default. It adds no required profile fields, storage layout or CLI behavior.

To try it in a supporting agent, invoke `$groundray-lite` or explicitly ask the
agent to read the linked skill and use it for the selected company. It is a
separate candidate; the full Groundray remains available. No global installation,
production installer integration or release is performed.

Start with [the Mosaic evidence view](answer.md). It asks whether three board
claims can be repeated: a blanket USD80 rate, redesign-driven 85% margin, and a
guaranteed November 20 launch. The short conclusion is followed by the exact
record/row/quote behind each disputed assertion, its scope and the next needed
decision. Ordinary Markdown links carry the preserved sources with this folder.

The demo is hand-authored by Codex from a selected fictional fixture, not an
observed skill run. All 21 source records have [origins and hashes](source-manifest.json).
Four owner cards are supplied explicitly for illustration, without pretending
they were obtained through questions or authenticating real approvals. Initial
records, corrections and later updates remain distinct. Case dates are fictional.

Use the [owner exercise](owner-exercise.md) to record a person's actual decision,
time, inspections and remaining questions. A [competent concise cited answer](ordinary-answer.md)
provides an alternative presentation. The two drafts share the facts but differ
in length and explanation, so a comparison cannot isolate the skill or format.
No benefit or human test result is claimed until observations exist. Useful
feedback may also be that the extra explanation is unnecessary.

Astra's read-only review found that the draft only exposed citations for disputed
claims. The candidate now cites every consequential assertion, with expanded
reasoning where needed. Follow-up review found no new actionable issues. Source
hashes, arithmetic and links after moving the demo folder were checked; these
checks do not measure actual owner usefulness.
