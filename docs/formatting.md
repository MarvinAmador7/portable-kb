# Deterministic formatting policy

- UTF-8 without a byte-order mark and LF line endings.
- Lowercase kebab-case `.md` concept filenames.
- YAML frontmatter begins at byte zero and uses two-space indentation.
- Profile dates and datetimes are double-quoted strings.
- Field order follows identity, lifecycle, generation, evidence,
  relationships, handling, then extensions.
- Lists use block style. Empty optional lists are omitted.
- The body begins with one H1 matching `title`; type sections use H2 headings.
- Internal links are ordinary Markdown links. Tool-specific wiki links and
  executable embedded HTML are not canonical.
- Index entries use `* [Title](target) - description` and deterministic
  case-insensitive title ordering.
- Log date headings are newest first.
- Parsers and lifecycle operations preserve unknown imported fields. Formatting
  an imported item is explicit, never a side effect of validation.
