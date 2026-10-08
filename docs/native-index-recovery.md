# Native index rebuild, recovery, and cleanup

The Tantivy development sidecar now supports atomic full rebuilds while other
processes query the last published index. Explicit cleanup reclaims unused
generations while protecting reader snapshots. The production `builtin`
provider uses this store, and standalone releases embed its native sidecar.
Python retains brain health checks and canonical citation remapping. Existing
QMD configurations are preserved.

## Layout and protocol

A managed store is separate from the original raw benchmark index:

```text
store/
├── write.lock
├── readers.lock
├── CURRENT.json
└── generations/
    ├── gen-<unique suffix>/
    │   ├── manifest.json
    │   ├── read.lock
    │   ├── records.jsonl
    │   └── index/
    ├── .build-<unique suffix>/  # unpublished, possibly interrupted
    └── .trash-gen-<suffix>/     # retired, possibly partially deleted
```

The version-1 manifest contains `schema_version`, `index_format`,
`engine_version`, `generation`, `record_count`, and `lease_version`. New
generations declare lease version 1 and carry a matching immutable manifest.
The production manifest also contains the brain ID, slug, and Git commit. An
absent lease version means legacy version 0. Native index format 2 stores byte
offsets so Python reads only the returned records for citation checks. Its generation is a bounded
local directory name. Readers reject unexpected layout versions, unsafe names,
incompatible engine/index versions, missing generations, and count mismatches.

The existing raw `build` and `query` operations retain their benchmark behavior.
The same bounded JSONL protocol adds:

| Operation | Request fields besides `protocol_version: 1` and `op` | Result |
|---|---|---|
| `rebuild` | `index_path` (store root), `records_path` | Published manifest and elapsed milliseconds |
| `recover` | `index_path` | Current manifest or null, plus removed staging-entry count |
| `cleanup` | `index_path` | Current manifest, removed generations, pinned generations, retained unrecognized entries, and removed trash count |
| `release_store` | `index_path` | Whether this sidecar released its cached snapshot |
| `query_store` | `index_path`, `query`, `tokens`, optional `exact_field`, `limit`, `filters` | Ranked hits, manifest, immutable generation records path, and open/query timings |

For example, after building `target/release/pkb-search`, run it with one JSON
request per line on standard input:

```json
{"protocol_version":1,"op":"rebuild","index_path":"/tmp/pkb-native-store","records_path":"/tmp/pkb-corpus/records.jsonl"}
{"protocol_version":1,"op":"query_store","index_path":"/tmp/pkb-native-store","query":"Aurora000000","tokens":["Aurora000000"],"limit":10}
{"protocol_version":1,"op":"recover","index_path":"/tmp/pkb-native-store"}
{"protocol_version":1,"op":"cleanup","index_path":"/tmp/pkb-native-store"}
```

The caller must supply a stable, validated normalized export. The engine copies
it into the generation and builds from that copy. Returned hits and
`records_path` refer to the same generation even if a writer publishes another
one during the query. The caller must consume the records mapping before
refreshing or releasing that sidecar snapshot or closing the process. A path
returned in a past response is not an independent lease. Python must still remap
IDs to the healthy pinned brain,
validate canonical paths and metadata, and construct final citations; sidecar
paths and retrieval scores do not grant authority.

## Publication and recovery contract

1. Acquire a nonblocking OS file lock for the store. A competing writer
   operation fails promptly. Readers do not take this lock. Process termination
   releases the lock; the persistent lock file is not a stale-lock indicator.
2. Validate the current manifest layout and remove only `.build-*` and
   `.current-*` temporary entries. A malformed or newer manifest is rejected
   before cleanup.
3. Copy the export into a new staging generation, build the complete index, and
   verify its schema and document count. No existing generation is modified.
4. Sync files and directories on Unix, rename the completed generation, and
   sync its parent directory. Write and sync a temporary manifest, atomically
   replace `CURRENT.json`, then sync the store directory.
5. Readers choose a generation under a short shared `readers.lock` gate and
   acquire a shared generation `read.lock` before releasing the gate. A sidecar
   retains one reader per store and checks the manifest on every request; a changed
   manifest opens a new reader before replacing the cached one. A failed
   refresh fails the request instead of silently serving an older version.

An interruption before manifest publication leaves the previous pointer
intact. An interruption after publication leaves the complete new generation
selected. An error after publication, including a directory-sync failure, may
mean publication already happened; `recover` validates the selected generation.
A failed initial build has no queryable generation until a rebuild succeeds.

