"""Shared theme and small UI helpers."""
from __future__ import annotations

import streamlit as st

COLOR_PRIMARY = "#F38020"   # Cloudflare orange (warm)
COLOR_SECONDARY = "#003682" # deep blue
COLOR_POS = "#16A34A"
COLOR_NEG = "#DC2626"
COLOR_NEUTRAL = "#64748B"

PALETTE = [COLOR_PRIMARY, COLOR_SECONDARY, "#16A34A", "#9333EA", "#F59E0B", "#06B6D4", "#EC4899", "#64748B"]


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
        <div style='padding:10px;border-radius:6px;background:#FFF7ED;border:1px solid #FDBA74;font-size:12px;'>
        <strong>Demo data only.</strong> 100% synthetic, generated with seed=42.
        No real customer or revenue data.
        </div>
        """,
        unsafe_allow_html=True,
    )


def fmt_money(x: float, short: bool = True) -> str:
    if x is None:
        return "—"
    if short:
        if abs(x) >= 1_000_000:
            return f"${x/1_000_000:.2f}M"
        if abs(x) >= 1_000:
            return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"


def fmt_pct(x: float) -> str:
    return f"{x:.1f}%"
