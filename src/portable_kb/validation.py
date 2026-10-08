"""Deterministic OKF v0.2 and core-kb/0.1 validation."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .links import LinkIndex
from .models import Finding, KnowledgeItem, Severity, ValidationReport, sorted_findings
from .parsing import discover_concepts, discover_reserved, iter_mapping_paths, parse_concept

PROFILE = "core-kb/0.1"
OKF_PROFILE = "OKF v0.2"
UTC_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UUID_URN = re.compile(
    r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
KEBAB_FILENAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
FOOTNOTE_REFERENCE = re.compile(r"\[\^([^\]]+)\](?!:)")
H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
LOG_DATE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
DATE_FIELDS = {
    "created_at",
    "updated_at",
    "generated.at",
    "valid_from",
    "stale_after",
    "archived.at",
}
DATE_SUFFIXES = (".last_modified", ".usage_window.from", ".usage_window.to", ".at")
MATERIAL_KEYS = {
    "type",
    "title",
    "description",
    "status",
    "sources",
    "valid_from",
    "stale_after",
    "related",
    "supersedes",
    "superseded_by",
    "sensitivity",
    "archived",
}
TYPE_SECTIONS: dict[str, tuple[str, ...]] = {
    "concept": ("Definition", "Context"),
    "decision": ("Decision", "Context", "Options considered", "Rationale", "Consequences"),
    "procedure": (
        "Purpose",
        "Preconditions",
        "Steps",
        "Verification",
        "Rollback",
        "Escalation",
        "Safety",
    ),
    "policy": ("Policy", "Scope", "Requirements", "Exceptions", "Review"),
    "system": (
        "Purpose",
        "Boundaries",
        "Architecture",
        "Dependencies",
        "Interfaces",
        "Operations",
        "Risks",
    ),
    "source-summary": ("Summary", "Key claims", "Limitations", "Relevance"),
    "question": ("Question", "Why it matters", "Known facts", "Resolution criteria", "Outcome"),
}


def _default_schema_path() -> Path:
    repository_path = Path(__file__).resolve().parents[2] / "schemas" / "knowledge-item.schema.yaml"
    if repository_path.exists():
        return repository_path
    return Path(__file__).resolve().parent / "schemas" / "knowledge-item.schema.yaml"


def _default_config_schema_path() -> Path:
    repository_path = Path(__file__).resolve().parents[2] / "schemas" / "bundle-config.schema.yaml"
    if repository_path.exists():
        return repository_path
    return Path(__file__).resolve().parent / "schemas" / "bundle-config.schema.yaml"


def _load_schema(path: Path) -> Mapping[str, Any]:
    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"Schema root is not a mapping: {path}")
    Draft202012Validator.check_schema(data)
    return data


def _finding(
    code: str,
    severity: Severity,
    item: KnowledgeItem,
    message: str,
    *,
    field: str | None = None,
    profile: str = PROFILE,
    remediation: str | None = None,
) -> Finding:
    top_field = field.split(".", 1)[0].split("[", 1)[0] if field else None
    return Finding(
        code,
        severity,
        item.relative_path,
        message,
        field=field,
        line=item.field_lines.get(top_field) if top_field else None,
        profile=profile,
        remediation=remediation,
    )


def validate_bundle(
    bundle: str | Path,
    *,
    as_of: date | str | None = None,
    schema_path: str | Path | None = None,
) -> ValidationReport:
    """Validate a bundle without mutating it or using the network."""

    root = Path(bundle).resolve()
    validation_date = _as_date(as_of)
    findings: list[Finding] = []
    if not root.is_dir():
        findings.append(
            Finding(
                "KB-E000",
                Severity.ERROR,
                ".",
                f"Bundle directory does not exist: {root}",
                remediation="Provide an existing knowledge bundle directory.",
            )
        )
        return ValidationReport(root, validation_date.isoformat(), tuple(findings), 0)

    validator = Draft202012Validator(
        _load_schema(Path(schema_path) if schema_path else _default_schema_path()),
        format_checker=FormatChecker(),
    )
    config, config_findings = _load_bundle_config(root)
    findings.extend(config_findings)
    items: list[KnowledgeItem] = []
    for path in discover_concepts(root):
        if path.is_symlink():
            findings.append(
                Finding(
                    "KB-E007",
                    Severity.ERROR,
                    path.relative_to(root).as_posix(),
                    "Concept files must not be symbolic links.",
                    remediation="Replace the link with a bundle-contained concept or an external source URI.",
                )
            )
            continue
        result = parse_concept(path, root)
        findings.extend(result.findings)
        if result.item is not None:
            items.append(result.item)
            findings.extend(_validate_item(result.item, validator, validation_date, root, config))

    findings.extend(_validate_configured_governance(items, config))
    findings.extend(_validate_reserved(root, discover_reserved(root), items))
    findings.extend(_validate_corpus(root, items, validation_date))
    return ValidationReport(
        root,
        validation_date.isoformat(),
        sorted_findings(_deduplicate(findings)),
        len(items),
    )


def _load_bundle_config(root: Path) -> tuple[Mapping[str, Any] | None, list[Finding]]:
    path = root / ".core-kb.yaml"
    if not path.exists():
        return None, [
            Finding(
                "KB-E700",
                Severity.ERROR,
                ".core-kb.yaml",
                "Bundle is missing its core profile configuration.",
                remediation="Add .core-kb.yaml conforming to schemas/bundle-config.schema.yaml.",
            )
        ]
    if path.is_symlink():
        return None, [
            Finding(
                "KB-E700",
                Severity.ERROR,
                ".core-kb.yaml",
                "Bundle configuration must not be a symbolic link.",
            )
        ]
    yaml = YAML(typ="safe")
    try:
        config = yaml.load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [
            Finding(
                "KB-E700",
                Severity.ERROR,
                ".core-kb.yaml",
                f"Bundle configuration is not valid safe YAML: {exc.__class__.__name__}.",
            )
        ]
    if not isinstance(config, Mapping):
        return None, [
            Finding(
                "KB-E700",
                Severity.ERROR,
                ".core-kb.yaml",
                "Bundle configuration must be a mapping.",
            )
        ]
    schema = _load_schema(_default_config_schema_path())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    findings = [
        Finding(
            "KB-E700",
            Severity.ERROR,
            ".core-kb.yaml",
            error.message,
            field=".".join(str(part) for part in error.absolute_path) or None,
            remediation="Update the bundle configuration to match its schema.",
        )
        for error in sorted(validator.iter_errors(config), key=_schema_error_key)
    ]
    return config, findings


def _validate_configured_governance(
    items: Sequence[KnowledgeItem], config: Mapping[str, Any] | None
) -> list[Finding]:
    if config is None:
        return []
    findings: list[Finding] = []
    active_types = config.get("active_types", [])
    active = set(active_types) if isinstance(active_types, list) else set()
    reviewers = config.get("authorized_reviewers", {})
    reviewer_map = reviewers if isinstance(reviewers, Mapping) else {}
    for item in items:
        if item.status == "stable" and item.type not in active:
            findings.append(
                _finding(
                    "KB-E701",
                    Severity.ERROR,
                    item,
                    f"Stable item uses a type that is not active for this bundle: {item.type}",
                    field="type",
                    remediation="Keep the item draft or activate the type through reviewed governance.",
                )
            )
        if item.status != "stable" or item.type not in {
            "decision",
            "procedure",
            "policy",
            "system",
        }:
            continue
        allowed_value = reviewer_map.get(item.type, [])
        allowed = set(allowed_value) if isinstance(allowed_value, list) else set()
        verified = item.metadata.get("verified", [])
        events = verified if isinstance(verified, list) else []
        actors = {event.get("by") for event in events if isinstance(event, Mapping)}
        if not (actors & allowed):
            findings.append(
                _finding(
                    "KB-E702",
                    Severity.ERROR,
                    item,
                    f"Stable {item.type} lacks verification by a configured authorized reviewer.",
                    field="verified",
                    remediation="Have an authorized human review the final snapshot and record their configured identifier.",
                )
            )
        if item.type == "system" and not actors:
            findings.append(
                _finding(
                    "KB-W307",
                    Severity.WARNING,
                    item,
                    "Stable system has no human verification for operational claims.",
                    field="verified",
                )
            )
    return findings


def _as_date(value: date | str | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _validate_item(
    item: KnowledgeItem,
    validator: Draft202012Validator,
    as_of: date,
    bundle: Path,
    config: Mapping[str, Any] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    if not item.metadata.get("type") or not isinstance(item.metadata.get("type"), str):
        findings.append(
            _finding(
                "KB-E100",
                Severity.ERROR,
                item,
                "Concept has no non-empty type.",
                field="type",
                profile=OKF_PROFILE,
                remediation="Add a non-empty type field.",
            )
        )
    for error in sorted(validator.iter_errors(item.metadata), key=_schema_error_key):
        findings.append(_schema_finding(item, error))

    findings.extend(_validate_profile_vocabulary(item, config, as_of))
    if not KEBAB_FILENAME.fullmatch(Path(item.relative_path).name):
        findings.append(
            _finding(
                "KB-E005",
                Severity.WARNING,
                item,
                "Concept filename is not lowercase kebab-case Markdown.",
                remediation="Rename the file without changing its immutable ID.",
            )
        )
    findings.extend(_validate_quoted_dates(item))
    findings.extend(_validate_dates(item, as_of))
    findings.extend(_validate_sources(item, bundle))
    findings.extend(_validate_body(item))
    return findings


def _validate_profile_vocabulary(
    item: KnowledgeItem, config: Mapping[str, Any] | None, as_of: date
) -> list[Finding]:
    findings: list[Finding] = []
    legacy = {"source", "generated_by", "verified_by", "author"}
    for field in sorted(legacy & set(item.metadata)):
        findings.append(
            _finding(
                "KB-E105",
                Severity.ERROR,
                item,
                f"Legacy metadata alias is not allowed: {field}",
                field=field,
                remediation="Migrate to sources, generated, or verified without dropping meaning.",
            )
        )
    documented_value = config.get("documented_extensions", []) if config else []
    documented = set(documented_value) if isinstance(documented_value, list) else set()
    for field in sorted(key for key in item.metadata if str(key).startswith("x-")):
        if field not in documented:
            findings.append(
                _finding(
                    "KB-W104",
                    Severity.WARNING,
                    item,
                    f"Extension has no owning proposal in bundle configuration: {field}",
                    field=str(field),
                )
            )
    if item.status == "deprecated" and not re.search(
        r"\b(deprecat|replac|supersed|abandon)", item.body, re.IGNORECASE
    ):
        findings.append(
            _finding(
                "KB-W312",
                Severity.WARNING,
                item,
                "Deprecated item does not explain its disposition or replacement.",
            )
        )
    archived = item.metadata.get("archived")
    if item.relative_path.startswith("archive/") and archived is None:
        findings.append(
            _finding(
                "KB-E313",
                Severity.ERROR,
                item,
                "Items under archive/ require archive reason and time metadata.",
                field="archived",
            )
        )
    elif archived is not None:
        allowed = item.status == "deprecated" or (
            item.status == "draft" and item.type == "question"
        )
        if not allowed or not item.relative_path.startswith("archive/"):
            findings.append(
                _finding(
                    "KB-E313",
                    Severity.ERROR,
                    item,
                    "Archive metadata requires an archived path and an allowed lifecycle status.",
                    field="archived",
                )
            )
    if item.status == "stable" and not item.metadata.get("tags"):
        findings.append(
            _finding(
                "KB-I604", Severity.INFORMATION, item, "Stable item has no tags.", field="tags"
            )
        )
    if item.relative_path.startswith("inbox/") and item.status == "draft":
        review_days = config.get("inbox_review_days", 30) if config else 30
        updated = _parse_datetime(item.metadata.get("updated_at"))
        if (
            isinstance(review_days, int)
            and updated
            and (as_of - updated.date()).days >= review_days
        ):
            findings.append(
                _finding(
                    "KB-I603",
                    Severity.INFORMATION,
                    item,
                    f"Draft has not changed within the {review_days}-day inbox review window.",
                    field="updated_at",
                )
            )
    title = item.metadata.get("title")
    description = item.metadata.get("description")
    if (
        isinstance(title, str)
        and isinstance(description, str)
        and _normalize_title(title) == _normalize_title(description.rstrip(".!?"))
    ):
        findings.append(
            _finding(
                "KB-W602",
                Severity.WARNING,
                item,
                "Description merely duplicates the title.",
                field="description",
            )
        )
    if item.status == "stable":
        verified = item.metadata.get("verified", [])
        events = verified if isinstance(verified, list) else []
        has_human = any(
            isinstance(event, Mapping)
            and isinstance(event.get("by"), str)
            and event["by"].startswith("human:")
            for event in events
        )
        if item.type == "decision" and (not item.metadata.get("valid_from") or not has_human):
            findings.append(
                _finding(
                    "KB-E302",
                    Severity.ERROR,
                    item,
                    "Stable decision lacks valid_from or human verification.",
                )
            )
        if item.type == "procedure" and (not item.metadata.get("stale_after") or not has_human):
            findings.append(
                _finding(
                    "KB-E303",
                    Severity.ERROR,
                    item,
                    "Stable procedure lacks stale_after or human verification.",
                )
            )
        if item.type == "policy" and (
            not item.metadata.get("valid_from")
            or not item.metadata.get("stale_after")
            or not item.metadata.get("sources")
            or not has_human
        ):
            findings.append(
                _finding(
                    "KB-E304",
                    Severity.ERROR,
                    item,
                    "Stable policy lacks a required date, source, or human verification.",
                )
            )
        if item.type == "system" and not item.metadata.get("stale_after"):
            findings.append(
                _finding("KB-E305", Severity.ERROR, item, "Stable system lacks stale_after.")
            )
        generated = item.metadata.get("generated")
        if (
            isinstance(generated, Mapping)
            and generated.get("method") == "agent-generated"
            and not has_human
        ):
            findings.append(
                _finding(
                    "KB-E306",
                    Severity.ERROR,
                    item,
                    "Stable agent-generated content lacks human verification.",
                )
            )
    verified_events = item.metadata.get("verified", [])
    if isinstance(verified_events, list):
        for event in verified_events:
            if not isinstance(event, Mapping):
                continue
            actor = event.get("by")
            timestamp = event.get("at")
            if isinstance(actor, str) and isinstance(timestamp, str):
                marker = f"<!-- core-kb-verification: {actor} at {timestamp} -->"
                if marker not in item.body:
                    findings.append(
                        _finding(
                            "KB-E703",
                            Severity.ERROR,
                            item,
                            "Verification event has no matching body scope record.",
                            field="verified",
                            remediation="Document what was checked and add the exact verification marker.",
                        )
                    )
    return findings


def _schema_error_key(error: ValidationError) -> tuple[str, str, str]:
    path = ".".join(str(part) for part in error.absolute_path)
    return (path, error.validator or "", error.message)


def _schema_finding(item: KnowledgeItem, error: ValidationError) -> Finding:
    path_parts = [str(part) for part in error.absolute_path]
    field = ".".join(path_parts) if path_parts else None
    code = "KB-E101"
    if error.validator == "additionalProperties":
        code = "KB-E103"
    elif field == "type" and error.validator == "enum":
        code = "KB-E102"
    elif field == "status" and error.validator == "enum":
        code = "KB-E300"
    elif field == "id":
        code = "KB-E120"
    elif field and field.startswith("tags"):
        code = "KB-E106"
    elif field and field.split(".", 1)[0] in {"related", "supersedes", "superseded_by"}:
        code = "KB-E400"
    elif field and (field.endswith(".by") or field.endswith(".author")):
        code = "KB-E208"
    elif field and (field.endswith("at") or field in {"created_at", "updated_at"}):
        code = "KB-E124"
    elif field and field.startswith("generated") and "agent-generated" in error.message:
        code = "KB-E209"
    elif error.validator == "required":
        missing = _missing_required(error)
        if missing == "type":
            code = "KB-E100"
            field = "type"
        elif missing == "sources":
            code = "KB-E201" if item.type in {"source-summary", "policy"} else "KB-E200"
            field = "sources"
        elif missing == "confidence":
            code = "KB-E209"
            field = "confidence"
        elif missing == "resource" and field and field.startswith("sources"):
            code = "KB-E202"
            field = f"{field}.resource"
        elif missing in {"verified", "valid_from", "stale_after"}:
            generated = item.metadata.get("generated")
            if (
                missing == "verified"
                and isinstance(generated, Mapping)
                and generated.get("method") == "agent-generated"
                and item.status == "stable"
            ):
                code = "KB-E306"
                field = "verified"
                return _finding(
                    code,
                    Severity.ERROR,
                    item,
                    error.message,
                    field=field,
                    remediation="Update frontmatter to satisfy schemas/knowledge-item.schema.yaml.",
                )
            type_codes = {
                "decision": "KB-E302",
                "procedure": "KB-E303",
                "policy": "KB-E304",
                "system": "KB-E305",
            }
            code = type_codes.get(item.type or "", "KB-E101")
            field = missing
    return _finding(
        code,
        Severity.ERROR,
        item,
        error.message,
        field=field,
        remediation="Update frontmatter to satisfy schemas/knowledge-item.schema.yaml.",
    )


def _missing_required(error: ValidationError) -> str | None:
    match = re.match(r"^'([^']+)' is a required property$", error.message)
    return match.group(1) if match else None


def _validate_quoted_dates(item: KnowledgeItem) -> list[Finding]:
    findings: list[Finding] = []
    for path, value in iter_mapping_paths(item.metadata):
        is_date_field = path in DATE_FIELDS or path.endswith(DATE_SUFFIXES)
        if is_date_field and not isinstance(value, DoubleQuotedScalarString):
            findings.append(
                _finding(
                    "KB-E124A",
                    Severity.ERROR,
                    item,
                    "Profile date and datetime values must be double-quoted YAML strings.",
                    field=path,
                    remediation="Serialize this date using double quotes.",
                )
            )
    return findings


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not UTC_DATETIME.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_flexible_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate_dates(item: KnowledgeItem, as_of: date) -> list[Finding]:
    findings: list[Finding] = []
    created = _parse_datetime(item.metadata.get("created_at"))
    updated = _parse_datetime(item.metadata.get("updated_at"))
    ordered_created = created or _parse_flexible_datetime(item.metadata.get("created_at"))
    ordered_updated = updated or _parse_flexible_datetime(item.metadata.get("updated_at"))
    generated = item.metadata.get("generated")
    generated_at = _parse_datetime(generated.get("at")) if isinstance(generated, Mapping) else None
    if ordered_created and ordered_updated and ordered_created > ordered_updated:
        findings.append(
            _finding(
                "KB-E123",
                Severity.ERROR,
                item,
                "created_at is later than updated_at.",
                field="created_at",
                remediation="Restore the immutable creation time or correct the update time.",
            )
        )
    if updated and generated_at and updated != generated_at:
        findings.append(
            _finding(
                "KB-E125",
                Severity.ERROR,
                item,
                "updated_at must equal generated.at for the current snapshot.",
                field="generated.at",
                remediation="Use the same current-content timestamp in both fields.",
            )
        )
    verified = item.metadata.get("verified", [])
    if isinstance(verified, Sequence) and not isinstance(verified, (str, bytes)) and updated:
        for index, event in enumerate(verified):
            if isinstance(event, Mapping):
                verified_at = _parse_datetime(event.get("at"))
                if verified_at and verified_at < updated:
                    findings.append(
                        _finding(
                            "KB-E127",
                            Severity.ERROR,
                            item,
                            "Verification predates the content snapshot it claims to cover.",
                            field=f"verified[{index}].at",
                            remediation="Remove the stale event or verify the final snapshot.",
                        )
                    )
    valid_from = _parse_date(item.metadata.get("valid_from"))
    stale_after = _parse_date(item.metadata.get("stale_after"))
    if valid_from and stale_after and stale_after <= valid_from:
        findings.append(
            _finding(
                "KB-E310",
                Severity.ERROR,
                item,
                "stale_after must be later than valid_from.",
                field="stale_after",
                remediation="Choose a review deadline after the effective date.",
            )
        )
    if stale_after and as_of >= stale_after:
        findings.append(
            _finding(
                "KB-W308",
                Severity.WARNING,
                item,
                f"Item is stale as of {as_of.isoformat()}.",
                field="stale_after",
                remediation="Reverify, revise, deprecate, or document a governed exception.",
            )
        )
    if valid_from and valid_from > as_of:
        findings.append(
            _finding(
                "KB-I309",
                Severity.INFORMATION,
                item,
                f"Item is not effective until {valid_from.isoformat()}.",
                field="valid_from",
            )
        )
    return findings


def _validate_sources(item: KnowledgeItem, bundle: Path) -> list[Finding]:
    findings: list[Finding] = []
    shared_window = item.metadata.get("usage_window")
    if isinstance(shared_window, Mapping) and not _valid_window(shared_window):
        findings.append(
            _finding(
                "KB-E206",
                Severity.ERROR,
                item,
                "Shared usage window must have from <= to.",
                field="usage_window",
            )
        )
    sources = item.metadata.get("sources")
    if not isinstance(sources, list):
        return findings
    verified_dates = [
        verified_at.date()
        for event in item.metadata.get("verified", [])
        if isinstance(item.metadata.get("verified"), list)
        and isinstance(event, Mapping)
        and (verified_at := _parse_datetime(event.get("at"))) is not None
    ]
    latest_verification = max(verified_dates, default=None)
    source_ids: list[str] = []
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            continue
        source_id = source.get("id")
        if isinstance(source_id, str):
            source_ids.append(source_id)
        resource = source.get("resource")
        if isinstance(resource, str):
            parsed = urlsplit(resource)
            if parsed.scheme in {"http", "https"} and not source.get("title"):
                findings.append(
                    _finding(
                        "KB-E202",
                        Severity.ERROR,
                        item,
                        "Absolute web sources require a diagnostic title.",
                        field=f"sources[{index}].title",
                        remediation="Add the source's human-readable title.",
                    )
                )
            elif not parsed.scheme:
                resolved_resource = _resolve_local_resource(item, resource, bundle).resolve()
                try:
                    resolved_resource.relative_to(bundle.resolve())
                except ValueError:
                    findings.append(
                        _finding(
                            "KB-E202",
                            Severity.ERROR,
                            item,
                            f"Local source resource escapes the bundle: {resource}",
                            field=f"sources[{index}].resource",
                            remediation="Use a bundle-contained path or an absolute external URI.",
                        )
                    )
                else:
                    if not resolved_resource.exists():
                        findings.append(
                            _finding(
                                "KB-E202",
                                Severity.ERROR,
                                item,
                                f"Local source resource does not resolve: {resource}",
                                field=f"sources[{index}].resource",
                                remediation="Correct the path or use an absolute external URI.",
                            )
                        )
        last_modified = _parse_date(source.get("last_modified"))
        if latest_verification and last_modified and last_modified > latest_verification:
            findings.append(
                _finding(
                    "KB-W309",
                    Severity.WARNING,
                    item,
                    "A source changed after the latest verification event.",
                    field=f"sources[{index}].last_modified",
                    remediation="Review the changed source and reverify or revise the item.",
                )
            )
        if (
            "usage_count" in source
            and "usage_window" not in source
            and "usage_window" not in item.metadata
        ):
            findings.append(
                _finding(
                    "KB-E206",
                    Severity.ERROR,
                    item,
                    "usage_count has no shared or per-source usage window.",
                    field=f"sources[{index}].usage_count",
                    remediation="Add a dated usage window or remove the count.",
                )
            )
        source_window = source.get("usage_window")
        if isinstance(source_window, Mapping) and not _valid_window(source_window):
            findings.append(
                _finding(
                    "KB-E206",
                    Severity.ERROR,
                    item,
                    "Per-source usage window must have from <= to.",
                    field=f"sources[{index}].usage_window",
                )
            )
    duplicates = {source_id for source_id, count in Counter(source_ids).items() if count > 1}
    for source_id in sorted(duplicates):
        findings.append(
            _finding(
                "KB-E203",
                Severity.ERROR,
                item,
                f"Source ID is duplicated: {source_id}",
                field="sources",
                remediation="Give each source a unique item-local ID.",
            )
        )
    cited = set(FOOTNOTE_REFERENCE.findall(item.body))
    known = set(source_ids)
    for missing in sorted(cited - known):
        findings.append(
            _finding(
                "KB-E204",
                Severity.ERROR,
                item,
                f"Body footnote has no matching sources[].id: {missing}",
                field="sources",
                remediation="Add the cited source ID or correct the footnote label.",
            )
        )
    for unused in sorted(known - cited):
        findings.append(
            _finding(
                "KB-W205",
                Severity.WARNING,
                item,
                f"Source is not cited in the body: {unused}",
                field="sources",
                remediation="Cite consequential sourced claims or remove unused provenance.",
            )
        )
    return findings


def _valid_window(value: Mapping[str, Any]) -> bool:
    start = _parse_date(value.get("from"))
    end = _parse_date(value.get("to"))
    return start is not None and end is not None and start <= end


def _resolve_local_resource(item: KnowledgeItem, resource: str, bundle: Path) -> Path:
    clean = unquote(resource.split("#", 1)[0])
    if clean.startswith("/"):
        return bundle / clean.lstrip("/")
    return item.path.parent / clean


def _validate_body(item: KnowledgeItem) -> list[Finding]:
    findings: list[Finding] = []
    heading = H1.search(item.body)
    if heading and isinstance(item.metadata.get("title"), str):
        if _normalize_title(heading.group(1)) != _normalize_title(item.metadata["title"]):
            findings.append(
                _finding(
                    "KB-W602",
                    Severity.WARNING,
                    item,
                    "The first H1 does not match the frontmatter title.",
                    field="title",
                    remediation="Align the visible heading and metadata title.",
                )
            )
    elif item.status == "stable":
        findings.append(
            _finding(
                "KB-W505",
                Severity.WARNING,
                item,
                "Stable item has no H1 heading.",
                remediation="Add one H1 matching the title.",
            )
        )
    if re.search(r"<\s*(script|iframe)\b", item.body, re.IGNORECASE):
        findings.append(
            _finding(
                "KB-E506",
                Severity.ERROR,
                item,
                "Embedded script or iframe is not allowed.",
                remediation="Remove executable or remotely embedded HTML.",
            )
        )
    if re.search(r"!\[[^\]]*\]\(https?://", item.body, re.IGNORECASE):
        findings.append(
            _finding(
                "KB-E506",
                Severity.ERROR,
                item,
                "Remote images are disallowed in the initial profile.",
                remediation="Mirror a lawful static artifact or use a descriptive external link.",
            )
        )
    if item.status == "stable" and re.search(r"\b(TODO|TBD|REPLACE_[A-Z0-9_]+)\b", item.body):
        findings.append(
            _finding(
                "KB-W507",
                Severity.ERROR if item.type in {"policy", "procedure"} else Severity.WARNING,
                item,
                "Stable content still contains a placeholder marker.",
                remediation="Resolve or remove the placeholder before promotion.",
            )
        )
    if item.status == "stable" and item.type in TYPE_SECTIONS:
        present = {
            match.group(1).strip().casefold()
            for match in re.finditer(r"^##\s+(.+?)\s*$", item.body, re.MULTILINE)
        }
        for section in TYPE_SECTIONS[item.type]:
            if section.casefold() not in present:
                findings.append(
                    _finding(
                        "KB-W505",
                        Severity.WARNING,
                        item,
                        f"Recommended section is missing: {section}",
                        remediation="Add the section or document why it is inapplicable.",
                    )
                )
    return findings


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _validate_corpus(root: Path, items: Sequence[KnowledgeItem], as_of: date) -> list[Finding]:
    findings: list[Finding] = []
    by_id: dict[str, list[KnowledgeItem]] = defaultdict(list)
    by_path = {item.relative_path: item for item in items}
    inbound: Counter[str] = Counter()
    for item in items:
        if item.id:
            by_id[item.id].append(item)
    for item_id, matches in sorted(by_id.items()):
        if len(matches) > 1:
            for item in matches:
                findings.append(
                    _finding(
                        "KB-E121",
                        Severity.ERROR,
                        item,
                        f"Immutable ID occurs in {len(matches)} concept files: {item_id}",
                        field="id",
                        remediation="Generate a new ID only for the accidentally duplicated identity.",
                    )
                )

    link_index = LinkIndex(items, root)
    relation_edges: dict[str, set[str]] = defaultdict(set)
    for item in items:
        findings.extend(_validate_links(item, link_index, inbound))
        findings.extend(_validate_relations(item, by_id, relation_edges, as_of, link_index))
        for index, source in enumerate(
            item.metadata.get("sources", [])
            if isinstance(item.metadata.get("sources"), list)
            else []
        ):
            if not isinstance(source, Mapping) or not isinstance(source.get("resource"), str):
                continue
            resource = source["resource"]
            if urlsplit(resource).scheme:
                continue
            try:
                target = (
                    _resolve_local_resource(item, resource, root)
                    .resolve()
                    .relative_to(root)
                    .as_posix()
                )
            except ValueError:
                continue
            target_item = by_path.get(target)
            if target_item and target_item.type == "source-summary":
                findings.append(
                    _finding(
                        "KB-W207",
                        Severity.WARNING,
                        item,
                        "Item relies on a source summary where a primary source may be available.",
                        field=f"sources[{index}].resource",
                    )
                )
    findings.extend(_validate_supersession_graph(items, by_id, relation_edges))

    normalized_titles: dict[tuple[str, str], list[KnowledgeItem]] = defaultdict(list)
    for item in items:
        title = item.metadata.get("title")
        if isinstance(title, str):
            scope = PurePosixPath(item.relative_path).parent.as_posix()
            normalized_titles[(scope, _normalize_title(title))].append(item)
    for (_scope, title), matches in sorted(normalized_titles.items()):
        if title and len(matches) > 1:
            for item in matches:
                findings.append(
                    _finding(
                        "KB-W600",
                        Severity.WARNING,
                        item,
                        f"Normalized title collides with {len(matches) - 1} other item(s).",
                        field="title",
                    )
                )
    resource_groups: dict[tuple[str, str], list[KnowledgeItem]] = defaultdict(list)
    for item in items:
        resource = item.metadata.get("resource")
        if isinstance(resource, str):
            resource_groups[(item.type or "", resource)].append(item)
        elif item.type == "source-summary":
            sources = item.metadata.get("sources")
            if isinstance(sources, list) and sources and isinstance(sources[0], Mapping):
                first_resource = sources[0].get("resource")
                if isinstance(first_resource, str):
                    resource_groups[(item.type, first_resource)].append(item)
    for (_item_type, resource), matches in sorted(resource_groups.items()):
        if len(matches) > 1:
            for item in matches:
                findings.append(
                    _finding(
                        "KB-W601",
                        Severity.WARNING,
                        item,
                        f"Multiple similarly scoped items claim the same canonical resource: {resource}",
                        field="sources" if item.type == "source-summary" else "resource",
                    )
                )
    conflict_groups: dict[str, list[KnowledgeItem]] = defaultdict(list)
    for item in items:
        tags = item.metadata.get("tags", [])
        if isinstance(tags, list) and any(tag in {"conflict", "conflict-fixture"} for tag in tags):
            conflict_groups[item.type or ""].append(item)
    for matches in conflict_groups.values():
        if len(matches) > 1:
            for item in matches:
                findings.append(
                    _finding(
                        "KB-W605",
                        Severity.WARNING,
                        item,
                        "Current items are explicitly marked as a possible semantic conflict.",
                    )
                )
    indexed = _indexed_concept_paths(root)
    for item in items:
        if (
            item.status == "stable"
            and inbound[item.relative_path] == 0
            and item.relative_path not in indexed
        ):
            findings.append(
                _finding(
                    "KB-I408",
                    Severity.INFORMATION,
                    item,
                    "Stable item has no inbound concept links.",
                )
            )
    return findings


def _indexed_concept_paths(root: Path) -> set[str]:
    indexed: set[str] = set()
    for index_path in root.rglob("index.md"):
        text = index_path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path.endswith(".md"):
                continue
            if parsed.path.startswith("/"):
                resolved = PurePosixPath(parsed.path.lstrip("/"))
            else:
                index_relative = index_path.relative_to(root).as_posix()
                resolved = PurePosixPath(index_relative).parent / unquote(parsed.path)
            normalized = _normalize_posix(resolved)
            if normalized != ".." and not normalized.startswith("../"):
                indexed.add(normalized)
    return indexed


def _validate_links(
    item: KnowledgeItem,
    index: LinkIndex,
    inbound: Counter[str],
) -> list[Finding]:
    findings: list[Finding] = []
    for link in index.outgoing(item):
        if link.status == "resolved" and link.item is not None:
            inbound[link.item.relative_path] += 1
        elif link.status not in {"external", "resource"}:
            curated = item.status == "stable" and not item.relative_path.startswith("inbox/")
            code = (
                "KB-W407" if link.reference.kind == "wiki" else "KB-E404" if curated else "KB-W405"
            )
            candidates = f"; candidates: {', '.join(link.candidates)}" if link.candidates else ""
            findings.append(
                _finding(
                    code,
                    Severity.ERROR if curated else Severity.WARNING,
                    item,
                    f"Internal {link.reference.kind} link is {link.status}: {link.reference.target}{candidates}",
                    remediation="Use a unique bundle-contained concept path and an existing heading. Labels do not resolve ambiguity.",
                )
            )
    return findings


def _normalize_posix(path: PurePosixPath) -> str:
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append(part)
            continue
        parts.append(part)
    return "/".join(parts)


def _validate_relations(
    item: KnowledgeItem,
    by_id: Mapping[str, Sequence[KnowledgeItem]],
    edges: dict[str, set[str]],
    as_of: date,
    link_index: LinkIndex,
) -> list[Finding]:
    findings: list[Finding] = []
    body_targets = {link.item.relative_path for link in link_index.outgoing(item)
                    if link.status == "resolved" and link.item is not None}
    for field in ("related", "supersedes", "superseded_by"):
        values = item.metadata.get(field, [])
        if not isinstance(values, list):
            continue
        for target in values:
            if not isinstance(target, str):
                continue
            if target == item.id:
                findings.append(
                    _finding(
                        "KB-E400",
                        Severity.ERROR,
                        item,
                        f"{field} cannot target the item's own ID.",
                        field=field,
                        remediation="Remove the self-reference and identify the actual related item.",
                    )
                )
            elif target not in by_id:
                findings.append(
                    _finding(
                        "KB-E400",
                        Severity.ERROR,
                        item,
                        f"{field} target does not exist: {target}",
                        field=field,
                        remediation="Add the target in the same change or remove the relation.",
                    )
                )
            elif by_id[target][0].relative_path not in body_targets:
                findings.append(
                    _finding(
                        "KB-W406",
                        Severity.WARNING,
                        item,
                        f"Typed {field} relation has no explanatory body link to its target.",
                        field=field,
                    )
                )
            if field == "supersedes" and item.id:
                edges[item.id].add(target)
                targets = by_id.get(target, ())
                if targets and targets[0].status != "deprecated":
                    findings.append(
                        _finding(
                            "KB-E403",
                            Severity.ERROR,
                            item,
                            "A superseded predecessor must be deprecated.",
                            field=field,
                        )
                    )
                if item.status != "stable" or (
                    _parse_date(item.metadata.get("valid_from"))
                    and _parse_date(item.metadata.get("valid_from")) > as_of
                ):
                    findings.append(
                        _finding(
                            "KB-E403",
                            Severity.ERROR,
                            item,
                            "A replacement must be stable and currently effective.",
                            field=field,
                        )
                    )
    return findings



def _validate_supersession_graph(
    items: Sequence[KnowledgeItem],
    by_id: Mapping[str, Sequence[KnowledgeItem]],
    edges: Mapping[str, set[str]],
) -> list[Finding]:
    findings: list[Finding] = []
    for item in items:
        if not item.id:
            continue
        for predecessor in (
            item.metadata.get("supersedes", [])
            if isinstance(item.metadata.get("supersedes", []), list)
            else []
        ):
            targets = by_id.get(predecessor, ())
            if targets and item.id not in targets[0].metadata.get("superseded_by", []):
                findings.append(
                    _finding(
                        "KB-E401",
                        Severity.ERROR,
                        item,
                        "Supersession is not reciprocal on the predecessor.",
                        field="supersedes",
                    )
                )
        for replacement in (
            item.metadata.get("superseded_by", [])
            if isinstance(item.metadata.get("superseded_by", []), list)
            else []
        ):
            targets = by_id.get(replacement, ())
            if targets and item.id not in targets[0].metadata.get("supersedes", []):
                findings.append(
                    _finding(
                        "KB-E401",
                        Severity.ERROR,
                        item,
                        "Supersession is not reciprocal on the replacement.",
                        field="superseded_by",
                    )
                )
    state: dict[str, int] = {}

    def visit(node: str, trail: tuple[str, ...]) -> None:
        if state.get(node) == 1:
            for item_id in trail[trail.index(node) :] if node in trail else trail:
                for item in by_id.get(item_id, ()):
                    findings.append(
                        _finding(
                            "KB-E402",
                            Severity.ERROR,
                            item,
                            "Supersession graph contains a cycle.",
                            field="supersedes",
                        )
                    )
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        for target in sorted(edges.get(node, set())):
            visit(target, trail + (node,))
        state[node] = 2

    for node in sorted(edges):
        visit(node, ())
    return findings


def _validate_reserved(
    root: Path, paths: Sequence[Path], items: Sequence[KnowledgeItem]
) -> list[Finding]:
    findings: list[Finding] = []
    item_paths = {item.relative_path: item for item in items}
    root_index = root / "index.md"
    if not root_index.exists():
        findings.append(
            Finding(
                "KB-W503",
                Severity.WARNING,
                "index.md",
                "The profile bundle has no root index.md.",
                remediation="Add a progressive root index declaring okf_version 0.2.",
            )
        )
    root_log = root / "log.md"
    if not root_log.exists():
        findings.append(
            Finding(
                "KB-W503",
                Severity.WARNING,
                "log.md",
                "The profile bundle has no root log.md.",
                remediation="Add a newest-first human-facing update log.",
            )
        )
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            findings.append(
                Finding(
                    "KB-E007",
                    Severity.ERROR,
                    relative,
                    "Reserved bundle documents must not be symbolic links.",
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        if path.name == "index.md":
            findings.extend(_validate_index(root, path, relative, text, item_paths))
        else:
            findings.extend(_validate_log(relative, text))
    if root_index.exists():
        for item in items:
            if item.status == "deprecated" or item.metadata.get("archived") is not None:
                continue
            index_path = item.path.parent / "index.md"
            target = item.path.name
            if not index_path.exists() or target not in {
                urlsplit(link).path
                for link in MARKDOWN_LINK.findall(index_path.read_text(encoding="utf-8"))
            }:
                findings.append(
                    _finding(
                        "KB-W503",
                        Severity.WARNING,
                        item,
                        "Current item is missing from its directory index.",
                        remediation="Regenerate the directory index.",
                    )
                )
    return findings


def _validate_index(
    root: Path,
    path: Path,
    relative: str,
    text: str,
    item_paths: Mapping[str, KnowledgeItem],
) -> list[Finding]:
    findings: list[Finding] = []
    body = text
    if text.startswith("---\n"):
        closing = text.find("\n---\n", 4)
        if closing < 0:
            findings.append(
                Finding(
                    "KB-E500",
                    Severity.ERROR,
                    relative,
                    "Index frontmatter is malformed.",
                    profile=OKF_PROFILE,
                )
            )
            return findings
        if path != root / "index.md":
            findings.append(
                Finding(
                    "KB-E500",
                    Severity.ERROR,
                    relative,
                    "Only the bundle-root index may have frontmatter.",
                    profile=OKF_PROFILE,
                )
            )
        payload = text[4:closing]
        yaml = YAML(typ="safe")
        try:
            metadata = yaml.load(payload)
        except Exception:
            metadata = None
        if (
            not isinstance(metadata, Mapping)
            or set(metadata) != {"okf_version"}
            or metadata.get("okf_version") != "0.2"
        ):
            findings.append(
                Finding(
                    "KB-E500",
                    Severity.ERROR,
                    relative,
                    'Root index frontmatter must contain only okf_version: "0.2".',
                    profile=OKF_PROFILE,
                )
            )
        body = text[closing + 5 :]
    elif path == root / "index.md":
        findings.append(
            Finding(
                "KB-E500",
                Severity.ERROR,
                relative,
                'Root index must pin okf_version: "0.2" for this profile.',
            )
        )
    for target in MARKDOWN_LINK.findall(body):
        parsed = urlsplit(target)
        if parsed.scheme or target.startswith("#"):
            continue
        clean = unquote(parsed.path)
        resolved_path = root / clean.lstrip("/") if clean.startswith("/") else path.parent / clean
        resolved_path = resolved_path.resolve()
        try:
            resolved_path.relative_to(root.resolve())
        except ValueError:
            findings.append(
                Finding(
                    "KB-E502",
                    Severity.ERROR,
                    relative,
                    f"Index entry escapes the bundle: {target}",
                )
            )
            continue
        if not resolved_path.exists():
            findings.append(
                Finding(
                    "KB-E502", Severity.ERROR, relative, f"Index entry does not resolve: {target}"
                )
            )
        else:
            try:
                target_relative = resolved_path.relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            item = item_paths.get(target_relative)
            if item and item.status == "deprecated":
                findings.append(
                    Finding(
                        "KB-W503",
                        Severity.WARNING,
                        relative,
                        f"Deprecated item appears in a current index: {target}",
                    )
                )
            if (
                item
                and isinstance(item.metadata.get("description"), str)
                and item.metadata["description"] not in body
            ):
                findings.append(
                    Finding(
                        "KB-W504",
                        Severity.WARNING,
                        relative,
                        f"Index does not reproduce the target description: {target}",
                    )
                )
    for line_number, line in enumerate(body.splitlines(), start=1):
        if line.startswith("* ") and not re.match(r"^\* \[[^\]]+\]\([^)]+\) - .+", line):
            findings.append(
                Finding(
                    "KB-E500",
                    Severity.ERROR,
                    relative,
                    "Index entry does not use '* [Title](target) - description'.",
                    line=line_number,
                    profile=OKF_PROFILE,
                )
            )
    return findings


def _validate_log(relative: str, text: str) -> list[Finding]:
    dates = LOG_DATE.findall(text)
    if not dates:
        return [
            Finding(
                "KB-E501",
                Severity.ERROR,
                relative,
                "Log has no ISO date headings.",
                profile=OKF_PROFILE,
            )
        ]
    if (
        dates != sorted(dates, reverse=True)
        or len(dates) != len(set(dates))
        or any(_parse_date(value) is None for value in dates)
    ):
        return [
            Finding(
                "KB-E501",
                Severity.ERROR,
                relative,
                "Log date headings must be valid ISO dates in newest-first order.",
                profile=OKF_PROFILE,
            )
        ]
    return []


def validate_transition(
    base_bundle: str | Path,
    proposed_bundle: str | Path,
    *,
    as_of: date | str | None = None,
    schema_path: str | Path | None = None,
) -> ValidationReport:
    """Validate a proposed tree plus immutable and lifecycle changes from a base tree."""

    proposed_report = validate_bundle(proposed_bundle, as_of=as_of, schema_path=schema_path)
    findings = list(proposed_report.findings)
    base_items = _parse_tree(Path(base_bundle).resolve())
    proposed_items = _parse_tree(Path(proposed_bundle).resolve())
    base_by_id = {item.id: item for item in base_items if item.id}
    proposed_by_id = {item.id: item for item in proposed_items if item.id}
    base_by_path = {item.relative_path: item for item in base_items}
    proposed_by_path = {item.relative_path: item for item in proposed_items}

    for path, old in base_by_path.items():
        new = proposed_by_path.get(path)
        if new and old.id and new.id and old.id != new.id:
            findings.append(
                _finding(
                    "KB-E122",
                    Severity.ERROR,
                    new,
                    "Immutable ID changed at an existing path.",
                    field="id",
                )
            )
    allowed = {
        ("draft", "draft"),
        ("draft", "stable"),
        ("draft", "deprecated"),
        ("stable", "draft"),
        ("stable", "stable"),
        ("stable", "deprecated"),
        ("deprecated", "deprecated"),
    }
    for item_id, old in base_by_id.items():
        new = proposed_by_id.get(item_id)
        if new is None:
            findings.append(
                _finding(
                    "KB-E314",
                    Severity.ERROR,
                    old,
                    "Knowledge identity was deleted from the proposed tree.",
                    field="id",
                    remediation="Deprecate or archive the item while preserving its ID and content.",
                )
            )
            continue
        if old.metadata.get("created_at") != new.metadata.get("created_at"):
            findings.append(
                _finding(
                    "KB-E123",
                    Severity.ERROR,
                    new,
                    "created_at changed for an existing identity.",
                    field="created_at",
                )
            )
        transition = (old.status, new.status)
        if transition not in allowed:
            findings.append(
                _finding(
                    "KB-E301",
                    Severity.ERROR,
                    new,
                    f"Disallowed lifecycle transition: {old.status} -> {new.status}",
                    field="status",
                )
            )
        if _is_material_change(old, new, base_by_path, proposed_by_path):
            if old.metadata.get("updated_at") == new.metadata.get("updated_at"):
                findings.append(
                    _finding(
                        "KB-W126",
                        Severity.WARNING,
                        new,
                        "Material change did not update production metadata.",
                        field="updated_at",
                    )
                )
            old_events = _verification_pairs(old.metadata.get("verified"))
            retained = old_events & _verification_pairs(new.metadata.get("verified"))
            if retained:
                findings.append(
                    _finding(
                        "KB-E311",
                        Severity.ERROR,
                        new,
                        "Material change retained verification from the prior snapshot.",
                        field="verified",
                    )
                )
    return ValidationReport(
        Path(proposed_bundle).resolve(),
        proposed_report.as_of,
        sorted_findings(_deduplicate(findings)),
        proposed_report.concept_count,
    )


def _parse_tree(root: Path) -> list[KnowledgeItem]:
    result: list[KnowledgeItem] = []
    for path in discover_concepts(root):
        parsed = parse_concept(path, root)
        if parsed.item is not None:
            result.append(parsed.item)
    return result


def _is_material_change(
    old: KnowledgeItem,
    new: KnowledgeItem,
    base_by_path: Mapping[str, KnowledgeItem],
    proposed_by_path: Mapping[str, KnowledgeItem],
) -> bool:
    if any(old.metadata.get(key) != new.metadata.get(key) for key in MATERIAL_KEYS):
        return True
    if old.body == new.body:
        return False
    return _canonical_link_body(old, base_by_path) != _canonical_link_body(new, proposed_by_path)


def _canonical_link_body(item: KnowledgeItem, by_path: Mapping[str, KnowledgeItem]) -> str:
    root = item.path.parents[len(PurePosixPath(item.relative_path).parts) - 1]
    index = LinkIndex(list(by_path.values()), root)
    body = item.body
    for link in reversed(index.outgoing(item)):
        if link.status != "resolved" or link.item is None or link.item.id is None:
            continue
        canonical = f"urn:core-kb-link:{link.item.id}"
        if link.fragment:
            canonical += "#" + link.fragment
        replacement = f"[{link.reference.label}]({canonical})"
        body = body[:link.reference.start] + replacement + body[link.reference.end:]
    return body.rstrip()


def _verification_pairs(value: Any) -> set[tuple[str, str]]:
    if not isinstance(value, list):
        return set()
    return {
        (event.get("by"), event.get("at"))
        for event in value
        if isinstance(event, Mapping)
        and isinstance(event.get("by"), str)
        and isinstance(event.get("at"), str)
    }


def _deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    seen: set[tuple[str, Severity, str, str | None, str]] = set()
    result: list[Finding] = []
    for finding in findings:
        key = (finding.code, finding.severity, finding.path, finding.field, finding.message)
        if key not in seen:
            seen.add(key)
            result.append(finding)
    return result
