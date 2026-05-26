"""Churn diagnostics — reasons, plan mix, and the headline annual-vs-monthly insight."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.theme import COLOR_NEG, COLOR_NEUTRAL, COLOR_POS, PALETTE, apply_plotly_theme, fmt_money, fmt_pct, page_header


def render() -> None:
    page_header(
        "Churn Diagnostics",
        "Why accounts leave, and which segments leave most.",
    )

    accounts = dl.load_accounts()
    churn = dl.load_churn()
    summary = metrics.churn_summary(churn, accounts)

    plan_df = summary["by_plan"]
    reason_df = summary["by_reason"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Logo churn rate (all-time)", fmt_pct(summary["logo_churn_rate"]))
    if not plan_df.empty:
        monthly_rate = plan_df.set_index("plan_type").loc["Monthly", "churn_rate_pct"] if "Monthly" in plan_df["plan_type"].values else 0
        annual_rate = plan_df.set_index("plan_type").loc["Annual", "churn_rate_pct"] if "Annual" in plan_df["plan_type"].values else 0
        col2.metric("Monthly plan churn", f"{monthly_rate:.2f}%")
        col3.metric("Annual plan churn", f"{annual_rate:.2f}%")

    st.info(
        f"**Headline insight.** Annual plans churn at **{annual_rate:.2f}%** versus **{monthly_rate:.2f}%** for monthly — "
        "a ~{:.2f}x retention advantage. Shifting plan mix is one of the highest-leverage retention levers.".format(
            (monthly_rate / annual_rate) if annual_rate else 0
        )
    )

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(reason_df.sort_values("churned_accounts"),
                     x="churned_accounts", y="churn_reason",
                     orientation="h",
                     color_discrete_sequence=[COLOR_NEG],
                     title="Churn reasons (account count)")
        fig.update_layout(height=380, yaxis_title=None, xaxis_title="Churned accounts")
        apply_plotly_theme(fig)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        rdf = reason_df.copy()
        rdf["churned_mrr"] = rdf["churned_mrr"].round(0)
        fig2 = px.bar(rdf.sort_values("churned_mrr"),
                      x="churned_mrr", y="churn_reason",
                      orientation="h",
                      color_discrete_sequence=[PALETTE[1]],
                      title="Lost MRR by churn reason ($)")
        fig2.update_layout(height=380, yaxis_title=None, xaxis_title="Last MRR ($)")
        apply_plotly_theme(fig2)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Churn over time
    if not churn.empty:
        ts = churn.groupby("churn_month").agg(
            accounts=("account_id", "count"),
            mrr=("last_mrr", "sum"),
        ).reset_index()
        fig3 = px.bar(ts, x="churn_month", y="accounts",
                      title="Churn events per month",
                      color_discrete_sequence=[COLOR_NEUTRAL])
        fig3.update_layout(height=320, yaxis_title="Churned accounts", xaxis_title=None)
        apply_plotly_theme(fig3)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.markdown("**Churn by segment at time of churn**")
    if not churn.empty:
        seg_split = churn.groupby("segment_at_churn").agg(
            accounts=("account_id", "count"),
            lost_mrr=("last_mrr", "sum"),
        ).reset_index()
        seg_split["lost_mrr"] = seg_split["lost_mrr"].apply(fmt_money)
        st.dataframe(seg_split, use_container_width=True, hide_index=True)
