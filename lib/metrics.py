"""Canonical metrics. Every page reads from here so numbers tie out.

This module is the 'semantic layer' for the dashboard. Definitions:

Movement classification per (account, month):
    new              first paying month
    expansion        prior-month MRR > 0 and MRR went up *within the same segment*
    contraction      prior-month MRR > 0 and MRR went down but still > 0
    flat             prior-month MRR > 0 and MRR unchanged
    churn            prior-month MRR > 0 and current MRR == 0
    reactivated      account had a churn earlier, now paying again
    tier_conversion  account moved PayGo -> Enterprise this month
                     (any MRR jump from the tier change is excluded from "expansion")

MRR bridge identity (must hold for every month transition):
    starting_mrr + new + expansion + reactivation + tier_conversion
                 - contraction - churn = ending_mrr

NRR / GRR (excluding tier conversion):
    Cohort = accounts with MRR > 0 at month t-12.
    For accounts in the cohort that converted to Enterprise between t-12 and t,
    we replace their latest MRR with the pre-graduation MRR so the tier jump
    does NOT inflate NRR. This is the "expansion-only" view of retention.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Public canonical names so all views agree
MOVEMENT_ORDER = [
    "new", "expansion", "reactivated", "tier_conversion",
    "flat", "contraction", "churn", "inactive",
]


# -------- Canonical filters --------

def active_accounts(mrr: pd.DataFrame, month: pd.Timestamp | None = None) -> pd.DataFrame:
    """Single source of truth for 'active accounts as of month'.

    Returns rows from mrr_monthly for the given month where MRR > 0.
    If month is None, uses the latest month present in the data.
    """
    if month is None:
        month = mrr["month"].max()
    snap = mrr[mrr["month"] == month]
    return snap[snap["mrr"] > 0].copy()


# -------- Movement bridge --------

def movement_bridge(mrr: pd.DataFrame) -> pd.DataFrame:
    """One row per (account, month) classifying the change vs prior month.

    Output columns: account_id, month, mrr, prev_mrr, delta, segment, prev_segment, movement
    """
    cols = ["account_id", "month", "mrr"]
    if "segment" in mrr.columns:
        cols.append("segment")
    df = mrr[cols].copy()
    df = df.sort_values(["account_id", "month"])

    # Build a continuous month index per account
    all_months = pd.date_range(df["month"].min(), df["month"].max(), freq="MS")
    full_idx = pd.MultiIndex.from_product(
        [df["account_id"].unique(), all_months],
        names=["account_id", "month"],
    )
    full = (
        df.set_index(["account_id", "month"])
        .reindex(full_idx)
        .reset_index()
    )
    full["mrr"] = full["mrr"].fillna(0.0)
    if "segment" in full.columns:
        # Forward-fill segment within account (sticky once Enterprise; pre-signup = NaN)
        full["segment"] = full.groupby("account_id")["segment"].ffill().fillna("PayGo")
    else:
        full["segment"] = "PayGo"

    full["prev_mrr"] = full.groupby("account_id")["mrr"].shift(1).fillna(0.0)
    full["prev_segment"] = full.groupby("account_id")["segment"].shift(1).fillna("PayGo")
    full["delta"] = full["mrr"] - full["prev_mrr"]

    def classify(row) -> str:
        cur, prev = row["mrr"], row["prev_mrr"]
        seg, prev_seg = row["segment"], row["prev_segment"]
        if prev_seg == "PayGo" and seg == "Enterprise" and cur > 0:
            return "tier_conversion"
        if prev == 0 and cur == 0:
            return "inactive"
        if prev == 0 and cur > 0:
            return "new"
        if prev > 0 and cur == 0:
            return "churn"
        if cur > prev:
            return "expansion"
        if cur < prev:
            return "contraction"
        return "flat"

    full["movement"] = full.apply(classify, axis=1)

    # Reclassify 'new' as 'reactivated' if account had a prior churn
    had_churn_month = (
        full[full["movement"] == "churn"]
        .groupby("account_id")["month"]
        .min()
        .to_dict()
    )
    mask_new = full["movement"] == "new"
    full.loc[mask_new, "movement"] = full.loc[mask_new].apply(
        lambda r: "reactivated"
        if r["account_id"] in had_churn_month and r["month"] > had_churn_month[r["account_id"]]
        else "new",
        axis=1,
    )

    return full


def monthly_bridge_summary(bridge: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the movement bridge into one row per month.

    Columns: month, starting_mrr, new, expansion, reactivation, tier_conversion,
    contraction, churn, ending_mrr, net_new_mrr, bridge_check.
    """
    grouped = bridge.groupby("month")
    out = pd.DataFrame({"month": sorted(bridge["month"].unique())}).set_index("month")
    out["ending_mrr"] = grouped["mrr"].sum()
    out["starting_mrr"] = grouped["prev_mrr"].sum()

    def signed(movement: str) -> pd.Series:
        return bridge[bridge["movement"] == movement].groupby("month")["delta"].sum()

    out["new"] = signed("new").reindex(out.index, fill_value=0.0)
    out["expansion"] = signed("expansion").reindex(out.index, fill_value=0.0)
    out["reactivation"] = signed("reactivated").reindex(out.index, fill_value=0.0)
    out["tier_conversion"] = signed("tier_conversion").reindex(out.index, fill_value=0.0)
    out["contraction"] = -signed("contraction").reindex(out.index, fill_value=0.0)
    out["churn"] = -signed("churn").reindex(out.index, fill_value=0.0)

    out["net_new_mrr"] = (
        out["new"] + out["expansion"] + out["reactivation"] + out["tier_conversion"]
        - out["contraction"] - out["churn"]
    )
    out["bridge_check"] = (
        out["starting_mrr"] + out["new"] + out["expansion"] + out["reactivation"]
        + out["tier_conversion"] - out["contraction"] - out["churn"] - out["ending_mrr"]
    )
    return out.reset_index()


