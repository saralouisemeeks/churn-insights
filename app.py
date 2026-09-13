"""churn-insights: read the notes your CRM never made you read."""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from analysis import (
    ARR_BANDS,
    HEALTH_BANDS,
    TENURE_BANDS,
    add_bands,
    churn_by,
    signal_strength,
)

# Categorical slots from the validated palette. Blue carries the primary
# measure, red is reserved for the churn/negative pole.
BLUE = "#2a78d6"
RED = "#e34948"
INK = "#52514e"

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="churn-insights", layout="wide")


@st.cache_data
def load_data():
    """Read the CRM export. Cached so the CSVs are parsed once per session."""
    accounts = pd.read_csv(
        DATA / "accounts.csv",
        parse_dates=["contract_start_date", "renewal_date", "churn_date"],
    )
    notes = pd.read_csv(DATA / "notes.csv", parse_dates=["note_date"])

    # Utilization is the one derived field worth computing up front.
    accounts["seat_utilization"] = (
        accounts["seats_active"] / accounts["seats_licensed"]
    ).round(2)
    accounts["note_count"] = accounts["account_id"].map(
        notes.groupby("account_id").size()
    ).fillna(0).astype(int)

    return accounts, notes


accounts, notes = load_data()

st.title("churn-insights")
st.caption("Read the notes your CRM never made you read.")

# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------

with st.sidebar:
    st.header("Filters")
    segments = st.multiselect(
        "Segment",
        sorted(accounts["segment"].unique()),
        default=sorted(accounts["segment"].unique()),
    )
    statuses = st.multiselect(
        "Status",
        sorted(accounts["status"].unique()),
        default=sorted(accounts["status"].unique()),
    )
    csms = st.multiselect("CSM", sorted(accounts["csm"].unique()), default=[])
    health_range = st.slider(
        "CRM health score",
        min_value=0,
        max_value=100,
        value=(0, 100),
        help=(
            "The CRM's own score. Set this to 65-100 with status 'churned' to "
            "isolate the accounts the CRM called healthy and lost anyway."
        ),
    )

# `base` deliberately ignores the status filter. A churn rate needs both
# churned and retained accounts in the denominator, so filtering to one status
# would make every rate on the analysis tab meaningless. `view` is base plus
# the status filter and drives the two account tabs.
base = accounts[
    accounts["segment"].isin(segments)
    & accounts["health_score"].between(health_range[0], health_range[1])
]
if csms:
    base = base[base["csm"].isin(csms)]

view = base[base["status"].isin(statuses)]

# --------------------------------------------------------------------------
# Headline numbers
# --------------------------------------------------------------------------

