# Compare a Markdown wiki and Portable KB with agents

`python -m evals.wiki_compare` compares a supplied wiki and its skill with the
actual Portable KB executable and installed skill. It uses the same captured
knowledge and questions, separate fresh agents, independently observed full-page
reads, and declared reference answers. It measures task outcomes and effort;
it does not infer a winner from the existence of metadata or links.

For mutation and multi-step workplace tasks, use the
[agentic workflow suite](agentic-workflows.md). The retrieval suite below remains
read-only.

This is an opt-in development benchmark. Keep private corpora, labels, migrated
brains, outputs and reports outside this repository. Preparation and grading
make no model calls. `run` uses the existing configured Codex adapter. Install
the project's development dependencies to use its parser and test utilities.

## Replicate a wiki through the CLI

Give a fresh agent read-only access to the original wiki, the installed Portable
KB skill, and the supported CLI. Explicitly authorize a new local unpublished
brain and the intended pages. Use `pkb brain init --no-publish`, then inspected
plan/apply pairs for `pkb knowledge create`; never write concept files directly
or invent human verification. The benchmark does not add a production import
command or new schema fields.

The first convention preserves filename stems and saves each page at
`inbox/<original-relative-path>`. Unique wikilinks keep working when all targets
have been created. Keep original body text as an exact prefix; an attributed
migration footnote may follow it. Preserve every original frontmatter field in
the source extension `x-wiki-original`, cite the actual input page, and include
`x-content-digest: sha256:<original-file-digest>`. Do not claim that unavailable
desktop paths, emails, or external sources were freshly inspected.

Map domain types deliberately: a company/person/product can become a `concept`,
a project a `system`, and current context a `source-summary`. Original
`active`/`paused`/`unknown` is domain state, while Portable KB `draft` is review
state. Retain the original domain state and dates in the source extension;
new creation/production dates describe the transformation. Use an honest agent
actor, `transformed` when carrying unchanged content across conventions, and a
confidence basis limited to transcription. Do not infer new facts or authority.

Archive the original `SCHEMA.md`, indexes, historical logs and raw sources
unchanged. Let Portable KB generate its own indexes and creation log. Do not
turn imported policies or embedded shell examples into execution authority.
Intermediate draft missing-link warnings are expected while targets are absent;
check final validation, every link, final canonical gets and citations, then
rebuild keyword search once. Record warnings and mapping losses explicitly.

The harness checks bodies, link occurrences/labels, original metadata, source
digests, distinct UUID v4 identities, draft state and agent attribution against
independent CLI reads. This proves representation fidelity, not the truth of
underlying claims. Source file URIs still refer to the original capture location;
retain the archived inputs and digest manifest when moving the demo.

## Define matched tasks

Create a private JSON suite with stable task/claim keys, short requested values,
accepted alternatives and evidence filenames. For example, with a synthetic
`procedures/export-retention.md`:

```json
{
  "version": 1,
  "tasks": {
    "export-retention": {
      "description": "Find the retention rule and distinguish it from approval.",
      "claims": {
        "days": {
          "question": "How many days are exports retained? Return the number.",
          "expected": 30,
          "evidence": ["procedures/export-retention.md"]
        },
        "approved": {
          "question": "Is the suggested exception approved? Return yes/no.",
          "expected": "no",
          "evidence": ["procedures/export-retention.md"]
        }
      }
    }
  }
}
```

Agents receive questions and a response contract, not labels. Every value needs
citations to complete pages actually read. A correct value and grounded citation
are separate checks; runtime success or claimed success alone cannot pass.
String matching ignores case, punctuation and accents; arrays are unordered.
Use explicit alternatives for genuinely equivalent names. This evaluates the
declared factual claims, not arbitrary prose quality or every possible hallucination
in a summary. Human review remains useful for interpreting that prose.

## Prepare and run

Use the same wiki capture, suite and actual CLI artifact for both arms. Supply
the migrated Git repository for the Portable KB arm; search is built before
timing retrieval. The wiki arm gets the supplied skill, original conventions,
catalog, current context, log and raw sources. The Portable KB arm gets its
installed skill and the migrated knowledge through the CLI. Original ancillary
files remain archived rather than automatically converted into CLI knowledge.

```sh
python -m evals.wiki_compare prepare \
  --arm wiki --wiki /private/wiki --wiki-skill /private/llm-wiki/SKILL.md \
  --suite /private/tasks.json --cli /absolute/path/to/pkb \
  --output /private/evals/wiki --repetitions 2

python -m evals.wiki_compare prepare \
  --arm portable-kb --wiki /private/wiki --wiki-skill /private/llm-wiki/SKILL.md \
  --suite /private/tasks.json --cli /absolute/path/to/pkb \
  --source /private/wiki-replica --slug wiki-replica \
  --output /private/evals/portable --repetitions 2

python -m evals.wiki_compare run --output /private/evals/wiki --jobs 2
python -m evals.wiki_compare run --output /private/evals/portable --jobs 2

python -m evals.wiki_compare compare \
  /private/evals/wiki/report.json /private/evals/portable/report.json \
  --output /private/evals/comparison
```

