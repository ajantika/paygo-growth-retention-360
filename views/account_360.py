"""Account 360 — per-account drilldown with PPTX export."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.export import build_account_deck
from lib.theme import PALETTE, apply_plotly_theme, fmt_money, kpi_row, page_header


def render() -> None:
    page_header(
        "Account 360",
        "Pick an account to see its full lifecycle — products, MRR trajectory, events.",
    )

    accounts = dl.load_accounts()
    mrr = dl.load_mrr_monthly()
    subs = dl.load_subscriptions()
    churn = dl.load_churn()
    grads = dl.load_graduations()

    # Filter chips
    col1, col2, col3 = st.columns(3)
    seg_filter = col1.selectbox("Segment", options=["(all)", "PayGo", "Enterprise"])
    plan_filter = col2.selectbox("Plan type", options=["(all)", "Monthly", "Annual"])
    status_filter = col3.selectbox("Status", options=["(all)", "Active", "Churned"])

    filtered = accounts.copy()
    if seg_filter != "(all)":
        filtered = filtered[filtered["current_segment"] == seg_filter]
    if plan_filter != "(all)":
        filtered = filtered[filtered["plan_type"] == plan_filter]
    if status_filter == "Active":
        filtered = filtered[filtered["is_active"]]
    elif status_filter == "Churned":
        filtered = filtered[~filtered["is_active"]]

    if filtered.empty:
        st.warning("No accounts match those filters.")
        return

    # Default to the most interesting account: a graduated one if any in filter
    graduated_ids = filtered[filtered["graduation_month"].notna()]["account_id"].tolist()
    default_id = graduated_ids[0] if graduated_ids else filtered.iloc[0]["account_id"]

    account_id = st.selectbox(
        "Account",
        options=filtered["account_id"].tolist(),
        index=filtered["account_id"].tolist().index(default_id),
    )

    account_row = accounts[accounts["account_id"] == account_id].iloc[0]
    ctx = metrics.account_timeline(account_id, mrr, subs, churn, grads)

    tenure_months = len(ctx["mrr"])
    latest_mrr = float(ctx["mrr"]["mrr"].iloc[-1]) if not ctx["mrr"].empty else 0.0
    peak_mrr = float(ctx["mrr"]["mrr"].max()) if not ctx["mrr"].empty else 0.0
    n_products = int(ctx["products"]["product"].nunique()) if not ctx["products"].empty else 0
    status = "Active" if account_row["is_active"] else "Churned"

    kpi_row([
        ("Segment", str(account_row["current_segment"]), None),
        ("Tenure", f"{tenure_months} mo", None),
        ("Latest MRR", fmt_money(latest_mrr), None),
        ("Peak MRR", fmt_money(peak_mrr), None),
        ("Products", f"{n_products}", None),
        ("Status", status, None),
    ])

    st.divider()

    # MRR trajectory
    if not ctx["mrr"].empty:
        fig = px.area(
            ctx["mrr"], x="month", y="mrr",
            color_discrete_sequence=[PALETTE[0]],
            title=f"MRR trajectory — {account_id}",
        )
        # Annotate graduation / churn events (use add_shape + add_annotation
        # to avoid plotly's add_vline Timestamp-midpoint bug).
        def _vline(month_ts, label, color):
            x_iso = pd.Timestamp(month_ts).isoformat()
            fig.add_shape(type="line", xref="x", yref="paper",
                          x0=x_iso, x1=x_iso, y0=0, y1=1,
                          line=dict(color=color, dash="dash", width=2))
            fig.add_annotation(x=x_iso, y=1.0, xref="x", yref="paper",
                               text=label, showarrow=False,
                               font=dict(color=color, size=12),
                               bgcolor="rgba(255,255,255,0.85)")

        if not ctx["graduation"].empty:
            _vline(ctx["graduation"].iloc[0]["graduation_month"], "Graduated", PALETTE[1])
        if not ctx["churn"].empty:
            churn_reason = ctx["churn"].iloc[0]["churn_reason"]
            _vline(ctx["churn"].iloc[0]["churn_month"], f"Churned: {churn_reason}", "#DC2626")
        fig.update_layout(height=380, yaxis_title="MRR ($)", xaxis_title=None)
        apply_plotly_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

    # Product timeline
    if not ctx["products"].empty:
        st.markdown("**Product adoption timeline**")
        timeline = ctx["products"].copy()
        timeline["start_month"] = pd.to_datetime(timeline["start_month"]).dt.strftime("%b %Y")
        timeline["end_month"] = pd.to_datetime(timeline["end_month"]).dt.strftime("%b %Y").fillna("ongoing")
        st.dataframe(timeline[["product", "start_month", "end_month"]], use_container_width=True, hide_index=True)

    # PPTX export
    st.divider()
    deck_bytes = build_account_deck(account_id, ctx, account_row)
    st.download_button(
        label="Download account report (.pptx)",
        data=deck_bytes,
        file_name=f"account_{account_id}_report.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