churned = view[view["status"] == "churned"]
active = view[view["status"] == "active"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Accounts", f"{len(view):,}")
col2.metric("Churned", f"{len(churned):,}")
col3.metric("Churned ARR", f"${churned['arr'].sum():,.0f}")
col4.metric("Active ARR", f"${active['arr'].sum():,.0f}")

# The calibration gap: churned accounts the CRM scored as healthy.
if len(churned):
    healthy_churned = churned[churned["health_score"] >= 65]
    pct = len(healthy_churned) / len(churned)
    st.warning(
        f"**{len(healthy_churned)} of {len(churned)} churned accounts ({pct:.0%}) "
        f"had a health score of 65 or above at the time they left**, representing "
        f"${healthy_churned['arr'].sum():,.0f} in ARR. The structured fields did not "
        f"see these coming."
    )

# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------

tab_accounts, tab_detail, tab_analysis = st.tabs(
    ["Accounts", "Account detail", "Churn analysis"]
)

with tab_accounts:
    st.dataframe(
        view[[
            "account_id", "account_name", "segment", "industry", "arr",
            "seats_licensed", "seats_active", "seat_utilization",
            "tenure_months", "csm", "health_score", "status",
            "crm_churn_reason", "note_count",
        ]].sort_values("arr", ascending=False),
        width="stretch",
        hide_index=True,
        column_config={
            "arr": st.column_config.NumberColumn("ARR", format="$%d"),
            "seat_utilization": st.column_config.ProgressColumn(
                "Seat util", min_value=0.0, max_value=1.0, format="%.0f%%"
            ),
            "health_score": st.column_config.ProgressColumn(
                "CRM health", min_value=0, max_value=100, format="%d"
            ),
        },
    )

with tab_detail:
    if view.empty:
        st.info("No accounts match the current filters.")
    else:
        labels = (
            view["account_name"] + "  (" + view["account_id"] + ")"
        ).sort_values().tolist()
        choice = st.selectbox("Account", labels)
        account_id = choice.split("(")[-1].rstrip(")")
        row = view[view["account_id"] == account_id].iloc[0]

        a, b, c, d = st.columns(4)
        a.metric("ARR", f"${row['arr']:,.0f}")
        b.metric("CRM health", int(row["health_score"]))
        c.metric("Seat util", f"{row['seat_utilization']:.0%}")
        d.metric("Status", row["status"].title())

        if row["status"] == "churned":
            reason = row["crm_churn_reason"] or "(blank)"
            st.error(f"Churned {row['churn_date'].date()}. CRM reason on file: **{reason}**")

        st.subheader(f"CSM notes ({row['note_count']})")
        st.caption(
            "This is the data no dashboard reads. Phase 3 puts an LLM through it."
        )

        account_notes = notes[notes["account_id"] == account_id].sort_values(
            "note_date", ascending=False
        )
        for _, note in account_notes.iterrows():
            st.markdown(f"**{note['note_date'].date()}** &nbsp; {note['note_text']}")
            st.divider()


# --------------------------------------------------------------------------
# Churn analysis
#
# This tab answers the question a CRM can already answer, so that Phase 3 can
# answer the one it cannot.
# --------------------------------------------------------------------------

def rate_bar(frame, dimension, title, order=None, overall=None):
    """A single-measure bar chart with direct labels.

    One measure, one axis. Logo churn and ARR churn are never combined on a
    single chart, because they move independently and a reader cannot tell
    which one a mixed chart is showing.
    """
    encoded = alt.Chart(frame).encode(
        x=alt.X(f"{dimension}:N", sort=order, title=None,
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y("churn_rate:Q", title="Churn rate",
                axis=alt.Axis(format="%"), scale=alt.Scale(domainMin=0)),
        tooltip=[
            alt.Tooltip(f"{dimension}:N", title=title),
            alt.Tooltip("accounts:Q", title="Accounts"),
            alt.Tooltip("churned:Q", title="Churned"),
            alt.Tooltip("churn_rate:Q", title="Churn rate", format=".1%"),
            alt.Tooltip("churned_arr:Q", title="Churned ARR", format="$,.0f"),
        ],
    )

    bars = encoded.mark_bar(
        color=BLUE, size=44, cornerRadiusTopLeft=4, cornerRadiusTopRight=4
    )
    labels = encoded.mark_text(dy=-9, color=INK, fontSize=12).encode(
        text=alt.Text("churn_rate:Q", format=".0%")
    )
    layers = [bars, labels]

    if overall is not None:
        line = alt.Chart(pd.DataFrame({"y": [overall]})).mark_rule(
            color=INK, strokeDash=[4, 4], strokeWidth=1
        ).encode(y="y:Q")
        layers.append(line)

    return alt.layer(*layers).properties(title=title, height=280)


with tab_analysis:
    if base.empty or base["status"].nunique() < 2:
        st.info(
            "The churn analysis needs both churned and retained accounts. "
            "Widen the segment, CSM, or health filters."
        )
    else:
        banded = add_bands(base)
        overall_rate = (banded["status"] == "churned").mean()

        st.caption(
            "This tab ignores the Status filter, because a churn rate needs "
            "both outcomes in the denominator. Segment, CSM, and health filters "
            "still apply."
        )

        left, right = st.columns(2)
        with left:
            st.altair_chart(
                rate_bar(
                    churn_by(banded, "segment",
                             order=["Enterprise", "Mid-Market", "SMB"]),
                    "segment", "Churn rate by segment",
                    order=["Enterprise", "Mid-Market", "SMB"],
                    overall=overall_rate,
                ),
                width="stretch",
            )
        with right:
            st.altair_chart(
                rate_bar(
                    churn_by(banded, "tenure_band",
                             order=[b[2] for b in TENURE_BANDS]),
                    "tenure_band", "Churn rate by tenure",
                    order=[b[2] for b in TENURE_BANDS],
                    overall=overall_rate,
                ),
                width="stretch",
            )

        st.subheader("Does the CRM health score work?")
        st.altair_chart(
            rate_bar(
                churn_by(banded, "health_band",
                         order=[b[2] for b in HEALTH_BANDS]),
                "health_band", "Churn rate by CRM health band",
                order=[b[2] for b in HEALTH_BANDS],
                overall=overall_rate,
            ),
            width="stretch",
        )
        st.caption(
            "A health score that worked would show a steep left-to-right "
            "decline. The dashed line is the overall churn rate."
        )

        # ------------------------------------------------------------------
        # The measurement that motivates Phase 3.
        # ------------------------------------------------------------------
        st.subheader("How well does any structured field predict churn?")

        signals = signal_strength(banded)
        best = signals.iloc[0]
        health_row = signals[
            signals["signal"].str.startswith("CRM health")
        ].iloc[0]

        a, b = st.columns(2)
        a.metric("CRM health score, AUC", f"{health_row['auc']:.2f}",
                 help="0.50 is a coin flip. 0.70 is useful. 0.80 is strong.")
        b.metric("Best structured signal, AUC", f"{best['auc']:.2f}",
                 help=best["signal"])

        st.dataframe(
            signals,
            width="stretch",
            hide_index=True,
            column_config={
                "signal": st.column_config.TextColumn("Signal"),
                "auc": st.column_config.NumberColumn("AUC", format="%.3f"),
                "reading": st.column_config.TextColumn("Reading"),
            },
        )

        st.markdown(
            f"""
**AUC** is the probability that a randomly chosen churned account scores
riskier than a randomly chosen retained one. 0.50 means the field carries no
information at all.

The strongest structured field here scores **{best['auc']:.2f}**. The health
score the CSM team actually looks at scores **{health_row['auc']:.2f}**.

Every one of these fields was available in the CRM the whole time. This is the
ceiling of what the structured data can tell you, and it is not high enough to
act on. The remaining signal is in the {len(notes):,} notes nobody reads.
"""
        )

        st.subheader("What the CRM recorded as the reason")
        churned_only = banded[banded["status"] == "churned"].copy()
        churned_only["crm_churn_reason"] = (
            churned_only["crm_churn_reason"].fillna("").replace("", "(blank)")
        )
        reasons = (
            churned_only.groupby("crm_churn_reason")
            .agg(accounts=("account_id", "count"), arr=("arr", "sum"))
            .reset_index()
            .sort_values("accounts", ascending=False)
        )

        reason_chart = alt.Chart(reasons).mark_bar(
            color=RED, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=24
        ).encode(
            y=alt.Y("crm_churn_reason:N", sort="-x", title=None),
            x=alt.X("accounts:Q", title="Churned accounts"),
            tooltip=[
                alt.Tooltip("crm_churn_reason:N", title="Reason on file"),
                alt.Tooltip("accounts:Q", title="Accounts"),
                alt.Tooltip("arr:Q", title="ARR", format="$,.0f"),
            ],
        ).properties(height=28 * len(reasons) + 40)

        st.altair_chart(reason_chart, width="stretch")
        st.caption(
            "Dropdown fields filled in at the end, by the person closing the "
            "record. They describe the paperwork, not the loss."
        )
