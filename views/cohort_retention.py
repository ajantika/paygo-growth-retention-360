"""Cohort retention — App Store Connect style.

A single integrated table:
  Cohort | Paid Starts | M1 | M2 | … | M12

With a Total row pinned to the top, gradient-shaded cells, and empty cells
for months a cohort hasn't reached yet. No axes, no colorbar, no chart titles
fighting for space.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from lib import data as dl
from lib import metrics
from lib.theme import PLOTLY_CONFIG, apply_plotly_theme, fmt_pct, kpi_row, page_header

MAX_MONTHS = 12


# ---------- Cell-color helper ----------

def _cell_color(v: float | None) -> str:
    """Map a retention % to a SOLID HSL color with a wide lightness ramp.

    Alpha-blending lavender over a dark background compressed everything into
    'some shade of medium purple'. Solid HSL colors vary lightness directly,
    giving 50%+ perceptual contrast between the dimmest and brightest cells.

    Range:
      50% retention → very dim violet (almost blends with bg) — "weak cohort"
      75% retention → medium violet                            — "average"
     100% retention → vivid bright lavender                    — "strong cohort"
    """
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "background-color: rgba(30, 41, 59, 0.25); color: #475569;"

    vc = max(50.0, min(100.0, float(v)))
    t = (vc - 50.0) / 50.0  # 0..1
    t = t ** 0.6  # mild gamma so 70-90% values spread out visually

    # Solid HSL: lightness 28% → 78% (50-point spread = huge perceptual jump)
    L = 28 + t * 50
    S = 60 + t * 25  # also more saturated as retention rises
    H = 262          # violet hue, same family as PALETTE[0]

    # Text: white reads everywhere in this lightness range
    return f"background-color: hsl({H}, {S:.0f}%, {L:.0f}%); color: #FFFFFF;"


def _build_styled_table(display: pd.DataFrame, sizes: pd.Series) -> str:
    """Return a self-contained HTML <table> styled like App Store Connect."""
    # Cell-formatted retention strings
    def fmt_cell(v) -> str:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return ""
        return f"{int(round(v))}%"

    months = list(display.columns)
    header_cells = (
        "<th class='cohort'>Cohort</th>"
        "<th class='starts'>Paid Starts</th>"
        + "".join(f"<th class='m'>M{m}</th>" for m in months)
    )

    rows_html: list[str] = []
    for cohort_label, row in display.iterrows():
        row_class = "total" if cohort_label == "Total" else ""
        starts = int(sizes.loc[cohort_label])
        cells = "".join(
            f"<td style='{_cell_color(v)}'>{fmt_cell(v)}</td>"
            for v in row.values
        )
        rows_html.append(
            f"<tr class='{row_class}'>"
            f"<td class='cohort'>{cohort_label}</td>"
            f"<td class='starts'>{starts:,}</td>"
            f"{cells}"
            f"</tr>"
        )

    table = f"""
    <style>
      .cohort-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 2px;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        color: #E2E8F0;
        margin-top: 0.5rem;
      }}
      .cohort-table th {{
        font-weight: 600;
        text-align: center;
        padding: 8px 6px;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-size: 11px;
        border-bottom: 1px solid rgba(148,163,184,0.25);
      }}
      .cohort-table th.cohort, .cohort-table th.starts {{
        text-align: left;
      }}
      .cohort-table td {{
        padding: 8px 6px;
        text-align: center;
        border-radius: 4px;
        min-width: 46px;
      }}
      .cohort-table td.cohort {{
        text-align: left;
        font-weight: 500;
        color: #CBD5E1;
        background: transparent;
        white-space: nowrap;
      }}
      .cohort-table td.starts {{
        text-align: right;
        font-variant-numeric: tabular-nums;
        color: #CBD5E1;
        background: transparent;
        padding-right: 14px;
      }}
      .cohort-table tr.total td {{
        font-weight: 700;
        border-top: 2px solid rgba(148,163,184,0.45);
        border-bottom: 2px solid rgba(148,163,184,0.45);
      }}
      .cohort-table tr.total td.cohort,
      .cohort-table tr.total td.starts {{
        color: #FFFFFF;
      }}
    </style>
    <table class='cohort-table'>
      <thead><tr>{header_cells}</tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    """
    return table


# ---------- Page ----------

def render() -> None:
    page_header(
        "Cohort Retention",
        "How long do accounts stick around after they sign up? "
        "Each percentage: **of the accounts that signed up in month X, what % are still paying N months later?**",
    )

    accounts = dl.load_accounts()
    mrr = dl.load_mrr_monthly()

    cr = metrics.cohort_retention(mrr, accounts)
    if cr.empty:
        st.warning("Not enough data to build cohorts yet.")
        return

    # ---- Headline retention KPIs ----
    def cohort_retention_at(month_offset: int) -> float:
        sub = cr[cr["months_since_signup"] == month_offset]
        return float(sub["retained_pct"].mean()) if not sub.empty else 0.0

    m1 = cohort_retention_at(1)
    m3 = cohort_retention_at(3)
    m6 = cohort_retention_at(6)
    m12 = cohort_retention_at(12)

    kpi_row([
        ("Month 1 retention", fmt_pct(m1), None,
         "Of all signup cohorts that have lived ≥1 month, the average % still active 1 month after signup."),
        ("Month 3 retention", fmt_pct(m3), None,
         "Of all signup cohorts that have lived ≥3 months, the average % still active 3 months after signup."),
        ("Month 6 retention", fmt_pct(m6), None,
         "Of all signup cohorts that have lived ≥6 months, the average % still active 6 months after signup. "
         "Most diagnostic — onboarding effects gone."),
        ("Month 12 retention", fmt_pct(m12), None,
         "Of all signup cohorts that have lived ≥12 months, the average % still active 12 months after signup."),
    ])
    st.caption(
        "Each KPI is the **average across cohorts** that have reached that age. "
        "Table below shows every cohort, side-by-side, with its paid-start count."
    )

    st.divider()
    st.markdown("#### Cohort retention table")

    # ---- Build cohort × month matrix ----
    cap = cr[cr["months_since_signup"].between(1, MAX_MONTHS)].copy()
    pivot = (
        cap.pivot(index="cohort_month", columns="months_since_signup", values="retained_pct")
        .sort_index()
        .reindex(columns=range(1, MAX_MONTHS + 1))
    )
    cohort_sizes = (
        cr.groupby("cohort_month")["cohort_size"].first().reindex(pivot.index)
    )

    total_row = pivot.mean(axis=0, skipna=True)
    total_size = int(cohort_sizes.sum())

    display = pd.concat([pd.DataFrame([total_row], index=["Total"]), pivot.copy()])
    sizes = pd.concat([pd.Series([total_size], index=["Total"]), cohort_sizes])
    display.index = ["Total"] + [pd.Timestamp(c).strftime("%b %Y") for c in pivot.index]
    sizes.index = display.index

    table_html = _build_styled_table(display, sizes)
    st.markdown(table_html, unsafe_allow_html=True)

    st.caption(
        "**Total row** = simple mean of each column across all cohorts that have reached that age (Apple's convention; unweighted). "
        "**Paid Starts** = paying accounts the cohort had in its first month. "
        "Empty cells = the cohort hasn't reached that age yet."
    )

    st.divider()

    # ---- Retention curve overlay ----
    st.markdown("#### Cohort survival curves")
    curve_df = cap.copy()
    curve_df["cohort_label"] = pd.to_datetime(curve_df["cohort_month"]).dt.strftime("%b %Y")
    cohorts_all = sorted(curve_df["cohort_month"].unique())
    if len(cohorts_all) > 8:
        step = max(1, len(cohorts_all) // 6)
        shown = cohorts_all[::step] + [cohorts_all[-1]]
        shown = sorted(set(shown))
        curve_df = curve_df[curve_df["cohort_month"].isin(shown)]

    fig2 = px.line(
        curve_df,
        x="months_since_signup", y="retained_pct", color="cohort_label",
    )
    fig2.update_traces(
        hovertemplate="Cohort: %{fullData.name}<br>Month: M%{x}<br>% retained: %{y:.0f}%<extra></extra>"
    )
    fig2.update_layout(
        height=400,
        yaxis_title="% of cohort retained",
        xaxis_title="Months since signup",
        legend_title="Cohort",
    )
    apply_plotly_theme(fig2)
    st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)
