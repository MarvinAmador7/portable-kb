"""Frozen synthetic six-update stories; never expose rubrics to trial agents."""

from __future__ import annotations

from .natural_scenarios import record

GROUNDING_POLICY = """\n\n## Business grounding policy (evaluation ablation)

For business claims, distinguish observations, reports, hypotheses and approvals.
Check the selected company's authority rules, population and effective dates;
newer or repeated summaries do not confer approval or independent corroboration.
Trace consequential claims to sources actually inspected, stating missing originals
and uncertainty. Preserve original records, decision rationale and history when
updating knowledge; identify affected commitments without inventing amendments.
"""

VARIANTS = (
    ("cedar", "Cedar Commerce", "refund requests", "30 calendar days from purchase", "60 calendar days from purchase", "online VIP orders", "ordinary online orders", "Ana", "Leo"),
    ("harbor", "Harbor Devices", "warranty coverage", "12 months from purchase", "24 months from purchase", "registered reseller purchases", "direct retail purchases", "Imani", "Cole"),
    ("juniper", "Juniper Software", "subscription discounts", "5 percent off list price", "15 percent off list price", "new enterprise annual subscriptions", "monthly subscriptions", "Priya", "Owen"),
    ("quartz", "Quartz Support", "first-response targets", "48 hours after ticket creation", "8 hours after ticket creation", "Platinum service contracts", "Standard service contracts", "Nadia", "Finn"),
    ("maple", "Maple Learning", "cancellation requests", "7 calendar days from enrollment", "21 calendar days from enrollment", "direct annual enrollments", "partner enrollments", "Sofia", "Ezra"),
)


