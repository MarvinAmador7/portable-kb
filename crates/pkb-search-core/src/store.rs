//! Disposable, immutable generations. Publication never edits an open index.

use crate::{build, Engine, ENGINE_VERSION};
use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

const MAX_MANIFEST_BYTES: u64 = 65_536;
const INDEX_FORMAT: u32 = 2;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct BrainPin {
    pub id: String,
    pub slug: String,
    pub commit: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub schema_version: u32,
    pub index_format: u32,
    pub engine_version: String,
    pub generation: String,
    pub record_count: usize,
    #[serde(default)]
    pub lease_version: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub brain: Option<BrainPin>,
}

fn directory(path: &Path) -> Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if !metadata.is_dir() || metadata.file_type().is_symlink() {
        bail!(
            "store directory must be a real directory: {}",
            path.display()
        );
    }
    Ok(())
}

fn regular_file(path: &Path) -> Result<File> {
    if !fs::symlink_metadata(path)?.is_file() {
        bail!("store file must be a regular file: {}", path.display());
    }
    Ok(File::open(path)?)
}

fn read_manifest_file(path: &Path) -> Result<Manifest> {
    let mut bytes = Vec::new();
    regular_file(path)?
        .take(MAX_MANIFEST_BYTES + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_MANIFEST_BYTES {
        bail!("store manifest exceeds 64 KiB");
    }
    let manifest: Manifest = serde_json::from_slice(&bytes).context("invalid store manifest")?;
    manifest.validate_layout()?;
    Ok(manifest)
}

fn read_manifest(root: &Path) -> Result<Option<Manifest>> {
    directory(root)?;
    let path = root.join("CURRENT.json");
    match fs::symlink_metadata(&path) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.into()),
        Ok(_) => {}
    }
    Ok(Some(read_manifest_file(&path)?))
}

impl Manifest {
    fn validate_layout(&self) -> Result<()> {
        if self.schema_version != 1
            || self.lease_version > 1
            || !self.generation.starts_with("gen-")
            || self.generation.len() <= 4
            || self.generation.len() > 128
            || !self
                .generation
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
        {
            bail!("unsupported or unsafe store manifest");
        }
        Ok(())
    }

    pub fn generation_path(&self, root: &Path) -> PathBuf {
        root.join("generations").join(&self.generation)
    }

    pub fn records_path(&self, root: &Path) -> PathBuf {
        self.generation_path(root).join("records.jsonl")
    }

    pub fn open(&self, root: &Path) -> Result<Snapshot> {
        let gate = reader_gate(root)?;
        gate.lock_shared()?;
        let pinned = pin(self.clone(), root)?;
        drop(gate);
        pinned.open()
    }

    fn open_engine(&self, root: &Path) -> Result<Engine> {
        self.validate_layout()?;
        directory(root)?;
        if self.index_format != INDEX_FORMAT || self.engine_version != ENGINE_VERSION {
            bail!("incompatible index version; explicitly rebuild from normalized records");
        }
        directory(&root.join("generations"))?;
        let generation = self.generation_path(root);
        directory(&generation)?;
        regular_file(&self.records_path(root))?;
        let index = generation.join("index");
        directory(&index)?;
        let engine = Engine::open(&index)?;
        if engine.record_count() != self.record_count as u64 {
            bail!("generation record count does not match manifest");
        }
        Ok(engine)
    }
}

/// Inspect the selected manifest; use pin_current to obtain a leased snapshot.
pub fn current(root: &Path) -> Result<Manifest> {
    read_manifest(root)?.context("store has no published generation; rebuild required")
}

fn reader_gate(root: &Path) -> Result<File> {
    directory(root)?;
    let path = root.join("readers.lock");
    if let Ok(metadata) = fs::symlink_metadata(&path) {
        if !metadata.is_file() {
            bail!("reader gate must be a regular file");
        }
    }
    Ok(OpenOptions::new()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .open(path)?)
}

pub struct PinnedGeneration {
    manifest: Manifest,
    root: PathBuf,
    _lease: Option<File>,
}

impl PinnedGeneration {
    pub fn manifest(&self) -> &Manifest {
        &self.manifest
    }

