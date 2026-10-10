import copy

import pytest

from evals.groundray.product_report import validate_review


def fixture():
    packet = {
        "items": [
            {
                "id": "case-1",
                "kind": "brain",
                "phase": 1,
                "archive": {
                    "topics/terms.md": "The standard is 120/hour; authority is unresolved."
                },
                "facets": {"commercial": "Retain scoped rate"},
            }
        ]
    }
    review = {
        "items": [
            {
                "id": "case-1",
                "facets": {
                    "commercial": {
                        "status": "qualified",
                        "provenance_supported": True,
                        "useful_for_next_operator": True,
                        "quote": "The standard is 120/hour; authority is unresolved.",
                        "reason": "Keeps supplied standard distinct from unknown authority.",
                        "paths": ["topics/terms.md"],
                    }
                },
                "material_unsupported_claims": [],
                "continuity": {},
            }
        ]
    }
    return packet, review


def test_grader_quotes_paths_and_status_are_validated():
    packet, review = fixture()
    validate_review(packet, review)
    for key, value, message in (
        ("quote", "All rates are 80", "nonverbatim"),
        ("paths", ["invented.md"], "unknown reviewed path"),
        ("status", "correct", "malformed facet"),
    ):
        changed = copy.deepcopy(review)
        changed["items"][0]["facets"]["commercial"][key] = value
        with pytest.raises(ValueError, match=message):
            validate_review(packet, changed)


def test_missing_duplicate_and_unquoted_overclaims_are_rejected():
    packet, review = fixture()
    changed = copy.deepcopy(review)
    changed["items"].append(changed["items"][0])
    with pytest.raises(ValueError, match="duplicate"):
        validate_review(packet, changed)
    changed = copy.deepcopy(review)
    changed["items"][0]["material_unsupported_claims"] = [
        {"quote": "All rates are 80", "reason": "Unsupported expansion"}
    ]
    with pytest.raises(ValueError, match="malformed overclaim"):
        validate_review(packet, changed)