`recover` validates the selected index before deleting staging entries. It
never picks an older index by directory age or name. A recognized manifest
with a missing, corrupt, or incompatible generation can be repaired by an
explicit full `rebuild` from the normalized export. This is also the index
migration strategy: no native data is reused across versions. Malformed or
future manifest layouts require a separate new disposable store; this version
refuses to overwrite them.

## Safe generation cleanup

Cleanup is explicit and separate from `recover` and `rebuild`. It holds the
store writer lock, validates the selected generation, and keeps the current
generation regardless of its reader count. For each other generation with a
recognized lease-version-1 manifest, it briefly acquires the exclusive reader
gate and tries to acquire its generation lock exclusively. An active shared
lease makes cleanup skip that generation. The gate closes the race between
reading a manifest and acquiring a lease.

An eligible generation is atomically renamed to `.trash-gen-*` while these
locks are held. Cleanup then releases the reader gate and removes the retired
files, so recursive deletion does not block new readers. An interruption after
retirement leaves trash that the next `cleanup` can finish removing. Current
manifest bytes are never changed by cleanup; a malformed or incompatible
current state fails before any deletion. Completed but unpublished generations
are eligible under the same lease rules.

A cached native reader holds its shared lease until it refreshes, receives
`release_store`, or its process exits. SIGKILL releases the OS lock and memory
mappings together. The Rust snapshot drops its engine before its lease. This
protects both the native index and its immutable source-record mapping. Idle
reader processes can therefore keep older generations on disk; cleanup reports
them in `pinned_generations` and never expires a live lease by age or PID.

Legacy generations without lease metadata, unknown lease versions, missing
lock files, malformed generation markers, and unexpected entry types are
retained and reported in `retained_unrecognized`. Earlier sidecars never took
leases, so cleanup cannot infer that their snapshots are unused. Rebuilds
produce new lease-enabled generations while these older ones remain retained.
Remove legacy state only after all older readers have stopped, or use a fresh
disposable store. Older sidecars reject the new manifest field rather than
opening lease-enabled generations through their older managed-store protocol.

The safety contract applies to readers using `query_store` or the Rust leased
snapshot API. Production rebuilds run cleanup after successful publication;
the direct native `rebuild` operation leaves cleanup explicit. Raw `query` is intended for raw benchmark indexes and does not
participate in managed-generation cleanup. No background cleanup runs. Product brain removal acquires `prepare_remove`
guards that exclude readers and writers while Python quarantines the derived
store and commits its catalog update. Active readers make removal fail. Closing
the guard sidecar releases the locks after success or rollback. Recovery
removes staging symlinks without following their targets; cleanup likewise
retains generation symlinks instead of traversing them.

## Verification and limits

Rust tests inject errors after snapshot copy, index build, generation rename,
before manifest replacement, and after publication. They verify the selected
index and an already-held reader at every boundary. Other tests cover initial
failure, abandoned staging cleanup, lock exclusion, unsafe/corrupt manifests,
version mismatches, and migration by full rebuild.

`tests/test_search_recovery.py` additionally kills an actual builder process
with SIGKILL during a deliberately blocked export copy, both before and after
an initial index exists. It verifies lock release, staging cleanup, unchanged
published bytes, continuing readers, and successful subsequent rebuilding.
Separate sidecar processes query during repeated successful rebuilds and check
that every returned ID belongs to its response's immutable records snapshot.
Deleted sections disappear from the new full rebuild, and cached readers reject
version changes. Cleanup tests additionally verify multiple active readers,
lease release after SIGKILL, refresh and explicit release, current-generation
preservation, delayed lease acquisition racing with cleanup, legacy retention,
and retry after interrupted trash removal.

Reproduce from the repository checkout:

```sh
cargo test --workspace --locked
cargo build --release --locked
PKB_TANTIVY_COMMAND="$PWD/target/release/pkb-search" \
  python -m pytest -q tests/test_search_recovery.py tests/test_search_benchmarks.py
```

These tests passed locally on Linux and are part of the native prototype CI
job. CI execution itself is not implied by local validation. The contract
assumes local filesystems with atomic replacement and functioning OS locks;
network filesystems are unverified. Unix file/directory syncing is implemented,
but simulated power loss and macOS/Intel/ARM operational checks remain pending.
Non-Unix directory durability is not supported. Incremental updates, automatic
rollback and background cleanup scheduling are not implemented. Lease-aware
product brain removal is integrated. Explicit generation cleanup is implemented and tested on Linux.
