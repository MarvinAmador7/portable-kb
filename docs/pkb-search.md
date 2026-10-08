# Built-in `pkb-search` plan

## Production integration

Portable KB 0.2.0 integrates a built-in, model-free Tantivy provider and embeds
its native sidecar in standalone releases. New setup selects builtin keyword
search; existing QMD settings are preserved. QMD remains a
supported optional provider until a native engine matches its retrieval quality
and operational reliability.

The selected implementation is a Rust engine built on Tantivy. SQLite
FTS5 is the required lower-complexity baseline, and QMD BM25 is the compatibility
baseline. Zig is not selected for the first prototype because Portable KB would
otherwise own substantially more tokenization, persistence, recovery, and index
compatibility code.

This plan does not authorize embeddings or model downloads. Semantic and hybrid
retrieval remain a later, explicitly selected capability.

## Requirements

The built-in provider must:

- index only a clean, valid brain pinned to an exact Git commit;
- treat indexes as disposable local state, never canonical knowledge;
- retain brain ID, immutable item ID, path, commit, lifecycle, and line-range
  citation data in every result;
- duplicate no OKF validation, lifecycle, provenance, or authority logic;
- perform no network access, hooks, commands from content, or model downloads;
- isolate one index per brain and publish a rebuild atomically;
- support interruption, concurrent callers, index-version migration, and full
  deletion/rebuild;
- expose a deterministic, versioned machine protocol; and
- equal or beat QMD BM25 on the agreed evaluation corpus before becoming the
  default provider.

## Boundary

```text
Git brain at pinned commit
        |
        v
Python parser + validator + trust layer
        |
        | normalized index records
        v
pkb-search engine (Rust/Tantivy candidate)
        |
        v
atomic per-brain derived index

query -> provider -> ranked item/section IDs -> Python trust remap -> citation
```

Python remains authoritative for brain health, safe path resolution, OKF
parsing, validation, lifecycle metadata, and final citations. The native engine
receives normalized records and returns discovery evidence only. A search score
never becomes an authority score.

## Provider contract

The Python consumer should depend on a provider-neutral interface:

```text
status(brain) -> provider/index/version/health
build(brain, records, destination) -> index manifest
query(brain, text, limit, filters) -> ranked section hits
remove(brain) -> derived state removed
```

The initial providers are:

- `builtin`: native keyword engine;
- `qmd`: current isolated QMD BM25 adapter; and
- `sqlite-fts5`: benchmark prototype, retained only if it wins the operational
  trade-off.

Changing the configured provider invalidates the disposable index and requires
an explicit rebuild. Configuration migration must preserve the existing QMD
choice instead of silently switching an installed user.

## Normalized index record

Each record represents a Markdown section rather than an arbitrary token-sized
chunk:

```json
{
  "schema_version": 1,
  "brain_id": "urn:uuid:...",
  "brain_slug": "business-a",
  "commit": "40-character-git-commit",
  "item_id": "urn:uuid:...",
  "path": "procedures/review-stale-knowledge.md",
  "title": "Review stale knowledge",
  "description": "Defines the review workflow.",
  "heading": "Escalation",
  "body": "Section text...",
  "line_start": 24,
  "line_end": 37,
  "type": "procedure",
  "status": "stable",
  "sensitivity": "internal",
  "stale_after": "2026-12-31",
  "updated_at": "2026-08-17T12:00:00Z",
  "content_hash": "sha256:..."
}
```

Frontmatter, reserved indexes/logs, and unsafe paths are never passed through as
searchable records. Exact identifiers and paths receive dedicated untokenized
fields. Title, description, heading, and body use separate weighted fields.

## Rust packaging strategy

Start with a Rust workspace containing a reusable library and an internal
sidecar executable:

```text
crates/
├── pkb-search-core/
└── pkb-search-cli/
```

`pkb` invokes the sidecar through bounded JSON Lines input/output and discovers
it relative to the installed executable. The standalone release installs both
artifacts atomically. Process isolation keeps native crashes outside the Python
governance process and lets a future macOS application link the same Rust crate
directly.

PyO3 remains an optimization option after the protocol stabilizes. It is not
the first boundary because it would replace the current universal Python wheel
with platform-specific wheels and couple native failures to the CLI process.

## Benchmark corpus

Generate deterministic, non-sensitive corpora at approximately 1,000, 10,000,
and 100,000 knowledge items. Include:

