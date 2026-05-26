"""PayGo -> Enterprise — graduation funnel and time-to-upgrade."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data as dl
from lib.theme import PALETTE, apply_plotly_theme, fmt_money, kpi_row, page_header


def render() -> None:
    page_header(
        "PayGo → Enterprise",
        "Which accounts graduate, how long it takes, and how big the jump is.",
    )

    accounts = dl.load_accounts()
    grads = dl.load_graduations()

    total = len(accounts)
    graduated = len(grads)
    churned_before_grad = int(
        accounts.assign(grad=accounts["graduation_month"].notna(),
                        churn=accounts["churn_month"].notna())
        .query("not grad and churn")["account_id"].count()
    )
    still_paygo = total - graduated - churned_before_grad
    grad_rate = graduated / total * 100.0 if total else 0.0

    median_ttu = float(grads["time_to_upgrade_days"].median()) if not grads.empty else 0.0
    avg_jump = (
        float((grads["enterprise_mrr_after"] / grads["paygo_mrr_at_graduation"]).median())
        if not grads.empty else 0.0
    )

    kpi_row([
        ("Total PayGo signups", f"{total:,}", None),
        ("Graduated to Enterprise", f"{graduated:,}", f"{grad_rate:.2f}%"),
        ("Churned before graduating", f"{churned_before_grad:,}", None),
        ("Median time-to-upgrade", f"{int(median_ttu)} days", None),
        ("Median MRR jump", f"{avg_jump:.2f}x", None),
    ])

    st.divider()

    # Funnel
    funnel_df = pd.DataFrame({
        "stage": ["PayGo signups", "Still active or graduated", "Graduated to Enterprise"],
        "accounts": [total, total - churned_before_grad, graduated],
    })
    fig = px.funnel(funnel_df, x="accounts", y="stage",
                    color_discrete_sequence=[PALETTE[0]])
    fig.update_layout(title="Graduation funnel", height=320)
    apply_plotly_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    if not grads.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig2 = px.histogram(grads, x="time_to_upgrade_days", nbins=20,
                                title="Time-to-upgrade distribution (days)",
                                color_discrete_sequence=[PALETTE[1]])
            fig2.update_layout(height=320, yaxis_title="Graduated accounts")
            apply_plotly_theme(fig2)
            st.plotly_chart(fig2, use_container_width=True)
        with col2:
            grads_disp = grads.assign(
                jump=grads["enterprise_mrr_after"] / grads["paygo_mrr_at_graduation"]
            )
            fig3 = px.scatter(
                grads_disp, x="time_to_upgrade_days", y="enterprise_mrr_after",
                size="jump", color="jump",
                color_continuous_scale="Purples",
                title="Time-to-upgrade vs. Enterprise MRR (size = MRR jump)",
            )
            fig3.update_layout(height=320, yaxis_title="Enterprise MRR ($)",
                               xaxis_title="Days to upgrade")
            apply_plotly_theme(fig3)
            st.plotly_chart(fig3, use_container_width=True)

        st.divider()
        st.markdown("**Recent graduations**")
        recent = grads.sort_values("graduation_month", ascending=False).head(15).copy()
        recent["paygo_mrr_at_graduation"] = recent["paygo_mrr_at_graduation"].apply(fmt_money)
        recent["enterprise_mrr_after"] = recent["enterprise_mrr_after"].apply(fmt_money)
        recent["graduation_month"] = pd.to_datetime(recent["graduation_month"]).dt.strftime("%b %Y")
        recent["first_paygo_month"] = pd.to_datetime(recent["first_paygo_month"]).dt.strftime("%b %Y")
        st.dataframe(recent[[
            "account_id", "first_paygo_month", "graduation_month",
            "time_to_upgrade_days", "paygo_mrr_at_graduation", "enterprise_mrr_after",
        ]], use_container_width=True, hide_index=True)