# -------- Headline KPIs --------

def current_kpis(mrr: pd.DataFrame, accounts: pd.DataFrame, graduations: pd.DataFrame) -> dict:
    """Snapshot KPIs as of the latest month — single canonical source for Overview."""
    latest = mrr["month"].max()
    active = active_accounts(mrr, latest)

    nrr, grr = revenue_retention(mrr, graduations)
    grad_count_active = int((active["segment"] == "Enterprise").sum())
    grad_rate = (grad_count_active / len(active) * 100.0) if len(active) > 0 else 0.0
    median_ttu = (
        float(graduations["time_to_upgrade_days"].median()) if not graduations.empty else 0.0
    )
    arpa = float(active["mrr"].mean()) if len(active) > 0 else 0.0

    return {
        "current_mrr": float(active["mrr"].sum()),
        "active_accounts": int(len(active)),
        "arpa": arpa,
        "latest_month": latest,
        "nrr": nrr,
        "grr": grr,
        "graduation_rate": grad_rate,
        "graduations": int(len(graduations)),
        "active_enterprise_accounts": grad_count_active,
        "median_time_to_upgrade_days": median_ttu,
    }


# -------- NRR / GRR (tier-conversion-adjusted) --------

def revenue_retention(
    mrr: pd.DataFrame,
    graduations: pd.DataFrame | None = None,
    lookback_months: int = 12,
) -> tuple[float, float]:
    """NRR and GRR, with tier-conversion gains excluded from the numerator.

    For an account that converted PayGo -> Enterprise between anchor and latest,
    we replace its latest MRR with its pre-graduation MRR. That way NRR reflects
    *organic expansion*, not the tier jump.

    NRR = sum(adjusted_latest_mrr) / sum(anchor_mrr) * 100
    GRR = sum(min(adjusted_latest_mrr, anchor_mrr)) / sum(anchor_mrr) * 100
    """
    months_sorted = sorted(mrr["month"].unique())
    if len(months_sorted) <= lookback_months:
        anchor = months_sorted[0]
        latest = months_sorted[-1]
    else:
        latest = months_sorted[-1]
        anchor = months_sorted[-1 - lookback_months]

    anchor_df = mrr[(mrr["month"] == anchor) & (mrr["mrr"] > 0)][["account_id", "mrr"]].rename(
        columns={"mrr": "mrr_anchor"}
    )
    latest_df = mrr[mrr["month"] == latest][["account_id", "mrr"]].rename(
        columns={"mrr": "mrr_latest"}
    )
    joined = anchor_df.merge(latest_df, on="account_id", how="left").fillna({"mrr_latest": 0.0})

    # Tier-conversion adjustment
    if graduations is not None and not graduations.empty:
        # Identify cohort accounts that graduated *between* anchor and latest
        grads_in_window = graduations[
            (graduations["graduation_month"] > anchor)
            & (graduations["graduation_month"] <= latest)
        ][["account_id", "paygo_mrr_at_graduation"]]
        joined = joined.merge(grads_in_window, on="account_id", how="left")
        # For graduated accounts, replace latest with pre-grad MRR (organic-only view)
        mask = joined["paygo_mrr_at_graduation"].notna()
        joined.loc[mask, "mrr_latest"] = joined.loc[mask, "paygo_mrr_at_graduation"]
        joined = joined.drop(columns=["paygo_mrr_at_graduation"])

    denom = joined["mrr_anchor"].sum()
    if denom == 0:
        return 0.0, 0.0

    nrr = joined["mrr_latest"].sum() / denom * 100.0
    capped = joined[["mrr_anchor", "mrr_latest"]].min(axis=1)
    grr = capped.sum() / denom * 100.0
    return float(nrr), float(grr)


