//! Model-free benchmark engine. Python owns governance and final citations.

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::cmp::Reverse;
use std::collections::BTreeMap;
use std::fs::File;
use std::io::{BufRead, BufReader, Read, Seek};
use std::path::Path;
use tantivy::collector::TopDocs;
use tantivy::query::{BooleanQuery, Occur, Query, QueryParser, TermQuery};
use tantivy::schema::{IndexRecordOption, Schema, Value, FAST, STORED, STRING, TEXT};
use tantivy::tokenizer::{AsciiFoldingFilter, LowerCaser, SimpleTokenizer, TextAnalyzer};
use tantivy::{doc, DocId, Index, IndexReader, Score, SegmentReader, TantivyDocument, Term};

pub const ENGINE_VERSION: &str = "tantivy-0.25.0/keyword-1";
pub mod store;
const MAX_RECORD_BYTES: usize = 1_048_576;

#[derive(Deserialize)]
pub struct Record {
    pub schema_version: u32,
    pub section_id: String,
    pub item_id: String,
    pub path: String,
    pub title: String,
    pub description: String,
    pub heading: String,
    pub body: String,
    pub line_start: u64,
    pub line_end: u64,
    #[serde(rename = "type")]
    pub item_type: String,
    pub status: String,
}

#[derive(Debug, Serialize)]
pub struct Hit {
    pub section_id: String,
    pub score: f32,
    pub record_offset: u64,
}

fn schema() -> Schema {
    let mut builder = Schema::builder();
    for name in ["section_id", "item_id", "path", "type", "status"] {
        builder.add_text_field(name, STRING | STORED);
    }
    for name in ["title", "description", "heading", "body"] {
        builder.add_text_field(name, TEXT);
    }
    builder.add_u64_field("ordinal", FAST | STORED);
    builder.add_u64_field("record_offset", STORED);
    builder.build()
}

fn configure_tokenizer(index: &Index) {
    // Keep literal Unicode terms; fold accents like SQLite unicode61's baseline.
    let analyzer = TextAnalyzer::builder(SimpleTokenizer::default())
        .filter(LowerCaser)
        .filter(AsciiFoldingFilter)
        .build();
    index.tokenizers().register("default", analyzer);
}

pub fn build(destination: &Path, records_path: &Path) -> Result<usize> {
    // Build only into a new directory. The benchmark orchestrator stages and
    // publishes completed indexes; the sidecar never overwrites an old index.
    std::fs::create_dir(destination).context("index destination must be new")?;
    let schema = schema();
    let index = Index::create_in_dir(destination, schema.clone())?;
    configure_tokenizer(&index);
    let field = |name: &str| schema.get_field(name).expect("fixed schema");
    let mut writer = index.writer_with_num_threads(1, 50_000_000)?;
    let mut reader = BufReader::new(File::open(records_path)?);
    let mut count = 0_u64;
    loop {
        let record_offset = reader.stream_position()?;
        let mut line = Vec::new();
        // Bounded line reading prevents a malformed export from allocating an
        // arbitrarily large buffer. Each canonical section has its own record.
        (&mut reader)
            .take((MAX_RECORD_BYTES + 1) as u64)
            .read_until(b'\n', &mut line)?;
        if line.is_empty() {
            break;
        }
        if line.len() > MAX_RECORD_BYTES {
            bail!("normalized record exceeds 1 MiB");
        }
        let record: Record = serde_json::from_slice(&line)?;
        if record.schema_version != 1
            || record.line_start == 0
            || record.line_end < record.line_start
        {
            bail!("unsupported or invalid normalized record");
        }
        writer.add_document(doc!(
            field("section_id") => record.section_id,
            field("item_id") => record.item_id,
            field("path") => record.path,
            field("type") => record.item_type,
            field("status") => record.status,
            field("title") => record.title,
            field("description") => record.description,
            field("heading") => record.heading,
            field("body") => record.body,
            field("ordinal") => count,
            field("record_offset") => record_offset,
        ))?;
        count += 1;
    }
    writer.commit()?;
    writer.wait_merging_threads()?;
    Ok(count as usize)
}

pub struct Engine {
    index: Index,
    reader: IndexReader,
}

impl Engine {
    pub fn record_count(&self) -> u64 {
        self.reader.searcher().num_docs()
    }

    pub fn open(path: &Path) -> Result<Self> {
        let index = Index::open_in_dir(path)?;
        if index.schema() != schema() {
            bail!("unsupported index schema; rebuild the prototype index");
        }
        configure_tokenizer(&index);
        let reader = index.reader()?;
        Ok(Self { index, reader })
    }