    pub fn open(self) -> Result<Snapshot> {
        let engine = self.manifest.open_engine(&self.root)?;
        Ok(Snapshot {
            engine,
            pinned: self,
        })
    }
}

// Drop the engine (and its memory mappings) before releasing the lease.
pub struct Snapshot {
    engine: Engine,
    pinned: PinnedGeneration,
}

impl Snapshot {
    pub fn manifest(&self) -> &Manifest {
        self.pinned.manifest()
    }
}

impl std::ops::Deref for Snapshot {
    type Target = Engine;
    fn deref(&self) -> &Engine {
        &self.engine
    }
}

fn pin(manifest: Manifest, root: &Path) -> Result<PinnedGeneration> {
    manifest.validate_layout()?;
    if manifest.index_format != INDEX_FORMAT || manifest.engine_version != ENGINE_VERSION {
        bail!("incompatible index version; explicitly rebuild from normalized records");
    }
    directory(&root.join("generations"))?;
    let generation = manifest.generation_path(root);
    directory(&generation)?;
    let marker = generation.join("manifest.json");
    let lease = if manifest.lease_version == 1 {
        if read_manifest_file(&marker)? != manifest {
            bail!("generation metadata does not match current manifest");
        }
        let lease = regular_file(&generation.join("read.lock"))?;
        lease.lock_shared()?;
        Some(lease)
    } else {
        if fs::symlink_metadata(marker).is_ok() {
            bail!("generation lease metadata cannot be downgraded");
        }
        None // Legacy generations are never eligible for automatic cleanup.
    };
    Ok(PinnedGeneration {
        manifest,
        root: root.to_owned(),
        _lease: lease,
    })
}

/// The short shared gate closes the pointer-read/lease-acquisition race with
/// cleanup. Index opening and querying take place after this gate is released.
pub fn pin_current(root: &Path) -> Result<PinnedGeneration> {
    let gate = reader_gate(root)?;
    gate.lock_shared()?;
    let pinned = pin(current(root)?, root)?;
    drop(gate);
    Ok(pinned)
}

fn writer_lock(root: &Path) -> Result<File> {
    fs::create_dir_all(root)?;
    directory(root)?;
    let lock_path = root.join("write.lock");
    if let Ok(metadata) = fs::symlink_metadata(&lock_path) {
        if !metadata.is_file() {
            bail!("writer lock must be a regular file");
        }
    }
    let lock = OpenOptions::new()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .open(lock_path)?;
    lock.try_lock()
        .context("another writer operation holds the store writer lock")?;
    // Refuse raw prototype indexes and unrelated directories.
    for entry in fs::read_dir(root)? {
        let name = entry?.file_name();
        let name = name.to_string_lossy();
        if !["write.lock", "readers.lock", "generations", "CURRENT.json"].contains(&name.as_ref())
            && !name.starts_with(".current-")
        {
            bail!("unexpected file in managed store: {name}");
        }
    }
    let generations = root.join("generations");
    fs::create_dir_all(&generations)?;
    directory(&generations)?;
    Ok(lock) // OS lock is released on drop, including process termination.
}

fn clean_staging(root: &Path) -> Result<usize> {
    let mut removed = 0;
    for entry in fs::read_dir(root.join("generations"))? {
        let entry = entry?;
        if entry.file_name().to_string_lossy().starts_with(".build-") {
            if entry.file_type()?.is_dir() {
                fs::remove_dir_all(entry.path())?;
            } else {
                fs::remove_file(entry.path())?;
            }
            removed += 1;
        }
    }
    for entry in fs::read_dir(root)? {
        let entry = entry?;
        if entry.file_name().to_string_lossy().starts_with(".current-") {
            if entry.file_type()?.is_dir() {
                bail!("unexpected directory in manifest staging state");
            }
            fs::remove_file(entry.path())?;
            removed += 1;
        }
    }
    // Retain every gen-* directory, including unpublished renamed generations.
    // Deletion could invalidate a snapshot held by another reader process.
    Ok(removed)
}

#[cfg(unix)]
fn sync_directory(path: &Path) -> Result<()> {
    File::open(path)?.sync_all()?;
    Ok(())
}

