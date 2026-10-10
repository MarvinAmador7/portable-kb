# Natural business questions

This opt-in suite asks five ordinary questions of an existing, deliberately noisy
synthetic wiki. Both skills receive the same 57-page corpus: business records,
stale/confident derived summaries, other-company comparisons and unrelated notes.
The user task supplies only company, as-of date and the question. There are no
answer categories, evidence instructions, qualification checklists or named source
files in the question prompt. Loading the selected skill is explicit: this tests
skill-guided behavior, not automatic discovery or activation.

The scenarios are customer delivery, scoped refund policy, revenue causality,
changed-assumption attention after handoffs, and missing-original evidence.
Each scenario has two independent repetitions per arm: 20 final question trials.
The handoff scenario adds two separate maintenance agents before each final answer,
bringing the total to 28 fresh sessions. Each maintenance user task says only
“Add today's engineering update to the brain.” A fresh session receives only the
saved wiki, frozen skill and new input, without the prior chat/answer/trace.

## Preparation and execution

```bash
python -m evals.groundray.natural prepare \
  --root /tmp/groundray-natural \
  --groundray .agents/skills/groundray \
  --wiki-skill /private/supplied-wiki-skill.md
```

Dispatch fresh foreground agents, without parent context. Each agent first reads
its `work/prompt.txt` and `work/skill/SKILL.md`, then completes the task using only
its workspace. All shell reads/writes run through `evals.agent_cli.observer` as
in the [continuity pilot](README.md). Save the normal user response in `answer.md`
and the exact same text in `agent-final.json` under the single `answer` key;
observer `finish` records that JSON. This output wrapper carries no answer labels.

For each handoff case, after an actual completed maintenance session:

```bash
python -m evals.groundray.natural advance \
  --root /tmp/groundray-natural --case handoff-wiki-1 --phase 2
```

A different fresh agent ingests the second update. Then advance to phase 3 and
dispatch another fresh agent for the ordinary question. Preserve failed sessions
and unmodified outputs; do not coach, repair or rerun to improve scores.

```bash
python -m evals.groundray.natural audit \
  --root /tmp/groundray-natural --output /tmp/groundray-natural/audit.json
python -m evals.groundray.natural blind-packet --root /tmp/groundray-natural
```

## Scoring

Four semantic criteria per scenario are fixed in `natural_scenarios.py` before
dispatch, alongside required evidence-read probes. They are outside the agent
workspace. Free-form answers are evaluated by a separate fresh reviewer using a
shuffled packet of questions, records, rubric and outputs. Skill/arm identifiers
and workspace prefixes are redacted. The reviewer must return each binary judgment
with quoted support or a concrete omission/overstatement, plus unsupported
material assertions. Root inspects disputed judgments against the unchanged
answer and fixed rubric. Report disagreements and adjustments explicitly; do not
quietly change the rubric or select the more favorable score.

Semantic judgments are model assessments, not deterministic truth verification.
Blinding hides labels, but style can still hint at the skill. Do not publish them
as a perfect oracle. Evidence probes independently measure complete record
exposure in successful observed outputs. This is a proxy for inspection, not
comprehension. Source names in an answer are discovery/citation signals, not proof
that a passage supports the claim; qualitative citation review remains necessary.

Audit old raw source bytes, current source captures, unchanged skills and saved
decision reasoning. New captures may have a metadata envelope if their supplied
payload remains unchanged. The audit distinguishes literal document preservation
from added YAML capture fields that preserve every original field and the exact
business body. The latter is not lost evidence. Both measurements remain visible.
The blinded packet includes retained derived pages as well as primary records;
otherwise a valid date or lineage assertion may appear unsupported to the judge.
Derived pages can be revised by an authorized ingest;
there is no artificial append-only instruction in these ordinary maintenance tasks.
Judge whether original approval and forecast chronology remain recoverable, not
whether every derived byte is unchanged. Question-session filing/logging is recorded
as a workflow difference, rather than automatically treated as semantic failure.

## Limits

The corpus deliberately contains authority and scope traps; it is not sampled
from real businesses. Both skills are explicitly loaded and run on one inherited,
unreported chat model. Two repetitions give descriptive results only. This is
Markdown skill evaluation, not a Portable KB CLI comparison. The fixture's fictional
approval records are supplied evidence, not independently authenticated approvals.
Case boundaries and observer use are agent instructions, not OS-enforced isolation.
Tokens, cost and reasoning traces may be unavailable; elapsed time includes thinking.
Private baseline skill text and raw trial traces are excluded from public artifacts.
