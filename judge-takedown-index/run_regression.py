"""Fit a per-judge model of card outcomes and report takedown exchange rates."""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

RESULTS_DIR = Path("results")
FEATURES = ["sig_diff", "td_diff", "ctrl_diff", "kd_diff"]
MIN_CARDS = 120
BOOTSTRAPS = 400
SEED = 126


def exchange_rate(df):
    """Takedown coefficient divided by strike coefficient, or None if the fit fails."""
    X = sm.add_constant(df[FEATURES], has_constant="add")
    try:
        model = sm.Logit(df["y"], X).fit(disp=0, maxiter=200)
    except Exception:
        return None
    b_strike = model.params["sig_diff"]
    if b_strike <= 0:
        return None
    return model.params["td_diff"] / b_strike


def bootstrap_interval(df, rng):
    rates = []
    for _ in range(BOOTSTRAPS):
        sample = df.sample(len(df), replace=True, random_state=int(rng.integers(1e9)))
        rate = exchange_rate(sample)
        if rate is not None and -50 < rate < 50:
            rates.append(rate)
    if len(rates) < 100:
        return np.nan, np.nan
    return np.percentile(rates, [2.5, 97.5])


def main():
    warnings.filterwarnings("ignore")
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(RESULTS_DIR / "judge_cards.csv", parse_dates=["DATE"])

    pooled = exchange_rate(df)
    print(f"all judges, {len(df)} cards: one takedown = {pooled:.2f} significant strikes of credit")

    rows = []
    for judge, sub in df.groupby("judge"):
        if len(sub) < MIN_CARDS:
            continue
        rate = exchange_rate(sub)
        if rate is None:
            continue
        low, high = bootstrap_interval(sub, rng)
        rows.append({
            "judge": judge,
            "cards": len(sub),
            "strikes_per_takedown": round(rate, 2),
            "ci_low": round(low, 2),
            "ci_high": round(high, 2),
            "vs_league": round(rate / pooled, 2),
            "above_league": bool(low > pooled),
            "below_league": bool(high < pooled),
        })

    table = pd.DataFrame(rows).sort_values("strikes_per_takedown", ascending=False)
    print(table.to_string(index=False))
    table.to_csv(RESULTS_DIR / "judge_takedown_index.csv", index=False)

    summary = {
        "pooled_rate": round(float(pooled), 2),
        "cards": int(len(df)),
        "judges": int(len(table)),
        "min_cards": MIN_CARDS,
        "first_event": df["DATE"].min().strftime("%B %Y"),
        "last_event": df["DATE"].max().strftime("%B %Y"),
    }
    (RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print("saved results/judge_takedown_index.csv and results/summary.json")


if __name__ == "__main__":
    main()