#[cfg(not(unix))]
fn sync_directory(_path: &Path) -> Result<()> {
    // Non-Unix durability is not a supported release contract yet.
    Ok(())
}

fn sync_tree(path: &Path) -> Result<()> {
    for entry in fs::read_dir(path)? {
        let entry = entry?;
        if entry.file_type()?.is_dir() {
            sync_tree(&entry.path())?;
        } else {
            regular_file(&entry.path())?.sync_all()?;
        }
    }
    sync_directory(path)
}

#[derive(Clone, Copy)]
enum Checkpoint {
    Snapshot,
    Index,
    Generation,
    BeforePublish,
    Published,
}

/// Full rebuild migrates a recognized manifest with an incompatible engine or
/// index version. No old native data is reused.
pub fn rebuild(root: &Path, records: &Path) -> Result<Manifest> {
    rebuild_for_brain(root, records, None)
}

pub fn rebuild_for_brain(root: &Path, records: &Path, brain: Option<BrainPin>) -> Result<Manifest> {
    rebuild_inner(root, records, brain, |_| Ok(()))
}

#[cfg(test)]
fn rebuild_with_hook(
    root: &Path,
    records: &Path,
    hook: impl FnMut(Checkpoint) -> Result<()>,
) -> Result<Manifest> {
    rebuild_inner(root, records, None, hook)
}

fn rebuild_inner(
    root: &Path,
    records: &Path,
    brain: Option<BrainPin>,
    mut hook: impl FnMut(Checkpoint) -> Result<()>,
) -> Result<Manifest> {
    let _lock = writer_lock(root)?;
    read_manifest(root)?; // Refuse malformed or future manifests before cleanup.
    clean_staging(root)?;
    let generations = root.join("generations");
    let stage = tempfile::Builder::new()
        .prefix(".build-")
        .tempdir_in(&generations)?;
    let snapshot = stage.path().join("records.jsonl");
    let mut input = File::open(records).context("cannot open normalized records")?;
    let mut output = File::create(&snapshot)?;
    std::io::copy(&mut input, &mut output)?;
    output.sync_all()?;
    hook(Checkpoint::Snapshot)?;
    let count = build(&stage.path().join("index"), &snapshot)?;
    hook(Checkpoint::Index)?;
    let generation = format!(
        "gen-{}",
        stage
            .path()
            .file_name()
            .unwrap()
            .to_string_lossy()
            .trim_start_matches(".build-")
    );
    let manifest = Manifest {
        schema_version: 1,
        index_format: INDEX_FORMAT,
        engine_version: ENGINE_VERSION.to_owned(),
        generation,
        record_count: count,
        lease_version: 1,
        brain,
    };
    // Metadata marks generations whose readers participate in safe cleanup.
    fs::write(
        stage.path().join("manifest.json"),
        serde_json::to_vec(&manifest)?,
    )?;
    File::create(stage.path().join("read.lock"))?;
    let engine = Engine::open(&stage.path().join("index"))?;
    if engine.record_count() != count as u64 {
        bail!("built index count mismatch");
    }
    drop(engine);
    sync_tree(stage.path())?;
    fs::rename(stage.path(), manifest.generation_path(root))?;
    sync_directory(&generations)?;
    hook(Checkpoint::Generation)?;
    let mut pointer = tempfile::Builder::new()
        .prefix(".current-")
        .tempfile_in(root)?;
    serde_json::to_writer(&mut pointer, &manifest)?;
    pointer.write_all(b"\n")?;
    pointer.as_file().sync_all()?;
    hook(Checkpoint::BeforePublish)?;
    pointer.persist(root.join("CURRENT.json"))?;
    sync_directory(root).context("generation published but directory sync failed")?;
    hook(Checkpoint::Published)?;
    Ok(manifest)
}

#[derive(Serialize)]
pub struct Recovery {
    pub current: Option<Manifest>,
    pub removed_staging_entries: usize,
}

/// Validate current state and remove unpublished temporary entries only.
/// Corrupt current state fails closed; recovery never guesses an older index.
pub fn recover(root: &Path) -> Result<Recovery> {
    let _lock = writer_lock(root)?;
    let current = read_manifest(root)?;
    if let Some(manifest) = &current {
        manifest.open(root)?;
    }
    let removed_staging_entries = clean_staging(root)?;
    Ok(Recovery {
        current,
        removed_staging_entries,
    })
}

