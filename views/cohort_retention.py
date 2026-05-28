"""Cohort retention — the App-Store-Connect-shaped view.

Signup-month cohorts × months-since-signup, colored by % of cohort still active.
Inspired by App Store Connect's Cohort Analysis layout: Total row at top,
Paid Starts column showing cohort size, then M1..M12 columns.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.theme import PLOTLY_CONFIG, apply_plotly_theme, fmt_pct, kpi_row, page_header

# Heatmap column window — App Store Connect shows M1..M12
MAX_MONTHS = 12


def render() -> None:
    page_header(
        "Cohort Retention",
        "How long do accounts stick around after they sign up? "
        "All percentages mean: **of the accounts that signed up in month X, what % are still paying us N months later?**",
    )

    accounts = dl.load_accounts()
    mrr = dl.load_mrr_monthly()

    cr = metrics.cohort_retention(mrr, accounts)
    if cr.empty:
        st.warning("Not enough data to build cohorts yet.")
        return

    # ---- Headline retention KPIs ----
    def cohort_retention_at(month_offset: int) -> float:
        sub = cr[cr["months_since_signup"] == month_offset]
        return float(sub["retained_pct"].mean()) if not sub.empty else 0.0

    m1 = cohort_retention_at(1)
    m3 = cohort_retention_at(3)
    m6 = cohort_retention_at(6)
    m12 = cohort_retention_at(12)

    kpi_row([
        ("Month 1 retention", fmt_pct(m1), None,
         "Of all signup cohorts that have lived ≥1 month, the average % of accounts still active 1 month after signup."),
        ("Month 3 retention", fmt_pct(m3), None,
         "Of all signup cohorts that have lived ≥3 months, the average % of accounts still active 3 months after signup."),
        ("Month 6 retention", fmt_pct(m6), None,
         "Of all signup cohorts that have lived ≥6 months, the average % of accounts still active 6 months after signup. "
         "Typically the most diagnostic — onboarding effects are gone."),
        ("Month 12 retention", fmt_pct(m12), None,
         "Of all signup cohorts that have lived ≥12 months, the average % of accounts still active 12 months after signup."),
    ])
    st.caption(
        "Each KPI is the **average across cohorts** that have reached that age. "
        "Heatmap below shows cohort-by-cohort detail with each cohort's paid-start count."
    )

    st.divider()

    # ---- Heatmap (App Store Connect style: Total row + Paid Starts column) ----

    # Pivot to cohort × months_since_signup
    cap = cr[cr["months_since_signup"].between(1, MAX_MONTHS)].copy()
    pivot = (
        cap.pivot(index="cohort_month", columns="months_since_signup", values="retained_pct")
        .sort_index()
    )
    pivot = pivot.reindex(columns=range(1, MAX_MONTHS + 1))

    # Cohort sizes (Paid Starts)
    cohort_sizes = (
        cr.groupby("cohort_month")["cohort_size"].first().reindex(pivot.index)
    )

    # Build the 'Total' row = simple mean of each column (across cohorts that reached that age)
    total_row = pivot.mean(axis=0, skipna=True)
    total_size = int(cohort_sizes.sum())

    # Compose the display matrix with Total row pinned to top
    display = pd.concat([pd.DataFrame([total_row], index=["Total"]), pivot.copy()])
    sizes = pd.concat([pd.Series([total_size], index=["Total"]), cohort_sizes])
    # Format cohort labels
    display.index = ["Total"] + [pd.Timestamp(c).strftime("%b %Y") for c in pivot.index]
    sizes.index = display.index

    # Round to whole percentages for both the cell text and the hover
    z = display.values.astype(float)
    z_rounded = np.where(np.isnan(z), np.nan, np.round(z))
    text = [
        [f"{int(v)}%" if not np.isnan(v) else "" for v in row]
        for row in z_rounded
    ]

    # Hover customdata: signup-cohort label + paid-starts size + integer retention
    customdata = []
    for cohort_label, size in zip(display.index, sizes.values):
        customdata.append([[cohort_label, int(size)]] * display.shape[1])
    customdata = np.array(customdata, dtype=object)

    fig = go.Figure(go.Heatmap(
        z=z_rounded,
        x=[f"M{i}" for i in display.columns],
        y=display.index,
        colorscale="Purples",
        zmin=0, zmax=100,
        text=text,
        texttemplate="%{text}",
        textfont={"color": "white", "size": 12},
        customdata=customdata,
        hovertemplate=(
            "Cohort: %{customdata[0]}<br>"
            "Paid Starts: %{customdata[1]:,}<br>"
            "Month: %{x}<br>"
            "% still active: %{z:.0f}%<extra></extra>"
        ),
        colorbar=dict(title="% still<br>active"),
    ))

    # Two side-by-side visuals: the heatmap, plus a Paid Starts column on the left
    fig.update_layout(
        title="Cohort retention — Total row + paid-start sizes (App Store Connect style)",
        height=620,
        xaxis=dict(side="top", title="Months since signup"),
        yaxis=dict(autorange="reversed", title="Signup cohort"),
    )
    apply_plotly_theme(fig)

    # Side-by-side: paid-starts table on the left, heatmap on the right
    col_left, col_right = st.columns([1, 5])
    with col_left:
        starts_df = pd.DataFrame({
            "Cohort": display.index,
            "Paid Starts": [f"{int(s):,}" for s in sizes.values],
        })
        st.markdown(" ")  # vertical alignment with heatmap title
        st.dataframe(
            starts_df, use_container_width=True, hide_index=True, height=600,
        )
    with col_right:
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    st.caption(
        "**Total row** = simple mean of each column across all cohorts that have reached that age. "
        "**Paid Starts** = how many paying accounts the cohort had in its first month. "
        "Read down the diagonal: each row is one cohort aging left to right."
    )

    st.divider()

    # ---- Retention curve overlay: one line per cohort ----
    st.markdown("**Cohort survival curves**")
    curve_df = cap.copy()
    curve_df["cohort_label"] = pd.to_datetime(curve_df["cohort_month"]).dt.strftime("%b %Y")
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
    fig2.update_traces(
        hovertemplate="Cohort: %{fullData.name}<br>Month: M%{x}<br>% retained: %{y:.0f}%<extra></extra>"
    )
    fig2.update_layout(
        height=400,
        yaxis_title="% of cohort retained",
        xaxis_title="Months since signup",
        legend_title="Cohort",
    )
    apply_plotly_theme(fig2)
    st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)
