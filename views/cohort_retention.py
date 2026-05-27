"""Cohort retention — the App-Store-Connect-shaped view.

Signup-month cohorts × months-since-signup, colored by % of cohort still active.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.theme import PLOTLY_CONFIG, apply_plotly_theme, fmt_pct, kpi_row, page_header


def render() -> None:
    page_header(
        "Cohort Retention",
        "How long do accounts stick around? Signup-month cohorts × months-since-signup. "
        "The shape of this matrix is the truest signal of product-market fit.",
    )

    accounts = dl.load_accounts()
    mrr = dl.load_mrr_monthly()

    cr = metrics.cohort_retention(mrr, accounts)
    if cr.empty:
        st.warning("Not enough data to build cohorts yet.")
        return

    # ---- Headline retention KPIs ----
    # Average retention at months 1, 3, 6, 12 across cohorts that have reached that age
    def cohort_retention_at(month_offset: int) -> float:
        sub = cr[cr["months_since_signup"] == month_offset]
        return float(sub["retained_pct"].mean()) if not sub.empty else 0.0

    m1 = cohort_retention_at(1)
    m3 = cohort_retention_at(3)
    m6 = cohort_retention_at(6)
    m12 = cohort_retention_at(12)

    kpi_row([
        ("Month 1 retention", fmt_pct(m1), None),
        ("Month 3 retention", fmt_pct(m3), None),
        ("Month 6 retention", fmt_pct(m6), None),
        ("Month 12 retention", fmt_pct(m12), None),
    ])
    st.caption(
        "Each KPI is the mean across all cohorts that have reached that age. "
        "The heatmap below shows cohort-by-cohort detail."
    )

    st.divider()

    # ---- Heatmap ----
    # Limit to first ~24 months since signup for legibility
    cap = cr[cr["months_since_signup"] <= 24].copy()
    pivot = cap.pivot(
        index="cohort_month", columns="months_since_signup", values="retained_pct"
    ).sort_index()

    # Format cohort labels as 'Jan 2024' etc
    pivot.index = pd.to_datetime(pivot.index).strftime("%b %Y")

    fig = px.imshow(
        pivot.values,
        x=pivot.columns,
        y=pivot.index,
        labels=dict(x="Months since signup", y="Cohort", color="Retention %"),
        color_continuous_scale="Purples",
        zmin=0, zmax=100,
        aspect="auto",
        text_auto=".0f",
    )
    fig.update_layout(
        title="Cohort retention (% of signup-month cohort still active)",
        height=560,
        coloraxis_colorbar=dict(title="%"),
    )
    apply_plotly_theme(fig)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    st.caption(
        "Read down the diagonal: each row is one cohort aging from left to right. "
        "If retention falls off a cliff at the same month-offset across cohorts, you've found a structural drop-off worth investigating."
    )

    st.divider()

    # ---- Retention curve overlay: one line per cohort ----
    st.markdown("**Cohort survival curves**")
    curve_df = cap.copy()
    curve_df["cohort_label"] = pd.to_datetime(curve_df["cohort_month"]).dt.strftime("%b %Y")
    # Show only every Nth cohort to avoid clutter — first, last, and quartiles
    cohorts_all = sorted(curve_df["cohort_month"].unique())
    if len(cohorts_all) > 8:
        step = max(1, len(cohorts_all) // 6)
        shown = cohorts_all[::step] + [cohorts_all[-1]]
        shown = sorted(set(shown))
        curve_df = curve_df[curve_df["cohort_month"].isin(shown)]

    fig2 = px.line(
        curve_df,
        x="months_since_signup", y="retained_pct", color="cohort_label",
        title="Retention curves by cohort",
    )
    fig2.update_layout(
        height=400,
        yaxis_title="% of cohort retained",
        xaxis_title="Months since signup",
        legend_title="Cohort",
    )
    apply_plotly_theme(fig2)
    st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)
