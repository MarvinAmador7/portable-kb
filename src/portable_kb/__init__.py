"""Portable KB core library.

The deterministic Python API remains the core seam. Optional consumers such as
the CLI and setup TUI call this API rather than reimplementing its rules.
"""

from .models import Finding, KnowledgeItem, Severity, ValidationReport
from .operations import (
    OperationError,
    OperationValidationError,
    plan_archive,
    plan_create,
    plan_move,
    plan_promote,
    plan_reverify,
    plan_supersede,
    plan_update,
)
from .search import SearchError, index_keyword_brain, search_keyword
from .validation import validate_bundle, validate_transition

__all__ = [
    "Finding",
    "KnowledgeItem",
    "OperationError",
    "OperationValidationError",
    "Severity",
    "SearchError",
    "ValidationReport",
    "plan_archive",
    "plan_create",
    "plan_move",
    "plan_promote",
    "plan_reverify",
    "plan_supersede",
    "plan_update",
    "index_keyword_brain",
    "search_keyword",
    "validate_bundle",
    "validate_transition",
]

__version__ = "0.1.0"
