"""Portable KB core library.

The deterministic Python API remains the core seam. Optional consumers such as
the CLI and inline setup prompts call this API rather than reimplementing its rules.
"""

from .authoring import (
    ConfidenceLevel,
    GenerationMethod,
    KnowledgeCreatePlan,
    KnowledgeCreateResult,
    KnowledgeType,
    Sensitivity,
    plan_knowledge_create,
    save_knowledge_create,
)
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
from .search import SearchError, get_knowledge_item, index_keyword_brain, search_keyword
from .skills import SkillError, SkillTarget, install_agent_skill
from .validation import validate_bundle, validate_transition

__all__ = [
    "ConfidenceLevel",
    "Finding",
    "GenerationMethod",
    "KnowledgeCreatePlan",
    "KnowledgeCreateResult",
    "KnowledgeItem",
    "KnowledgeType",
    "OperationError",
    "OperationValidationError",
    "Severity",
    "SearchError",
    "Sensitivity",
    "SkillError",
    "SkillTarget",
    "ValidationReport",
    "plan_archive",
    "plan_create",
    "plan_knowledge_create",
    "save_knowledge_create",
    "plan_move",
    "plan_promote",
    "plan_reverify",
    "plan_supersede",
    "plan_update",
    "get_knowledge_item",
    "index_keyword_brain",
    "install_agent_skill",
    "search_keyword",
    "validate_bundle",
    "validate_transition",
]

__version__ = "0.1.0"
