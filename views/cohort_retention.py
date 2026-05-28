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
    """Map a retention % to a pale-to-medium blue, like Apple's App Store
    Connect Cohort Analysis / Daily Retention tables.

    Apple's convention (matched here exactly):
      low retention  -> very pale, nearly white-blue
      high retention -> medium saturated Apple-blue (NOT very dark)
      dark slate text on every cell

    Range (after a 0.5 gamma so 60-80% values spread out visually):
      50%  -> hsl(213, 100%, 92%)  nearly white with a blue tint
      75%  -> hsl(213,  82%, 73%)  light blue
     100%  -> hsl(213,  72%, 62%)  medium Apple-blue

    Lightness DECREASES as retention RISES (Apple's convention),
    inverting the usual dark-theme "high = bright" rule.
    """
    if v is None or (isinstance(v, float) and np.isnan(v)):
        # Future / not-yet-reached cell: very faint slate, no emphasis
        return "background-color: rgba(255, 255, 255, 0.03); color: #475569;"

    # Real cohort-retention data clusters in 60-100%. Map to the actual data
    # range, not the theoretical 0-100, so 60% gets the lightest tint and
    # 100% gets the strongest — giving a full visible gradient.
    vc = max(60.0, min(100.0, float(v)))
    t = (vc - 60.0) / 40.0  # 0..1 across actual data range
    t = t ** 0.65           # gamma so 80-95% values stretch visually

    H = 213                 # Apple-blue hue
    S = 100 - t * 25        # 100% -> 75%
    L = 95 - t * 38         # 95%  -> 57%  (38-point spread, big visible jump)

    # Dark slate text everywhere — Apple's convention, readable down to L~55
    return f"background-color: hsl({H}, {S:.0f}%, {L:.0f}%); color: #0F172A;"


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
