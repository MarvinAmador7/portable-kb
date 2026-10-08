# Research findings

Research date: 2026-08-06. The mutable OKF repository was inspected at main
commit `930b65fc3f5619d5d0591f88c72ebae8b848d60d`.

This document separates facts directly stated by a source from architectural
recommendations made for this project. “Direct” means the cited source states
the claim. “Recommendation” means the conclusion is a local design choice or a
synthesis across sources.

## Primary-source register

| Source | Status | What it directly supports |
|---|---|---|
| [Google Cloud: How the Open Knowledge Format can improve data sharing](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/) | Official launch announcement, June 2026 | OKF is a format rather than a service; producer/consumer independence; Markdown plus frontmatter; exactly one always-required concept field in v0.1; open and vendor-neutral intent. |
| [Google Cloud: OKF v0.2 adds trust signals](https://cloud.google.com/blog/products/data-analytics/okf-v0-2-adds-trust-signals/) | Official v0.2 announcement, July 24, 2026 | The five questions of provenance, trust, freshness, lifecycle, and attestation; the optional `sources`, `generated`, `verified`, `status`, and `stale_after` vocabulary; trust is derived from signals rather than a stored score. |
| [GoogleCloudPlatform/knowledge-catalog: OKF SPEC.md](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) | Canonical current specification, v0.2 | Normative file, directory, frontmatter, link, index, log, actor, lifecycle, trust-tier, and conformance rules. |
| [W3C PROV-O](https://www.w3.org/TR/prov-o/) | W3C Recommendation | Provenance can be modeled around entities, activities, and agents; the design can grow beyond a simple source list if needed. |
| [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/) | W3C Recommendation, 2009 | SKOS is a data model for concept schemes, labels, notes, semantic relationships, collections, and mappings. |
| [W3C RDF 1.2 Concepts](https://www.w3.org/TR/rdf12-concepts/) | Candidate Recommendation snapshot, 2026; RDF 1.1 remains the latest Recommendation | A graph is a set of subject-predicate-object triples and can be visualized as nodes and directed arcs. Used only for comparison, not adopted. |
| [KCS v6 Practices Guide](https://library.serviceinnovation.org/KCS/KCS_v6/KCS_v6_Practices_Guide) | Official Consortium for Service Innovation guide | Capture in the moment, simple article structure, reuse, linking, quality, Solve Loop and Evolve Loop practices. |
| [Lewis et al., Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401) | Original RAG research paper, 2020 | RAG combines parametric generation with retrieved non-parametric memory; it is an inference architecture, not a durable source format. |
| [Microsoft Learn: SharePoint as a Copilot Studio knowledge source](https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-add-sharepoint) | Official product documentation | SharePoint can be a permission-aware, live grounding source for agents; retrieval and access control are platform services. |
| [Microsoft Learn: Semantic indexing for Microsoft 365 Copilot](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot) | Official product documentation | Microsoft’s semantic index supports conceptual retrieval and uses content plus metadata as grounding signals. |
| [Forte Labs: PARA project-based organization](https://fortelabs.com/blog/the-box-twyla-tharp-on-project-based-organizing/) | Originator’s explanatory material | PARA organizes information by actionability into Projects, Areas, Resources, and Archives. |
| [Zettelkasten Method introduction](https://zettelkasten.de/introduction/) | Practitioner reference; no normative standard exists | Zettelkasten emphasizes personal, atomic, hypertextual notes and relationships. |
| [YAML 1.2.2 specification](https://yaml.org/spec/1.2.2/) | Language specification | YAML is Unicode-based, portable, and designed for human-readable data serialization. |
| [CommonMark specification](https://spec.commonmark.org/0.31.2/) | Markdown specification | The portable syntax and parsing rules for headings, links, lists, code fences, and other Markdown constructs. |

No blog post or search snippet was used to override the official OKF
specification. Product and methodology comparisons use primary or originating
sources where available. Zettelkasten and “knowledge graph” do not have a
single controlling standard, so those comparisons are explicitly conceptual.

## Current OKF findings

### Format and bundle

Direct findings from OKF v0.2:

- A knowledge bundle is a directory tree and a concept is one UTF-8 Markdown
  document with YAML frontmatter and a Markdown body.
- The concept ID in baseline OKF is the concept file’s bundle-relative path
  without `.md`.
- A bundle may be a Git repository, an archive, or a subdirectory.
- `index.md` and `log.md` are reserved names at every directory level.
- `index.md` supports progressive disclosure. Except for an optional
  `okf_version` in the root index, it has no frontmatter.
- `log.md` is a newest-first list grouped under ISO date headings.
- A `references/` directory is a convention, not a requirement.

Recommendation:

- Put the future bundle under `knowledge/` so repository-level design,
  templates, and code do not accidentally become OKF concepts.
- Add an immutable UUID URN to each concept because path identity alone does
  not survive moves. Keep path identity for baseline OKF consumption and use
  UUIDs only as a compatible extension.

### Frontmatter and body

Direct findings from OKF v0.2:

- `type` is the only field required of every concept.
- `title`, `description`, `resource`, and `tags` are recommended.
- Type values are not centrally registered. Consumers must tolerate unknown
  types.
- Producers may add fields. Consumers should preserve unknown fields on
  round-trip and must not reject a concept only because fields are unknown.
- Structured Markdown is preferred. `# Schema`, `# Examples`, and
  `# Computation` have conventional meaning, but no body section is required.

Recommendation:

- Define a strict local profile with a small controlled vocabulary and
  namespaced `x-` extension escape hatch. Strict authoring improves governance;
  importers must still preserve unknown OKF fields.
- Require `id`, `title`, `description`, lifecycle dates, and production
  metadata locally even though baseline OKF does not.

### Provenance and source credibility

Direct findings from OKF v0.2:

- `sources` records the materials from which a concept derives.
- Each source entry requires `resource` if the entry is present; `id`, `title`,
  `author`, `usage_count`, and `last_modified` are optional.
- A Markdown footnote label may match `sources[].id` for claim-level
  attribution.
- `usage_window` gives context to `usage_count`.
- OKF records objective source signals, not a portable credibility score.
- Deeper lineage is out of scope for v0.2 and may be expressed with links.

Recommendation:

- Require at least one source for imported, transformed, calculated,
  summarized, and agent-generated items. Do not invent a source for original
  human knowledge; its actor and Git history are its creation provenance.
- Require source IDs when bodies use claim-level citations and validate every
  footnote/source join.
- Treat `usage_count` only as liveness evidence, never as authority.
- Start with OKF’s flat source list. Map to W3C PROV only if later requirements
  need explicit activities, delegation, or multi-hop lineage.

### Generation, verification, trust, freshness, and lifecycle

Direct findings from OKF v0.2:

- `generated` records who or what produced the current content; `verified`
  records independent confirmations.
- Actors use `<producer>/<version>` for agents/tools, `human:<id>` for people,
  and `process:<id>` for automated processes.
- Consumers derive three advisory tiers: unverified, machine-confirmed, and
  human-reviewed. A tier is not access control.
- `status` is `draft`, `stable`, or `deprecated`; absence means `stable`.
- `stale_after` is an absolute date and content is stale when
  `today >= stale_after`.
- All these fields are optional in baseline OKF. Their absence carries meaning
  but does not invalidate a bundle.
- v0.2 supersedes v0.1’s `timestamp` with `generated.at` and its body citation
  list with `sources`.

Recommendation:

- Make the OKF fields explicit and mandatory where the local profile needs
  them. Never rely on OKF’s implicit stable status.
- Add `generated.method` to distinguish human-authored, imported,
  transformed, agent-generated, and calculated content without replacing the
  OKF actor convention.
- Require an uncertainty statement for agent-generated content. Keep it
  distinct from source authority and verification.
- Invalidate current verification on a material content change. Git preserves
  old verification events in history; current frontmatter must describe only
  the current content.
- Treat archive as a location/disposition, not a fourth OKF status.

### Links and conformance

Direct findings from OKF v0.2:

- Relationships use ordinary Markdown links. Bundle-root paths beginning with
  `/` are recommended; relative paths are allowed.
- Relationship type comes from surrounding prose; baseline links are untyped.
- Broken links do not make an OKF concept malformed.
- A conformant v0.2 bundle requires parseable frontmatter with non-empty
  `type` on every non-reserved Markdown file and conforming reserved files.
- Consumers must not reject a bundle merely for missing optional fields,
  unknown types/keys, broken cross-links, or missing indexes.

Recommendation:

- Use ordinary Markdown links as the readable graph and local UUID fields for
  the three typed relations needed initially: `related`, `supersedes`, and
  `superseded_by`.
- Make broken internal links a local error in curated content and a warning in
  inbox drafts. This is stricter than OKF conformance and must be reported as
  such.

## Comparisons

| Approach | Primary purpose | How it differs from this design | Useful idea retained |
|---|---|---|---|
| Normal Markdown wiki | Human browsing and collaborative pages | Usually has no portable schema for provenance, generation method, verification, staleness, or lifecycle. Link meaning and history depend on the platform. | Readable prose, simple links, low authoring friction. |
| Zettelkasten | Personal thinking through atomic, strongly connected notes | Personal and emergent rather than organizational and governed; it normally does not define authority, verification, source ranking, or operational lifecycle. | Atomicity, stable addresses, deliberate links, structure notes. |
| PARA | Organize information by actionability | A filing method, not an interchange format or trust model. Folder placement changes as actionability changes. | Projects and archive as useful navigation/disposition views. |
| RAG | Generate answers using retrieved external memory | A runtime inference pattern. It neither defines the durable source corpus nor makes retrieved similarity authoritative. | The corpus should expose clean chunks, metadata, and citations for future retrieval. |
| Vector database | Efficient vector similarity search and filtering | An index/storage engine. Embeddings are derived, model-dependent, and insufficient for provenance or authority. | Future disposable index over canonical files. |
| Knowledge graph | Explicit entities and typed relationships, often as RDF triples or property graphs | A graph data model and query system; more formal and operationally heavier than linked Markdown. | Stable IDs and relationships make later graph projection possible. |
| SharePoint / Microsoft Copilot KM | Managed content, permissions, indexing, semantic retrieval, and grounding inside Microsoft 365 | Platform services with identity, live connectors, permissions, licenses, and proprietary operational behavior. This design is portable files and intentionally has no authorization or retrieval service. | Metadata, source scoping, freshness, and permission-aware retrieval are future integration concerns. |
| KCS | A service-management practice for capturing, reusing, improving, and governing articles in the workflow | A socio-technical operating method rather than a file format. It is optimized around resolving demand and reuse. | Capture in the moment, simple templates, link/reuse, quality reviews, and continuous improvement loops. |
| SKOS | Standard representation of controlled vocabularies and concept schemes | Defines labels, broader/narrower/related relations, mappings, and schemes; it does not define a Markdown article lifecycle or operational runbook model. | A later taxonomy export and controlled terminology layer, if justified. |

OKF can coexist with all of these. It can be the canonical source consumed by a
RAG pipeline, indexed in a vector database, projected into a graph, organized
with some PARA-like folders, or imported into enterprise platforms. None of
those systems replaces the file-level provenance and lifecycle contract.

## Human-readable and agent-readable patterns

Directly supported patterns:

- OKF recommends structured Markdown and progressive `index.md` files.
- CommonMark defines portable headings, lists, fenced code, and links.
- YAML 1.2 is human-oriented and language-portable.
- KCS recommends simple structure, capture in the workflow, linking, reuse,
  and quality practices.

Recommendations:

- Put facts people/agents filter on in frontmatter; put explanation and context
  in the body.
- Use predictable headings per content type without making prose robotic.
- Make descriptions one sentence so indexes and previews stay useful.
- Use explicit UTC timestamps and absolute stale dates.
- Prefer one durable subject per file, but do not fragment procedures or
  decisions into unusably small notes.
- Standard links remain the portable interchange form. The user-approved
  Portable KB wikilink extension adds exact local resolution and a standard
  Markdown view; it is a local consumer convention, not upstream OKF syntax.
  See [the contract and migration notes](links.md).
- Keep generated indexes reproducible and never hand-edit generated regions.
- Keep every important claim close to its citation.

## Risks found in the research

The official OKF v0.2 motivation explicitly identifies the loss of implicit
human accountability when agents generate a large corpus. The following
operational risks are project recommendations derived from that problem:

- **Generated authority laundering:** polished prose can look approved. Control
  it with `generated.method`, draft status, source requirements, and human
  verification gates for authoritative types.
- **Staleness:** a recent file edit does not prove a fact is current. Track
  source modification, generation time, verification time, and an explicit
  `stale_after` separately.
- **Duplicate concepts:** filenames and semantic similarity are not identity.
  Use immutable IDs, normalized titles, exact source/resource matching, and
  human review of similarity candidates.
- **Conflicts:** multiple sources may be valid in different scopes or periods.
  Do not average or silently merge. Preserve both, state scope and effective
  dates, and create a resolution decision or question.
- **Citation drift:** prose changes while citations stay. Require source IDs,
  claim-level footnotes for consequential claims, and re-verification after
  material changes.
- **Metadata theater:** frontmatter describes evidence; it does not make a
  statement true. Verification must define what was checked and reviewers must
  inspect the body and sources.
- **Folder semantics:** moves can silently change meaning in folder-only
  systems. Keep identity, type, and lifecycle in the document.
- **Schema overgrowth:** trying to model all domains early creates unused,
  inconsistent fields. Begin with seven types and a small extension policy.

## Source-supported conclusions versus recommendations

Source-supported conclusions:

1. OKF v0.2 is the current target, not v0.1.
2. Baseline OKF is deliberately permissive and has one universally required
   concept key: `type`.
3. OKF v0.2 provides optional standard vocabulary for provenance, generation,
   verification, trust-tier derivation, staleness, lifecycle, and attested
   computations.
4. OKF uses path identity and ordinary Markdown links.
5. Git is a recommended distribution mechanism and provides diffs/history.
6. KCS, SKOS, RAG, vector indexes, and Microsoft’s platform solve different
   layers of the knowledge problem.

Architectural recommendations:

1. Add immutable UUID identity while retaining OKF path identity.
2. Apply a strict local profile at authoring time but keep import/round-trip
   behavior permissive and lossless.
3. Separate confidence (uncertainty) from authority and verification.
4. Require sources conditionally and human approval for stable authoritative
   content.
5. Treat archive as location, not status.
6. Keep canonical data in files and treat all future indexes as rebuildable.
7. Defer attested computation, taxonomy standards, graph projection, and all
   retrieval/integration work until the file model is proven.

## Wikilink consumer extension review

On 2026-10-07, upstream cross-linking section 6 was rechecked at specification
commit `62432a095456147ee71e70ac6e4dc0d2dea3ac30`. It defines standard Markdown
relative/bundle-root links and untyped relationships conveyed by prose.
Portable KB wikilinks are a local authoring/navigation extension with a derived
standard Markdown view; this does not redefine upstream link semantics.
The motivating private wiki was reviewed outside the source repository.
Product fixtures and agent scenarios use independently invented content.
