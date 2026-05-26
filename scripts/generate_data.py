"""Generate synthetic PayGo customer lifecycle data.

Produces 5 parquet files in /data:
- accounts.parquet         one row per account
- mrr_monthly.parquet      one row per (account, month) with MRR
- subscriptions.parquet    one row per (account, product, start, end)
- churn_events.parquet     one row per churn event with reason
- graduations.parquet      PayGo -> Enterprise upgrades with time-to-upgrade

Everything is synthetic. Seed pinned for reproducibility.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_ACCOUNTS = 600
START_MONTH = pd.Timestamp("2024-01-01")
END_MONTH = pd.Timestamp("2026-04-01")

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

PRODUCT_BASE_MRR = {
    "Workers": 25,
    "R2 Storage": 45,
    "Zero Trust": 38,
    "Pages": 18,
    "Stream": 60,
    "Images": 28,
    "D1": 22,
    "Queues": 24,
}

# Per-month churn hazard
HAZARD_MONTHLY = 0.030
HAZARD_ANNUAL = 0.006
HAZARD_ENT_MULT = 0.10  # Enterprise much stickier


def month_range(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="MS")


def main() -> None:
    rng = np.random.default_rng(SEED)
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    months = month_range(START_MONTH, END_MONTH)

    # ---- Accounts ----
    # Skew signups toward more recent months
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
        plan = acc["plan_type"]
        entry = acc["entry_product"]
        scale = float(np.clip(rng.lognormal(mean=0.2, sigma=0.7), 0.4, 6.0))
        cur_mrr = max(8.0, PRODUCT_BASE_MRR[entry] * scale)

        products = {entry}
        sub_rows.append(
            {
                "account_id": acc["account_id"],
                "product": entry,
                "start_month": signup,
                "end_month": pd.NaT,
            }
        )

        segment = "PayGo"
        churned = False

        for m in months:
            if m < signup:
                continue

            tenure_m = (m.year - signup.year) * 12 + (m.month - signup.month)

            # Monthly MRR drift: small positive expected value, some noise
            if segment == "PayGo":
                drift = float(rng.normal(loc=0.022, scale=0.07))
            else:
                drift = float(rng.normal(loc=0.008, scale=0.04))
            cur_mrr = max(0.0, cur_mrr * (1 + drift))

            # Cross-sell: chance to adopt new product (PayGo more dynamic)
            cross_sell_p = 0.07 if segment == "PayGo" else 0.03
            if rng.random() < cross_sell_p and len(products) < 5:
                remaining = [p for p in PRODUCTS if p not in products]
                if remaining:
                    new_p = rng.choice(remaining)
                    products.add(new_p)
                    add_mrr = float(rng.uniform(15, 55))
                    cur_mrr += add_mrr
                    sub_rows.append(
                        {
                            "account_id": acc["account_id"],
                            "product": new_p,
                            "start_month": m,
                            "end_month": pd.NaT,
                        }
                    )

            # PayGo -> Enterprise graduation: tenure + MRR gated
            if segment == "PayGo" and tenure_m >= 3 and cur_mrr > 120:
                grad_prob = min(0.22, 0.05 + (cur_mrr - 120) / 2400.0)
                if plan == "Annual":
                    grad_prob *= 1.4
                if rng.random() < grad_prob:
                    pre_grad_mrr = cur_mrr
                    jump = float(rng.uniform(2.5, 5))
                    cur_mrr = cur_mrr * jump
                    segment = "Enterprise"
                    grad_rows.append(
                        {
                            "account_id": acc["account_id"],
                            "first_paygo_month": signup,
                            "graduation_month": m,
                            "time_to_upgrade_days": int((m - signup).days),
                            "paygo_mrr_at_graduation": float(pre_grad_mrr),
                            "enterprise_mrr_after": float(cur_mrr),
                        }
                    )

            # Churn hazard
            hazard = HAZARD_ANNUAL if plan == "Annual" else HAZARD_MONTHLY
            if segment == "Enterprise":
                hazard *= HAZARD_ENT_MULT
            if tenure_m > 6:
                hazard *= 0.85
            if rng.random() < hazard:
                churn_rows.append(
                    {
                        "account_id": acc["account_id"],
                        "churn_month": m,
                        "churn_reason": rng.choice(
                            CHURN_REASONS, p=[0.22, 0.18, 0.24, 0.14, 0.12, 0.10]
                        ),
                        "last_mrr": float(cur_mrr),
                        "segment_at_churn": segment,
                        "plan_type": plan,
                    }
                )
                mrr_rows.append(
                    {
                        "account_id": acc["account_id"],
                        "month": m,
                        "mrr": float(cur_mrr),
                        "segment": segment,
                        "n_products": len(products),
                        "plan_type": plan,
                        "region": acc["region"],
                    }
                )
                for sr in sub_rows:
                    if sr["account_id"] == acc["account_id"] and pd.isna(sr["end_month"]):
                        sr["end_month"] = m
                churned = True
                break

            mrr_rows.append(
                {
                    "account_id": acc["account_id"],
                    "month": m,
                    "mrr": float(cur_mrr),
                    "segment": segment,
                    "n_products": len(products),
                    "plan_type": plan,
                    "region": acc["region"],
                }
            )

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

    print("Generated:")
    print(f"  accounts:       {len(accounts):>6}")
    print(f"  mrr rows:       {len(mrr):>6}")
    print(f"  churn events:   {len(churn):>6}")
    print(f"  subscriptions:  {len(subs):>6}")
    print(f"  graduations:    {len(grads):>6}")
    print(f"  active now:     {int(accounts['is_active'].sum()):>6}")
    print(f"\nWritten to {data_dir}/")


if __name__ == "__main__":
    main()
