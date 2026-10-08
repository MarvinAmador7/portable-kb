# Search prototype benchmarks

SQLite FTS5 and Rust/Tantivy now have working development prototypes. Tantivy
leads the initial Linux results on passage ranking, index size, large-corpus
query latency, and process memory. This is evidence for continuing with the
Tantivy engine now integrated as the production builtin provider for 0.2.0;
existing QMD configuration is preserved. The default
choice still requires representative domain judgments, operational tests, the
reference Apple Silicon run, and the supported release matrix.

## What is implemented

- `portable_kb.search_records` normalizes validated concepts into sections with
  immutable item IDs, canonical paths, exact Git pins, lifecycle metadata,
  source line ranges, and body hashes. It excludes reserved documents,
  frontmatter search text, hidden files, symbolic links, and heading-only
  scaffolding. It recognizes ATX and single-line setext headings outside fenced
  code; it is not a complete CommonMark renderer.
- `benchmarks.sqlite_fts5` uses SQLite's contentless FTS5 index and separate
  metadata tables. Ingestion commits every 1,000 sections to limit pending
  transaction state. A final optimization merges the derived index.
- `crates/pkb-search-core` owns Tantivy indexing and ranking. The
  `pkb-search-cli` sidecar speaks version-1 JSON Lines with 64 KiB request and
  1 MiB normalized-record limits. The runner bounds responses to 16 MiB and
  applies per-call timeouts. There are no models, network calls, or content
  execution hooks in either engine.
- Both prototypes use literal Unicode keyword conjunctions, accent folding,
  weighted title/description/heading/body fields (8/3/5/1), dedicated exact
  ID/path fields, and explicit type/status filters. Equal scores use input
  ordinal as a deterministic tie breaker, including ties at the result limit.
- The runner builds in unpublished staging directories and renames only a
  completed index into a new result directory. Engines reject existing build
  destinations; failed builds cannot overwrite a previous index. This is
  initial publication. Tantivy also exposes a separate managed-generation store
  for atomic full rebuilds, interruption recovery, concurrent readers, and
  explicit version migration, and reader-leased generation cleanup. See
  [native index recovery](native-index-recovery.md).

The performance tables below measure the original raw build/query path. They
exclude managed-store export copying, directory syncing, per-request manifest
lookup, and retained generations/record snapshots.

SQLite remains a development baseline. Tantivy is now wired into `pkb`
settings, canonical citation checks, native release artifacts, and lease-aware
brain removal. The Python wheel keeps its Python dependencies; standalone
releases embed the sidecar, while wheel users supply `pkb-search` separately.

## Shared comparison inputs

Every provider receives the same logical normalized sections. SQLite and
Tantivy consume JSONL records. The unmodified QMD 2.8.3 CLI consumes a derived
Markdown file per section containing its title, description, heading, body,
item ID, and canonical path. No canonical files are changed.

QMD cannot accept the prototypes' separate weighted fields or metadata filters.
The adapter quotes literal query words, retrieves all candidates for filtered
and exact-ID/path cases, then applies equality checks against the shared
record map. UUIDs and Unicode paths are split into literal words for discovery
and checked against their complete original value. QMD's own tokenizer,
stemming, field weights, and score ties remain unchanged. Its raw BM25 scores
are not compared numerically with prototype scores.

`tests/fixtures/retrieval/reference-sections.json` supplies explicit passage
judgments alongside the existing item judgments. The export checks that each
item/heading target resolves uniquely. The reference corpus has fourteen items
and 78 substantive sections, with six positive queries and one no-result query.

The deterministic synthetic generator produces two sections per item, English
and Spanish passages, Unicode paths, short concepts and longer procedures,
three lifecycle statuses, exact UUID/path cases, explicit filter cases, and an
intentional synonym-only miss. Its fifteen queries include thirteen positives
and two no-result cases. Fixtures declare `origin: synthetic-benchmark` and
`commit: null`; they never claim to be a validated Git brain or reviewed human
knowledge. Their deterministic UUID-shaped IDs are test identities only.

The synthetic positives use discriminating product terms. They measure exact
discovery and scaling, not general relevance across ambiguous real business
questions. All keyword engines miss `restore` when the passage says `recover`;
the labels preserve that miss rather than awarding a keyword engine invented
semantic ability.

## Reproduce a run

From the repository checkout, install the development dependencies and build
the pinned Rust workspace:

```console
python -m pip install -e '.[dev]'
cargo build --release --locked
python -m benchmarks.search generate --items 1000 --output /tmp/pkb-corpus-1000
python -m benchmarks.search run /tmp/pkb-corpus-1000 --output /tmp/pkb-results-1000 --tantivy target/release/pkb-search --repeat 3
```

