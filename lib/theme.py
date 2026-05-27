"""Shared theme and small UI helpers."""
from __future__ import annotations

import streamlit as st

# Dark theme palette — pops on the dark navy background
COLOR_PRIMARY = "#A78BFA"    # lavender accent (matches Customer 360 vibe)
COLOR_SECONDARY = "#60A5FA"  # sky blue
COLOR_POS = "#34D399"        # emerald
COLOR_NEG = "#F87171"        # rose
COLOR_NEUTRAL = "#94A3B8"    # slate

PALETTE = [
    "#A78BFA",  # lavender
    "#60A5FA",  # sky
    "#34D399",  # emerald
    "#FBBF24",  # amber
    "#F472B6",  # pink
    "#22D3EE",  # cyan
    "#FB923C",  # orange
    "#94A3B8",  # slate
]

# Plotly template tuned for dark theme
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#E2E8F0", family="sans-serif"),
    xaxis=dict(gridcolor="rgba(148,163,184,0.15)", zerolinecolor="rgba(148,163,184,0.2)"),
    yaxis=dict(gridcolor="rgba(148,163,184,0.15)", zerolinecolor="rgba(148,163,184,0.2)"),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)

# Pass this to every st.plotly_chart(..., config=PLOTLY_CONFIG) to hide the modebar.
PLOTLY_CONFIG = {"displayModeBar": False}

# Canonical color mapping for movement categories so every view agrees.
MOVEMENT_COLORS = {
    "new": "#34D399",             # emerald
    "expansion": "#A78BFA",       # lavender (primary)
    "reactivated": "#22D3EE",     # cyan
    "tier_conversion": "#FBBF24", # amber (distinctive — it's a structural event)
    "flat": "#94A3B8",            # slate
    "contraction": "#FB923C",     # orange
    "churn": "#EF4444",           # red
    "inactive": "#475569",        # dim slate
}


def apply_plotly_theme(fig):
    fig.update_layout(**PLOTLY_LAYOUT)
    return fig


def page_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)


def kpi_row(items: list[tuple[str, str, str | None]]) -> None:
    """Render a row of KPI cards. items = [(label, value, delta), ...]."""
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items):
        with col:
            st.metric(label=label, value=value, delta=delta if delta else None)


def demo_banner() -> None:
    st.sidebar.markdown(
        """
        <div style='padding:10px;border-radius:8px;background:rgba(167,139,250,0.10);
        border:1px solid rgba(167,139,250,0.40);font-size:12px;color:#E2E8F0;'>
        <strong>⚠️ Demo data only.</strong> 100% synthetic, generated with seed=42.
        No real customer or revenue data.
        </div>
        """,
        unsafe_allow_html=True,
    )


def fmt_money(x: float, short: bool = True) -> str:
    """Format currency as a whole number."""
    if x is None:
        return "—"
    if short:
        if abs(x) >= 1_000_000:
            return f"${x/1_000_000:.0f}M"
        if abs(x) >= 1_000:
            return f"${x/1_000:.0f}K"
    return f"${x:,.0f}"


def fmt_pct(x: float) -> str:
    """Format percentage as a whole number."""
    return f"{x:.0f}%"
