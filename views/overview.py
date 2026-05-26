"""Overview — KPI cockpit + headline charts + exec deck export."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.export import build_exec_summary_deck
from lib.theme import PALETTE, apply_plotly_theme, fmt_money, fmt_pct, kpi_row, page_header


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
        ("Graduated to Enterprise", fmt_pct(kpis["graduation_rate"]), f"{kpis['graduations']} accts"),
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
    apply_plotly_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    # Plan mix — show the headline insight: monthly churns much more than annual
    st.markdown("#### Plan mix and retention")
    cs = metrics.churn_summary(dl.load_churn(), accounts)
    plan = cs["by_plan"].copy()
    plan["retained"] = plan["total"] - plan["churned"]

    col1, col2 = st.columns([3, 2])
    with col1:
        # Stacked bar — total accounts split by retained vs churned, side by side for each plan
        fig2 = go.Figure()
        fig2.add_bar(
            name="Retained",
            x=plan["plan_type"],
            y=plan["retained"],
            marker_color=PALETTE[2],
            text=plan["retained"],
            textposition="inside",
        )
        fig2.add_bar(
            name="Churned",
            x=plan["plan_type"],
            y=plan["churned"],
            marker_color=PALETTE[4],
            text=plan["churned"],
            textposition="inside",
        )
        fig2.update_layout(
            barmode="stack",
            title="Accounts by plan — retained vs churned",
            yaxis_title="Accounts",
            xaxis_title=None,
            height=360,
        )
        apply_plotly_theme(fig2)
        st.plotly_chart(fig2, use_container_width=True)
    with col2:
        st.markdown("")
        st.markdown("")
        for _, row in plan.iterrows():
            churn_pct = row["churn_rate_pct"]
            color = "#F87171" if churn_pct > 20 else "#34D399"
            st.markdown(
                f"<div style='padding:12px 14px;margin-bottom:10px;border-radius:8px;"
                f"background:rgba(148,163,184,0.08);border:1px solid rgba(148,163,184,0.25);'>"
                f"<div style='font-size:12px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.05em;'>"
                f"{row['plan_type']}</div>"
                f"<div style='font-size:22px;font-weight:600;margin-top:4px;color:{color};'>{churn_pct:.2f}% churn</div>"
                f"<div style='font-size:13px;color:#CBD5E1;margin-top:2px;'>"
                f"{int(row['churned'])} churned of {int(row['total'])} total</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.caption("Annual plans retain ~4× better than monthly — a key insight for partner pricing strategy.")

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
