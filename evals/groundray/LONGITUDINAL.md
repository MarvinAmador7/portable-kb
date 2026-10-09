# Longitudinal business brains

Opt-in development experiment, comparing the user-supplied original wiki skill,
that exact skill plus a 64-word grounding policy, and the frozen Groundray skill.
The policy text is in `longitudinal_scenarios.py`; the original private skill is
not redistributed. No production CLI, schema or installed skill is changed.

Five fictional companies exercise refunds, warranties, subscription discounts,
service-response targets and cancellation terms. Each has six updates: proposal
and copied assertions, scoped approval, another company's approval, measured
finance reconciliation, prospective withdrawal, and loss of a source attachment.
Each update is followed by an ordinary question. Every operation uses a separate
fresh foreground agent: 15 chains, 180 sessions, 90 scored answers. These are five
variations of one designed event pattern, not five independently sampled businesses.

Each handoff carries only the saved Markdown brain and unchanged skill. Question
filing/logging is permitted when chosen by a skill and carries into the next
update. User prompts provide company, as-of date and a short ingest request or
business question, without the rubric or an evidence checklist. Skills are
explicitly loaded. All trial shell actions use the existing recorded observer.
Boundaries are protocol instructions, not OS isolation. No coaching, output
repair or selective reruns; preserve interruptions and incomplete sessions.

Preparation:

```bash
python -m evals.groundray.longitudinal prepare --root /tmp/longitudinal \
  --groundray .agents/skills/groundray --wiki-skill /private/wiki-skill.md
```

Dispatch `session-01` as a fresh agent, read `work/prompt.txt` and
`work/skill/SKILL.md`, and use `evals.agent_cli.observer` to execute commands.
Save the normal response in `answer.md` and identical text in `agent-final.json`
under the sole `answer` key; observer `finish` records the result. After completion:

```bash
python -m evals.groundray.longitudinal advance --root /tmp/longitudinal \
  --case cedar-wiki --phase 2
```

Repeat with a new agent for every phase through 12. Odd phases ingest; even phases
answer. Phase 11 simulates archive loss by removing standalone captures with all
original finance-note metadata and the same body, ignoring only boundary newline characters (added capture fields
are allowed).
It never rewrites derived pages or removes original payloads embedded in larger
authored pages. Record removed paths. If embedded evidence survives, credit an
honest agent that inspects it; do not demand a false missing-original assertion.

```bash
python -m evals.groundray.longitudinal audit --root /tmp/longitudinal \
  --output /tmp/longitudinal/audit.json
python -m evals.groundray.longitudinal blind-packet --root /tmp/longitudinal
```

Four semantic criteria per round are frozen before dispatch. Separate blinded
reviewers receive shuffled answers, questions, rubrics, chronological supplied
records, and each answer session's actual retained archive. Grade using only
records available by that round; later updates are not evidence an earlier agent
could inspect. Require binary judgments, quotations/reasons and material
unsupported claims. Empty answers fail. Root checks disputed judgments and
retained history; retain original reviews and publish any corrections explicitly.
Blinding removes arm labels and case paths, but writing style may reveal the arm.
Model judgment is not deterministic truth verification or source authentication.

Report semantic scores, unsupported approved-fact assertions, lost scope/history,
prospective withdrawal behavior, source preservation, query mutations, file growth
and elapsed time. Capture metadata additions are not counted as lost original
content. Timing is descriptive with an inherited, unknown model and uncontrolled
host scheduling; no token/cost claims. The short policy ablation tests whether
Groundray's additional instructions help beyond a few grounding rules; it does
not isolate every individual rule or establish a general product winner.
