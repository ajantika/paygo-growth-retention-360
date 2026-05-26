"""Product Adoption — entry-product distribution, cross-sell Sankey, products-per-account."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.theme import PALETTE, page_header


def render() -> None:
    page_header(
        "Product Adoption",
        "Entry products, cross-sell journeys, and account breadth.",
    )

    accounts = dl.load_accounts()
    subs = dl.load_subscriptions()

    col1, col2 = st.columns(2)
    with col1:
        entry = accounts.groupby("entry_product").size().reset_index(name="accounts")
        fig = px.bar(entry.sort_values("accounts", ascending=True),
                     x="accounts", y="entry_product",
                     orientation="h",
                     color_discrete_sequence=[PALETTE[0]],
                     title="Entry product distribution")
        fig.update_layout(height=380, yaxis_title=None, xaxis_title="Accounts")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        dist = metrics.products_per_account(subs)
        fig2 = px.bar(dist, x="n_products", y="accounts",
                      color_discrete_sequence=[PALETTE[1]],
                      title="Products adopted per account")
        fig2.update_layout(height=380, xaxis_title="# products", yaxis_title="Accounts")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Cross-sell Sankey
    pairs = metrics.cross_sell_pairs(subs)
    if not pairs.empty:
        labels = pd.concat([pairs["source"], pairs["target"]]).unique().tolist()
        idx = {label: i for i, label in enumerate(labels)}
        fig3 = go.Figure(go.Sankey(
            node={
                "label": labels,
                "color": PALETTE[0],
                "pad": 12, "thickness": 14,
            },
            link={
                "source": pairs["source"].map(idx).tolist(),
                "target": pairs["target"].map(idx).tolist(),
                "value": pairs["accounts"].tolist(),
                "color": "rgba(243,128,32,0.35)",
            },
        ))
        fig3.update_layout(title="Cross-sell: entry product → expansion product", height=480)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.markdown("**Top cross-sell journeys**")
    if not pairs.empty:
        st.dataframe(pairs.head(15), use_container_width=True, hide_index=True)
