"""Structured churn analysis.

Pure functions over the CRM export. No Streamlit in here on purpose: the UI
should be replaceable without touching the analysis, and functions that take a
DataFrame and return a DataFrame are the ones you can actually test.

The closing function, signal_strength, is the point of this module. It measures
how well each structured field predicts churn. The answer is "poorly," which is
the argument for reading the notes.
"""

import numpy as np
import pandas as pd

TENURE_BANDS = [(0, 12, "0-12 mo"), (13, 24, "13-24 mo"),
                (25, 36, "25-36 mo"), (37, 999, "37+ mo")]

ARR_BANDS = [(0, 10_000, "<$10K"), (10_000, 50_000, "$10-50K"),
             (50_000, 100_000, "$50-100K"), (100_000, 10**9, "$100K+")]

HEALTH_BANDS = [(0, 39, "0-39"), (40, 54, "40-54"), (55, 64, "55-64"),
                (65, 79, "65-79"), (80, 100, "80-100")]


def _band(value, bands):
    for low, high, label in bands:
        if low <= value <= high:
            return label
    return bands[-1][2]


def add_bands(accounts):
    """Attach the banded columns the charts group by."""
    out = accounts.copy()
    out["tenure_band"] = out["tenure_months"].apply(lambda v: _band(v, TENURE_BANDS))
    out["arr_band"] = out["arr"].apply(lambda v: _band(v, ARR_BANDS))
    out["health_band"] = out["health_score"].apply(lambda v: _band(v, HEALTH_BANDS))
    return out


def churn_by(accounts, column, order=None):
    """Churn rate and churned ARR grouped by one column.

    Logo churn and ARR churn are reported separately and never plotted on the
    same axis. They are different measures and combining them on one chart is
    the most common way a churn dashboard misleads its reader.
    """
    grouped = accounts.groupby(column, dropna=False).agg(
        accounts=("account_id", "count"),
        churned=("status", lambda s: (s == "churned").sum()),
        total_arr=("arr", "sum"),
    )
    churned_arr = (
        accounts[accounts["status"] == "churned"].groupby(column)["arr"].sum()
    )
    grouped["churned_arr"] = churned_arr.reindex(grouped.index).fillna(0)
    grouped["churn_rate"] = grouped["churned"] / grouped["accounts"]
    grouped["arr_churn_rate"] = grouped["churned_arr"] / grouped["total_arr"]
    grouped = grouped.reset_index()

    if order:
        grouped[column] = pd.Categorical(grouped[column], categories=order, ordered=True)
        grouped = grouped.sort_values(column)

    return grouped


def auc(scores, labels):
    """Area under the ROC curve, computed from ranks (Mann-Whitney U).

    Plain reading: the probability that a randomly chosen churned account is
    scored as riskier than a randomly chosen retained one.

        0.50  no better than a coin flip
        0.70  useful
        0.80  strong

    Computed from ranks rather than imported, so the project carries no
    modelling dependency for one formula.
    """
    frame = pd.DataFrame({"score": scores, "label": labels}).dropna()
    n_pos = int((frame["label"] == 1).sum())
    n_neg = int((frame["label"] == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")

    ranks = frame["score"].rank()
    rank_sum_pos = ranks[frame["label"] == 1].sum()
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def signal_strength(accounts):
    """How well does each structured field predict churn on its own?

    Every signal is oriented so that a higher value means higher predicted
    risk, which is what makes the AUCs comparable.
    """
    labels = (accounts["status"] == "churned").astype(int)

    # Note density rather than raw note count. Churned accounts have shorter
    # timelines by definition, so raw volume leaks the outcome rather than
    # measuring engagement.
    note_density = accounts["note_count"] / accounts["tenure_months"].clip(lower=1)

    signals = {
        "CRM health score (inverted)": -accounts["health_score"],
        "Seat utilization (inverted)": -accounts["seat_utilization"],
        "ARR (inverted, smaller = riskier)": -accounts["arr"],
        "Tenure (inverted, newer = riskier)": -accounts["tenure_months"],
        "Note density (inverted, quieter = riskier)": -note_density,
    }

    rows = [
        {"signal": name, "auc": auc(values, labels)}
        for name, values in signals.items()
    ]
    out = pd.DataFrame(rows).sort_values("auc", ascending=False).reset_index(drop=True)
    out["reading"] = np.select(
        [out["auc"] >= 0.80, out["auc"] >= 0.70, out["auc"] >= 0.60],
        ["Strong", "Useful", "Weak"],
        default="Near coin flip",
    )
    return out
