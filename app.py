"""PayGo Growth & Retention 360 — Streamlit entry point.

Sibling project to Customer 360 / Product 360. Same st.navigation
multi-page layout, same metric vocabulary (MRR, regions, channels).
All data is synthetic (seed=42).
"""
from __future__ import annotations

import streamlit as st

from lib.theme import demo_banner
from views import (
    account_360,
    churn_diagnostics,
    cohort_retention,
    overview,
    paygo_enterprise,
    product_adoption,
    revenue_lifecycle,
)


def main() -> None:
    st.set_page_config(
        page_title="PayGo Growth & Retention 360",
        page_icon="📈",
        layout="wide",
    )
    demo_banner()

    pages = [
        st.Page(overview.render, title="Overview", icon="🏠", url_path="overview", default=True),
        st.Page(revenue_lifecycle.render, title="Revenue Lifecycle", icon="💸", url_path="revenue-lifecycle"),
        st.Page(cohort_retention.render, title="Cohort Retention", icon="📊", url_path="cohort-retention"),
        st.Page(paygo_enterprise.render, title="Tier Conversion", icon="🚀", url_path="tier-conversion"),
        st.Page(churn_diagnostics.render, title="Churn Diagnostics", icon="📉", url_path="churn-diagnostics"),
        st.Page(product_adoption.render, title="Feature Adoption", icon="🧩", url_path="feature-adoption"),
        st.Page(account_360.render, title="Account 360", icon="🔍", url_path="account-360"),
    ]
    nav = st.navigation(pages)
    nav.run()


if __name__ == "__main__":
    main()