#[derive(Default, Serialize)]
pub struct Cleanup {
    pub current: Option<Manifest>,
    pub removed_generations: Vec<String>,
    pub pinned_generations: Vec<String>,
    pub retained_unrecognized: Vec<String>,
    pub removed_trash_entries: usize,
}

/// Explicit cleanup reclaims only generations with the supported lease marker.
/// Current and leased snapshots always survive. Legacy state is retained.
pub fn cleanup(root: &Path) -> Result<Cleanup> {
    cleanup_with_hook(root, |_| Ok(()))
}

fn cleanup_with_hook(
    root: &Path,
    mut after_rename: impl FnMut(&Path) -> Result<()>,
) -> Result<Cleanup> {
    let _writer = writer_lock(root)?;
    let current = read_manifest(root)?;
    if let Some(manifest) = &current {
        manifest.open(root)?;
    }
    let mut result = Cleanup {
        current,
        ..Cleanup::default()
    };
    let generations = root.join("generations");
    let mut entries: Vec<_> = fs::read_dir(&generations)?.collect::<std::io::Result<_>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    for entry in entries {
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.starts_with(".trash-gen-") && entry.file_type()?.is_dir() {
            // Rename to trash happens only after excluding all readers. No
            // reader can acquire the original path after the rename.
            fs::remove_dir_all(entry.path())?;
            result.removed_trash_entries += 1;
            continue;
        }
        if !name.starts_with("gen-")
            || result
                .current
                .as_ref()
                .is_some_and(|m| m.generation == name)
        {
            continue;
        }
        if !entry.file_type()?.is_dir() {
            result.retained_unrecognized.push(name);
            continue;
        }
        let marker = read_manifest_file(&entry.path().join("manifest.json"));
        if !matches!(marker, Ok(ref m) if m.lease_version == 1 && m.generation == name) {
            result.retained_unrecognized.push(name);
            continue;
        }
        let gate = reader_gate(root)?;
        gate.lock()?;
        let lease = match regular_file(&entry.path().join("read.lock")) {
            Ok(lease) => lease,
            Err(_) => {
                result.retained_unrecognized.push(name);
                continue;
            }
        };
        match lease.try_lock() {
            Ok(()) => {}
            Err(std::fs::TryLockError::WouldBlock) => {
                result.pinned_generations.push(name);
                continue;
            }
            Err(error) => return Err(error.into()),
        }
        let trash = generations.join(format!(".trash-{name}"));
        if fs::symlink_metadata(&trash).is_ok() {
            bail!("generation trash destination already exists");
        }
        fs::rename(entry.path(), &trash)?;
        sync_directory(&generations)?;
        drop(gate); // Slow recursive removal does not block new readers.
        after_rename(&trash)?;
        fs::remove_dir_all(&trash)?;
        drop(lease);
        result.removed_generations.push(name);
    }
    sync_directory(&generations)?;
    Ok(result)
}

/// Held across Python's catalog/quarantine transaction. Files are disposable,
/// but no native memory mapping may be unlinked while its reader is alive.
pub struct RemovalGuard {
    _leases: Vec<File>,
    _gate: File,
    _writer: File,
}