# -------- ARPA / cohort retention --------

def arpa_over_time(mrr: pd.DataFrame) -> pd.DataFrame:
    """ARPA = total MRR / active accounts, per month. Returns month, arpa."""
    snap = mrr[mrr["mrr"] > 0].groupby("month").agg(
        total_mrr=("mrr", "sum"),
        active=("account_id", "nunique"),
    )
    snap["arpa"] = snap["total_mrr"] / snap["active"]
    return snap.reset_index()


def cohort_retention(mrr: pd.DataFrame, accounts: pd.DataFrame) -> pd.DataFrame:
    """Signup-month cohorts x months-since-signup retention.

    Returns a long-form DataFrame:
        cohort_month, months_since_signup, retained_pct
    where retained_pct = active accounts at (cohort_month + months_since_signup)
    divided by initial cohort size.
    """
    sign = accounts[["account_id", "signup_month"]].copy()
    sign["cohort_month"] = sign["signup_month"].dt.to_period("M").dt.to_timestamp()

    active = mrr[mrr["mrr"] > 0][["account_id", "month"]].merge(sign, on="account_id")
    active["months_since_signup"] = (
        (active["month"].dt.year - active["cohort_month"].dt.year) * 12
        + (active["month"].dt.month - active["cohort_month"].dt.month)
    )
    active = active[active["months_since_signup"] >= 0]

    cohort_sizes = sign.groupby("cohort_month").size().rename("cohort_size")
    retained = (
        active.groupby(["cohort_month", "months_since_signup"])["account_id"]
        .nunique()
        .reset_index(name="retained")
    )
    retained = retained.join(cohort_sizes, on="cohort_month")
    retained["retained_pct"] = retained["retained"] / retained["cohort_size"] * 100.0
    return retained


# -------- Churn diagnostics --------

def churn_summary(churn: pd.DataFrame, accounts: pd.DataFrame) -> dict:
    """Churn rates and breakdowns."""
    if churn.empty:
        return {"logo_churn_rate": 0.0, "by_reason": pd.DataFrame(), "by_plan": pd.DataFrame()}

    total_accounts = len(accounts)
    logo_churn_rate = len(churn) / total_accounts * 100.0

    by_reason = (
        churn.groupby("churn_reason")
        .agg(churned_accounts=("account_id", "count"), churned_mrr=("last_mrr", "sum"))
        .reset_index()
        .sort_values("churned_accounts", ascending=False)
    )

    by_plan = (
        accounts.assign(churned=accounts["churn_month"].notna())
        .groupby("plan_type")
        .agg(total=("account_id", "count"), churned=("churned", "sum"))
        .reset_index()
    )
    by_plan["churn_rate_pct"] = (by_plan["churned"] / by_plan["total"] * 100.0).round(2)

    return {
        "logo_churn_rate": float(logo_churn_rate),
        "by_reason": by_reason,
        "by_plan": by_plan,
    }


# -------- Product adoption --------

def cross_sell_pairs(subs: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    """For each account: pair the entry product with each later-adopted product.

    Returns rows: source, target, accounts (count). If top_n given, keep only top pairs.
    """
    first = (
        subs.sort_values(["account_id", "start_month"])
        .groupby("account_id")
        .first()
        .reset_index()[["account_id", "product"]]
        .rename(columns={"product": "entry_product"})
    )
    pairs = subs.merge(first, on="account_id")
    pairs = pairs[pairs["product"] != pairs["entry_product"]]
    counts = (
        pairs.groupby(["entry_product", "product"]).size().reset_index(name="accounts")
    )
    counts = counts.rename(columns={"entry_product": "source", "product": "target"})
    counts = counts.sort_values("accounts", ascending=False)
    if top_n:
        counts = counts.head(top_n)
    return counts


def products_per_account(subs: pd.DataFrame) -> pd.DataFrame:
    counts = subs.groupby("account_id")["product"].nunique().reset_index(name="n_products")
    dist = counts.groupby("n_products").size().reset_index(name="accounts")
    return dist


# -------- Account 360 view helpers --------

def account_timeline(account_id: str, mrr: pd.DataFrame, subs: pd.DataFrame,
                     churn: pd.DataFrame, grads: pd.DataFrame) -> dict:
    """Pull everything needed for the per-account drilldown page."""
    return {
        "mrr": mrr[mrr["account_id"] == account_id].sort_values("month"),
        "products": subs[subs["account_id"] == account_id].sort_values("start_month"),
        "churn": churn[churn["account_id"] == account_id],
        "graduation": grads[grads["account_id"] == account_id],
    }
