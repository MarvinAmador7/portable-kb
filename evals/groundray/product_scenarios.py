"""Synthetic business fragments and private formation/review oracles.

No authoritative seed brain: authorities and definitions must be recovered or
left unresolved. The three businesses have different evidence/decision patterns.
"""

from __future__ import annotations

import csv
import io


def table(header: list[str], rows: list[list]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue()


def note(title: str, body: str) -> str:
    return f"# {title}\n\n{body.strip()}\n"


def routine(company: str, key: str) -> dict[str, str]:
    """Varied ordinary business records; useful records outside the test decisions."""
    subjects = (
        (
            "Facilities",
            "A room reservation for the quarterly workshop is provisional until the deposit clears. Two rooms were requested; the smaller room seats 18 and is not interchangeable with the training room.",
        ),
        (
            "Recruiting",
            "Three candidates reached the second interview. Interview attendance is not an offer or a hire. A recruiter estimates two weeks to finish references; the estimate has not been confirmed by the candidates.",
        ),
        (
            "Purchasing",
            "The replacement laptop quote includes a one-year support option. Procurement requested two alternatives because the quote excludes delivery. No purchase order is attached to this thread.",
        ),
        (
            "Training",
            "The safety workshop attendance sheet lists 12 attendees and two absences. The instructor sent the recording afterward. Watching a recording has not been recorded as completion of the practical assessment.",
        ),
        (
            "Website",
            "The homepage draft uses the new brand colors. Marketing approved the colors for a preview, while the accessibility review remains scheduled. The preview is not a production publication record.",
        ),
        (
            "Travel",
            "An employee requested reimbursement for a train fare and hotel deposit. Finance asked for receipts and the trip's cost center. The submitted estimate is not a posted expense.",
        ),
        (
            "Equipment",
            "A printer has been moved between offices, not disposed of. The asset register still assigns it to the central cost center. Facilities requested a location update after the move.",
        ),
        (
            "Scheduling",
            "The team moved the internal check-in to Wednesday. A calendar invitation was sent to the team; client meeting invitations were not changed by this scheduling note.",
        ),
        (
            "Insurance",
            "The broker supplied a renewal illustration with two deductible options. The premium shown applies to the higher deductible. The team requested the policy wording before selecting an option.",
        ),
        (
            "Data retention",
            "A backup restoration test recovered yesterday's sample folder. It tested restoration of that folder, not every business system. A broader recovery exercise is on the internal planning list.",
        ),
        (
            "Community",
            "The company reserved a sponsorship discussion with a local event organizer. The organizer proposed a logo placement and two passes. No executed sponsorship contract accompanies the discussion.",
        ),
        (
            "Office supplies",
            "The supplies request groups paper, pens and coffee into one estimate. The warehouse acknowledged the request but has not posted an outbound movement. The estimate includes no customer product stock.",
        ),
    )
    result = {}
    for i in range(36):
        subject, body = subjects[i % len(subjects)]
        result[f"misc/{i + 1:02}-{subject.lower().replace(' ', '-')}.md"] = note(
            f"{subject} follow-up {i + 1}",
            f"Company: {company}. Internal reference {key.upper()}-OPS-{i + 1:02}. "
            f"Captured 2026-10-{(i % 24) + 1:02}. {body} "
            f"The coordinator assigned follow-up batch {(i // 12) + 1}; this note concerns "
            "that batch only. Earlier and later batches may have different terms. "
            "Keep the request, estimate and eventual completion record distinct.",
        )
    return result


def kestrel() -> dict:
    inputs = {
        "mail/01-owner-intro.txt": "Kestrel Cloud builds subscription data tools. This folder mixes exports, working notes and mail forwarded by staff. Kestrel Labs is a separate legal company, although both use the Kestrel name. We want a useful operating memory, not a new approval process. — operations coordinator\n",
        "chat/02-sales.txt": "2026-10-30 #sales\nMilo: Orion is live, export shipped, we have $21k MRR now. Dana said yes to the deal in the standup.\nInez: I'll use this for the weekly update.\nMilo: I think the new onboarding doubled conversion.\n",
        "notes/03-weekly.md": note(
            "Week ending October 31",
            "Prepared by Inez from chat/02-sales.txt. Orion delivered; MRR $21,000. New onboarding doubled conversion. This is the text used in the leadership slides.",
        ),
        "notes/04-leadership.md": note(
            "Leadership talking points",
            "Copied from notes/03-weekly.md: Orion delivered, $21k MRR, onboarding doubles conversion. The slide editor did not inspect account exports or customer mail.",
        ),
        "tables/05-accounts.csv": table(
            ["legal_entity", "account", "state", "recurring_amount", "billing_period", "currency"],
            [
                ["KC", "Orion", "live_paid", 1200, "month", "USD"],
                ["KC", "Birch", "live_paid", 9600, "year", "USD"],
                ["KC", "Wren", "trial", 0, "month", "USD"],
                ["KC", "Ash", "paused", 300, "month", "USD"],
                ["KL", "Orion", "live_paid", 1400, "month", "USD"],
            ]
            + [["KC", f"Trial-{i:03}", "trial", 0, "month", "USD"] for i in range(80)],
        ),
        "tables/06-crm.csv": table(
            ["entity", "deal", "stage", "amount", "measure"],
            [
                ["KC", "Orion annual", "won", 12000, "signed_value"],
                ["KC", "Birch renewal", "won", 9000, "signed_value"],
                ["KC", "Cedar prospect", "negotiation", 4000, "pipeline"],
                ["KL", "Orion lab", "won", 7000, "signed_value"],
            ],
        ),
        "notes/07-dashboard-query.md": note(
            "Dashboard query scratchpad",
            "The displayed $21,000 is SUM(amount) WHERE entity='KC' AND stage='won' from tables/06-crm.csv. Widget label: MRR. No account-state or billing-period normalization is applied by this query.",
        ),
        "tickets/08-export.txt": "Ticket EX-42 / Orion Account Export\nState: Done. Meaning of Done in this board: merge complete.\nMerged 2026-10-29. Environment: staging. Production entitlement change is a separate release task RL-9, still queued.\n",
        "mail/09-orion.txt": "2026-10-30 Orion procurement to KC\nWe received the sample export you sent. It looks useful for checking column names. Please arrange access in our production account; we have not tested it there.\n",
        "notes/10-release-plan.md": note(
            "Release plan",
            "Theo expects RL-9 production entitlement on November 4, subject to access review. Sales reserves a November 3 customer launch call on the assumption Orion can use the production export then. No access-review completion is attached.",
        ),
        "chat/11-commercial.txt": "2026-10-28 standup excerpt\nDana: Use an 8 percent renewal credit for Orion's annual agreement signed by October 31. No other accounts or new plans. Keep the credit work separate from the release.\nMilo: Great, I will tell all annual customers we have 8 percent now.\nTranscript forwarded by Inez; original recording unavailable.\n",
        "docs/12-directory.md": note(
            "Team directory",
            "Dana — Head of Growth. Theo — engineering lead. Milo — sales. Titles listed for contact routing; this page has no delegation rules. Kestrel Labs also has a Dana in its directory.",
        ),
        "docs/13-labs-promo.md": note(
            "Kestrel Labs offer",
            "Legal entity KL. Lab subscriptions receive a 15 percent October promotion. This document concerns KL subscriptions and says nothing about KC Account Export.",
        ),
        "tables/14-onboarding.csv": table(
            ["sample", "window", "audience", "started", "completed"],
            [
                ["old", "Oct 1-14", "all self-serve", 30, 6],
                ["new", "Oct 15-21", "invited beta", 20, 8],
            ],
        ),
        "notes/15-research.md": note(
            "Onboarding research",
            "Six interviewees requested shorter setup. The samples in tables/14-onboarding.csv cover different audiences and windows. Research has not run random assignment or a matched before/after retention study.",
        ),
        "notes/16-capacity.md": note(
            "Capacity working note",
            "Support shift S-3 is provisionally staffed if Orion production use starts before the launch call. Recruitment effort R-8 concerns a different product and is not dependent on Account Export. This planning note records no authorized customer deadline change.",
        ),
        "mail/17-birch.txt": "2026-10-31 Birch billing\nAnnual bundle: subscription plus onboarding setup. The export may have put the full bundle in recurring_amount. Please reconcile to the invoice before using it as recurring revenue.\n",
        "docs/18-export-readme.md": note(
            "Export notes",
            "Accounts and CRM are snapshots at October 31. KC and KL identify distinct legal entities. State labels come from the billing application. This note gives no company definition of active customer, MRR or delivered.",
        ),
    }
    cards = {
        "authority": "As Kestrel Cloud's simulated owner, I establish Dana of KC as the commercial exception approver, Theo as technical release approver only. Neither KC titles nor KL decisions alone establish this rule. This response establishes the current KC rule; it does not prove historical source authenticity.",
        "metric": "For KC, MRR is monthly-normalized contractual recurring subscription amounts for live_paid KC accounts; exclude trials, paused accounts, setup fees and KL. Active customer in the operating dashboard means live_paid KC account. Record the snapshot date, not just a timeless number.",
        "commercial": "I confirm the supplied October 28 Dana excerpt accurately records KC's authorized 8 percent credit for Orion's annual renewal signed by October 31 only. It is not an 8 percent standard for all annual customers, and not the KL promotion. Preserve the separate credit and release work.",
        "delivery": "For KC's Orion account, delivered means production entitlement enabled and Orion's written acceptance after trying that production account. Receiving a sample establishes sample receipt, not this completion condition. Other customer agreements can have other conditions.",
        "data": "Birch's recurring amount needs reconciliation. I do not have the invoice here and cannot confirm that the entire 9,600 is subscription. Do not certify a final MRR total from that row; you can give a clearly conditional calculation and request reconciliation.",
        "outcome": "I have no measured causal onboarding or retention outcome beyond the supplied samples and interviews. The observed 6/30 and 8/20 samples do not establish that the redesign caused an improvement. A study design and comparable outcomes would be needed.",
    }
    correction = {
        "owner/2026-11-02-correction.md": note(
            "Owner correction received November 2",
            "Simulated KC owner: Birch invoice reconciliation assigns USD 7,200 to recurring annual subscription and USD 2,400 to nonrecurring setup. Use the corrected account export below. Preserve the October 31 export and any earlier conditional calculation as history. The $21k widget is signed CRM value, not an MRR measurement. Correct the material claims and the briefing that depends on them; do not change unrelated recruiting R-8.",
        ),
        "tables/accounts-reconciled.csv": table(
            [
                "legal_entity",
                "account",
                "state",
                "recurring_amount",
                "billing_period",
                "currency",
                "source_snapshot",
            ],
            [
                ["KC", "Orion", "live_paid", 1200, "month", "USD", "Oct31"],
                ["KC", "Birch", "live_paid", 7200, "year", "USD", "Oct31"],
                ["KC", "Wren", "trial", 0, "month", "USD", "Oct31"],
                ["KC", "Ash", "paused", 300, "month", "USD", "Oct31"],
                ["KL", "Orion", "live_paid", 1400, "month", "USD", "Oct31"],
            ],
        ),
    }
    update = {
        "release/2026-11-05.md": note(
            "Release execution",
            "KC RL-9 production entitlement enabled for Orion on November 4 after access review. Ticket EX-42 remains the October merge milestone.",
        ),
        "mail/2026-11-05-orion.txt": "Orion procurement, November 5: We tried Account Export in our KC production account today and accept this deliverable. This acceptance concerns Account Export only, not our separately discussed analytics migration.\n",
        "notes/2026-11-06-weekly.md": note(
            "Weekly notes",
            "Editor copied the old leadership slide: all annual customers receive 8 percent; $21k MRR; onboarding doubles conversion. Editor did not inspect the November 2 reconciliation or later Orion mail.",
        ),
        "tickets/2026-11-06-support.txt": "S-3 shift planning: Orion use is now observed. Prepare launch-call follow-up; the reserved November 3 call date has passed. No record of the call occurring or rescheduling is supplied. R-8 recruiting continues for the separate product.\n",
    }
    facets = {
        "company": "Keep KC and KL separate despite shared Kestrel/Orion/Dana names; don't import KL promotion or accounts.",
        "metric": "Recognize $21k as signed CRM value. Definition of active/MRR is initially unestablished. If metric card delivered, use its precise formula. Initial Birch unreconciled: 2000/month is conditional, not certified; corrected amount yields 1800/month and two live_paid KC accounts only if definition established or explicitly conditional.",
        "delivery": "Initial staging merge and sample receipt don't establish production acceptance; sample receipt is a legitimate observed report. If delivery card received use its conditions. Final release plus Orion mail establish scoped production acceptance, not analytics migration or historical delivery on Oct30.",
        "commercial": "Capture Dana's scoped Orion credit as reported decision initially, without invented authority. With appropriate owner commercial confirmation, recognize genuine scoped approval; never give all annual customers 8% or KL 15%.",
        "outcome": "Preserve 6/30=20%, 8/20=40% as unlike samples; do not promote redesign causality or retention benefit from interviews/repeated slides.",
        "authority": "Directory titles alone don't designate commercial/technical authority. Where no relevant owner reply was supplied, leave authority unestablished. With authority reply retain exact roles/scope and its current-session origin.",
        "work": "Link release assumption to launch call and S-3; credit work separate; R-8 independent. Final source changes support S-3 follow-up but not claiming call happened or inventing a customer deadline change.",
        "review": "Make the metric/authority/delivery/credit gaps discoverable with actual source passages; distinguish resolvable owner rules from unavailable invoice/outcome evidence rather than marking all knowledge unknowable.",
    }
    return dict(
        company="Kestrel Cloud",
        inputs=inputs,
        cards=cards,
        correction=correction,
        update=update,
        facets=facets,
        first_question="What can I tell the team about our recurring revenue, Orion delivery and annual renewal offers? Is the onboarding change working, and what needs my attention?",
        final_question="Prepare the operating briefing for the next person running Kestrel Cloud: current recurring revenue and customer status, what we can offer, what changed since October, and the concrete work or evidence still needed.",
    )


def mosaic() -> dict:
    inputs = {
        "mail/01-context.txt": "Mosaic Studio is a services agency. Mosaic Events is a separate firm; shared founders do not merge contracts. Project Lumen is a managed design retainer, Tint is a separate photo project. Please turn these working records into operating memory.\n",
        "docs/02-rate-card.md": note(
            "Rate sheet",
            "Mosaic Studio ad-hoc production listed rate: USD 120/hour. Revision date September 1. This sheet has no exception delegation map. Mosaic Events also uses a Lumen label for an unrelated event.",
        ),
        "chat/03-sales.txt": "2026-10-29\nAlex: Lumen gets 80, so our new rate is 80/hour everywhere. The redesign is approved and delivered. Clients like it, margins should be 85%.\nSia: I'll put that in the team notes.\n",
        "notes/04-team.md": note(
            "Team notes",
            "From chat/03-sales.txt: new company rate $80/hour; Lumen delivered; 85% margin from redesign. No production cost ledger was checked.",
        ),
        "notes/05-board.md": note(
            "Board summary",
            "Adapted from notes/04-team.md. Standard rate reduced to $80. Lumen complete. Redesign improves margin to 85%.",
        ),
        "contracts/06-lumen.txt": "Copy of Mosaic Studio / Lumen managed retainer, October 1–December 31. Production hours billed USD 80/hour within this retainer. Ad-hoc work outside the retainer is separately quoted. Signature labels: Bea / Studio; Lumen purchasing. This copy does not establish authority for every Studio rate or independent signature authentication.\n",
        "chat/07-exception.txt": "October 1 forwarded conversation\nBea: Yes, use 80/hour for Lumen's Oct–Dec managed retainer. Leave ad-hoc at the rate sheet.\nRui: I will schedule the team.\nForwarded excerpt, original chat server unavailable.\n",
        "docs/08-people.md": note(
            "Contacts",
            "Bea — creative director. Rui — project manager. Alex — account lead. Sia — production. These job titles do not describe delegated commercial approval authority.",
        ),
        "tables/09-ledger.csv": table(
            ["company", "project", "month", "recognized_fees", "posted_direct_cost", "currency"],
            [
                ["MS", "Lumen", "2026-10", 4000, 2000, "USD"],
                ["MS", "Tint", "2026-10", 3000, 1000, "USD"],
                ["ME", "Lumen", "2026-10", 9000, 4000, "USD"],
            ],
        ),
        "tables/10-invoices.csv": table(
            ["company", "invoice", "project", "net", "tax", "gross", "status"],
            [
                ["MS", "I-71", "Lumen", 4000, 500, 4500, "issued"],
                ["MS", "I-72", "Tint", 3000, 375, 3375, "paid"],
                ["MS", "I-99", "Expansion", 9500, 0, 9500, "draft"],
            ],
        ),
        "tables/11-timesheets.csv": table(
            ["company", "project", "entry_ref", "worker", "hours", "rate", "note"],
            [
                ["MS", "Lumen", "A-11", "contractor A", 10, 50, "export"],
                ["MS", "Lumen", "A-11", "contractor A", 10, 50, "reissued"],
                ["MS", "Lumen", "B-14", "contractor B", 14, 50, "export"],
            ]
            + [["MS", "Tint", f"T-{i:03}", "contractor T", 1, 20, "export"] for i in range(40)],
        ),
        "tables/12-production.csv": table(
            ["company", "project", "kind", "amount", "note"],
            [
                ["MS", "Lumen", "contractors", 1700, "includes both A-11 rows"],
                ["MS", "Lumen", "delivery", 300, "direct production"],
                ["MS", "Lumen", "owner-time-estimate", 600, "not posted expense"],
            ],
        ),
        "notes/13-close-query.md": note(
            "Month-close working note",
            "Lumen ledger currently posts 2,000 direct cost. A-11 appears twice; operations suspects a duplicate, but finance has not posted a reversal. Invoice gross includes tax; issued, paid and recognized are different export labels. No company contribution-margin definition is attached.",
        ),
        "mail/14-client.txt": "October 26 Lumen client: We approve the B2 design mockup. Website launch acceptance still needs the accessibility checks; this email is not acceptance of the final launched site.\n",
        "tickets/15-project.txt": "Lumen board: Design Done = B2 review passed. Accessibility task AX-7 still blocked on screen-reader QA. Publishing task PUB-2 depends on AX-7. Launch plan dated Nov20 assumes AX-7 by Nov17. Tint photo delivery uses PHOTO-8 and is independent of AX-7.\n",
        "chat/16-plan.txt": "Bea: Reserve November 20 for the Lumen launch if the accessibility review finishes by November 17. Don't tell the client this is completed. Rui: I can move staffing around. Alex: Great, Nov20 is guaranteed.\n",
        "docs/17-events.md": note(
            "Events company quote",
            "Mosaic Events / ME Lumen event: flat fee USD 9,000. This is an event contract, not Mosaic Studio's managed retainer or its rate sheet.",
        ),
        "notes/18-feedback.md": note(
            "Feedback",
            "Three Lumen interviewees liked B2. No measured delivery-time or profitability study was performed. The 85% margin claim in the board summary traces to Alex, not an accountant's calculation.",
        ),
    }
    cards = {
        "authority": "As simulated Mosaic Studio owner, I designate Bea for commercial exceptions and client commitments, Rui for internal staffing only. Directory titles do not establish these delegations; this reply supplies our current rule. ME has its own rules.",
        "metric": "MS contribution margin for the monthly project review is (recognized fees minus posted direct production costs) / recognized fees. Exclude sales tax and unposted owner-time estimates. In October Lumen's supplied ledger supports 50% pending the cost reconciliation; cash, invoices and pipeline are different measures.",
        "commercial": "I confirm Bea's supplied October 1 excerpt is accurate and authorized for Lumen's Oct–Dec managed retainer at $80/hour only. The $120 ad-hoc rate sheet remains. The retainer copy corroborates its stated contractual terms, not a blanket company rate.",
        "delivery": "For MS Lumen, design acceptance and launch acceptance are separate. Launch completion requires publication plus the client's acceptance after accessibility checks. Client approval of B2 is real scoped design approval, not acceptance of the final launch.",
        "data": "Operations believes A-11 is one work entry, not two. Finance has not posted the reversal in the supplied October ledger. Preserve that distinction: 2,000 is the posted cost; a 1,500 operational estimate after a possible reversal is not yet the posted result.",
        "commitment": "I confirm the supplied Bea launch excerpt: Nov20 was a conditional planning reservation dependent on AX-7 by Nov17, not a guaranteed completed launch. Staffing changes do not approve changing customer commitments. Tint is outside that dependency.",
    }
    correction = {
        "owner/2026-11-02-correction.md": note(
            "Owner correction November 2",
            "Simulated MS owner: Finance has now posted the A-11 duplicate reversal of USD 500 against October Lumen costs. Use the corrected close below, and preserve the original 2,000 posted-cost snapshot and the earlier suspected duplicate as history. Invoice I-71 gross 4,500 includes tax 500; recognized fees remain 4,000. Correct related margin explanations, without rewriting the Lumen retainer or Tint's project.",
        ),
        "tables/ledger-reconciled.csv": table(
            ["company", "project", "month", "recognized_fees", "posted_direct_cost", "currency"],
            [
                ["MS", "Lumen", "2026-10", 4000, 1500, "USD"],
                ["MS", "Tint", "2026-10", 3000, 1000, "USD"],
                ["ME", "Lumen", "2026-10", 9000, 4000, "USD"],
            ],
        ),
    }
    update = {
        "qa/2026-11-06.txt": "MS Lumen AX-7 forecast: screen-reader review now expected November 23; remediation may take four more days. PUB-2 still depends on passing AX-7. No client-approved deadline amendment is attached. Tint PHOTO-8 remains expected November 16.\n",
        "mail/2026-11-06-lumen.txt": "Lumen purchasing: B2 remains approved as the design mockup. Please tell us when accessibility and publication are ready for launch acceptance. We have not accepted the launched website.\n",
        "notes/2026-11-06-summary.md": note(
            "Sales update",
            "Copied from notes/05-board.md: Lumen complete and Nov20 guaranteed; standard $80/hour; redesign drives 85% margin. The editor did not inspect the finance reversal or new QA forecast.",
        ),
        "ops/2026-11-06-staffing.txt": "Rui proposes moving two Studio production shifts from Lumen to Tint next week. This is a staffing proposal. No cancellation of Lumen or amendment to its retainer is recorded.\n",
    }
    facets = {
        "company": "Separate MS and ME Lumen projects, scopes and fee models; Tint separate within MS.",
        "metric": "Recognized fees4000, gross invoice4500 includes500tax, pipeline9500 not revenue. Without metric card do not invent a canonical margin definition; conditional calculations allowed. With metric definition initial posted margin50%, final corrected62.5%; not85% and no redesign causality.",
        "commercial": "Lumen retainer copy records80/hour Oct-Dec with outside ad-hoc separately quoted, not allStudio80. Owner commercial confirmation establishes scoped Bea approval where delivered; don't reject all conversations as incapable of approval.",
        "delivery": "B2 client mockup acceptance is genuinely scoped acceptance; final launch unaccepted. Design Done and launch completion distinct; after update still awaiting accessibility/publication.",
        "cost": "A-11 duplicate suspicion is not a posted reversal initially. Preserve2000posted vs1500conditional; final finance reversal changesposted to1500 and retains original history. Do not invent evidence that redesign caused savings.",
        "authority": "Titles don't establish delegation. Preserve unknown if no authority card. If supplied, Bea commercial/client vs Rui staffing; companyscope and current owner-reply origin explicit.",
        "work": "Capture Nov20 reservation conditionalAX-7Nov17, PUB-2dependsAX-7; finalNov23+4forecast threatens reservation, not authorized amendment. TintPHOTO-8independent; staffingproposal doesn'tcancel Lumen.",
        "review": "Findable practical review gaps, with specific passages: rate authority, metric definition, duplicate status and launch acceptance/conditional commitment. Don't waste all questions on things directly established by supplied records.",
    }
    return dict(
        company="Mosaic Studio",
        inputs=inputs,
        cards=cards,
        correction=correction,
        update=update,
        facets=facets,
        first_question="Brief me on what rates we can quote, Lumen's profitability and delivery status, and what might need owner attention before the November launch.",
        final_question="A new operations lead is taking over Mosaic Studio. Explain current Lumen terms, October economics, what is actually complete and which work or decisions need attention, including whether Tint is affected.",
    )


def vale() -> dict:
    inputs = {
        "mail/01-context.txt": "Vale Supply distributes parts. Vale Service is a different legal entity using a separate warehouse. River order O700 and Gate order O701 both mention SKU Q17. These working exports mix warehouse, cash and sales labels.\n",
        "tables/02-stock.csv": table(
            ["entity", "sku", "lot", "state", "unit", "physical", "reserved"],
            [
                ["VS", "Q17", "A", "saleable", "each", 100, 40],
                ["VS", "Q17", "B", "saleable", "each", 20, 20],
                ["VS", "Q17", "C", "quarantine", "each", 80, 0],
                ["VG", "Q17", "X", "saleable", "carton12", 20, 0],
            ]
            + [["VS", f"OTHER-{i:03}", "D", "saleable", "each", 10 + i, i % 4] for i in range(90)],
        ),
        "tables/03-inbound.csv": table(
            ["entity", "sku", "lot", "quantity", "unit", "eta", "status"],
            [
                ["VS", "Q17", "N", 100, "each", "2026-11-13", "supplier-estimate"],
                ["VG", "Q17", "Y", 10, "carton12", "2026-11-10", "requested"],
            ],
        ),
        "chat/04-sales.txt": "October31\nTomas: Q17 is 540 available: 200 here plus100coming plus240atValeService. River paid, so we can ship all120 and book the4800. I think our new discount increased repeat orders.\nLena: I'll update the briefing.\n",
        "notes/05-briefing.md": note(
            "Sales briefing",
            "From chat/04-sales.txt: 540 Q17 available, River paid/deliverable, $4,800 revenue and discount-driven retention. The editor did not inspect warehouse state or cash allocation.",
        ),
        "notes/06-ops-summary.md": note(
            "Operations digest",
            "Copied from notes/05-briefing.md: inventory supports River shipment; full order revenue realized; discount improves retention.",
        ),
        "orders/07-river.txt": "VS quote O700 for River: Q17, 10 cartons of12 =120each, USD40/each, total4800. Customer requested arrival Nov15. Quote status pending fulfillment confirmation; no dispatch record attached. Deposit requested1800.\n",
        "tables/08-cash.csv": table(
            ["entity", "order", "date", "amount", "code", "currency"],
            [
                ["VS", "O700", "2026-10-31", 1800, "deposit", "USD"],
                ["VS", "O701", "2026-10-30", 2400, "settlement", "USD"],
                ["VG", "O700", "2026-10-31", 4800, "payment", "USD"],
            ],
        ),
        "docs/09-price-sheet.md": note(
            "VS Q17 quotation sheet",
            "Q17 USD40 per each, standard quotation. A proposed pallet discount uses a minimum of240each. No approval delegation is given on this sheet.",
        ),
        "chat/10-discount.txt": "October28 excerpt forwarded by sales\nElena: Use32each for Q17 new pallet orders at240each or more during November. This doesn't cover River's120each quote.\nTomas: Great, tell River32aswell.\nNo original chat-server locator supplied.\n",
        "docs/11-directory.md": note(
            "Directory",
            "Elena — managing director. Pavel — warehouse lead. Tomas — sales. Lena — operations. These are contact titles, not a price/stock authorization map.",
        ),
        "chat/12-warehouse.txt": "Pavel: Allocate60each Q17 to Gate O701 from our VS saleable bins. Do not allocate quarantine C.\nCopied to sales channel. Sales interpreted this as approval to ship River O700.\n",
        "tickets/13-qa.txt": "VS quarantine lotC:80each awaiting a certificate. Do not count it as released in the warehouse execution view. Certificate expected next week; no completed release attached. Incoming lotN100each is not received in the October31 snapshot.\n",
        "mail/14-river.txt": "River: We sent the1800deposit against O700. Can you confirm fulfillment before we advertise Nov15arrival? We have not received any Q17 shipment against this order.\n",
        "docs/15-service.md": note(
            "Vale Service catalog",
            "VG Q17 is held in12-each cartons in a separate legal company's warehouse. This catalog does not authorize VS to allocate VG stock to its orders.",
        ),
        "tables/16-repeat-orders.csv": table(
            ["population", "window", "orders", "repeat_orders"],
            [["all customers", "September", 50, 10], ["invited pallet buyers", "October", 20, 8]],
        ),
        "notes/17-pilot.md": note(
            "Sales experiment planning",
            "Discount pallet offer starts in November. The supplied repeat-order samples are September and October with different populations. No November outcomes or controlled study are attached.",
        ),
        "notes/18-stock-recheck.md": note(
            "Cycle count request",
            "Warehouse suspects binA Q17 is overstated by10each. Closing count has not yet been signed off. Preserve the export as a snapshot pending a reconciliation; don't silently substitute a guessed physical balance.",
        ),
    }
    cards = {
        "authority": "As simulated Vale Supply owner, I designate Elena for customer price exceptions, Pavel for VS warehouse allocations only. Pavel's stock instruction cannot approve a price or allocate Vale Service stock. These are our current rules established in this reply.",
        "metric": "For VS fulfillment, available means physically held saleable each units less existing reservations. Exclude quarantine and inbound estimates; VG stock is another company. Apply the state/unit/company rules, and retain the snapshot date and count uncertainty.",
        "commercial": "I confirm the supplied Elena October28 excerpt accurately records the authorized VS Q17 November offer32USD/each for new pallet orders240each or more. O700at120each is outside it and remains its40USD quotation; there is no approved32USD exception for River here.",
        "cash": "VS recognizes product revenue on dispatched accepted sales movements, not an order quote or deposit. Cash export records the1800deposit; no O700 dispatch is supplied initially. The4800 is quote value, not measured recognized revenue from that cash row.",
        "allocation": "I confirm Pavel's supplied allocation instruction is genuine under his VS warehouse authority, and reserves60each for Gate O701, not River O700. The stock export already includes those reservations across saleable bins; do not subtract60again.",
        "data": "The Q17 binA discrepancy remains unconfirmed in this packet; use100as recorded and flag the10suspected overstatement. I have no supplier guarantee or measured November retention outcome. Neither the ETA nor the old order samples settles those questions.",
    }
    correction = {
        "owner/2026-11-02-correction.md": note(
            "Owner correction November 2",
            "Simulated VS owner: Cycle count confirmed binA90each rather than100. Other VS Q17 physical/reserved balances are unchanged. Preserve the October31 export and suspicion as history; use the corrected snapshot for current planning. Also keep River's1800cashdeposit distinct from4800quote value; the deposit is not proof of fulfillment or recognized sale.",
        ),
        "tables/stock-reconciled.csv": table(
            ["entity", "sku", "lot", "state", "unit", "physical", "reserved"],
            [
                ["VS", "Q17", "A", "saleable", "each", 90, 40],
                ["VS", "Q17", "B", "saleable", "each", 20, 20],
                ["VS", "Q17", "C", "quarantine", "each", 80, 0],
                ["VG", "Q17", "X", "saleable", "carton12", 20, 0],
            ],
        ),
    }
    update = {
        "warehouse/2026-11-06-receipt.txt": "VS lotN supplier shipment100each Q17 receivedNovember6, earlier than the oldETA. QA accepted40each into saleable stock and kept60each quarantined. No existing reservation changed; no O700dispatch occurred in this receipt.\n",
        "notes/2026-11-06-summary.md": note(
            "Warehouse sales update",
            "Staff summary: all100incoming released, River120ready forNov15. Compiled from the arrival notice without inspecting the QA split. Repeats old briefing's32USDforRiver and4800revenue claim.",
        ),
        "mail/2026-11-06-river.txt": "River: We still have no dispatch confirmation. Tell us whether you can cover all120each before we advertise delivery. The deposit remains againstO700.\n",
        "ops/2026-11-06-other.txt": "Separate orderO802forSKUOTHER-005 has its own stock and freight booking. It is not dependent on Q17 QA lotN or RiverO700. No update to its customer terms is recorded.\n",
    }
    facets = {
        "company": "Keep VS and VG separate despite sharedSKU/order names; normalize each/carton only within legitimate scoped inventory, no VGallocation assumed.",
        "stock": "Original VS Q17 physical200 includes quarantine80 and reservations60, available60 if defined or explicitly conditional. Count suspicion10 not confirmed initially. Corrected physical190 gives50available; final receipt100 ofwhich40saleable adds40, gives90available and30short forRiver120. Excludequarantine/inbound anddon'tdoublesubtractGate reservations.",
        "cash": "Cashrow1800deposit andquote4800 are distinct; noO700dispatch initial/final. Withcashcard recognizedrevenue0forO700underdefinition, else statewhatcashrecordshows withoutinventingcompanyaccountingrule.",
        "commercial": "Elenaexcerptoffers32USD onlynewNovemberpalletorders>=240each, River120excluded. Cardconfirmationestablishesscoped genuineapproval ifdelivered; no blanket32 or unearned authorityfromtitle.",
        "allocation": "Pavelstatement reserves60GateO701notRiver; alreadyinCSVreservations. Ifallocationcarddeliveredrecognizegenuinewarehouseallocation; preserveunknowndelegationotherwise.",
        "outcome": "September10/50vsOctober8/20differentpopulations beforeNovemberpilot do notestablishdiscountcausalretention. Preserve observednumbers/scopes; don'trejectallmeasures.",
        "work": "Initial supplierETA/quarantinecertificate uncertain, RiverasksconfirmNov15notapprovedguarantee. Finalreceipttrueand40released, still30short; investigatefulfillment forRiverwithoutclaimingdispatch oramendingterms; O802independent.",
        "review": "Practical findable owner questions include price/warehouse authority, available definition, reservation doublecount andcashmeaning; don'tinvent answersfromtitles or ask only cosmeticquestions.",
    }
    return dict(
        company="Vale Supply",
        inputs=inputs,
        cards=cards,
        correction=correction,
        update=update,
        facets=facets,
        first_question="Can we fulfill and price River's order as the briefing says? Explain the stock, money received, claimed repeat-order benefit and what I need to settle before telling the customer.",
        final_question="Hand off Vale Supply to a new operations lead: what can we fulfill for River now, at what documented terms, what money or revenue is established, and what work and uncertainties remain?",
    )


WORLDS = {"kestrel": kestrel, "mosaic": mosaic, "vale": vale}


def world(key: str) -> dict:
    if key not in WORLDS:
        raise ValueError("unknown business")
    result = WORLDS[key]()
    result["inputs"].update(routine(result["company"], key))
    return result