pub fn prepare_removal(root: &Path) -> Result<RemovalGuard> {
    let writer = writer_lock(root)?;
    read_manifest(root)?;
    let gate = reader_gate(root)?;
    gate.try_lock()
        .context("native readers are selecting a snapshot; retry removal")?;
    let mut leases = Vec::new();
    for entry in fs::read_dir(root.join("generations"))? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().into_owned();
        if !name.starts_with("gen-") {
            continue;
        }
        directory(&entry.path())?;
        let marker = read_manifest_file(&entry.path().join("manifest.json"))?;
        if marker.lease_version != 1 || marker.generation != name {
            bail!("unrecognized generation lease metadata; removal refused");
        }
        let lease = regular_file(&entry.path().join("read.lock"))?;
        lease
            .try_lock()
            .context("native readers still hold a generation; retry after they exit")?;
        leases.push(lease);
    }
    Ok(RemovalGuard {
        _leases: leases,
        _gate: gate,
        _writer: writer,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn records(path: &Path, id: &str) -> Result<()> {
        fs::write(
            path,
            serde_json::json!({
                "schema_version": 1, "section_id": id, "item_id": id, "path": "x.md",
                "title": "Policy", "description": "", "heading": "Policy", "body": "Recovery",
                "line_start": 1, "line_end": 1, "type": "procedure", "status": "draft"
            })
            .to_string(),
        )?;
        Ok(())
    }

    fn ids(engine: &Snapshot) -> Result<Vec<String>> {
        Ok(engine
            .query("policy", &["policy".to_owned()], None, 10, &BTreeMap::new())?
            .into_iter()
            .map(|hit| hit.section_id)
            .collect())
    }

    #[test]
    fn failures_at_each_publication_boundary_preserve_readable_snapshots() -> Result<()> {
        for failure in 0..5 {
            let temp = tempfile::tempdir()?;
            let root = temp.path().join("store");
            let input = temp.path().join("records.jsonl");
            records(&input, "old")?;
            let old = rebuild(&root, &input)?;
            let held = old.open(&root)?;
            records(&input, "new")?;
            let mut checkpoint = 0;
            let outcome = rebuild_with_hook(&root, &input, |_| {
                // Existing readers see the old pointer at every pre-publication
                // boundary and the complete new pointer after publication.
                let visible = current(&root)?;
                let expected = if checkpoint == 4 { "new" } else { "old" };
                assert_eq!(ids(&visible.open(&root)?)?, vec![expected]);
                let this_checkpoint = checkpoint;
                checkpoint += 1;
                if this_checkpoint == failure {
                    bail!("injected interruption");
                }
                Ok(())
            });
            assert!(outcome.is_err());
            assert_eq!(ids(&held)?, vec!["old"]);
            let recovered = recover(&root)?.current.unwrap();
            assert_eq!(
                ids(&recovered.open(&root)?)?,
                vec![if failure == 4 { "new" } else { "old" }]
            );
            assert!(old.records_path(&root).is_file());
        }
        Ok(())
    }

    #[test]
    fn incompatible_versions_require_explicit_rebuild_and_future_layouts_are_untouched(
    ) -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "old")?;
        rebuild(&root, &input)?;
        let pointer = root.join("CURRENT.json");
        for engine_mismatch in [true, false] {
            let mut old = current(&root)?;
            if engine_mismatch {
                old.engine_version = "older-engine".to_owned();
            } else {
                old.index_format = 99;
            }
            fs::write(&pointer, serde_json::to_vec(&old)?)?;
            assert!(current(&root)?.open(&root).is_err());
            assert!(recover(&root).is_err());
            records(&input, "new")?;
            let new = rebuild(&root, &input)?;
            assert_eq!(ids(&new.open(&root)?)?, vec!["new"]);
        }
        let mut future = current(&root)?;
        future.schema_version = 2;
        let before = serde_json::to_vec(&future)?;
        fs::write(&pointer, &before)?;
        fs::create_dir(root.join("generations/.build-abandoned"))?;
        assert!(rebuild(&root, &input).is_err());
        assert!(recover(&root).is_err());
        assert_eq!(fs::read(&pointer)?, before);
        assert!(root.join("generations/.build-abandoned").exists());
        Ok(())
    }

    #[test]
    fn corrupt_or_unsafe_current_fails_closed_without_guessing_an_old_index() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "old")?;
        let old = rebuild(&root, &input)?;
        let pointer = root.join("CURRENT.json");
        for generation in ["../escape", "gen-missing"] {
            let mut broken = old.clone();
            broken.generation = generation.to_owned();
            fs::write(&pointer, serde_json::to_vec(&broken)?)?;
            assert!(current(&root)
                .and_then(|manifest| manifest.open(&root))
                .is_err());
            assert!(recover(&root).is_err());
        }
        let mut broken = old.clone();
        broken.record_count = 500;
        fs::write(&pointer, serde_json::to_vec(&broken)?)?;
        assert!(broken.open(&root).is_err());
        // A recognized but broken generation can be replaced from the export.
        assert!(rebuild(&root, &input)?.open(&root).is_ok());
        fs::write(&pointer, "{")?;
        assert!(recover(&root).is_err());
        assert!(rebuild(&root, &input).is_err());
        Ok(())
    }

    #[test]
    fn writer_lock_excludes_recovery_and_rebuild_but_never_readers() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "old")?;
        rebuild(&root, &input)?;
        let lock = writer_lock(&root)?;
        assert!(rebuild(&root, &input).is_err());
        assert!(recover(&root).is_err());
        assert_eq!(ids(&current(&root)?.open(&root)?)?, vec!["old"]);
        drop(lock);
        rebuild(&root, &input)?;
        Ok(())
    }

    #[test]
    fn initial_failure_and_abandoned_staging_can_be_recovered() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("bad.jsonl");
        fs::write(&input, "invalid JSON\n")?;
        assert!(rebuild(&root, &input).is_err());
        assert!(current(&root).is_err());
        fs::create_dir(root.join("generations/.build-orphan"))?;
        fs::write(root.join("generations/.build-orphan/partial"), "partial")?;
        fs::write(root.join(".current-orphan"), "partial")?;
        let recovery = recover(&root)?;
        assert!(recovery.current.is_none());
        assert_eq!(recovery.removed_staging_entries, 2);
        records(&input, "new")?;
        assert_eq!(ids(&rebuild(&root, &input)?.open(&root)?)?, vec!["new"]);
        Ok(())
    }

    #[test]
    fn removal_guard_refuses_live_readers_and_blocks_new_ones_until_release() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "current")?;
        let current = rebuild(&root, &input)?;
        let held = current.open(&root)?;
        assert!(prepare_removal(&root).is_err());
        drop(held);
        let guard = prepare_removal(&root)?;
        assert!(reader_gate(&root)?.try_lock_shared().is_err());
        assert!(rebuild(&root, &input).is_err());
        drop(guard);
        assert_eq!(ids(&pin_current(&root)?.open()?)?, vec!["current"]);
        Ok(())
    }

    #[test]
    fn cleanup_skips_leased_snapshots_then_reclaims_them_after_release() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "old")?;
        let old = rebuild(&root, &input)?;
        let held = old.open(&root)?;
        records(&input, "new")?;
        let new = rebuild(&root, &input)?;
        let before = fs::read(root.join("CURRENT.json"))?;
        let result = cleanup(&root)?;
        assert_eq!(result.pinned_generations, vec![old.generation.clone()]);
        assert!(result.removed_generations.is_empty());
        assert_eq!(ids(&held)?, vec!["old"]);
        assert!(old.records_path(&root).is_file());
        drop(held);
        let result = cleanup(&root)?;
        assert_eq!(result.removed_generations, vec![old.generation.clone()]);
        assert!(!old.generation_path(&root).exists());
        assert!(old.open(&root).is_err()); // No lock inode is recreated after deletion.
        assert_eq!(fs::read(root.join("CURRENT.json"))?, before);
        assert_eq!(ids(&pin_current(&root)?.open()?)?, vec!["new"]);
        assert!(new.records_path(&root).is_file());
        assert!(cleanup(&root)?.removed_generations.is_empty());
        Ok(())
    }

    #[test]
    fn selection_gate_prevents_retirement_before_reader_lease_acquisition() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "old")?;
        let old = rebuild(&root, &input)?;
        records(&input, "new")?;
        rebuild(&root, &input)?;
        // Pause a reader between selecting an old manifest and acquiring its
        // lease. Cleanup must wait for this shared gate before retirement.
        let gate = reader_gate(&root)?;
        gate.lock_shared()?;
        let other_root = root.clone();
        let collector = std::thread::spawn(move || cleanup(&other_root));
        let probe = regular_file(&root.join("write.lock"))?;
        let started = std::time::Instant::now();
        loop {
            match probe.try_lock() {
                Err(std::fs::TryLockError::WouldBlock) => break,
                Ok(()) => probe.unlock()?,
                Err(error) => return Err(error.into()),
            }
            assert!(started.elapsed() < std::time::Duration::from_secs(5));
            std::thread::sleep(std::time::Duration::from_millis(1));
        }
        let pinned = pin(old.clone(), &root)?;
        drop(gate);
        let result = collector.join().unwrap()?;
        assert_eq!(result.pinned_generations, vec![old.generation.clone()]);
        let snapshot = pinned.open()?;
        assert_eq!(ids(&snapshot)?, vec!["old"]);
        drop(snapshot);
        assert_eq!(cleanup(&root)?.removed_generations, vec![old.generation]);
        Ok(())
    }

    #[test]
    fn interrupted_cleanup_retries_trash_without_touching_current() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "old")?;
        let old = rebuild(&root, &input)?;
        records(&input, "new")?;
        rebuild(&root, &input)?;
        assert!(cleanup_with_hook(&root, |trash| {
            assert!(trash.exists());
            assert!(!old.generation_path(&root).exists());
            bail!("interruption after retirement")
        })
        .is_err());
        assert_eq!(ids(&pin_current(&root)?.open()?)?, vec!["new"]);
        let result = cleanup(&root)?;
        assert_eq!(result.removed_trash_entries, 1);
        assert!(!root
            .join("generations")
            .join(format!(".trash-{}", old.generation))
            .exists());
        Ok(())
    }

    #[test]
    fn cleanup_retains_legacy_unknown_and_unleased_generations() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "legacy")?;
        let mut legacy = rebuild(&root, &input)?;
        fs::remove_file(legacy.generation_path(&root).join("manifest.json"))?;
        fs::remove_file(legacy.generation_path(&root).join("read.lock"))?;
        legacy.lease_version = 0;
        let mut encoded = serde_json::to_value(&legacy)?;
        encoded.as_object_mut().unwrap().remove("lease_version");
        fs::write(root.join("CURRENT.json"), serde_json::to_vec(&encoded)?)?;
        let held = current(&root)?.open(&root)?;
        records(&input, "unsupported")?;
        let unsupported = rebuild(&root, &input)?;
        let mut marker = unsupported.clone();
        marker.lease_version = 2;
        fs::write(
            unsupported.generation_path(&root).join("manifest.json"),
            serde_json::to_vec(&marker)?,
        )?;
        records(&input, "missing-lock")?;
        let missing = rebuild(&root, &input)?;
        fs::remove_file(missing.generation_path(&root).join("read.lock"))?;
        records(&input, "current")?;
        rebuild(&root, &input)?;
        let result = cleanup(&root)?;
        assert!(result.removed_generations.is_empty());
        assert_eq!(result.retained_unrecognized.len(), 3);
        assert_eq!(ids(&held)?, vec!["legacy"]);
        drop(held);
        assert_eq!(cleanup(&root)?.retained_unrecognized.len(), 3);
        Ok(())
    }

    #[test]
    fn cleanup_reclaims_unpublished_completed_generations_but_refuses_bad_current() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        let input = temp.path().join("records.jsonl");
        records(&input, "unpublished")?;
        assert!(rebuild_with_hook(&root, &input, |checkpoint| {
            if matches!(checkpoint, Checkpoint::Generation) {
                bail!("interruption before initial publication");
            }
            Ok(())
        })
        .is_err());
        let result = cleanup(&root)?;
        assert!(result.current.is_none());
        assert_eq!(result.removed_generations.len(), 1);
        let manifest = rebuild(&root, &input)?;
        fs::write(root.join("CURRENT.json"), "broken")?;
        assert!(cleanup(&root).is_err());
        assert!(manifest.generation_path(&root).exists());
        Ok(())
    }

    #[cfg(unix)]
    #[test]
    fn recovery_removes_staging_symlinks_without_touching_targets() -> Result<()> {
        use std::os::unix::fs::symlink;
        let temp = tempfile::tempdir()?;
        let root = temp.path().join("store");
        recover(&root)?;
        let external = temp.path().join("external");
        fs::create_dir(&external)?;
        fs::write(external.join("keep"), "safe")?;
        symlink(&external, root.join("generations/.build-link"))?;
        assert_eq!(recover(&root)?.removed_staging_entries, 1);
        assert_eq!(fs::read_to_string(external.join("keep"))?, "safe");
        symlink(&external, root.join("CURRENT.json"))?;
        assert!(current(&root).is_err());
        assert!(rebuild(&root, &external.join("keep")).is_err());
        Ok(())
    }
}
