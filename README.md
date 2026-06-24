# PAYGO Growth & Retention 360

A revenue lifecycle product for a usage-based PAYGO customer base — covering the entire revenue journey from acquisition through churn.

🔗 **[Live Demo](https://paygo-growth-retention-360.streamlit.app/)**

## What it does
- Full revenue lifecycle tracking: new, expansion, contraction, churn, tier conversion
- **PAYGO → Enterprise graduation funnel** with time-to-convert analysis
- Churn-reason diagnostics and cohort retention heatmaps
- Per-account drilldowns tied to a single canonical metric layer

## The craft
- **MRR Bridge** — every dollar of movement named and tied out month over month
- **Plan vs Usage model** — splits MRR into subscription proceeds vs consumption
- **Tier conversion isolated** from organic expansion so NRR isn't artificially inflated by self-serve → Enterprise jumps
- **Cohort retention heatmap** — signup-month cohorts across months since signup, spotting structural drop-offs
- **Native PPTX export** — branded executive deck and per-account report in one click
- Every metric has a definition tooltip; every page reads from a single semantic layer (lib/metrics.py)

🧩 **Framework: MRR Bridge + Plan-vs-Usage model** — every dollar of movement named and accounted for

## Impact
- 📊 Covers ~90% of customer base in the original Cloudflare context
- 📈 Contributed to **24% YoY MRR increase**
- 🔍 End-to-end revenue lifecycle: acquisition, conversion, retention, churn

## Stack
Python · Streamlit · Plotly · pandas · python-pptx · PyArrow

---

Built by [Ajantika Paul](https://ajantika.github.io) · Lead Product Data Analyst @ Cloudflare
