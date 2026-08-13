from __future__ import annotations

from pathlib import Path

from portable_kb.models import Finding, Severity, ValidationReport, sorted_findings


def test_finding_and_report_serialization() -> None:
    warning = Finding(
        "KB-W999",
        Severity.WARNING,
        "item.md",
        "Review this.",
        field="title",
        line=4,
        remediation="Change the title.",
    )
    info = Finding("KB-I999", Severity.INFORMATION, "a.md", "Notice.")
    report = ValidationReport(Path("knowledge"), "2026-08-12", sorted_findings([warning, info]), 2)
    assert Severity.ERROR.label == "error"
    assert warning.as_dict()["line"] == 4
    assert warning.as_dict()["remediation"] == "Change the title."
    assert report.errors == ()
    assert report.information == (info,)
    assert report.profile_passes
    assert report.as_dict()["core_kb_0_1"] == "pass-with-warnings"
    assert report.as_dict()["bundle"] == "knowledge"
    rendered = report.render_text()
    assert "OKF v0.2: pass" in rendered
    assert "WARNING KB-W999 item.md:4 [title]: Review this." in rendered
    assert "Remediation: Change the title." in rendered


def test_okf_failure_is_reported_separately() -> None:
    failure = Finding("KB-E100", Severity.ERROR, "bad.md", "Missing type.", profile="OKF v0.2")
    report = ValidationReport(Path("knowledge"), "2026-08-12", (failure,), 1)
    assert not report.okf_passes
    assert not report.profile_passes
    assert report.as_dict()["okf_v0_2"] == "fail"
    assert report.as_dict()["core_kb_0_1"] == "fail-with-errors"
