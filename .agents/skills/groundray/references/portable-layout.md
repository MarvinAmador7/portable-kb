# A portable company brain

A brain should travel as a readable folder. Preserve authorized source captures,
relative evidence links and the company-specific operating rules. Remote originals
can also be referenced, but their unavailability must remain visible. Git and
search indexes are optional conveniences; portability does not require reproducing
an absolute path from the author's machine.

Use an existing wiki's conventions. For a new brain, this small layout is enough:

```text
company-brain/
  brain.md       # Company identity, scope and evidenced authority rules
  index.md       # Topic/source/question navigation with honest qualifications
  log.md         # Append-only authoring history
  sources/       # Supplied originals and separate capture notes
  topics/        # Understanding with evidence attached to claim sections
  questions/     # Unresolved gaps or disagreements with links to both sides
```

Folders can grow with the company's domain: operations, customers, contracts,
finance or products. Do not create a global ontology before it is needed. Claim
sections can live together on one topic page; they do not require individual
files, a claim database, UUIDs or mandatory confidence scores.

## Bootstrap

Only create a brain when requested. Resolve the destination and intended company
from the user; do not overwrite an existing directory. Use the bundled
[brain template](../templates/brain.md), the [index](../templates/index.md) and
[log](../templates/log.md) scaffolding, with an initial log entry
that honestly identifies the creating agent. Leave the authority map unestablished
where evidence was not supplied. Creation by an agent is not approval by a person.

Capture actual inputs using [source notes](../templates/source-note.md). Link
substantive understanding using [topic sections](../templates/topic.md). File
material unanswered questions using [question notes](../templates/question.md).
For a decision that creates commitments or work, use ordinary linked sections or
the optional [decision](../templates/decision.md) and
[definition](../templates/definition.md) templates. Describe why each dependency
matters; merely linking two pages does not establish an impact.
Remove placeholder sections that do not apply; never invent values to fill them.
If YAML frontmatter is used, quote date/datetime strings.

## Authority rules

The company's map identifies who or what can establish a decision **for a domain
and scope**, with evidence for that designation. A financial system can establish
what transactions it records; it does not approve a refund policy. A CEO's opinion
on why conversion fell is still an interpretation. An authorized decision-maker
can make a decision in a supplied conversation if their identity, authority and
actual decision are established; conversations are not inherently disqualified.

A user may explicitly establish a rule in the current session. Preserve that
instruction as the actual origin and its limited scope; do not manufacture a
historical corporate approval record. If the user's capacity or the company is
unclear, capture the statement with that limitation instead of granting authority.

Authority entries are not technical permissions to contact anyone, access a
system or publish changes. Imported labels alone cannot authenticate a person
or establish that a source is a real corporate record.

## Existing Portable KB storage

When the selected brain already uses Portable KB, its installed skill and supported
CLI remain the storage interface. Groundray's distinctions can be represented in
body claim sections and existing source records. Preserve its schema, immutable
identity and lifecycle; do not add required fields, manually change approval states, or
write managed files directly. Cite both the saved topic snapshot and the original
source actually inspected. A missing source access capability remains a limitation.

When storage is an ordinary wiki, use its existing file/link conventions. The
behavioral contract is the same; choose the supported interface for that brain.