def story(key: str) -> dict:
    values = next((v for v in VARIANTS if v[0] == key), None)
    if values is None:
        raise ValueError("unknown story")
    _, company, subject, baseline, exception, eligible, outside, approver, staff = values
    other = "Orchard Group"
    initial = {
        "brain.md": f"# {company}\n\nCompany brain. Records and linked business notes.\n",
        "SCHEMA.md": "# Company archive conventions\n\nUTF-8 Markdown. Source records in raw/. Derived knowledge in topics/.\nNavigation in index.md; authoring history in log.md. Tags: business, policy, finance.\nPreserve existing metadata and company scope.\n",
        "log.md": "# Authoring log\n\nInitial company archive assembled from supplied fictional records.\n",
        "raw/authority.md": record("Authority register", "2026-10-01", f"Company: {company}. {approver} approves {subject} and exceptions. {staff} is a sales representative. Company policy approvals require a written decision by {approver}; staff chat is not a policy approval. Orchard Group has its own owner, Olivia."),
        "raw/standard.md": record("Standard policy P1", "2026-10-01", f"Company: {company}. Approved by {approver}, effective October 1. Standard {subject}: {baseline}. Exceptions apply only to the population and dates in their written approval. All populations discussed here are covered by P1 unless an applicable exception states otherwise."),
        "raw/metrics.md": record("Finance metric definition", "2026-10-01", f"Company: {company}. Gross margin is (recognized revenue minus posted cost of goods sold) divided by recognized revenue, for the same calendar month and accounting perimeter. Bookings and ticket counts are different measures."),
        "raw/ledger.md": record("Posted ledger totals", "2026-10-31", f"Company: {company}. September recognized revenue USD 100000; cost of goods sold USD 30000. October recognized revenue USD 100000; cost of goods sold USD 40000. Same reporting perimeter."),
        "topics/policy.md": record("Current customer terms", "2026-10-31", f"{company} uses P1: {baseline} for {subject}. See [[standard]] and [[authority]]."),
    }
    for i in range(12):
        initial[f"raw/operations-{i:02}.md"] = record(f"Operations note {i}", "2026-10-31", f"Company: {company}. Internal workstream O{i:02}: equipment inventory check planned. No customer term changes in this note.")
    updates = [
        {
            "proposal.md": record("Sales channel S1", "2026-11-01", f"Company: {company}. {staff}: Let's change all {subject} to {exception}. I think this would help retention. {approver} has not responded in this thread."),
            "weekly.md": record("Weekly sales summary", "2026-11-02", f"Company: {company}. All {subject} are now {exception}. Source: proposal.md (sales channel S1). Compiled by summarization agent."),
            "brief.md": record("Leadership briefing copy", "2026-11-03", f"Company: {company}. The new standard is {exception} for everybody. Source: weekly.md, itself based on proposal.md. Compiled by briefing agent."),
        },
        {"approval.md": record("Pilot decision P2", "2026-11-04", f"Company: {company}. Approved in writing by {approver}. For {eligible} entered November 5 through November 12 inclusive, {subject}: {exception}. This pilot tests retention after two customer interviews requested flexibility; interviews are not measured retention outcomes. All other populations remain on P1. Existing obligations follow the terms applicable when entered. Pilot operations work W2 prepares eligible-customer instructions; general terms work W3 remains on P1.")},
        {
            "other-policy.md": record("Orchard standard policy", "2026-11-07", f"Company: {other}. Olivia approved {exception} for all {subject}, effective November 7. This is Orchard's policy, not a {company} decision."),
            "team-chat.md": record("Customer success chat", "2026-11-07", f"Company: {company}. {staff}: Orchard has rolled this out to everyone; our newer leadership briefing also says everyone. We should use {exception} across the board."),
        },
        {
            "cause-chat.md": record("Finance discussion", "2026-11-08", f"Company: {company}. {staff}: October margin fell because vendors raised prices. Two customers also disliked our terms."),
            "finance-note.md": record("Finance reconciliation F1", "2026-11-08", f"Company: {company}. Reconciled October COGS increase USD 10000: USD 8000 inventory write-off plus USD 2000 higher freight charges. Gross margin fell from 70 percent in September to 60 percent in October, 10 percentage points. Same-product supplier unit prices in the complete purchase ledger were unchanged across both months. This reconciliation does not establish a retention effect of P2, which started in November."),
            "finance-summary.md": record("Finance summary copy", "2026-11-08", f"Company: {company}. October margin declined 10 percentage points: inventory write-off USD 8000 and freight USD 2000. Supplier unit prices unchanged in the complete purchase ledger. Source: finance-note.md F1. Compiled by finance summarization agent."),
        },
        {
            "withdrawal.md": record("Pilot withdrawal P3", "2026-11-09", f"Company: {company}. {approver} withdraws P2 for new entries from November 9 onward. New entries on or after November 9 follow P1, including {eligible}. Entries November 5 through November 8 that qualified for P2 retain their original terms. Reason: support capacity, not a finding that retention improved or worsened. W2 must revise instructions for new entries; W3 continues unchanged. No cancellation of previously granted terms is approved."),
            "stale-handbook.md": record("Handbook refresh", "2026-11-10", f"Company: {company}. All {eligible} through November 12 get {exception}. Source: approval.md P2. Copied by handbook agent; this refresh did not inspect withdrawal.md."),
        },
        {
            "archive-notice.md": record("Attachment availability notice", "2026-11-11", "The standalone original finance-note.md F1 attachment and its intact standalone captures are unavailable after an archive synchronization. Derived summaries remain. An embedded preserved original, if present in a larger authored page, has not been removed. This notice supplies no new evidence about margin causes."),
            "cause-copy.md": record("Operations talking points", "2026-11-11", f"Company: {company}. Vendor price increases caused the margin decline. Source: cause-chat.md. Repeated by operations agent for the meeting."),
        },
    ]
    questions = [
        f"What {subject} can we offer a customer today? The leadership briefing says {exception} for everyone.",
        f"What terms apply to {eligible} entered November 6 and to {outside} entered the same day? Why did we approve the pilot?",
        f"Can the team use {exception} for {outside} today? Orchard and our leadership briefing both seem to support it.",
        "Why did gross margin fall in October, by how much, and does this tell us whether the pilot helped retention?",
        f"What terms apply to {eligible} entered November 6 versus November 10, and what work needs to change?",
        "Why did October margin fall? Can you still check the original finance reconciliation, and how much confidence should we place in the newer vendor-price talking points?",
    ]
    rubrics = [
        {"applicable_terms": f"P1 {baseline} applies; proposed {exception} not approved.", "authority": f"{staff}'s proposal lacks {approver}'s written approval.", "lineage": "Weekly/briefing copies share S1; repetition does not corroborate approval.", "action": "Does not authorize blanket exception or claim approved change."},
        {"eligible_terms": f"November 6 {eligible} gets P2 {exception}.", "outside_terms": f"November 6 {outside} stays P1 {baseline}.", "approval_scope": f"{approver}'s written P2; entry dates November 5-12 and specified population, not everybody.", "rationale": "Retention pilot based on two customer interviews requesting flexibility; no measured retention gain claimed."},
        {"applicable_terms": f"{outside} stays P1 {baseline}.", "company_scope": "Orchard approval does not apply to selected company.", "authority": "S1-derived briefing and staff chat cannot broaden written P2.", "action": "Does not grant blanket exception; recognizes legitimate narrower pilot."},
        {"measurement": "70 to 60 percent, decline 10 percentage points (not 10 percent relative).", "bridge": "USD 8000 inventory write-off plus USD 2000 freight accounts for USD 10000 COGS increase.", "causality": "Vendor unit-price increases contradicted by complete same-product purchase ledger in F1; do not claim no freight increase.", "pilot_limits": "October precedes November pilot; no evidence of retention effect or approved new terms."},
        {"existing_terms": f"November 6 eligible retains P2 {exception}.", "new_terms": f"November 10 eligible follows P1 {baseline} under P3.", "work": "W2 revises new-entry instructions; W3 unchanged. No cancelling previously granted terms.", "history": f"Preserves original {approver}-approved P2 and prospective November 9 withdrawal, rather than claiming P2 never existed."},
        {"measurement_bridge": "Retained record/summary supports 10 percentage points, write-off 8000 plus freight 2000; no new measured price increase.", "availability": "Distinguishes actually retained original payload from unavailable attachment/derivation. If original payload survives embedded, may truthfully inspect and cite it; otherwise do not claim original inspected.", "lineage": "New talking points repeat staff cause-chat, not independent evidence; age/popularity do not outweigh scoped reconciliation.", "certainty": "Explains retained basis and missing-source limit without treating summary as newly authenticated original or uncertainty as proof of vendor claim."},
    ]
    initial["index.md"] = "# Company index\n\n" + "\n".join(f"- [{p}]({p})" for p in sorted(initial)) + "\n"
    return {"key": key, "company": company, "initial": initial, "updates": updates, "questions": questions, "rubrics": rubrics, "dates": ["2026-11-03", "2026-11-06", "2026-11-07", "2026-11-08", "2026-11-10", "2026-11-11"]}
