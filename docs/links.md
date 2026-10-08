# Navigate connected knowledge

Use links to explain relationships in prose, then follow their canonical items:

```sh
pkb links "customer-onboarding" --brain team --json
pkb backlinks "customer-onboarding" --brain team --json
pkb get "[[procedures/customer-onboarding]]" --brain team --json
pkb get "customer-onboarding" --brain team --markdown-links --json
```

These commands read a clean, validated, pinned installed brain. They do not need
a keyword index, a model, or a graph database. An explicit `--brain` preserves
scope and never changes the active selection. Retrieval refuses dirty or invalid
checkouts through the same health gate as `get` and search.

## Authoring links

Standard inline Markdown links remain supported. Wikilinks are an optional
Portable KB body-syntax extension; upstream OKF specifies standard Markdown
links. Generic readers may display wikilinks literally. Use the Markdown view
when sharing with a standard Markdown reader. Reserved indexes and logs keep
their existing standard Markdown format.

| Syntax | Resolution |
| --- | --- |
| `[[customer-onboarding]]` | Exact, case-sensitive filename stem, unique across this brain |
| `[[procedures/customer-onboarding]]` | Exact path from the bundle root, with optional `.md` |
| `[[/procedures/customer-onboarding.md]]` | Explicit bundle-root path |
| `[[../procedures/customer-onboarding]]` | Path relative to the page containing this link |
| `[[customer-onboarding\|Onboarding procedure]]` | Same target with a display label |
| `[[customer-onboarding#Verification]]` | Existing ATX heading; resolves to `verification` |
| `[[customer-onboarding#verification-1]]` | Explicit anchor for the second duplicate heading |
| `[[#Verification]]` | Heading on the containing page |
| `[[urn:uuid:...]]` | Item UUID within this brain |

Display labels are not alternate lookup names. Titles and frontmatter aliases
are not lookup keys. Duplicate slugs require a bundle-qualified path or UUID;
the resolver never guesses based on folder proximity. Relative and heading-only
references need a containing page and are not accepted as standalone CLI item
references. CLI UUID and path retrieval retain their previous meaning; unique
slugs and full wikilinks are additional reference forms.

Headings use lowercase text, punctuation removal, whitespace-to-hyphen conversion
and duplicate suffixes. Heading text and generated anchors are both accepted.
Links inside fenced/indented code, code spans, comments or escaped opening
brackets are ignored. Attachment embeds, reference-style Markdown links,
setext headings and custom HTML anchors are outside this first resolver.

## Results and diagnostics

`links` returns body-link occurrences, retaining labels, full-file line numbers,
resolved heading fragments and canonical source/target citation tuples. A
resolved target includes lifecycle status, `stale_after`, and a scoped
`get_command` argument list. `backlinks` returns the occurrences pointing to the
selected item, with a scoped command to retrieve each source page. External URLs
and local non-concept resources are outside this concept-navigation result.

The `resolution` field is `resolved`, `missing`, `ambiguous`, `unsafe`, or
`missing-heading`. Ambiguous links include candidate paths; unresolved links have
no target citation or follow-up command. `ok` reports snapshot health, not that
every draft link resolves. Inspect each link's resolution.

Resolved wikilinks pass validation. Unresolved wikilinks use `KB-W407`: a warning
for drafts/inbox content, an error for stable curated content. Standard internal
links use `KB-W405`/`KB-E404`, including missing heading targets. This replaces
the previous blanket warning/error for any wikilink. Existing plain Markdown
content requires no migration. Older CLI versions may reject stable wikilinks.

`get --markdown-links` keeps the canonical `body`, `content`, metadata and citation
unchanged in JSON, and adds derived `rendered_body` and `rendered_content` fields.
Text output shows the rendered view after its citation. It refuses conversion
when an active wikilink cannot resolve; code examples remain unchanged. Relative
rendered links assume the original bundle directory layout. This is a per-item
view, not a whole-wiki import/export or source rewrite.

## Identity and evidence

Each edge resolves to the target UUID at the selected Git commit. Plain slugs
and paths do not independently survive an arbitrary manual rename. The existing
reviewed move planner repairs resolved wikilinks to qualified paths and preserves
their display labels, UUIDs, metadata and code examples. A change to the target
UUID or heading is a material change under the normal provenance/review rules.

Backlinks are computed from body links; authors do not need to manually add a
reciprocal link. Optional typed `related`/supersession metadata remains separate.
A link supplies context, not source authority or human verification. Retrieve
the linked item before using its claims and cite that complete item's own tuple.
Prefer relevant links; there is no minimum outbound-link count or automatic
write-back of synthesized answers.
