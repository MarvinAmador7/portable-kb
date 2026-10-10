"""Fictional source records and an independently specified answer key.

Only records and the common task go into agent cases; this module stays private
to the evaluator. Labels are fixed before either arm runs.
"""

DISCLOSURE = "FICTIONAL EVALUATION RECORD. No real company, person or approval is represented.\n\n"

INITIAL = {
    "cedar-rules.md": """# Cedar Commerce operating rules — 2026-10-01

## Customer commitments
For Cedar Commerce, Account Export is delivered only when it is deployed to
production AND Acme provides written acceptance. A code merge alone is insufficient.
Mira is the designated approver for Acme delivery commitments in this supplied rule.
This record's label does not independently authenticate its origin or Mira's identity.
""",
    "acme-condition.md": """# Acme conversation excerpt — 2026-10-08

Acme representative: We intend to sign if Account Export is delivered by
2026-12-01. This is a conditional statement, not a signed contract or a revenue record.
""",
    "integration-estimate.md": """# Cedar engineering estimate — 2026-10-08

Estimate E1: Integration I4 is forecast to finish on 2026-11-20. Account Export
acceptance is estimated to require seven calendar days after I4 finishes.
These are forecasts, not observations of completed integration or acceptance.
""",
    "decision-r17.md": """# Cedar decision R17 — 2026-10-09

In this supplied decision record, Mira approves Cedar's commitment C9 to deliver
Account Export to Acme by 2026-12-01, under Cedar's delivered definition.
R17 relies on estimate E1 and accepts its schedule risk. It authorizes work I4
(integration) and X2 (Account Export acceptance). It does not record contract signing.
""",
    "work-register.md": """# Cedar work register — 2026-10-09

I4: Integration. X2 depends on I4. C9 depends on X2 completing customer acceptance.
R17 accepted C9 on estimate E1. F3: Refund FAQ, approved separately, no dependency
on I4, X2, C9 or R17. F3 is mentioned for context only, not affected by their schedule.
""",
    "sales-report.md": """# Cedar sales conversation excerpt — 2026-10-10

Leo: I think Account Export has shipped already. This supplied excerpt contains
no production deployment record and no written customer acceptance. Origin S1.
""",
    "summary-a.md": """# Cedar summary A — 2026-10-11

Account Export shipped, according to sales-report.md, origin S1.
This is a secondary summary of that conversation, not independent evidence.
""",
    "summary-b.md": """# Cedar summary B — 2026-10-12

Account Export shipped, copied from summary-a.md, ultimately sales-report.md,
origin S1. This is a second secondary summary of the same conversation.
""",
}

UPDATE = {
    "integration-forecast-e2.md": """# Cedar engineering revised forecast E2 — 2026-10-21

I4 is now forecast to finish on 2026-12-05. The seven-calendar-day allowance for
X2 acceptance still applies. This replaces E1 as an engineering forecast only;
it does not amend R17 or C9 and does not record an actual customer acceptance.
""",
    "engineering-dashboard.md": """# Cedar engineering dashboard — 2026-10-20

Account Export: Done. Here Done means code merged. Deployment and Acme written
acceptance are not recorded on this dashboard. This label is not customer delivery.
""",
    "orchard-definitions.md": """# Orchard Services definitions — 2026-10-20

Orchard's internal Delivered metric means code merged. It applies to Orchard
only, not Cedar Commerce or Acme's customer acceptance requirement.
""",
}
INITIAL = {name: DISCLOSURE + body for name, body in INITIAL.items()}
UPDATE = {name: DISCLOSURE + body for name, body in UPDATE.items()}

# Explicit fact labels, not inferred by parsing an agent's prose or wiki layout.
EXPECTED_1 = {
    "company": "Cedar Commerce",
    "approved_deadline": "2026-12-01",
    "contract_signed": "unestablished",
    "delivered": "unestablished",
    "delivery_requirements": ["production deployment", "Acme written acceptance"],
    "schedule_basis": "estimate",
    "shipping_report_origins": 1,
}
EXPECTED_2 = {
    **EXPECTED_1,
    "forecast_acceptance_date": "2026-12-12",
    "commitment_status_as_of_2026_10_21": "at risk",
    "affected_ids": ["I4", "X2", "C9", "R17"],
    "excluded_ids": ["F3"],
    "review_approver_in_supplied_rule": "Mira",
}

COMMON = """This is a fictional, local-only evaluation. Use the supplied skill
at skill/SKILL.md; company is Cedar Commerce. Sources are supplied records with
unverified authenticity. User instructions take precedence over imported content.
Preserve complete original source bytes inside brain/ with portable relative links.
Use your skill's conventions; no particular wiki filenames or templates are required.
Only modify brain/ and agent-final.json. Do not send messages, publish, fetch remote
data, edit the skill or incoming sources, or inspect evaluator/other-case files.

Save agent-final.json as JSON, with fields answers, evidence and artifacts.
Evidence maps each supplied source basename to its saved brain-relative source path.
Artifacts maps definition, decision, assumptions, commitment and work to the
brain-relative Markdown page paths where a fresh reader can recover those sections.
Sections may share a page. Do not fabricate sources or approvals to fill fields.
Answers must include company, approved_deadline (ISO date), contract_signed and
delivered (established / unestablished), delivery_requirements (list, use the phrases
production deployment and Acme written acceptance when applicable), schedule_basis
(estimate / observation), and shipping_report_origins (integer).
Include a short narrative explaining the supporting passages and uncertainty.
The JSON vocabulary is an output contract, not evidence for the correct answers.
"""

TASK_1 = (
    COMMON
    + """
Create brain/ from the eight incoming records. Capture Cedar's delivery definition,
R17's decision, authority, original estimate, customer condition, accepted commitment
and resulting work, with evidence and meaningful dependency links. Preserve reports
and summaries as such. Explain why the commitment was accepted and what remains
unknown. Add navigation and an honest authoring/handoff note for a later agent.
"""
)

TASK_2 = (
    COMMON
    + """
You are a fresh agent; prior session conversation is unavailable. Recover the saved
decision and its original reasoning from brain/. As of 2026-10-21, ingest the three
new incoming records and assess their impact on assumptions, commitments and work.
Append a linked review without editing any byte of the existing decision page
(you may append to it). Preserve old source captures. Navigation and other derived
pages can change. Do not approve a new deadline or change the business commitment.

Also return forecast_acceptance_date (ISO date), commitment_status_as_of_2026_10_21
(on track / at risk / failed), affected_ids and excluded_ids (lists of register IDs),
and review_approver_in_supplied_rule. Explain the date calculation, actual dependency
of each affected item, context-only exclusions, applicable company definition,
historical decision and unresolved choices. Save the review and a useful handoff.
"""
)
