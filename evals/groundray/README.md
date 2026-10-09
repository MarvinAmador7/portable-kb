# Company-decision continuity pilot

The later [natural-question suite](NATURAL.md) exercises five ordinary business
questions without evidence instructions in the user prompts.

The [longitudinal study](../../docs/groundray-longitudinal-evaluation.md) runs 180
fresh-agent tasks across three skill arms. The [product experiment](PRODUCT.md)
runs 108 tasks starting from empty company brains, with simulated owner review,
corrections and operator handoffs; its [results](../../docs/groundray-product-evaluation.md)
separate coverage, usefulness, portability and work burden.

Two fresh sessions per case: an agent builds a fictional Cedar Commerce brain;
a different agent recovers that saved brain and assesses a changed forecast.
Both the supplied Hermes wiki skill and Groundray receive identical records,
tasks, file tools and JSON output contracts. This evaluates skill-guided Markdown
authoring and continuity; it does not exercise or claim a Portable KB CLI benefit.

The supplied source labels do not authenticate approvals or people. A conditional
customer statement, supplied decision record, estimate, repeated sales report,
engineering completion label and another company's definition remain distinct.
The fixed answer key lives in `scenario.py`, outside agent workspaces.

## Run explicitly

Agent/model runs are opt-in. A development harness prepares isolated case folders:

```bash
python -m evals.groundray.harness prepare \
  --root /tmp/groundray-pilot \
  --groundray .agents/skills/groundray \
  --wiki-skill /private/supplied-wiki-skill.md
```

Preparation refuses an existing root and freezes per-case skills. Dispatch a fresh
foreground agent for each `session-1`, without parent conversation or evaluator
access. All actions go through the existing recorded-shell observer:

```bash
python -m evals.agent_cli.observer --case /tmp/groundray-pilot/wiki-1/session-1 \
  exec --command 'cat prompt.txt skill/SKILL.md'
```

The agent reads the task, skill, relevant references and records; saves the brain
and JSON; then calls observer `finish --final-file CASE/work/agent-final.json`.
Preserve failure traces. Do not coach answers, patch the brain, or rerun to improve
scores. After the first agent completes:

```bash
python -m evals.groundray.harness stage-second \
  --root /tmp/groundray-pilot --case wiki-1
```

Staging copies only the saved brain and frozen skill into a new `session-2`, with
new incoming records and the same common task. It does not copy the prior chat,
final response or command trace. A separate fresh agent performs this stage.
Repeat for all cases, then:

```bash
python -m evals.groundray.harness report \
  --root /tmp/groundray-pilot --output /tmp/groundray-pilot/report.json
```

## Measurements and limits

Deterministic checks cover fixed semantic answer fields, complete source exposure
in observed outputs, unchanged captured bytes, navigation, observed recovery of
the prior decision/reasoning pages, preserved original decision bytes, and unchanged
skills/incoming records. Second-stage history is append-only by the identical user
task, not an assumed universal wiki rule. Exposure is a reading proxy, not proof
of comprehension. Link presence does not prove a correct dependency explanation.

Inspect each saved brain and review manually for source-adjacent qualifications,
actual dependency reasoning, exclusions, uncertainty, honest agent authorship
and unresolved choices. Report manual findings separately from mechanical scores.
An exact JSON field alone is insufficient evidence of a good company brain.

Default two repetitions per arm produce four case chains and eight agent sessions,
not eight independent end-to-end trials. Shared instructions deliberately request
provenance and history: this pilot cannot measure spontaneous skill activation or
prove general superiority. Chat model, reasoning, tokens and cost may be unavailable;
record that limitation instead of inventing them. Elapsed time includes deliberation.

The private supplied wiki skill and raw traces stay outside the repository. Public
results can contain hashes, synthetic IDs, scores, aggregate timing and sanitized
manual findings, with no company data or pasted private source material.
