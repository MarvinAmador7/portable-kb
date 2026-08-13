"""Shared immutable result models for validation and lifecycle planning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any


class Severity(IntEnum):
    """Finding severity, ordered from least to most severe."""

    INFORMATION = 1
    WARNING = 2
    ERROR = 3

    @property
    def label(self) -> str:
        return self.name.lower()


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic validation result."""

    code: str
    severity: Severity
    path: str
    message: str
    field: str | None = None
    line: int | None = None
    profile: str = "core-kb/0.1"
    remediation: str | None = None

    @property
    def sort_key(self) -> tuple[str, int, str, str]:
        return (self.path, self.line or 0, self.code, self.field or "")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.label,
            "path": self.path,
            "message": self.message,
            "profile": self.profile,
        }
        if self.field is not None:
            result["field"] = self.field
        if self.line is not None:
            result["line"] = self.line
        if self.remediation is not None:
            result["remediation"] = self.remediation
        return result


@dataclass(slots=True)
class KnowledgeItem:
    """A parsed knowledge concept and its source representation."""

    path: Path
    relative_path: str
    metadata: Mapping[str, Any]
    body: str
    frontmatter_text: str
    source_text: str
    field_lines: Mapping[str, int] = field(default_factory=dict)

    @property
    def id(self) -> str | None:
        value = self.metadata.get("id")
        return value if isinstance(value, str) else None

    @property
    def type(self) -> str | None:
        value = self.metadata.get("type")
        return value if isinstance(value, str) else None

    @property
    def status(self) -> str | None:
        value = self.metadata.get("status")
        return value if isinstance(value, str) else None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Complete deterministic result for one validation run."""

    bundle: Path
    as_of: str
    findings: tuple[Finding, ...]
    concept_count: int

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.severity is Severity.WARNING)

    @property
    def information(self) -> tuple[Finding, ...]:
        return tuple(
            finding for finding in self.findings if finding.severity is Severity.INFORMATION
        )

    @property
    def profile_passes(self) -> bool:
        return not self.errors

    @property
    def okf_passes(self) -> bool:
        return not any(
            finding.severity is Severity.ERROR and finding.profile == "OKF v0.2"
            for finding in self.findings
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "bundle": self.bundle.name,
            "as_of": self.as_of,
            "concept_count": self.concept_count,
            "okf_v0_2": "pass" if self.okf_passes else "fail",
            "core_kb_0_1": (
                "pass-with-warnings"
                if self.profile_passes and self.warnings
                else "pass"
                if self.profile_passes
                else "fail-with-errors"
            ),
            "findings": [finding.as_dict() for finding in self.findings],
        }

    def render_text(self) -> str:
        """Render a stable human-readable report without ANSI or host-specific paths."""

        okf = "pass" if self.okf_passes else "fail"
        profile = self.as_dict()["core_kb_0_1"]
        lines = [
            f"Bundle: {self.bundle}",
            f"As of: {self.as_of}",
            f"Concepts: {self.concept_count}",
            f"OKF v0.2: {okf}",
            f"core-kb/0.1: {profile}",
        ]
        for finding in self.findings:
            location = finding.path
            if finding.line is not None:
                location += f":{finding.line}"
            if finding.field is not None:
                location += f" [{finding.field}]"
            lines.append(
                f"{finding.severity.label.upper()} {finding.code} {location}: {finding.message}"
            )
            if finding.remediation:
                lines.append(f"  Remediation: {finding.remediation}")
        return "\n".join(lines) + "\n"


def sorted_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """Return findings in the stable order used by reports and tests."""

    return tuple(sorted(findings, key=lambda finding: finding.sort_key))
