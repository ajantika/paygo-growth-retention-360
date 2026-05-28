"""Overview — KPI cockpit + headline charts + exec deck export."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.export import build_exec_summary_deck
from lib.theme import (
    PALETTE, apply_plotly_theme, fmt_money, fmt_pct, kpi_row, page_header, PLOTLY_CONFIG,
)


def render() -> None:
    page_header(
        "PayGo Growth & Retention 360",
        "Self-serve partner reporting — monthly proceeds, retention, and tier conversion in one place.",
    )

    accounts = dl.load_accounts()
    mrr = dl.load_mrr_monthly()
    grads = dl.load_graduations()

    kpis = metrics.current_kpis(mrr, accounts, grads)

    kpi_row([
        ("Monthly Proceeds", fmt_money(kpis["current_mrr"]), None,
         "Monthly recurring revenue (MRR) — total recurring revenue across all active accounts "
         "in the latest month. Sum of plan_mrr + usage_mrr."),
        ("ARPA", fmt_money(kpis["arpa"]), None,
         "Average Revenue Per Account = Total MRR ÷ Active accounts. "
         "Shows how much value each customer brings on average."),
        ("Active accounts", f"{kpis['active_accounts']:,}", None,
         "Accounts with MRR > 0 in the latest month. Single canonical definition used everywhere in this app."),
        ("NRR", fmt_pct(kpis["nrr"]), None,
         "Net Revenue Retention. Of accounts active 12 months ago, what % of revenue is still here today — "
         "INCLUDING organic expansion but EXCLUDING tier-conversion jumps. >100% = the existing base is growing on its own."),
        ("GRR", fmt_pct(kpis["grr"]), None,
         "Gross Revenue Retention. Same cohort as NRR, but no expansion credit — pure 'how much did we keep?'. "
         "Always ≤ NRR. Healthy SaaS: 85-95%."),
        ("Tier conversion rate", fmt_pct(kpis["graduation_rate"]), None,
         "% of active accounts that have converted from PayGo to Enterprise. "
         "Apple equivalent: indie developer → studio relationship."),
    ])
    st.caption(
        f"{kpis['active_enterprise_accounts']} accounts on Enterprise · "
        f"Median time-to-upgrade: {int(kpis['median_time_to_upgrade_days'])} days · "
        f"NRR is tier-conversion-adjusted (organic expansion only)."
    )

    st.divider()

    # ---- MRR over time, split into plan vs usage ----
    seg = mrr.groupby("month", as_index=False).agg(
        plan_mrr=("plan_mrr", "sum"),
        usage_mrr=("usage_mrr", "sum"),
    )
    fig = go.Figure()
    fig.add_traces([
        go.Scatter(
            x=seg["month"], y=seg["plan_mrr"], stackgroup="one", name="Plan (subscription)",
            line=dict(color=PALETTE[0], width=0),
            fillcolor="rgba(167,139,250,0.55)",
        ),
        go.Scatter(
            x=seg["month"], y=seg["usage_mrr"], stackgroup="one", name="Usage (consumption)",
            line=dict(color=PALETTE[1], width=0),
            fillcolor="rgba(96,165,250,0.55)",
        ),
    ])
    fig.update_layout(
        title="Monthly Proceeds over time — plan vs usage",
        yaxis_title="MRR ($)", xaxis_title=None, legend_title=None, height=380,
    )
    apply_plotly_theme(fig)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ---- Plan mix and retention ----
    st.markdown("#### Plan mix and retention")
    cs = metrics.churn_summary(dl.load_churn(), accounts)
    plan = cs["by_plan"].copy()
    plan["retained"] = plan["total"] - plan["churned"]

    col1, col2 = st.columns([3, 2])
    with col1:
        fig2 = go.Figure()
        fig2.add_bar(
            name="Retained", x=plan["plan_type"], y=plan["retained"],
            marker_color="#34D399", text=plan["retained"], textposition="inside",
        )
        fig2.add_bar(
            name="Churned", x=plan["plan_type"], y=plan["churned"],
            marker_color="#EF4444", text=plan["churned"], textposition="inside",
        )
        fig2.update_layout(
            barmode="stack",
            title="Accounts by plan — retained vs churned",
            yaxis_title="Accounts", xaxis_title=None, height=360,
        )
        apply_plotly_theme(fig2)
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)
    with col2:
        st.markdown("")
        st.markdown("")
        for _, row in plan.iterrows():
            churn_pct = row["churn_rate_pct"]
            color = "#EF4444" if churn_pct > 20 else "#34D399"
            st.markdown(
                f"<div style='padding:12px 14px;margin-bottom:10px;border-radius:8px;"
                f"background:rgba(148,163,184,0.08);border:1px solid rgba(148,163,184,0.25);'>"
                f"<div style='font-size:12px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.05em;'>"
                f"{row['plan_type']}</div>"
                f"<div style='font-size:22px;font-weight:600;margin-top:4px;color:{color};'>{churn_pct:.0f}% churn</div>"
                f"<div style='font-size:13px;color:#CBD5E1;margin-top:2px;'>"
                f"{int(row['churned'])} churned of {int(row['total'])} total</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.caption("Annual plans retain ~4× better than monthly — a key insight for partner pricing strategy.")

    st.divider()

    # ---- Exec summary deck export ----
    st.markdown("**Executive summary export**")
    trend = mrr.groupby("month", as_index=False)["mrr"].sum().sort_values("month")
    deck_bytes = build_exec_summary_deck(kpis, trend)
    st.download_button(
        label="Download executive summary (.pptx)",
        data=deck_bytes,
        file_name="paygo_exec_summary.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
