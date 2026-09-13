"""churn-insights: read the notes your CRM never made you read."""

from pathlib import Path

import pandas as pd
import streamlit as st

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

view = accounts[
    accounts["segment"].isin(segments)
    & accounts["status"].isin(statuses)
    & accounts["health_score"].between(health_range[0], health_range[1])
]
if csms:
    view = view[view["csm"].isin(csms)]

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

tab_accounts, tab_detail = st.tabs(["Accounts", "Account detail"])

with tab_accounts:
    st.dataframe(
        view[[
            "account_id", "account_name", "segment", "industry", "arr",
            "seats_licensed", "seats_active", "seat_utilization",
            "tenure_months", "csm", "health_score", "status",
            "crm_churn_reason", "note_count",
        ]].sort_values("arr", ascending=False),
        use_container_width=True,
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
