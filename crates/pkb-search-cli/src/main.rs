//! Bounded JSON Lines benchmark sidecar; no network, models, or content hooks.

use anyhow::{bail, Context, Result};
use pkb_search_core::{build, store, Engine, ENGINE_VERSION};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};
use std::io::{self, BufRead, Read, Write};
use std::path::PathBuf;
use std::time::Instant;

const MAX_REQUEST_BYTES: usize = 65_536;

fn peak_rss_kib() -> Option<u64> {
    // Optional Linux process high-water mark; other targets report unavailable.
    std::fs::read_to_string("/proc/self/status")
        .ok()?
        .lines()
        .find(|line| line.starts_with("VmHWM:"))?
        .split_whitespace()
        .nth(1)?
        .parse()
        .ok()
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    protocol_version: u32,
    op: String,
    index_path: Option<PathBuf>,
    records_path: Option<PathBuf>,
    brain: Option<store::BrainPin>,
    query: Option<String>,
    tokens: Option<Vec<String>>,
    exact_field: Option<String>,
    limit: Option<usize>,
    #[serde(default)]
    filters: BTreeMap<String, String>,
}

type StoreReaders = HashMap<PathBuf, store::Snapshot>;

fn handle(
    request: Request,
    engines: &mut HashMap<PathBuf, Engine>,
    stores: &mut StoreReaders,
    removals: &mut HashMap<PathBuf, store::RemovalGuard>,
) -> Result<Value> {
    if request.protocol_version != 1 {
        bail!("unsupported protocol version");
    }
    if request.op == "status" {
        return Ok(json!({"version": ENGINE_VERSION}));
    }
    let path = request.index_path.context("index_path is required")?;
    let started = Instant::now();
    if removals.contains_key(&path) && request.op != "release_remove" {
        bail!("store is prepared for removal");
    }
    match request.op.as_str() {
        "build" => {
            let records = request.records_path.context("records_path is required")?;
            let count = build(&path, &records)?;
            Ok(
                json!({"record_count": count, "elapsed_ms": started.elapsed().as_secs_f64() * 1000.0}),
            )
        }
        "rebuild" => {
            let records = request.records_path.context("records_path is required")?;
            let manifest = store::rebuild_for_brain(&path, &records, request.brain)?;
            Ok(
                json!({"manifest": manifest, "elapsed_ms": started.elapsed().as_secs_f64() * 1000.0}),
            )
        }
        "recover" => Ok(serde_json::to_value(store::recover(&path)?)?),
        "prepare_remove" => {
            stores.remove(&path);
            removals.insert(path.clone(), store::prepare_removal(&path)?);
            Ok(json!({"prepared": true}))
        }
        "release_remove" => Ok(json!({"released": removals.remove(&path).is_some()})),
        "cleanup" => Ok(serde_json::to_value(store::cleanup(&path)?)?),
        "release_store" => Ok(json!({"released": stores.remove(&path).is_some()})),
        "query_store" => {
            let pinned = store::pin_current(&path)?;
            let manifest = pinned.manifest().clone();
            let opened = stores
                .get(&path)
                .is_none_or(|cached| cached.manifest() != &manifest);
            if opened {
                // Open before replacing the cached reader. Failed refreshes do
                // not mutate the old snapshot, but the request fails closed.
                let snapshot = pinned.open()?;
                stores.insert(path.clone(), snapshot);
            }
            let open_ms = started.elapsed().as_secs_f64() * 1000.0;
            let query_started = Instant::now();
            let hits = stores[&path].query(
                &request.query.context("query is required")?,
                &request.tokens.context("tokens are required")?,
                request.exact_field.as_deref(),
                request.limit.unwrap_or(10),
                &request.filters,
            )?;
            Ok(json!({"hits": hits, "manifest": manifest,
                "records_path": manifest.records_path(&path),
                "query_ms": query_started.elapsed().as_secs_f64() * 1000.0,
                "open_ms": open_ms, "opened": opened}))
        }
        "query" => {
            let opened = !engines.contains_key(&path);
            if opened {
                engines.insert(path.clone(), Engine::open(&path)?);
            }
            let open_ms = started.elapsed().as_secs_f64() * 1000.0;
            let query_started = Instant::now();
            let hits = engines[&path].query(
                &request.query.context("query is required")?,
                &request.tokens.context("tokens are required")?,
                request.exact_field.as_deref(),
                request.limit.unwrap_or(10),
                &request.filters,
            )?;
            Ok(
                json!({"hits": hits, "query_ms": query_started.elapsed().as_secs_f64() * 1000.0,
                "open_ms": open_ms, "opened": opened}),
            )
        }
        _ => bail!("unsupported operation"),
    }
}

fn main() -> Result<()> {
    let stdin = io::stdin();
    let mut input = stdin.lock();
    let mut output = io::stdout().lock();
    let mut engines = HashMap::new();
    let mut stores = HashMap::new();
    let mut removals = HashMap::new();
    loop {
        let mut line = Vec::new();
        (&mut input)
            .take((MAX_REQUEST_BYTES + 1) as u64)
            .read_until(b'\n', &mut line)?;
        if line.is_empty() {
            break;
        }
        let oversized = line.len() > MAX_REQUEST_BYTES;
        let result = if oversized {
            Err(anyhow::anyhow!("request exceeds 64 KiB"))
        } else {
            serde_json::from_slice::<Request>(&line)
                .map_err(anyhow::Error::from)
                .and_then(|request| handle(request, &mut engines, &mut stores, &mut removals))
        };
        let response = match result {
            Ok(value) => {
                json!({"protocol_version":1, "ok":true, "result":value, "peak_rss_kib":peak_rss_kib()})
            }
            Err(error) => json!({"protocol_version":1, "ok":false, "error":format!("{error:#}")}),
        };
        serde_json::to_writer(&mut output, &response)?;
        writeln!(output)?;
        output.flush()?;
        if oversized {
            break;
        }
    }
    Ok(())
}
