# Keyword retrieval evaluation

`pkb search evaluate` measures the existing keyword provider against explicit
item-level relevance judgments. QMD remains the only configured provider. The
evaluation does not create knowledge, install models, rebuild indexes, or apply
trust filters.

## Run a report

Install/select your brain and explicitly build its index first. Then run:

```console
pkb search evaluate labels.json --brain my-brain --as-of 2026-08-17 --repeat 2 > report.json
```

`--config` selects another local installation. The date is required so freshness
validation is reproducible. `--repeat` accepts 1–20 runs per query; one run cannot
establish ranking stability and reports it as `null`.

## Label format

```json
{
  "schema_version": 1,
  "name": "my-brain-keyword-v1",
  "queries": [
    {
      "id": "stale-review",
      "query": "review stale knowledge",
      "relevance": {
        "urn:uuid:0adaf3c7-c3e0-4cdc-85f4-90438dd72020": 3
      }
    },
    {"id": "absent-topic", "query": "zxqvnotincorpus92817", "relevance": {}}
  ]
}
```

Each query ID must be unique. Relevance maps canonical UUID URNs to integer
grades: 1 = useful supporting item, 2 = relevant answer, 3 = direct answer.
Multiple answers may be legitimate. An empty map explicitly means no result
should be returned. All labeled IDs must exist in the selected pinned brain;
labels are not silently remapped after corpus changes. Duplicate JSON fields,
unknown schema fields, invalid IDs/grades, and invalid queries are rejected.

Judgments are supplied by the label author, not inferred from search scores.
Unjudged returned items earn no gain. Review label completeness before treating
low precision as evidence of poor retrieval; a useful but unlabeled item will
count as irrelevant. These labels evaluate discovery, not factual authority.

## Metrics and evidence

For positive queries the report calculates:

- **Precision at 5:** relevant items in the first five slots divided by five;
  missing slots count as misses.
- **Recall at 10:** distinct labeled items found in ten slots divided by all
  labeled items for that query.
- **Reciprocal rank at 10:** inverse rank of the first relevant item, or zero
  when none is found in ten slots. Its mean is MRR at 10.
- **NDCG at 10:** discounted gain using `2^grade - 1` and `log2(rank + 1)`,
  normalized against the ideal labeled ordering.

Duplicate item hits consume rank slots but earn no extra relevance gain.
Aggregate relevance metrics are means over positive queries only. Explicit
no-result queries receive separate accuracy; empty positive or negative groups
report `null` metrics rather than invented perfect scores.

Every returned citation must match the selected brain ID, slug, exact commit,
canonical item ID, and parsed path. A changed brain/provider/index or incorrect
citation aborts the run. `checked_result_count` includes all repeated queries;
citation correctness is `null` when nothing was returned. Repeated rankings
compare item ID, path, and optional line anchor, preserving provider order.

Reports retain the label-file SHA-256, parsed concept corpus SHA-256, full index
metadata (including the QMD version used to build it), validation date/warnings,
platform details, raw per-query results, and timing samples. Compare corpus and
label fingerprints before comparing quality. Keep provider versions and machine
conditions fixed for latency comparisons.

Timing includes brain/Git validation, citation parsing, executable version
checks, and provider process startup. First-pass and repeated-pass p50/p95/p99
use nearest-rank percentiles. First-pass timings do not imply an OS cold-cache
measurement; repeated passes still launch fresh QMD processes. These timings do
not measure the native engine-only 30 ms target in the built-in search plan.

## Starter QMD baseline

`tests/fixtures/retrieval/reference-labels.json` contains six English positive
queries and one no-result query for the fourteen-item reference fixture. The
labels include multiple graded answers for two queries. They are synthetic
test judgments, not production knowledge or reviewed organizational authority.

The real-QMD integration test installs a committed copy of that fixture in an
isolated temporary brain, indexes it, evaluates all seven queries twice, and
checks citation correctness, ranking stability, and no-result behavior. CI uses
QMD 2.8.3 on Node.js 24 and uploads the `qmd-evaluation` JSON artifact. It does
not impose relevance or latency thresholds from this small corpus.

A local Linux x86-64 run using Python 3.12.14 and QMD 2.8.3 produced:

| Measure | Result |
|---|---:|
| Mean precision at 5 | 0.2333 |
| Mean recall at 10 | 0.9167 |
| MRR at 10 | 1.0000 |
| Mean NDCG at 10 | 0.9862 |
| No-result accuracy | 1.0000 |
| Checked citations across repeated queries | 30, all correct |
| Repeated rankings | Identical |
| Repeated-pass end-to-end p95 | Approximately 424 ms |

The supporting reviewer question was missed for `verification evidence`; the
direct verification concept ranked first. This explains the recall shortfall
without changing the judgments to fit the provider.

Run the same test locally with an installed supported QMD executable:

```console
PKB_REAL_QMD=1 PKB_QMD_EVALUATION_REPORT=/tmp/qmd-evaluation.json python -m pytest -q tests/test_qmd_integration.py
```

`PKB_QMD_COMMAND` can select an isolated QMD executable for this test. The
installation is test tooling; product setup does not install QMD automatically.

## Remaining benchmark work

The product command continues to score items. A separate development benchmark
now adds normalized section records and judgments, SQLite FTS5 and Tantivy
prototypes, a QMD projection of the same records, and deterministic synthetic
English/Spanish corpora at 1,000–100,000 items. It exercises exact IDs, Unicode
paths, explicit lifecycle/type filters, and a deliberate synonym gap. It records
full build cost, engine/transport query latency, process memory, and index size;
CI retains small comparison reports. See
[prototype benchmarks](search-prototype-benchmarks.md) for commands and results.

Representative domain judgments, incremental indexing, true cold-cache tests,
interruption/concurrency/rebuild and migration behavior, the reference Apple
Silicon run, and supported release targets remain pending. Semantic/hybrid
evaluation requires its later explicit capability selection.
