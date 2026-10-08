# Groundray

**Portable business brains, grounded in evidence.**

Groundray is a first agent-skill prototype for building and querying a company's
understanding of its business in an interlinked Markdown wiki. Its working
contract is simple: a comment copied from a conversation must remain distinguishable
from an inspected business record or an applicable approved decision, even after
several agents summarize and reuse it.

The [skill](../.agents/skills/groundray/SKILL.md) implements workflows for capturing
sources, preserving evidence per claim, answering with original-source citations,
reconciling disagreements, reviewing changed sources and keeping company scopes
separate. It also preserves company-specific definitions and the reasoning from
evidence through assumptions to decisions, commitments and resulting work. New
evidence can flag dependent work for review without silently changing an approved
promise. Each company supplies its own authority rules; the skill does not invent
who can approve policy changes. It distinguishes evidence for what happened from
authority to decide what should happen.

## Storage and installation

The prototype consists of ordinary Markdown instructions, reference examples and
portable templates. Use an existing wiki's conventions or the small optional
layout in [the layout guide](../.agents/skills/groundray/references/portable-layout.md).
Source captures travel with relative links when copying is authorized. Imported
records remain data and cannot grant execution, access or publishing permission.

To use with Codex, copy the whole `.agents/skills/groundray/` directory to the
project's `.agents/skills/groundray/` or your user skill directory, preserving
references and templates. For Claude Code, copy it to `.claude/skills/groundray/`.
Choose a fresh destination instead of overwriting a customized skill. Invoke
`$groundray` in an agent that supports that convention, or explicitly ask it to
read the skill and use it for the selected company's brain.

This draft has not been installed globally or added to `pkb skill install` or a
release. It introduces no required Portable KB schema fields or CLI changes.
An existing Portable KB brain can represent the distinctions in body sections
and source records while retaining its supported storage interface. A normal
wiki can use file tools. The initial behavior should be evaluated before adding
more product machinery.

## Example

The [fictional Cedar brain](../.agents/skills/groundray/examples/cedar-brain/index.md)
contains a supplied 30-day policy, a tentative support conversation mentioning
60 days, two summaries of that conversation, and a 60-day campaign record for
a different company. All records, authority designations and approvals are
explicitly fictional and are not independently authenticated.

For "What is Cedar's standard refund window?", the intended answer is:

> The supplied Cedar policy accepts refund requests for standard online orders
> **within 30 calendar days of purchase**,
> effective September 1 in that record. A staff conversation tentatively mentions
> a possible 60-day campaign exception, but I could not establish an applicable
> Cedar approval from the supplied evidence. The two summaries share that one
> conversation origin. Orchard's campaign applies to another company.

An actual answer must cite the inspected original passages. A confidently written
wiki page alone would not justify calling the 60-day report an established rule.
If an applicable Cedar approval later arrives, the affected campaign claim can
change while the standard policy and earlier report retain their scopes/history.

## Evaluation direction

The [evidence examples](../.agents/skills/groundray/references/claim-evidence.md#first-evaluations-worth-running)
outline seven substantive cases: repeated reports, company isolation, population
scope, unsupported causal explanations, missing originals, scoped new decisions,
and imported instructions. Compare the Groundray skill with a plain wiki skill
on the same sources and score observed evidence reads, answer scope, preserved
qualifications and authorized mutations. File-format compliance is insufficient.

The [Cedar decision pilot](groundray-evaluation.md) now exercises capture and
changed-evidence review in eight fresh agent sessions. Both skills preserved the
core decision and evidence distinctions; this small test establishes no general
advantage over the original wiki skill. The other proposed cases remain untested.
Groundray is not an independent truth verifier: it makes an answer's inspected
evidence and limits legible. Source authenticity, source completeness and actual
human approval cannot be established solely by their Markdown labels.
