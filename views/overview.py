"""Overview — KPI cockpit + headline charts + exec deck export."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.export import build_exec_summary_deck
from lib.theme import PALETTE, fmt_money, fmt_pct, kpi_row, page_header


def render() -> None:
    page_header(
        "PayGo Growth & Retention 360",
        "Self-serve partner reporting — revenue lifecycle, retention, and graduation in one place.",
    )

    accounts = dl.load_accounts()
    mrr = dl.load_mrr_monthly()
    grads = dl.load_graduations()

    kpis = metrics.current_kpis(mrr, accounts, grads)

    kpi_row([
        ("Current MRR", fmt_money(kpis["current_mrr"]), None),
        ("Active accounts", f"{kpis['active_accounts']:,}", None),
        ("NRR", fmt_pct(kpis["nrr"]), None),
        ("GRR", fmt_pct(kpis["grr"]), None),
        ("Graduated to Enterprise", f"{kpis['graduation_rate']:.1f}%", f"{kpis['graduations']} accts"),
        ("Median time-to-upgrade", f"{int(kpis['median_time_to_upgrade_days'])} days", None),
    ])

    st.divider()

    # MRR over time, segmented
    seg = (
        mrr.groupby(["month", "segment"], as_index=False)["mrr"].sum().sort_values("month")
    )
    fig = px.area(
        seg, x="month", y="mrr", color="segment",
        color_discrete_sequence=PALETTE,
        title="MRR over time, by segment",
    )
    fig.update_layout(yaxis_title="MRR ($)", xaxis_title=None, legend_title=None, height=380)
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        region_latest = mrr[mrr["month"] == mrr["month"].max()].groupby("region", as_index=False)["mrr"].sum()
        fig2 = px.bar(
            region_latest.sort_values("mrr", ascending=False), x="region", y="mrr",
            color_discrete_sequence=[PALETTE[0]],
            title="MRR by region (latest month)",
        )
        fig2.update_layout(yaxis_title="MRR ($)", xaxis_title=None, height=330)
        st.plotly_chart(fig2, use_container_width=True)
    with col2:
        plan_mix = accounts.groupby("plan_type").size().reset_index(name="accounts")
        fig3 = px.pie(plan_mix, names="plan_type", values="accounts",
                      color_discrete_sequence=PALETTE, title="Plan mix (all accounts)")
        fig3.update_layout(height=330)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # Exec summary deck export
    st.markdown("**Executive summary export**")
    trend = mrr.groupby("month", as_index=False)["mrr"].sum().sort_values("month")
    deck_bytes = build_exec_summary_deck(kpis, trend)
    st.download_button(
        label="Download executive summary (.pptx)",
        data=deck_bytes,
        file_name="paygo_exec_summary.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