- short decisions and long procedures;
- exact UUID, filename, acronym, and product-name queries;
- English and Spanish prose plus Unicode paths;
- lifecycle/type filters;
- common synonyms, low-frequency terms, and no-result queries; and
- section-level relevance labels with multiple legitimate answers.

Compare QMD BM25, SQLite FTS5, and Tantivy using identical normalized records.
Record:

- full and incremental index time;
- cold start and warm p50/p95/p99 query latency;
- peak resident memory and on-disk index size;
- interruption/rebuild behavior;
- precision at 5, recall at 10, MRR, and NDCG at 10; and
- citation correctness and deterministic ordering.

## Provisional acceptance gates

The built-in provider may become the default only when it:

- reaches p95 keyword-query latency below 30 ms at 50,000 representative items
  on the reference Apple Silicon machine;
- returns the first relevant result for at least 95% of labeled exact-policy
  and procedure queries;
- matches or exceeds QMD BM25 MRR and NDCG at 10;
- rebuilds atomically after interruption without corrupting the previous index;
- produces identical ranked IDs for identical input, engine version, and
  platform where scores do not tie; and
- passes the supported Linux/macOS and Intel/ARM release matrix.

These thresholds are hypotheses. Record the hardware and revise them through a
reviewed benchmark decision rather than tuning only to a convenient fixture.

## Delivery phases

1. Extract the provider interface without changing the default. **Implemented:**
   `KeywordSearchProvider` separates QMD execution/index details from the shared
   brain health, safe path, canonical parsing, and citation checks. Settings
   schema 1, existing QMD indexes, and CLI result schemas remain compatible.
   Transactional index deletion remains with brain removal. The QMD adapter
   continues to consume validated Markdown; the benchmark prototypes below
   consume normalized section records and return section IDs.
2. Add the labeled retrieval evaluation harness and QMD baseline. **Starter
   implemented:** `pkb search evaluate` scores labeled item IDs, checks citations
   and repeated rankings, and measures end-to-end query latency. The pinned-QMD
   CI job retains its report. Section judgments, synthetic English/Spanish scale
   data, and build/query/memory/disk measurements are implemented in the
   prototype work below. Representative domain corpora and broader operational
   evaluations remain pending. See [retrieval evaluation](retrieval-evaluation.md).
3. Implement SQLite FTS5 and Tantivy benchmark prototypes. **Implemented:**
   shared line-cited sections, a contentless FTS5 baseline, the Rust library and
   bounded JSONL sidecar, literal Unicode queries, exact ID/path lookup,
   explicit type/status filters, and deterministic score ties. The runner
   compares both engines and unmodified QMD on the same logical section records.
   Reference section judgments and reproducible synthetic corpora at 1,000,
   10,000, and 100,000 items have been exercised. CI retains reference and
   1,000-item comparison reports.
4. Select the engine through measured quality, latency, footprint, and
   operational complexity. **In progress:** Tantivy leads the initial Linux
   measurements. Representative domain judgments, the reference Apple Silicon
   run, broader filesystem/platform safety checks, incremental costs,
   and the release matrix are still required before a default-provider choice.
   Atomic full rebuilds, recovery, concurrent readers, and rebuild-based version
   migration, plus explicit reader-leased generation cleanup, are implemented
   and tested locally on Linux. See
   [native index recovery](native-index-recovery.md) and
   [prototype benchmarks](search-prototype-benchmarks.md).
5. **Integrated for 0.2.0:** standalone packages embed the native sidecar, and
   release runners gate publication on native tests and frozen index/query smoke
   checks for all four targets. Remote release checks must still pass.
6. **Integrated for 0.2.0:** setup selects `builtin` for new users, preserves
   existing QMD configuration, and supports explicit provider choice. Continue
   collecting representative domain and reference-machine evaluation evidence.

## Later semantic capability

A future explicit semantic tier may use a versioned local embedding model and a
native vector index, then combine dense and keyword rankings with reciprocal
rank fusion. Model identity, dimensions, tokenizer, chunking strategy, and
embedding version must live in the disposable index manifest. Changing any of
them requires re-indexing. No model downloads occur during setup or keyword
search without a separate capability choice.

## Main risks

- Native packaging increases the release matrix and supply-chain surface.
- Tokenization choices may lower multilingual recall even when latency improves.
- Incremental indexing can retain deleted or stale records unless commit and
  content-hash invariants are tested aggressively.
- Benchmark fixtures can overfit product terminology and hide real business
  retrieval failures.
- A faster ranker can still return inapplicable or unauthorized knowledge;
  lifecycle and brain-scope handling remain the Python trust layer's job.
