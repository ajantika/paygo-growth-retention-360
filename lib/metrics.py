"""Canonical metrics. Every page reads from here so numbers tie out.

This module is the 'semantic layer' for the dashboard. Definitions:

- Movement classification per (account, month):
    new          first paying month
    expansion    prior-month MRR > 0 and MRR went up
    contraction  prior-month MRR > 0 and MRR went down but still > 0
    flat         prior-month MRR > 0 and MRR unchanged
    churn        prior-month MRR > 0 and current MRR == 0  (or churn event)
    reactivated  account had a churn earlier, now paying again

- MRR bridge identity (must hold for every month transition):
    starting_mrr + new + expansion + reactivation - contraction - churn = ending_mrr

- NRR (Net Revenue Retention):
    cohort = accounts with MRR > 0 at month t-12
    NRR = sum(MRR at t for cohort, incl 0 for churned) / sum(MRR at t-12 for cohort)

- GRR (Gross Revenue Retention): same cohort but cap expansion at $0 of growth.
"""
from __future__ import annotations

import pandas as pd


# -------- Movement bridge --------

def movement_bridge(mrr: pd.DataFrame) -> pd.DataFrame:
    """One row per (account, month) classifying the change vs prior month.

    Output columns: account_id, month, mrr, prev_mrr, delta, movement
    """
    df = mrr[["account_id", "month", "mrr"]].copy()
    df = df.sort_values(["account_id", "month"])

    # Build a continuous month index per account from min(month) to max(month)
    all_months = pd.date_range(df["month"].min(), df["month"].max(), freq="MS")
    full = (
        df.set_index(["account_id", "month"])
        .reindex(
            pd.MultiIndex.from_product(
                [df["account_id"].unique(), all_months],
                names=["account_id", "month"],
            ),
            fill_value=0.0,
        )
        .reset_index()
    )
    full["prev_mrr"] = full.groupby("account_id")["mrr"].shift(1).fillna(0.0)
    full["delta"] = full["mrr"] - full["prev_mrr"]

    def classify(row) -> str:
        cur = row["mrr"]
        prev = row["prev_mrr"]
        if prev == 0 and cur == 0:
            return "inactive"
        if prev == 0 and cur > 0:
            return "new"  # may be reclassified to 'reactivated' below
        if prev > 0 and cur == 0:
            return "churn"
        if cur > prev:
            return "expansion"
        if cur < prev:
            return "contraction"
        return "flat"

    full["movement"] = full.apply(classify, axis=1)

    # Reclassify 'new' as 'reactivated' if the account had any churn before this month
    had_churn = (
        full[full["movement"] == "churn"]
        .groupby("account_id")["month"]
        .min()
        .to_dict()
    )
    mask_new = full["movement"] == "new"
    full.loc[mask_new, "movement"] = full.loc[mask_new].apply(
        lambda r: "reactivated" if r["account_id"] in had_churn and r["month"] > had_churn[r["account_id"]] else "new",
        axis=1,
    )

    return full


def monthly_bridge_summary(bridge: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the movement bridge into one row per month.

    Output columns: month, starting_mrr, new, expansion, reactivation,
    contraction, churn, ending_mrr, net_new_mrr.
    """
    grouped = bridge.groupby("month")
    out = pd.DataFrame({"month": sorted(bridge["month"].unique())}).set_index("month")
    out["ending_mrr"] = grouped["mrr"].sum()
    out["starting_mrr"] = grouped["prev_mrr"].sum()

    def signed_sum(movement: str, sign: int = 1) -> pd.Series:
        d = bridge[bridge["movement"] == movement].groupby("month")["delta"].sum()
        return d * sign

    out["new"] = signed_sum("new").reindex(out.index, fill_value=0.0)
    out["expansion"] = signed_sum("expansion").reindex(out.index, fill_value=0.0)
    out["reactivation"] = signed_sum("reactivated").reindex(out.index, fill_value=0.0)
    out["contraction"] = -signed_sum("contraction").reindex(out.index, fill_value=0.0)  # store as positive magnitude
    # churn delta is negative (mrr went 0); flip sign for magnitude
    out["churn"] = -signed_sum("churn").reindex(out.index, fill_value=0.0)

    out["net_new_mrr"] = (
        out["new"] + out["expansion"] + out["reactivation"] - out["contraction"] - out["churn"]
    )
    out["bridge_check"] = (
        out["starting_mrr"] + out["new"] + out["expansion"] + out["reactivation"]
        - out["contraction"] - out["churn"] - out["ending_mrr"]
    )
    return out.reset_index()


# -------- Headline KPIs --------

def current_kpis(mrr: pd.DataFrame, accounts: pd.DataFrame, graduations: pd.DataFrame) -> dict:
    """Snapshot KPIs as of the latest month."""
    latest = mrr["month"].max()
    last_month_mrr = mrr[mrr["month"] == latest]
    active = last_month_mrr[last_month_mrr["mrr"] > 0]

    nrr, grr = revenue_retention(mrr)
    grad_rate = (
        len(graduations) / len(accounts) * 100.0 if len(accounts) > 0 else 0.0
    )
    median_ttu = (
        float(graduations["time_to_upgrade_days"].median()) if not graduations.empty else 0.0
    )

    return {
        "current_mrr": float(active["mrr"].sum()),
        "active_accounts": int(len(active)),
        "latest_month": latest,
        "nrr": nrr,
        "grr": grr,
        "graduation_rate": grad_rate,
        "graduations": int(len(graduations)),
        "median_time_to_upgrade_days": median_ttu,
    }


# -------- NRR / GRR --------

def revenue_retention(mrr: pd.DataFrame, lookback_months: int = 12) -> tuple[float, float]:
    """NRR and GRR computed over a trailing window.

    Cohort: accounts with MRR > 0 at the anchor month (latest - lookback).
    NRR = sum(MRR at latest for cohort, 0 for churned) / sum(MRR at anchor).
    GRR = same numerator capped per-account at MRR at anchor (no expansion credit).
    """
    months_sorted = sorted(mrr["month"].unique())
    if len(months_sorted) <= lookback_months:
        # Fall back to first vs last when window is short
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

    denom = joined["mrr_anchor"].sum()
    if denom == 0:
        return 0.0, 0.0

    nrr = joined["mrr_latest"].sum() / denom * 100.0
    capped = joined.assign(mrr_capped=joined[["mrr_anchor", "mrr_latest"]].min(axis=1))
    grr = capped["mrr_capped"].sum() / denom * 100.0
    return float(nrr), float(grr)


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

def cross_sell_pairs(subs: pd.DataFrame) -> pd.DataFrame:
    """For each account: pair the entry product with each later-adopted product.

    Returns rows: source, target, accounts (count).
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
    return counts.sort_values("accounts", ascending=False)


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
