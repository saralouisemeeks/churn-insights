"""Generate a synthetic B2B SaaS CRM export for churn-insights.

Everything produced here is fabricated. No real customer data is used anywhere
in this project.

Run:
    python3 scripts/generate_data.py

Writes:
    data/accounts.csv       account-level CRM fields
    data/notes.csv          free-text CSM notes
    data/ground_truth.csv   the risk themes actually injected per account

ground_truth.csv is never read by the app. It exists so that Phase 4 can
measure how well the LLM recovers themes it was never shown, rather than
grading its own homework.

Three properties are built in deliberately:

1. Risk signal lives in the free-text notes, not in the structured fields.
   If a column predicted churn, an LLM would be unnecessary.
2. The CRM's own health_score is poorly calibrated. About 40% of churned
   accounts carry a healthy score, which is typical of real CRM hygiene.
3. Retained accounts also exhibit risk themes. Churn is therefore not
   linearly separable. The signal is in theme co-occurrence and recency.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
TODAY = date(2026, 9, 13)
N_ACCOUNTS = 220

random.seed(SEED)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# --------------------------------------------------------------------------
# Name generation
# --------------------------------------------------------------------------

COMPANY_HEADS = [
    "Northgate", "Brightwater", "Kestrel", "Halcyon", "Ironvale", "Meridian",
    "Clearpoint", "Summit Ridge", "Tallgrass", "Bluestem", "Vantage", "Cobalt",
    "Fairhaven", "Redstone", "Oakline", "Pinecrest", "Silverbrook", "Granite",
    "Harborview", "Windrow", "Copperfield", "Larkspur", "Stonebridge", "Quarry",
    "Foxglove", "Amberline", "Drexel", "Wayfarer", "Trellis", "Junction",
    "Alderwood", "Beacon Hill", "Cinderpath", "Dunmore", "Eastbrook", "Ferncliff",
]

COMPANY_TAILS = [
    "Systems", "Logistics", "Health", "Analytics", "Partners", "Group",
    "Technologies", "Financial", "Labs", "Industries", "Solutions", "Networks",
    "Capital", "Media", "Software", "Dynamics", "Holdings", "Robotics",
]

FIRST_NAMES = [
    "Priya", "Marcus", "Dana", "Ethan", "Yusuf", "Claire", "Devon", "Ingrid",
    "Raj", "Nora", "Tomas", "Bianca", "Owen", "Leila", "Grant", "Simone",
    "Hector", "Alice", "Jonah", "Mei", "Felix", "Carmen", "Reid", "Anya",
    "Malik", "Erin", "Soren", "Talia", "Wes", "Junko", "Dmitri", "Rosa",
]

LAST_NAMES = [
    "Okafor", "Lindqvist", "Ramirez", "Chen", "Whitfield", "Barros", "Nakamura",
    "Delgado", "Hollis", "Petrov", "Abbott", "Ferreira", "Nwosu", "Kaminski",
    "Stroud", "Vasquez", "Doyle", "Achterberg", "Mbeki", "Saltzman",
]

CSM_NAMES = [
    "Brittney Cole", "Nuala Byrne", "Caick Moreira", "Shairyar Khan",
    "Owen Trask", "Leila Haddad",
]

INDUSTRIES = [
    "Manufacturing", "Healthcare", "Financial Services", "Logistics",
    "Retail", "Energy", "Professional Services", "Education", "Media",
]

COMPETITORS = [
    "Lattitude", "Corveo", "Helmsman", "Nimbus Track", "Parallax", "Orderly",
    "an in-house build", "a spreadsheet-based process",
]

PRODUCT_AREAS = [
    "the reporting module", "the API", "SSO", "the bulk import", "dashboards",
    "the mobile app", "role permissions", "the Salesforce sync",
    "the alerting rules", "data retention",
]


def person():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def company():
    return f"{random.choice(COMPANY_HEADS)} {random.choice(COMPANY_TAILS)}"


# --------------------------------------------------------------------------
# Note templates
#
# Each theme has many phrasings so that the language varies the way real CSM
# notes do. Placeholders are filled per account so that the same theme never
# reads identically twice.
# --------------------------------------------------------------------------

RISK_TEMPLATES = {
    "champion_departure": [
        "Heads up, {champion} is leaving at the end of the month. She was our main advocate here.",
        "{champion} has moved to a different company. No replacement named yet.",
        "Org change on their side. {champion} no longer owns this relationship.",
        "New VP came in over {champion}'s team and is reviewing all vendor relationships.",
        "Found out {champion} put in notice. Trying to get introduced to whoever picks this up.",
        "Our sponsor {champion} was reorged out of the function. Starting over on relationship mapping.",
        "{champion} is on leave through Q4 and nobody was designated to cover the account.",
        "Their new director does not know who we are. Sent an intro note, no reply yet.",
        "Lost our exec sponsor. {champion} was the reason this renewed last year.",
        "{champion} confirmed she is taking a role elsewhere. Asked her who to talk to, she was vague.",
    ],
    "low_adoption": [
        "Only {n} of their licensed seats logged in last month.",
        "Usage is flat. {n} weekly active users against a much larger contract.",
        "They bought for the whole department but adoption never left the pilot team.",
        "Ran the numbers before the call. {n} active users, down from last quarter.",
        "Admin told me most of the team still does this work in spreadsheets.",
        "Seat utilization is under a third. Raised it, they acknowledged and moved on.",
        "Nobody outside the original two users has touched {product_area} since onboarding.",
        "Their team never completed rollout to the second region. {n} users total.",
        "Login activity dropped off after the project lead changed. {n} active this month.",
        "They are paying for far more than they use and finance has started to notice.",
    ],
    "unresolved_escalation": [
        "Still waiting on the fix for {product_area}. This has been open for weeks.",
        "Escalation on {product_area} is not moving. They asked for a timeline and I do not have one.",
        "Third follow-up from them on the same defect. Getting hard to defend.",
        "They are frustrated. {product_area} broke again during their month-end close.",
        "Support ticket has been open since before the last QBR. No engineering ETA.",
        "Reopened the issue with {product_area}. Their patience is visibly thin.",
        "{champion} asked me directly whether this is ever going to be fixed.",
        "Outage during their peak week. They want a written explanation.",
        "Promised a fix date last month and we missed it. Had to tell them today.",
        "The workaround we gave them for {product_area} stopped working.",
    ],
    "budget_scrutiny": [
        "Finance is reviewing every software line item this cycle.",
        "They flagged that procurement now requires justification for anything over the threshold.",
        "Their CFO asked for a cost per user breakdown. Sent it, waiting.",
        "Budget freeze announced internally. Renewals are being looked at individually.",
        "They asked whether we can do a shorter term or a smaller seat count.",
        "Told me the spend is being questioned above {champion}'s level.",
        "Company-wide cost reduction effort. We are on the list being evaluated.",
        "Asked about downgrade options unprompted.",
        "Their procurement team has entered the conversation for the first time.",
        "Layoffs on their side. Seat count is going to come down at renewal.",
    ],
    "competitor_evaluation": [
        "They mentioned they are piloting {competitor} with one team.",
        "Came up that {competitor} has been in talking to their leadership.",
        "Asked me how we compare to {competitor}. First time that has come up.",
        "Their new director used {competitor} at her last company and prefers it.",
        "They are running a formal evaluation and we are one of three.",
        "Heard secondhand that {competitor} gave them aggressive pricing.",
        "Requested a feature comparison against {competitor}. Sent one.",
        "They are considering consolidating onto {competitor} as part of a platform play.",
        "Mentioned an RFP is going out before renewal.",
        "Their team has been evaluating {competitor} for two months and did not tell us.",
    ],
    "disengagement": [
        "Third reschedule on the QBR. No new date proposed.",
        "No response in six weeks. Tried email and LinkedIn.",
        "They cancelled the check-in an hour before. No reason given.",
        "Have not been able to get anyone on a call since the summer.",
        "Sent the usage summary. No acknowledgement.",
        "{champion} stopped replying after the last pricing conversation.",
        "Meeting attendance has dropped to one junior person.",
        "They skipped the business review entirely this cycle.",
        "Four unanswered emails. Going to try their admin.",
        "Went quiet after the escalation. Not sure who owns us there now.",
    ],
    "technical_friction": [
        "Their {product_area} integration broke again during their data load.",
        "Data quality issues on their side keep surfacing as complaints about us.",
        "They do not have the internal engineering capacity to finish the integration.",
        "The {product_area} setup has never worked the way they expected.",
        "Their IT team is blocking the SSO change we need for rollout.",
        "Sync failures every week. Their admin is the one absorbing the pain.",
        "They want us to match a workflow that our product does not support.",
        "Migration off their legacy system stalled. We are stuck waiting.",
        "Configuration drifted and nobody on their side owns it now.",
        "{product_area} is slow at their data volume and they have said so repeatedly.",
    ],
}

NEUTRAL_TEMPLATES = {
    "routine_checkin": [
        "Monthly check-in. Nothing new to report.",
        "Quick sync with {champion}. Business as usual.",
        "Touched base. They are heads down on their own roadmap right now.",
        "Short call. Reviewed open items, nothing escalated.",
        "Standing check-in held. Team is steady.",
        "Brief call with the admin. No issues raised.",
    ],
    "training_delivered": [
        "Ran a refresher session on {product_area} for {n} of their people.",
        "Delivered onboarding for the new hires on their team.",
        "Walked their analysts through {product_area}. Good engagement.",
        "Office hours session. {n} attendees, mostly questions about reporting.",
        "Sent over the enablement material they asked for.",
    ],
    "positive_qbr": [
        "QBR went well. They presented our numbers to their leadership.",
        "Business review complete. {champion} called out time savings on their team.",
        "Strong QBR. They want to talk about expanding to a second department.",
        "Reviewed the year. They are happy with where adoption landed.",
        "Good session. Their exec attended and was engaged.",
    ],
    "expansion_interest": [
        "They asked what it would take to add {n} more seats.",
        "Interest in {product_area} for a team that is not on the contract yet.",
        "Talked through a multi-year option. They want pricing.",
        "Their second division reached out directly about getting access.",
        "Asked about the higher tier. Sending over details.",
    ],
    "exec_alignment": [
        "Their CIO joined the call and reiterated this is a strategic system for them.",
        "{champion} was promoted and now owns a larger scope. Good for us.",
        "They included us in their annual planning conversation.",
        "Exec sponsor confirmed budget is protected for next year.",
        "New leadership reviewed the stack and kept us. Told me directly.",
    ],
    "resolved_issue": [
        "The {product_area} issue is resolved. Confirmed with their admin.",
        "Fix shipped. They tested it and closed the ticket themselves.",
        "Escalation closed out. They appreciated the follow-through.",
        "We got the integration working. Their team is back to normal.",
        "Root cause shared with them. They were satisfied with the explanation.",
    ],
}

CRM_CHURN_REASONS = [
    "Price", "Competitor", "Budget cut", "Other", "Lack of adoption",
    "Merger/Acquisition", "", "", "Other", "Price",
]


def fill(template, ctx):
    return template.format(
        champion=ctx["champion"],
        competitor=random.choice(COMPETITORS),
        product_area=random.choice(PRODUCT_AREAS),
        n=random.randint(2, 14),
    )


# --------------------------------------------------------------------------
# Account and note generation
# --------------------------------------------------------------------------

SEGMENTS = [
    ("Enterprise", 0.20, (80_000, 400_000), (60, 900)),
    ("Mid-Market", 0.45, (20_000, 80_000), (20, 200)),
    ("SMB", 0.35, (3_000, 20_000), (3, 40)),
]


def pick_segment():
    r = random.random()
    cum = 0.0
    for name, weight, arr_range, seat_range in SEGMENTS:
        cum += weight
        if r <= cum:
            return name, arr_range, seat_range
    return SEGMENTS[-1][0], SEGMENTS[-1][2], SEGMENTS[-1][3]


def build_accounts():
    accounts = []
    used_names = set()

    for i in range(N_ACCOUNTS):
        name = company()
        while name in used_names:
            name = company()
        used_names.add(name)

        segment, arr_range, seat_range = pick_segment()
        tenure = random.randint(4, 48)
        start = TODAY - timedelta(days=tenure * 30)
        arr = round(random.uniform(*arr_range), -2)
        seats = random.randint(*seat_range)

        # Churn rate varies by segment, the way it does in practice.
        base_churn = {"Enterprise": 0.12, "Mid-Market": 0.22, "SMB": 0.34}[segment]
        churned = random.random() < base_churn and tenure >= 8

        if churned:
            churn_date = TODAY - timedelta(days=random.randint(20, 420))
            if churn_date <= start + timedelta(days=120):
                churn_date = start + timedelta(days=150)
            status = "churned"
            renewal = churn_date
            crm_reason = random.choice(CRM_CHURN_REASONS)
        else:
            churn_date = None
            status = "active"
            months_to_renewal = random.randint(1, 12)
            renewal = TODAY + timedelta(days=months_to_renewal * 30)
            crm_reason = ""

        # Health score is deliberately poorly calibrated.
        if churned:
            health = random.randint(58, 92) if random.random() < 0.40 else random.randint(22, 64)
        else:
            health = random.randint(45, 98)

        active_seats = max(1, int(seats * random.uniform(0.15, 1.0)))

        accounts.append({
            "account_id": f"ACC-{1000 + i}",
            "account_name": name,
            "segment": segment,
            "industry": random.choice(INDUSTRIES),
            "arr": int(arr),
            "seats_licensed": seats,
            "seats_active": active_seats,
            "contract_start_date": start.isoformat(),
            "renewal_date": renewal.isoformat(),
            "tenure_months": tenure,
            "csm": random.choice(CSM_NAMES),
            "health_score": health,
            "status": status,
            "churn_date": churn_date.isoformat() if churn_date else "",
            "crm_churn_reason": crm_reason,
            "_champion": person(),
            "_churned": churned,
            "_start": start,
            "_end": churn_date or TODAY,
        })

    return accounts


def build_notes(accounts):
    notes = []
    ground_truth = []
    note_id = 1

    risk_names = list(RISK_TEMPLATES.keys())
    neutral_names = list(NEUTRAL_TEMPLATES.keys())

    for acct in accounts:
        ctx = {"champion": acct["_champion"]}
        start, end = acct["_start"], acct["_end"]
        churned = acct["_churned"]

        # Which themes this account exhibits, and how many notes carry each.
        if churned:
            themes = random.sample(risk_names, random.randint(2, 4))
        else:
            # Retained accounts still show risk. Some show a lot of it.
            n_themes = random.choices([0, 1, 2, 3], weights=[30, 35, 25, 10])[0]
            themes = random.sample(risk_names, n_themes)

        ground_truth.append({
            "account_id": acct["account_id"],
            "status": acct["status"],
            "injected_themes": "|".join(sorted(themes)),
        })

        # Notes roughly every two to four weeks.
        cursor = start + timedelta(days=random.randint(5, 20))
        window_days = (end - start).days
        danger_zone = end - timedelta(days=90)

        while cursor < end:
            in_danger_zone = cursor >= danger_zone

            # Risk themes concentrate near the end for churned accounts,
            # and are spread out and often resolved for retained ones.
            if themes:
                if churned:
                    p_risk = 0.72 if in_danger_zone else 0.18
                else:
                    p_risk = 0.30 if not in_danger_zone else 0.22
            else:
                p_risk = 0.0

            if random.random() < p_risk:
                theme = random.choice(themes)
                text = fill(random.choice(RISK_TEMPLATES[theme]), ctx)
            else:
                # Retained accounts with risk get resolution notes.
                if themes and not churned and random.random() < 0.25:
                    theme = "resolved_issue"
                else:
                    theme = random.choice(neutral_names)
                text = fill(random.choice(NEUTRAL_TEMPLATES[theme]), ctx)

            notes.append({
                "note_id": f"N-{note_id:05d}",
                "account_id": acct["account_id"],
                "note_date": cursor.isoformat(),
                "author": acct["csm"],
                "note_text": text,
            })
            note_id += 1
            cursor += timedelta(days=random.randint(12, 30))

    return notes, ground_truth


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    DATA.mkdir(exist_ok=True)

    accounts = build_accounts()
    notes, ground_truth = build_notes(accounts)

    account_fields = [
        "account_id", "account_name", "segment", "industry", "arr",
        "seats_licensed", "seats_active", "contract_start_date",
        "renewal_date", "tenure_months", "csm", "health_score", "status",
        "churn_date", "crm_churn_reason",
    ]

    write_csv(DATA / "accounts.csv", accounts, account_fields)
    write_csv(DATA / "notes.csv", notes, ["note_id", "account_id", "note_date", "author", "note_text"])
    write_csv(DATA / "ground_truth.csv", ground_truth, ["account_id", "status", "injected_themes"])

    churned = sum(1 for a in accounts if a["_churned"])
    healthy_churned = sum(1 for a in accounts if a["_churned"] and a["health_score"] >= 65)

    print(f"accounts:      {len(accounts)}")
    print(f"  churned:     {churned} ({churned / len(accounts):.0%})")
    print(f"  churned but scored healthy (>=65): {healthy_churned} ({healthy_churned / max(churned,1):.0%})")
    print(f"notes:         {len(notes)}")
    print(f"written to:    {DATA}")


if __name__ == "__main__":
    main()
