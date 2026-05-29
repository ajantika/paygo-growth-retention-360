"""Account 360 — per-account drilldown with PPTX export."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.export import build_account_deck
from lib.theme import PALETTE, PLOTLY_CONFIG, apply_plotly_theme, fmt_money, kpi_row, page_header


def render() -> None:
    # Reserve a slot for the title at the very top — we'll fill it in
    # AFTER the account is selected so the header shows the actual ID.
    header_slot = st.container()

    accounts = dl.load_accounts()
    mrr = dl.load_mrr_monthly()
    subs = dl.load_subscriptions()
    churn = dl.load_churn()
    grads = dl.load_graduations()

    # Filter chips (now includes PayGo subtier — Free/Pro/Business)
    col1, col2, col3, col4 = st.columns(4)
    seg_filter = col1.selectbox("Segment", options=["(all)", "PayGo", "Enterprise"])
    subtier_filter = col2.selectbox("PayGo subtier", options=["(all)", "Free", "Pro", "Business"])
    plan_filter = col3.selectbox("Plan type", options=["(all)", "Monthly", "Annual"])
    status_filter = col4.selectbox("Status", options=["(all)", "Active", "Churned"])

    filtered = accounts.copy()
    if seg_filter != "(all)":
        filtered = filtered[filtered["current_segment"] == seg_filter]
    if subtier_filter != "(all)":
        filtered = filtered[filtered["paygo_subtier"] == subtier_filter]
    if plan_filter != "(all)":
        filtered = filtered[filtered["plan_type"] == plan_filter]
    if status_filter == "Active":
        filtered = filtered[filtered["is_active"]]
    elif status_filter == "Churned":
        filtered = filtered[~filtered["is_active"]]

    if filtered.empty:
        # Fill the reserved title slot even on the empty path so the page isn't headless
        with header_slot:
            page_header(
                "Account 360",
                "No accounts match those filters — relax one of them.",
            )
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

    # Now that we know which account is selected, fill the reserved title slot
    # so the page header reads "Account 360 — A01518" instead of just "Account 360".
    total_accounts = len(accounts)
    filtered_count = len(filtered)
    with header_slot:
        page_header(
            f"Account 360 — {account_id}",
            f"Showing 1 of {filtered_count:,} accounts matching the filters above "
            f"(out of {total_accounts:,} total). Full lifecycle below: products, MRR trajectory, events.",
        )

    account_row = accounts[accounts["account_id"] == account_id].iloc[0]
    ctx = metrics.account_timeline(account_id, mrr, subs, churn, grads)

    tenure_months = len(ctx["mrr"])
    latest_mrr = float(ctx["mrr"]["mrr"].iloc[-1]) if not ctx["mrr"].empty else 0.0
    peak_mrr = float(ctx["mrr"]["mrr"].max()) if not ctx["mrr"].empty else 0.0
    n_products = int(ctx["products"]["product"].nunique()) if not ctx["products"].empty else 0
    status = "Active" if account_row["is_active"] else "Churned"

    # Split into 2 rows so 'Enterprise' / 'Business' aren't truncated by narrow columns
    kpi_row([
        ("Segment", str(account_row["current_segment"]), None,
         "PayGo (self-serve, pay-as-you-go) or Enterprise (contracted, negotiated). "
         "Accounts move PayGo → Enterprise via tier conversion."),
        ("Subtier", str(account_row.get("paygo_subtier", "—")), None,
         "PayGo plan tier: Free ($0 plan), Pro ($20/mo plan), or Business ($200/mo plan). "
         "Each tier has its own usage-MRR ceiling."),
        ("Tenure", f"{tenure_months} mo", None,
         "Months between first paying month and the latest month in the dataset."),
        ("Status", status, None,
         "Active = still paying. Churned = MRR went to $0 at some point and never came back."),
    ])
    kpi_row([
        ("Latest MRR", fmt_money(latest_mrr), None,
         "Monthly recurring revenue in the most recent month for this account. plan_mrr + usage_mrr."),
        ("Peak MRR", fmt_money(peak_mrr), None,
         "Highest single-month MRR this account has ever recorded."),
        ("Products", f"{n_products}", None,
         "Distinct products this account has ever subscribed to (entry product + later adoptions)."),
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
            _vline(ctx["graduation"].iloc[0]["graduation_month"], "Tier conversion", PALETTE[1])
        if not ctx["churn"].empty:
            churn_reason = ctx["churn"].iloc[0]["churn_reason"]
            _vline(ctx["churn"].iloc[0]["churn_month"], f"Churned: {churn_reason}", "#DC2626")
        fig.update_layout(height=380, yaxis_title="MRR ($)", xaxis_title=None)
        apply_plotly_theme(fig)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # Product timeline — show product, when they adopted it, and a clean status
    if not ctx["products"].empty:
        st.markdown("**Product adoption timeline**")
        timeline = ctx["products"].copy()
        timeline["Adopted"] = pd.to_datetime(timeline["start_month"]).dt.strftime("%b %Y")
        end_dates = pd.to_datetime(timeline["end_month"])
        timeline["Status"] = end_dates.apply(
            lambda d: "🟢 Active" if pd.isna(d) else f"🔴 Ended {d.strftime('%b %Y')}"
        )
        timeline = timeline.rename(columns={"product": "Product"})
        st.dataframe(
            timeline[["Product", "Adopted", "Status"]],
            use_container_width=True, hide_index=True,
        )

    # PPTX export
    st.divider()
    deck_bytes = build_account_deck(account_id, ctx, account_row)
    st.download_button(
        label="Download account report (.pptx)",
        data=deck_bytes,
        file_name=f"account_{account_id}_report.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
