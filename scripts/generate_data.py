"""Generate synthetic PayGo customer lifecycle data — v2.

Schema upgrades vs v1:
- accounts.paygo_subtier              Free / Pro / Business (filter, not headline split)
- mrr_monthly.plan_mrr, usage_mrr     subscription vs consumption split
                                      (App Store analogue: subscription proceeds vs in-app proceeds)
- Enterprise contracts now sampled from lognormal $3K-$50K
- mrr = plan_mrr + usage_mrr  (always)

Files produced in /data:
  accounts.parquet         one row per account
  mrr_monthly.parquet      one row per (account, month)
  subscriptions.parquet    one row per (account, product) — start/end months
  churn_events.parquet     one row per churn
  graduations.parquet      PayGo -> Enterprise upgrades with time-to-upgrade

100% synthetic. Seed pinned for reproducibility.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_ACCOUNTS = 800
START_MONTH = pd.Timestamp("2024-01-01")
END_MONTH = pd.Timestamp("2026-04-01")

# Real Cloudflare-shaped product list (plus a couple developer-platform names)
PRODUCTS = ["Workers", "R2 Storage", "Zero Trust", "Pages", "Stream", "Images", "D1", "Queues"]
REGIONS = ["NAMER", "EMEA", "APAC", "LATAM"]
CHANNELS = ["Self-serve", "Inbound sales", "Partner referral", "Marketing"]
CHURN_REASONS = [
    "Price too high",
    "Switched to competitor",
    "Project ended / no longer needed",
    "Billing / payment failure",
    "Consolidating vendors",
    "Missing feature",
]

# PayGo subtiers (analogous to Cloudflare's Free / Pro / Business)
SUBTIERS = ["Free", "Pro", "Business"]
SUBTIER_WEIGHTS = [0.40, 0.45, 0.15]
PLAN_MRR_BY_SUBTIER = {"Free": 0.0, "Pro": 20.0, "Business": 200.0}
# Usage MRR shape (lognormal params + cap) per subtier
USAGE_SHAPE = {
    "Free":     {"mu": 1.5, "sigma": 1.1, "cap": 80.0,   "growth": 0.015},
    "Pro":      {"mu": 3.0, "sigma": 1.0, "cap": 400.0,  "growth": 0.025},
    "Business": {"mu": 4.5, "sigma": 1.0, "cap": 1800.0, "growth": 0.030},
}

# Per-month churn hazard
HAZARD_MONTHLY = 0.025
HAZARD_ANNUAL = 0.005
HAZARD_ENT_MULT = 0.08  # Enterprise much stickier


def month_range(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="MS")


def sample_initial_usage(subtier: str, rng: np.random.Generator) -> float:
    shape = USAGE_SHAPE[subtier]
    return float(min(shape["cap"], rng.lognormal(shape["mu"] * 0.6, shape["sigma"] * 0.8)))


def sample_enterprise_contract(rng: np.random.Generator) -> float:
    """Enterprise plan MRR: lognormal centered ~$8K, clipped to [$3K, $40K]."""
    raw = rng.lognormal(mean=np.log(8_000), sigma=0.55)
    return float(np.clip(raw, 3_000.0, 40_000.0))


def main() -> None:
    rng = np.random.default_rng(SEED)
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    months = month_range(START_MONTH, END_MONTH)

    # ---- Accounts ----
    weights = np.linspace(0.6, 1.6, len(months))
    weights = weights / weights.sum()
    signup_idx = rng.choice(len(months), size=N_ACCOUNTS, p=weights)
    signup_months = months[signup_idx]

    accounts = pd.DataFrame(
        {
            "account_id": [f"A{1000 + i:05d}" for i in range(N_ACCOUNTS)],
            "signup_month": pd.to_datetime(signup_months),
            "region": rng.choice(REGIONS, size=N_ACCOUNTS, p=[0.45, 0.30, 0.18, 0.07]),
            "channel": rng.choice(CHANNELS, size=N_ACCOUNTS, p=[0.55, 0.20, 0.15, 0.10]),
            "plan_type": rng.choice(["Monthly", "Annual"], size=N_ACCOUNTS, p=[0.72, 0.28]),
            "paygo_subtier": rng.choice(SUBTIERS, size=N_ACCOUNTS, p=SUBTIER_WEIGHTS),
            "entry_product": rng.choice(
                PRODUCTS, size=N_ACCOUNTS, p=[0.32, 0.18, 0.14, 0.12, 0.08, 0.06, 0.06, 0.04]
            ),
        }
    ).sort_values("signup_month").reset_index(drop=True)

    # ---- Simulate per-account timeline ----
    mrr_rows: list[dict] = []
    sub_rows: list[dict] = []
    churn_rows: list[dict] = []
    grad_rows: list[dict] = []

    for _, acc in accounts.iterrows():
        signup = acc["signup_month"]
        plan_type = acc["plan_type"]
        entry = acc["entry_product"]
        subtier = acc["paygo_subtier"]
        shape = USAGE_SHAPE[subtier]

        plan_mrr = PLAN_MRR_BY_SUBTIER[subtier]
        usage_mrr = sample_initial_usage(subtier, rng)

        products = {entry}
        sub_rows.append({
            "account_id": acc["account_id"],
            "product": entry,
            "start_month": signup,
            "end_month": pd.NaT,
        })

        segment = "PayGo"
        churned = False

        for m in months:
            if m < signup:
                continue

            tenure_m = (m.year - signup.year) * 12 + (m.month - signup.month)

            # Usage MRR drift: subtier-specific growth + noise, capped
            growth = shape["growth"] if segment == "PayGo" else 0.008
            drift = float(rng.normal(loc=growth, scale=0.08))
            usage_mrr = max(0.0, usage_mrr * (1 + drift))
            usage_mrr = min(usage_mrr, shape["cap"] if segment == "PayGo" else plan_mrr * 0.35)

            # Cross-sell: chance to adopt new product (PayGo more dynamic)
            cross_sell_p = 0.06 if segment == "PayGo" else 0.025
            if rng.random() < cross_sell_p and len(products) < 5:
                remaining = [p for p in PRODUCTS if p not in products]
                if remaining:
                    new_p = rng.choice(remaining)
                    products.add(new_p)
                    # New product adds a usage bump (not a plan change)
                    usage_bump = float(rng.uniform(8, 40)) if subtier == "Free" else float(rng.uniform(20, 150))
                    usage_mrr = min(shape["cap"], usage_mrr + usage_bump)
                    sub_rows.append({
                        "account_id": acc["account_id"],
                        "product": new_p,
                        "start_month": m,
                        "end_month": pd.NaT,
                    })

            cur_mrr = plan_mrr + usage_mrr

            # PayGo -> Enterprise (tier conversion): tenure + MRR gated
            # Only Business-tier or high-usage Pro accounts typically graduate
            tier_gate = (subtier == "Business") or (subtier == "Pro" and cur_mrr > 200)
            if segment == "PayGo" and tenure_m >= 4 and tier_gate:
                base_p = 0.015 if subtier == "Pro" else 0.04
                grad_prob = min(0.10, base_p + (cur_mrr - 100) / 8000.0)
                if plan_type == "Annual":
                    grad_prob *= 1.3
                if rng.random() < grad_prob:
                    pre_grad_mrr = cur_mrr
                    new_plan = sample_enterprise_contract(rng)
                    plan_mrr = new_plan
                    usage_mrr = new_plan * float(rng.uniform(0.05, 0.25))
                    segment = "Enterprise"
                    grad_rows.append({
                        "account_id": acc["account_id"],
                        "first_paygo_month": signup,
                        "graduation_month": m,
                        "time_to_upgrade_days": int((m - signup).days),
                        "paygo_mrr_at_graduation": float(pre_grad_mrr),
                        "enterprise_mrr_after": float(plan_mrr + usage_mrr),
                    })
                    cur_mrr = plan_mrr + usage_mrr

            # Churn hazard
            hazard = HAZARD_ANNUAL if plan_type == "Annual" else HAZARD_MONTHLY
            if segment == "Enterprise":
                hazard *= HAZARD_ENT_MULT
            if subtier == "Free":
                hazard *= 1.2  # Free tier churns slightly more
            if tenure_m > 6:
                hazard *= 0.85
            if rng.random() < hazard:
                churn_rows.append({
                    "account_id": acc["account_id"],
                    "churn_month": m,
                    "churn_reason": rng.choice(
                        CHURN_REASONS, p=[0.22, 0.18, 0.24, 0.14, 0.12, 0.10]
                    ),
                    "last_mrr": float(cur_mrr),
                    "segment_at_churn": segment,
                    "plan_type": plan_type,
                })
                mrr_rows.append({
                    "account_id": acc["account_id"],
                    "month": m,
                    "mrr": float(cur_mrr),
                    "plan_mrr": float(plan_mrr),
                    "usage_mrr": float(usage_mrr),
                    "segment": segment,
                    "paygo_subtier": subtier,
                    "n_products": len(products),
                    "plan_type": plan_type,
                    "region": acc["region"],
                })
                for sr in sub_rows:
                    if sr["account_id"] == acc["account_id"] and pd.isna(sr["end_month"]):
                        sr["end_month"] = m
                churned = True
                break

            mrr_rows.append({
                "account_id": acc["account_id"],
                "month": m,
                "mrr": float(cur_mrr),
                "plan_mrr": float(plan_mrr),
                "usage_mrr": float(usage_mrr),
                "segment": segment,
                "paygo_subtier": subtier,
                "n_products": len(products),
                "plan_type": plan_type,
                "region": acc["region"],
            })

    mrr = pd.DataFrame(mrr_rows)
    churn = pd.DataFrame(churn_rows)
    subs = pd.DataFrame(sub_rows)
    grads = pd.DataFrame(grad_rows)

    # ---- Persist denormalized fields onto accounts ----
    if not churn.empty:
        churn_first = churn.sort_values("churn_month").groupby("account_id").first()
        accounts = accounts.merge(
            churn_first[["churn_month", "churn_reason"]],
            left_on="account_id", right_index=True, how="left",
        )
    else:
        accounts["churn_month"] = pd.NaT
        accounts["churn_reason"] = pd.NA

    if not grads.empty:
        grad_first = grads.groupby("account_id").first()
        accounts = accounts.merge(
            grad_first[["graduation_month", "time_to_upgrade_days"]],
            left_on="account_id", right_index=True, how="left",
        )
    else:
        accounts["graduation_month"] = pd.NaT
        accounts["time_to_upgrade_days"] = pd.NA

    last_seg = mrr.sort_values("month").groupby("account_id")["segment"].last()
    accounts["current_segment"] = accounts["account_id"].map(last_seg).fillna("PayGo")
    accounts["is_active"] = accounts["churn_month"].isna()

    accounts.to_parquet(data_dir / "accounts.parquet", index=False)
    mrr.to_parquet(data_dir / "mrr_monthly.parquet", index=False)
    churn.to_parquet(data_dir / "churn_events.parquet", index=False)
    subs.to_parquet(data_dir / "subscriptions.parquet", index=False)
    grads.to_parquet(data_dir / "graduations.parquet", index=False)

    latest = mrr["month"].max()
    last = mrr[mrr["month"] == latest]
    total_mrr = last["mrr"].sum()
    active_now = (last["mrr"] > 0).sum()
    avg_ent_mrr = last[last["segment"] == "Enterprise"]["mrr"].mean() if (last["segment"] == "Enterprise").any() else 0.0

    print("Generated:")
    print(f"  accounts:         {len(accounts):>6}")
    print(f"  mrr rows:         {len(mrr):>6}")
    print(f"  churn events:     {len(churn):>6}")
    print(f"  subscriptions:    {len(subs):>6}")
    print(f"  graduations:      {len(grads):>6}")
    print(f"  active now:       {int(active_now):>6}")
    print(f"  total MRR (latest): ${total_mrr:>10,.0f}")
    print(f"  avg Enterprise MRR: ${avg_ent_mrr:>10,.0f}")
    print(f"\nWritten to {data_dir}/")


if __name__ == "__main__":
    main()