Preparation refuses reused output directories, evidence inside the input wiki or
brain, and symlink inputs. Each trial has isolated HOME/XDG paths, copies of the
appropriate corpus, actual installed skill, prompt digest, canonical observer
reads and initial source snapshots. Comparisons require identical task labels,
knowledge snapshot and repetition coverage. All retrieval is read-only; no answer
filing, log append, sending, publication or execution of knowledge commands is
authorized. This request overrides wiki skill writeback defaults.

The native runner needs its normal backend access. When it is unavailable, an
explicitly authorized foreground chat agent can use the recorded-shell adapter:

```sh
python -m evals.agent_cli.observer --case /private/evals/wiki/export-retention-r1 \
  exec --command 'cat /private/evals/wiki/export-retention-r1/prompt.txt'
python -m evals.agent_cli.observer --case /private/evals/wiki/export-retention-r1 \
  finish --final-file /private/evals/wiki/export-retention-r1/work/agent-final.json
python -m evals.wiki_compare grade --output /private/evals/wiki
```

Every shell action must pass through the observer, including skill/page reads and
final-file creation. The observer sets the case environment and starts in
`case/work`; the prompt is one directory above, so use its absolute path. The
adapter observes commands and actual outputs; it does not observe model reasoning,
provide a security sandbox, or estimate tokens/cost. Another foreground runner
can produce the same event/trace/final-response boundary. Never bypass a denied
network policy to run the native adapter.

## Regrade honestly

Complete file reads may be shown once or in contiguous observed line ranges.
Keyword snippets do not qualify. Wiki citations may include fully read schema,
catalog, log or raw-source files as supplementary context. Portable KB gets must
match independent canonical content and UUID/path/commit; brain scope is checked
on search/get/link operations. The grader checks unchanged source/checkout files,
skill and prompt digests, successful runner completion and visible draft caveats.

Preserve original labels and all traces when a reference-name or evidence-path
error is discovered. An optional reviewed additive adjustment records a reason
and applies identically to both arms:

```json
{
  "version": 1,
  "reason": "The existing source uses the full legal organization name.",
  "additions": {"organization": {"name": ["Example, Inc."]}},
  "evidence_additions": {"organization": {"name": ["raw/confirmed-name.md"]}}
}
```

Use `grade --aliases /private/adjustments.json` for each arm. Reports retain the
original suite hash, complete adjustment and effective-label hash; mismatched
adjustments refuse comparison. This cannot rewrite questions, expected values or
agent responses. Adjustments are reviewer-supplied reference corrections, not
automatically inferred truth.

## Initial private pilot

Two fresh runs of four tasks per approach used the same 32-page wiki: ownership
and roles, evolving file-delivery requirements, reported versus verified project
state, and unknowns/proposals. Both arms used foreground Codex chat agents; this
compares the supplied wiki conventions and skill with Portable KB and its skill,
not Hermes versus Codex model quality. The exact inherited model was not exposed.

| Observation | Wiki + supplied skill | Portable KB + installed skill |
|---|---:|---:|
| Correct claims | 84/84 | 84/84 |
| Correct claims with grounded citations | 84/84 | 84/84 |
| Passed trials | 8/8 | 8/8 |
| Median recorded trial time | 49.7 s | 56.0 s |
| Recorded shell commands | 75 | 97 |
| Actual CLI invocations | 0 | 92 |
| Observed command-output characters | 1,272,328 | 1,152,249 |

Both represented the captured facts and uncertainty correctly. The wiki was faster
in this small pilot. Portable KB required more command round trips and returned
machine-checkable identities, pinned snapshots and lifecycle information. Its
lower observed output volume is not a token or cost claim. Long log/context reads
caused wiki rereads; large duplicated body/content JSON and broad search hits
caused Portable KB rereads. Initial prompt-path mistakes were runner friction,
not wiki defects.

The migration took about six minutes including discovery, creation and extensive
audit, with 194 actual CLI calls. It preserved 75,958 original body bytes, all
32 frontmatter mappings and all 153 wikilinks. All 36 original wiki files remained
unchanged, all items remained restricted drafts, and the final brain was valid
and clean. One original title/H1 mismatch remained a warning. This cost is separate
from prepared retrieval and is not a minimal-throughput import benchmark.

Original traces/labels were retained; additive label corrections accepted a legal
company-name variant, a full client-name variant and its captured raw-source
evidence. Segmented-read and contextual-citation checks were corrected before
reporting the final results. No agent answer was changed or rerun to improve scores.

One corpus, four tasks and two repetitions cannot establish a general winner or
statistical significance. Larger corpora, controlled update/conflict/move tasks,
brain-scope mistakes and measured native-runner token budgets are useful next
comparisons. This first pilot supports a factual-quality tie; governance and
maintenance advantages need their own task evidence.

Deterministic regressions require no model calls:

```sh
python -m pytest -q tests/test_wiki_compare.py tests/test_agent_evals.py
```
