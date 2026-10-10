"""Command-line decision backtest: would ranking markets by estimated net return have beaten
simple rules on this price history?

Example:
    python backtest.py --csv data/sample/demo_prices.csv --commodity Tomato --quantity-kg 1000 \
        --transport 18 --spoilage 2 --sensitivity --out results/backtest_daily.csv

Results are conditional on the cost assumptions you pass in. On the bundled synthetic CSV they
describe the data generator, not the world.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from engine import (
    STRATEGY_LABELS,
    backtest_strategies,
    evaluate_arrival_signal,
    evaluate_moving_average,
    is_synthetic,
    sensitivity_backtest,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest market-selection strategies on a price history CSV.")
    ap.add_argument("--csv", type=Path, default=Path(__file__).parent / "data/sample/demo_prices.csv")
    ap.add_argument("--commodity", default="Tomato")
    ap.add_argument("--quantity-kg", type=float, default=1000.0)
    ap.add_argument("--transport", type=float, default=18.0, help="Rs per km per truck, one way")
    ap.add_argument("--spoilage", type=float, default=2.0, help="assumed value loss, percent per 100 km")
    ap.add_argument("--truck-kg", type=float, default=10000.0)
    ap.add_argument("--round-trip", action="store_true")
    ap.add_argument("--window", type=int, default=7)
    ap.add_argument("--max-stale-days", type=int, default=7)
    ap.add_argument("--outcome-window-days", type=int, default=1, help="use first price within this many days after the decision")
    ap.add_argument("--sensitivity", action="store_true", help="also sweep transport and loss assumptions")
    ap.add_argument("--out", type=Path, default=None, help="write the per-day results to this CSV")
    args = ap.parse_args()

    raw = pd.read_csv(args.csv)
    print(f"Data: {args.csv} ({'SYNTHETIC' if is_synthetic(raw) else 'user-supplied, verify provenance'})")
    print(f"Assumptions: {args.quantity_kg:g} kg of {args.commodity}, Rs {args.transport:g}/km/truck, "
          f"{args.spoilage:g}% loss per 100 km, truck {args.truck_kg:g} kg, round trip: {args.round_trip}\n")

    common = dict(
        truck_capacity_kg=args.truck_kg,
        round_trip=args.round_trip,
        max_stale_days=args.max_stale_days,
        outcome_window_days=args.outcome_window_days,
    )
    last_daily = None
    for method, name in (("ma", f"{args.window}-observation moving average"), ("last", "last observed price")):
        res = backtest_strategies(raw, args.commodity, args.quantity_kg, args.transport, args.spoilage, args.window, forecast_method=method, **common)
        print(f"=== Forecast used by the net-return strategy: {name}")
        if res.days_evaluated == 0:
            print("Not enough overlapping history to evaluate.\n")
            continue
        view = res.summary[["label", "mean_realised_net_rs", "mean_regret_rs", "mean_gain_vs_nearest_rs", "ci_low", "ci_high", "share_days_better_than_nearest"]]
        print(view.round(1).to_string(index=False))
        print(f"\ndays scored: {res.days_evaluated}, skipped: {res.days_skipped}; "
              f"net-return pick differs from nearest on {res.share_days_net_return_differs:.0%} of days\n")
        if method == "ma":
            last_daily = res.daily

    ma = evaluate_moving_average(raw, args.commodity, args.window)
    print("=== One-step-ahead price forecast check (RMSE, Rs/quintal)")
    print(f"moving average {ma['moving_average_rmse']:.2f} vs last value {ma['last_value_rmse']:.2f} "
          f"({ma['n_test_predictions']} predictions) -> moving average beats last value: {ma['moving_average_beats_last_value']}")
    sig = evaluate_arrival_signal(raw, args.commodity, args.window)
    print(f"arrivals: {sig['verdict']}")
    if sig["n_test"]:
        print(f"best simple baseline {sig['best_baseline_rmse']:.2f} vs best arrivals model {sig['best_arrivals_rmse']:.2f} "
              f"({sig['n_train']} train / {sig['n_test']} test)\n")

    if args.sensitivity:
        print("=== Sensitivity of 'net return vs nearest' to cost assumptions (moving-average forecast)")
        sens = sensitivity_backtest(
            raw, args.commodity, args.quantity_kg,
            sorted({round(args.transport * f, 2) for f in (0.5, 1.0, 1.5)}),
            sorted({round(args.spoilage * f, 2) for f in (0.5, 1.0, 2.0)}),
            args.window, **common,
        )
        print(sens.round(2).to_string(index=False))

    if args.out and last_daily is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        last_daily.to_csv(args.out, index=False)
        print(f"\nPer-day results written to {args.out}")


if __name__ == "__main__":
    main()
