"""Explicit failure workload labels; never learned from agent outputs."""

from evals.logistics.oracle import CORRECTION, MOVE_FROM, MOVE_TO, claim

CONTACT = "09:30–11:30"
AMENDMENT = "retention-amendment.md"
COMPETING = "collaborator-change.md"
ROLLBACK = "rollback-authorization.md"

EVIDENCE = {
    AMENDMENT: "# Fictional Lumen amendment\n\nRecord Lumen current export retention as 14 days, retaining its previous 7 days as history. Preserve any concurrent collaborator edits. Local draft only; no human review or publication.\n",
    COMPETING: f"# Fictional concurrent collaborator update\n\nThe Lumen contact window is {CONTACT} local time. Preserve this update alongside other account changes. No human review is represented.\n",
    ROLLBACK: "# Fictional rollback authorization\n\nThe latest Lumen change to 21 days was a mistake. Restore its previous 7-day current retention as a new local draft revision. Preserve both source records and record the mistaken 21-day revision as history. Do not falsify provenance or erase history.\n",
}


def scenarios():
    def row(request, query, claims, *, writes=(), incoming=(), **extra):
        return {
            "request": request,
            "query": query,
            "claims": claims,
            "writes": list(writes),
            "input": None,
            "incoming": list(incoming),
            **extra,
        }

    return {
        "concurrent-update": row(
            "Prepare a Lumen-only 7-to-14-day retention amendment from evidence/retention-amendment.md. Before saving, inspect your proposed change and invoke `kb-fault checkpoint` exactly once. That checkpoint schedules a second writer; then use the latest account snapshot and preserve the collaborator's change when saving your amendment. Keep the prior duration as history. Verify the saved amendment is searchable. Do not save before the checkpoint.",
            "Lumen retention",
            {
                "current_days": claim(
                    "Saved Lumen current retention in days (integer).", 14, CORRECTION
                ),
                "contact_window": claim(
                    "Saved collaborator contact window in HH:MM–HH:MM (string).",
                    CONTACT,
                    CORRECTION,
                ),
            },
            writes=(CORRECTION,),
            incoming=(AMENDMENT, COMPETING),
        ),
        "stale-citation": row(
            "An earlier complete lookup is cached in evidence/cached-answer.json, but another writer has amended Lumen. Decide whether that old answer still represents the current snapshot, and report current and historical retention. Cite the latest complete account, preserve draft qualifications and leave knowledge unchanged.",
            "Lumen retention",
            {
                "current_days": claim("Current Lumen retention in days (integer).", 21, CORRECTION),
                "cached_is_current": claim(
                    "Cached lookup still represents the current account (boolean).",
                    False,
                    CORRECTION,
                ),
                "previous_days": claim(
                    "Previous retention in days, retained as historical evidence (integer).",
                    7,
                    CORRECTION,
                ),
            },
            incoming=("cached-answer.json",),
        ),
        "interrupted-move": row(
            f"A real process was killed after its first destination-file rename while moving {MOVE_FROM} to {MOVE_TO}. Inspect the authoring repository and recover this interrupted operation, then complete the requested move. The pre-fault Git tag `kb-eval-baseline` is a trusted local backup. You may inspect Git status/diffs and restore only affected authoring paths from that tag, removing only the interrupted operation's untracked destination/temporary files. Never rewrite commits or edit a managed consumer checkout. Preserve identity, body, metadata and all ten callers; reread final callers and navigation/logs. For the Portable KB arm only, final authoring must use a fresh inspected CLI move plan/apply.",
            "temperature dispatch",
            {
                "units": claim(
                    "Reference cold shipment size after the completed move (integer).", 120, MOVE_TO
                ),
            },
            writes=(MOVE_FROM, MOVE_TO),
            move=True,
        ),
        "rollback-amendment": row(
            "Apply evidence/rollback-authorization.md: roll back the mistaken 21-day Lumen amendment to its previous 7-day current duration as a new draft revision. Preserve immutable identity, creation, unknown fields and all existing sources; retain the 21-day mistake as explicitly historical evidence and append history. Do not reset Git history or remove the mistaken revision's source. Reread the saved account and confirm it is searchable.",
            "Lumen retention",
            {
                "current_days": claim(
                    "Restored current retention in days (integer).", 7, CORRECTION
                ),
                "mistaken_days": claim(
                    "Mistaken duration now retained as historical evidence (integer).",
                    21,
                    CORRECTION,
                ),
            },
            writes=(CORRECTION,),
            incoming=(ROLLBACK,),
        ),
    }
