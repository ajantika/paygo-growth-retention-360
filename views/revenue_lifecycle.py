"""Revenue Lifecycle — MRR bridge waterfall, NRR/GRR trend, movement mix."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.theme import COLOR_NEG, COLOR_POS, PALETTE, apply_plotly_theme, fmt_money, page_header


def render() -> None:
    page_header(
        "Revenue Lifecycle",
        "The MRR bridge — every dollar accounted for, every month.",
    )

    mrr = dl.load_mrr_monthly()
    bridge = metrics.movement_bridge(mrr)
    summary = metrics.monthly_bridge_summary(bridge)

    months = summary["month"].tolist()
    sel_month = st.select_slider(
        "Show bridge for month transition ending in",
        options=months[1:],  # need a prior month for transition
        value=months[-1],
        format_func=lambda m: pd.Timestamp(m).strftime("%b %Y"),
    )
    row = summary[summary["month"] == sel_month].iloc[0]

    # Waterfall
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "relative", "relative", "total"],
        x=["Starting MRR", "New", "Expansion", "Reactivation", "Contraction", "Churn", "Ending MRR"],
        y=[
            row["starting_mrr"],
            row["new"],
            row["expansion"],
            row["reactivation"],
            -row["contraction"],
            -row["churn"],
            row["ending_mrr"],
        ],
        text=[
            fmt_money(row["starting_mrr"]),
            f"+{fmt_money(row['new'])}",
            f"+{fmt_money(row['expansion'])}",
            f"+{fmt_money(row['reactivation'])}",
            f"-{fmt_money(row['contraction'])}",
            f"-{fmt_money(row['churn'])}",
            fmt_money(row["ending_mrr"]),
        ],
        textposition="outside",
        increasing={"marker": {"color": COLOR_POS}},
        decreasing={"marker": {"color": COLOR_NEG}},
        totals={"marker": {"color": PALETTE[1]}},
    ))
    fig.update_layout(
        title=f"MRR bridge — month ending {pd.Timestamp(sel_month).strftime('%b %Y')}",
        height=420,
        yaxis_title="MRR ($)",
        showlegend=False,
    )
    apply_plotly_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    bridge_err = float(row["bridge_check"])
    st.caption(
        f"Bridge identity check: start + new + expansion + reactivation - contraction - churn - ending = {bridge_err:.6f}  "
        "(should be ~0; proves the canonical metric layer ties out across views)."
    )

    st.divider()

    # Trend of net new MRR over time
    trend = summary[["month", "net_new_mrr", "ending_mrr"]].copy()
    col1, col2 = st.columns(2)
    with col1:
        fig2 = px.bar(trend, x="month", y="net_new_mrr",
                      title="Net new MRR per month",
                      color_discrete_sequence=[PALETTE[0]])
        fig2.update_layout(yaxis_title="Net new MRR ($)", xaxis_title=None, height=320)
        apply_plotly_theme(fig2)
        st.plotly_chart(fig2, use_container_width=True)
    with col2:
        fig3 = px.line(trend, x="month", y="ending_mrr",
                       title="Ending MRR trend",
                       color_discrete_sequence=[PALETTE[1]])
        fig3.update_layout(yaxis_title="MRR ($)", xaxis_title=None, height=320)
        apply_plotly_theme(fig3)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.markdown("**Movement classification — accounts per month**")
    mvmt = bridge[bridge["movement"] != "inactive"].groupby(
        ["month", "movement"]
    ).size().reset_index(name="accounts")
    fig4 = px.area(mvmt, x="month", y="accounts", color="movement",
                   color_discrete_sequence=PALETTE,
                   title="Account movement mix over time")
    fig4.update_layout(height=360, xaxis_title=None, legend_title=None)
    apply_plotly_theme(fig4)
    st.plotly_chart(fig4, use_container_width=True)
