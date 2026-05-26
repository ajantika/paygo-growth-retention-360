# PayGo Growth & Retention 360

A self-serve partner reporting product that turns a usage-based customer base into a clear, actionable view of the full revenue lifecycle — sign-up, expansion, graduation to Enterprise, and churn — backed by a single canonical metric layer so every number ties out across views.

Built as a sibling to [Customer 360 / Product 360](https://ajantika-customer-360.streamlit.app/), using the same Streamlit multi-page pattern, the same metric vocabulary, and the same data-product principles.

**100% synthetic data.** Seeded generator (`seed=42`), no real customer or revenue data.

## Story / talking track

Three sentences for sharing the link:

> I built a self-serve reporting product for a usage-based (PayGo) customer base — answering the questions a Partner Data & Analytics team owns daily: how is MRR moving, who's graduating, who's churning, and what cross-sell is working. Every view reads from one canonical metrics module, so NRR/GRR, the MRR bridge, churn rates, and the conversion funnel all reconcile. The headline finding from the synthetic dataset: annual plans churn at a fraction of monthly — making plan mix one of the highest-leverage retention levers.

## How it maps to App Store developer reporting

| Apple's Partner Data & Analytics work | What this project demonstrates |
| --- | --- |
| Build partner-facing reporting / data products | Six-page Streamlit dashboard, partner-segmented |
| Turn large datasets into clear, actionable reports | KPI cockpit + drilldowns + per-account PPTX export |
| Ideate metrics & KPIs | NRR, GRR, MRR bridge, time-to-upgrade, cross-sell pairs |
| Ensure accuracy and continuity across data products | One canonical `lib/metrics.py` — bridge identity holds to ~1e-11 |
| Support multiple content types / partner segments | PayGo vs Enterprise; Monthly vs Annual; 8 products; 4 regions |
| Privacy-respecting analytics | All synthetic; no real customer attribution |
| Partner with engineering on data pipelines | Generator → semantic layer → 5 parquet sources → cached loaders |

## Pages

| Page | What it answers |
| --- | --- |
| **Overview** | Headline KPIs (MRR, active accounts, NRR, GRR, graduation rate, time-to-upgrade), MRR over time by segment, plan/region mix. **Exec summary PPTX download.** |
| **Revenue Lifecycle** | The MRR bridge waterfall (start + new + expansion + reactivation − contraction − churn = end), bridge identity check, account movement mix. |
| **PayGo → Enterprise** | Graduation funnel, time-to-upgrade distribution, jump multiplier at graduation, recent graduations table. |
| **Churn Diagnostics** | Logo churn rate, reasons (account count + lost MRR), the annual-vs-monthly headline insight, churn over time. |
| **Product Adoption** | Entry-product distribution, cross-sell Sankey (entry → expansion), products-per-account, top journeys. |
| **Account 360** | Per-account drilldown with MRR trajectory, key-event annotations (graduation / churn), product timeline. **Per-account PPTX report download.** |

## Tech stack

- **Python · Streamlit · Plotly** — same stack as Customer 360
- **pandas · numpy · pyarrow** for the data + metrics layer
- **python-pptx** for branded exports (KPI cards + native charts; works on Streamlit Cloud, no external binaries)

## Repo layout

```
paygo-growth-retention-360/
├── app.py                       # entry — st.navigation
├── requirements.txt
├── README.md
├── data/                        # committed parquet (synthetic)
│   ├── accounts.parquet
│   ├── mrr_monthly.parquet
│   ├── subscriptions.parquet
│   ├── churn_events.parquet
│   └── graduations.parquet
├── lib/
│   ├── data.py                  # cached parquet loaders
│   ├── metrics.py               # canonical metric definitions
│   ├── theme.py                 # palette, KPI cards, demo banner
│   └── export.py                # PPTX deck builder
├── scripts/
│   └── generate_data.py         # seeded synthetic generator
└── views/                       # one render() per page
    ├── overview.py
    ├── revenue_lifecycle.py
    ├── paygo_enterprise.py
    ├── churn_diagnostics.py
    ├── product_adoption.py
    └── account_360.py
```

## Run locally

```bash
pip install -r requirements.txt
python scripts/generate_data.py    # only needed if data/ is empty
streamlit run app.py
```

Open <http://localhost:8501>.

## Deploy

1. Push this repo to GitHub (public).
2. On [share.streamlit.io](https://share.streamlit.io), Create app → pick the repo → main file `app.py` → Deploy.
3. No secrets or API keys required — the synthetic parquet files in `/data` ship with the repo.

## Methodology notes

- **Bridge identity.** Every (account, month) is classified — new / expansion / contraction / flat / churn / reactivated — and the monthly aggregates must satisfy `start + new + expansion + reactivation − contraction − churn − ending = 0`. The Revenue Lifecycle page surfaces the residual; in this dataset it's ~1e-11.
- **NRR cohort.** Trailing 12-month cohort: accounts with MRR > 0 at month *t-12*. NRR includes graduation jumps in the numerator; GRR caps each account at its anchor MRR (no expansion credit), which is why GRR is lower and a better pure-retention read.
- **Graduation.** Modeled as tenure ≥ 3 months + PayGo MRR ≥ $120, with probability scaling on MRR and a stickiness multiplier for annual plans. On graduation, MRR jumps 2.5–5x to reflect a negotiated Enterprise contract.

---

*Built by [Ajantika Paul](https://ajantika.github.io/). Synthetic data only — no real customer information.*