The toolchain file pins Rust 1.90.0; `Cargo.lock` pins Tantivy 0.25.0 and its
dependencies. Add `--qmd /path/to/qmd` to compare an explicitly installed
supported QMD executable. Product setup still does not install QMD automatically.
Output directories must be new. Generated records and indexes belong outside
canonical knowledge and outside Git.

For an installed, healthy, clean brain, export its validated pinned version
using item labels and item/heading/grade section judgments:

```console
python -m benchmarks.search export --config /path/to/config.yaml --brain my-brain --as-of 2026-08-17 --labels labels.json --section-labels sections.json --output /tmp/pkb-brain-corpus
```

Use the two reference fixture label files only with the matching reference
corpus. The export refuses dirty/unpinned/invalid brains and absent or ambiguous
judgments. The benchmark refuses altered corpus fingerprints, duplicate
sections, absent labeled IDs, invalid relevance grades, and unknown filters.

Each `report.json` retains corpus and query fingerprints, the labels, engine
versions and implementation fingerprints, per-query rankings and canonical
line citations, raw timing samples, build time, index bytes, projection cost,
and available worker memory evidence. Item metrics collapse section duplicates
before scoring ten distinct items; section metrics score the actual passage
ordering. Explicit no-result cases are scored separately. Citation records are
remapped from known sections; QMD's projection filenames never become canonical
paths.

## Measurement scopes

Native engines run in persistent isolated workers. Reports separate worker
startup, index opening, engine query time, and total IPC call time. QMD runs as
a new CLI process for each query; its engine-only time is unavailable. Compare
transport timings as operational costs, not as identical engine workloads.
First-pass timings do not establish an OS cold-cache test, and repeated-pass
timings are warm worker measurements.

Worker peak RSS includes build and query phases, along with Python overhead for
SQLite. Tantivy's Linux RSS comes from `VmHWM`; SQLite uses `getrusage` with
platform unit conversion. QMD process RSS is unavailable in this runner and
reports `null`. Index byte counts exclude the shared corpus, runtime binaries,
and dependencies; QMD's additional Markdown projection is measured separately.
Synthetic runs at 10,000 and 100,000 items compare only the two prototypes;
QMD was compared on the reference and 1,000-item corpora.

## Initial measured results

Local Linux x86-64 measurements used Python 3.12.14, SQLite 3.53.1, Rust 1.90.0,
Tantivy 0.25.0, QMD 2.8.3, and three runs per query. These are small-sample
development measurements on a shared VM, not the Apple Silicon acceptance run.

Reference corpus quality:

| Provider | Item MRR at 10 | Item NDCG at 10 | Section MRR at 10 | Section NDCG at 10 |
|---|---:|---:|---:|---:|
| QMD | 1.0000 | 0.9862 | 0.2611 | 0.4427 |
| SQLite FTS5 | 1.0000 | 0.9862 | 0.2611 | 0.4272 |
| Tantivy | 1.0000 | 0.9862 | 0.7500 | 0.7223 |

All engines retrieved every labeled reference section within ten results and
preserved repeated rankings. The reference's supporting reviewer question was
still missed at the item level for `verification evidence`, as in the earlier
QMD baseline. Tantivy ranked the intended passages earlier; it did not change
the underlying item judgments.

At 100,000 items / 200,000 sections:

| Provider | Full build | Index size | Repeated engine p95 | Worker peak RSS |
|---|---:|---:|---:|---:|
| SQLite FTS5 | Approximately 7.9 s | 105.5 MiB | Approximately 6.6 ms | Approximately 584 MiB |
| Tantivy | Approximately 2.8 s | 28.3 MiB | Approximately 0.33 ms | Approximately 81 MiB |

The SQLite merge still has a substantial memory peak despite bounded ingestion
batches. That cost remains part of this prototype's evidence; it is not hidden
by comparing only its warm query memory. Both native engines and QMD reached
0.9231 section MRR/NDCG/recall on the 1,000-item synthetic corpus, with the same
single synonym miss and correct no-result/filter behavior. The two prototypes
preserved that relevance result through 100,000 items.

CI runs Rust formatting, Clippy, native tests, normalization/prototype tests,
and shared reference/1,000-item comparisons. It uploads the
`search-prototype-comparison` artifact without enforcing quality or latency
thresholds from these fixtures. Existing QMD compatibility and product
evaluation jobs remain in place.

## Remaining selection and delivery gates

Continue with Tantivy as the leading candidate while collecting representative
domain judgments and the reference-machine measurements. Before product
integration/default selection, extend the Linux-tested generation-store safety
contract and reader-leased cleanup across supported filesystems/platforms,
implement full removal, measure incremental costs, repeat builds across
Linux/macOS and Intel/ARM, and exercise packaging with clean
install/upgrade/remove behavior. Production settings migration and provider
selection must preserve existing users' QMD choice. Trust-policy filtering and
semantic/hybrid retrieval remain separate roadmap work.