    pub fn query(
        &self,
        text: &str,
        tokens: &[String],
        exact_field: Option<&str>,
        limit: usize,
        filters: &BTreeMap<String, String>,
    ) -> Result<Vec<Hit>> {
        if !(1..=100).contains(&limit) || text.len() > 4096 || tokens.len() > 256 {
            bail!("invalid query bounds");
        }
        let schema = self.index.schema();
        let field = |name: &str| schema.get_field(name).expect("fixed schema");
        let lexical: Box<dyn Query> = if let Some(name) = exact_field {
            if !["item_id", "path"].contains(&name) {
                bail!("unsupported exact field");
            }
            Box::new(TermQuery::new(
                Term::from_field_text(field(name), text),
                IndexRecordOption::Basic,
            ))
        } else {
            if tokens.is_empty() {
                return Ok(Vec::new());
            }
            if tokens
                .iter()
                .any(|term| term.is_empty() || !term.chars().all(char::is_alphanumeric))
            {
                bail!("query tokens must be literal alphanumeric words");
            }
            let mut parser = QueryParser::for_index(
                &self.index,
                vec![
                    field("title"),
                    field("description"),
                    field("heading"),
                    field("body"),
                ],
            );
            parser.set_field_boost(field("title"), 8.0);
            parser.set_field_boost(field("description"), 3.0);
            parser.set_field_boost(field("heading"), 5.0);
            let literal = tokens
                .iter()
                .map(|token| format!("\"{token}\""))
                .collect::<Vec<_>>()
                .join(" AND ");
            parser.parse_query(&literal)?
        };
        let mut clauses = vec![(Occur::Must, lexical)];
        for (name, value) in filters {
            if !["type", "status"].contains(&name.as_str()) {
                bail!("unsupported filter");
            }
            clauses.push((
                Occur::Must,
                Box::new(TermQuery::new(
                    Term::from_field_text(field(name), value),
                    IndexRecordOption::Basic,
                )) as Box<dyn Query>,
            ));
        }
        let query = BooleanQuery::new(clauses);
        let searcher = self.reader.searcher();
        // Break score ties by normalized input ordinal, including ties at the
        // limit boundary. Segment merging cannot change the final tie order.
        let collector = TopDocs::with_limit(limit).tweak_score(|segment: &SegmentReader| {
            let ordinals = segment
                .fast_fields()
                .u64("ordinal")
                .expect("fixed ordinal field");
            move |doc: DocId, score: Score| (score, Reverse(ordinals.first(doc).unwrap_or(0)))
        });
        searcher
            .search(&query, &collector)?
            .into_iter()
            .map(|((score, _), address)| {
                let document: TantivyDocument = searcher.doc(address)?;
                let id = document
                    .get_first(field("section_id"))
                    .and_then(|value| value.as_str())
                    .context("missing section ID")?;
                Ok(Hit {
                    section_id: id.to_owned(),
                    score,
                    record_offset: document
                        .get_first(field("record_offset"))
                        .and_then(|value| value.as_u64())
                        .context("missing record offset")?,
                })
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn exact_ties_filters_and_literal_unicode_terms() -> Result<()> {
        let directory = tempfile::tempdir()?;
        let records = directory.path().join("records.jsonl");
        let rows: Vec<_> = (0..3)
            .map(|ordinal| {
                json!({
                    "schema_version": 1, "section_id": format!("section-{ordinal}"),
                    "item_id": "opaque-item", "path": "rotación.md", "title": "Autorización",
                    "description": "", "heading": "Pasos", "body": "Recuperar acceso.",
                    "line_start": 1, "line_end": 1, "type": "procedure", "status": "draft",
                })
                .to_string()
            })
            .collect();
        std::fs::write(&records, rows.join("\n"))?;
        let destination = directory.path().join("index");
        assert_eq!(build(&destination, &records)?, 3);
        let engine = Engine::open(&destination)?;
        let hits = engine.query("opaque-item", &[], Some("item_id"), 2, &BTreeMap::new())?;
        assert_eq!(
            hits.iter()
                .map(|hit| hit.section_id.as_str())
                .collect::<Vec<_>>(),
            vec!["section-0", "section-1"]
        );
        assert!(engine
            .query(
                "opaque-item",
                &[],
                Some("item_id"),
                2,
                &BTreeMap::from([("status".to_owned(), "stable".to_owned())])
            )?
            .is_empty());
        assert_eq!(
            engine
                .query(
                    "autorizacion",
                    &["autorizacion".to_owned()],
                    None,
                    2,
                    &BTreeMap::new()
                )?
                .len(),
            2
        );
        assert!(engine
            .query(
                "bad",
                &["foo\" OR bar".to_owned()],
                None,
                2,
                &BTreeMap::new()
            )
            .is_err());
        assert!(build(&destination, &records).is_err());
        Ok(())
    }

    #[test]
    fn unsupported_record_version_fails() -> Result<()> {
        let directory = tempfile::tempdir()?;
        let records = directory.path().join("bad.jsonl");
        std::fs::write(
            &records,
            json!({
                "schema_version": 2, "section_id": "section", "item_id": "item", "path": "x.md",
                "title": "X", "description": "", "heading": "X", "body": "Text",
                "line_start": 1, "line_end": 1, "type": "concept", "status": "draft",
            })
            .to_string(),
        )?;
        assert!(build(&directory.path().join("index"), &records).is_err());
        Ok(())
    }
}
