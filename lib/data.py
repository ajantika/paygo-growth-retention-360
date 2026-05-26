"""Cached parquet loaders. One source of truth for every page."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data(show_spinner=False)
def load_accounts() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "accounts.parquet")


@st.cache_data(show_spinner=False)
def load_mrr_monthly() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "mrr_monthly.parquet")


@st.cache_data(show_spinner=False)
def load_churn() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "churn_events.parquet")


@st.cache_data(show_spinner=False)
def load_subscriptions() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "subscriptions.parquet")


@st.cache_data(show_spinner=False)
def load_graduations() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "graduations.parquet")
