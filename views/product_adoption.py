"""Product Adoption — entry-product distribution, cross-sell Sankey, products-per-account."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.theme import PALETTE, apply_plotly_theme, page_header


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
        apply_plotly_theme(fig)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        dist = metrics.products_per_account(subs)
        fig2 = px.bar(dist, x="n_products", y="accounts",
                      color_discrete_sequence=[PALETTE[1]],
                      title="Products adopted per account")
        fig2.update_layout(height=380, xaxis_title="# products", yaxis_title="Accounts")
        apply_plotly_theme(fig2)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Cross-sell Sankey — distinct node columns for source vs target so it flows left → right.
    pairs = metrics.cross_sell_pairs(subs)
    if not pairs.empty:
        source_labels = [f"{s} (entry)" for s in pairs["source"].unique()]
        target_labels = [f"{t} (added)" for t in pairs["target"].unique()]
        labels = source_labels + target_labels

        idx_src = {s: i for i, s in enumerate(pairs["source"].unique())}
        idx_tgt = {t: i + len(source_labels) for i, t in enumerate(pairs["target"].unique())}

        # X positions: sources on left (0.01), targets on right (0.99)
        node_x = [0.01] * len(source_labels) + [0.99] * len(target_labels)
        # Color sources lavender, targets sky-blue
        node_colors = [PALETTE[0]] * len(source_labels) + [PALETTE[1]] * len(target_labels)

        fig3 = go.Figure(go.Sankey(
            arrangement="snap",
            node={
                "label": labels,
                "color": node_colors,
                "pad": 18,
                "thickness": 18,
                "x": node_x,
                "y": [0.5] * len(labels),
                "line": dict(color="rgba(148,163,184,0.3)", width=0.5),
            },
            link={
                "source": pairs["source"].map(idx_src).tolist(),
                "target": pairs["target"].map(idx_tgt).tolist(),
                "value": pairs["accounts"].tolist(),
                "color": "rgba(167,139,250,0.35)",
            },
        ))
        fig3.update_layout(
            title="Cross-sell: entry product → expansion product",
            height=520,
            font=dict(color="#E2E8F0"),
        )
        apply_plotly_theme(fig3)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.markdown("**Top cross-sell journeys**")
    if not pairs.empty:
        st.dataframe(pairs.head(15), use_container_width=True, hide_index=True)
