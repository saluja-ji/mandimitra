"""Tests for the MandiMitra engine. Several use small hand-calculated tables so the
expected numbers can be checked with a pencil."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine import (
    Assumptions,
    add_distance_from_origin,
    backtest_strategies,
    evaluate_arrival_signal,
    evaluate_moving_average,
    forecast_by_market,
    haversine_km,
    is_synthetic,
    rank_markets,
    sensitivity_backtest,
    validate_prices,
)

ROOT = Path(__file__).parent.parent
COLS = ["date", "market", "commodity", "modal_price_rs_per_quintal", "arrivals_tonnes", "distance_km"]


def demo():
    return pd.read_csv(ROOT / "data/sample/demo_prices.csv")


def table(rows):
    return pd.DataFrame(rows, columns=COLS)


def two_market(days=20, a_price=2000.0, b_price=2300.0):
    """Near market A (10 km) and far market B (100 km) with constant prices."""
    rows = []
    for i in range(days):
        d = (pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)).date().isoformat()
        rows.append([d, "A", "Tomato", a_price, 10.0, 10.0])
        rows.append([d, "B", "Tomato", b_price, 10.0, 100.0])
    return table(rows)


# ------------------------------------------------------------------ validation
def test_validation_sorts_and_keeps_rows():
    df = validate_prices(demo())
    assert len(df) == 900
    assert df.date.is_monotonic_increasing


def test_missing_column_raises_with_name():
    with pytest.raises(ValueError, match="arrivals_tonnes"):
        validate_prices(demo().drop(columns=["arrivals_tonnes"]))


def test_bad_rows_are_dropped():
    df = two_market(days=3)
    df["modal_price_rs_per_quintal"] = df["modal_price_rs_per_quintal"].astype(object)   # allow a stray text value
    df.loc[0, "modal_price_rs_per_quintal"] = -5          # negative price
    df.loc[1, "modal_price_rs_per_quintal"] = "n/a"        # not a number
    df.loc[2, "date"] = "not a date"                       # bad date
    df.loc[3, "distance_km"] = -1                          # negative distance
    out = validate_prices(df)
    assert len(out) == len(df) - 4


def test_all_rows_invalid_raises():
    df = two_market(days=2)
    df["modal_price_rs_per_quintal"] = 0
    with pytest.raises(ValueError, match="No valid"):
        validate_prices(df)


def test_duplicate_varieties_are_merged_arrival_weighted():
    df = table([
        ["2026-01-01", "A", "Tomato", 2000.0, 30.0, 10.0],
        ["2026-01-01", "A", "Tomato", 3000.0, 10.0, 10.0],   # second variety
    ])
    out = validate_prices(df)
    assert len(out) == 1
    assert out.iloc[0]["arrivals_tonnes"] == pytest.approx(40.0)
    assert out.iloc[0]["modal_price_rs_per_quintal"] == pytest.approx((2000 * 30 + 3000 * 10) / 40)


def test_duplicates_with_zero_arrivals_use_plain_mean():
    df = table([
        ["2026-01-01", "A", "Tomato", 2000.0, 0.0, 10.0],
        ["2026-01-01", "A", "Tomato", 3000.0, 0.0, 10.0],
    ])
    assert validate_prices(df).iloc[0]["modal_price_rs_per_quintal"] == pytest.approx(2500.0)


def test_is_synthetic_flag():
    assert is_synthetic(demo())
    assert not is_synthetic(two_market(days=2))


# ------------------------------------------------------- net-return arithmetic
def test_net_return_hand_calculation():
    # 1000 kg = 10 quintals, Rs 20/km, 2% loss per 100 km, one truck, one way.
    # A: gross 2000*10 = 20000; transport 10*20 = 200; loss 0.2% = 40  -> net 19760
    # B: gross 2300*10 = 23000; transport 100*20 = 2000; loss 2% = 460 -> net 20540
    ranked = rank_markets(two_market(), "Tomato", 1000, 20, 2, window=3)
    out = ranked.set_index("market")
    assert out.loc["A", "estimated_net_rs"] == pytest.approx(19760.0)
    assert out.loc["B", "estimated_net_rs"] == pytest.approx(20540.0)
    assert list(ranked.market) == ["B", "A"]


def test_ranking_is_sorted_descending():
    out = rank_markets(demo(), "Tomato", 1000, 18, 2, 7)
    assert out.estimated_net_rs.is_monotonic_decreasing


def test_break_even_price_and_margin():
    # B ties with nearest A when B_price*10*(1-0.02) - 2000 = 19760  -> B_price = 21760/9.8
    out = rank_markets(two_market(), "Tomato", 1000, 20, 2, window=3).set_index("market")
    be = 21760 / 9.8
    assert out.loc["B", "break_even_price"] == pytest.approx(be)
    assert out.loc["B", "price_margin_vs_nearest"] == pytest.approx(2300 - be)
    assert out.loc["A", "price_margin_vs_nearest"] == pytest.approx(0.0, abs=1e-9)


def test_margin_zero_means_a_tie():
    # Price B exactly at break-even -> equal net returns.
    be = 21760 / 9.8
    out = rank_markets(two_market(b_price=be), "Tomato", 1000, 20, 2, window=3).set_index("market")
    assert out.loc["B", "estimated_net_rs"] == pytest.approx(out.loc["A", "estimated_net_rs"])


def test_truck_trips_and_round_trip_scale_transport():
    base = rank_markets(two_market(), "Tomato", 1000, 20, 2, window=3).set_index("market")
    three = rank_markets(two_market(), "Tomato", 25000, 20, 2, window=3, truck_capacity_kg=10000).set_index("market")
    assert three.loc["B", "transport_cost_rs"] == pytest.approx(base.loc["B", "transport_cost_rs"] * 3)  # ceil(2.5) trucks
    rt = rank_markets(two_market(), "Tomato", 1000, 20, 2, window=3, round_trip=True).set_index("market")
    assert rt.loc["B", "transport_cost_rs"] == pytest.approx(base.loc["B", "transport_cost_rs"] * 2)


def test_loss_percentage_is_capped_at_100():
    out = rank_markets(two_market(), "Tomato", 1000, 20, 500, window=3).set_index("market")  # 500% per 100 km
    assert out.loc["B", "estimated_loss_pct"] == pytest.approx(100.0)
    assert out.loc["B", "spoilage_cost_rs"] == pytest.approx(out.loc["B", "gross_revenue_rs"])


@pytest.mark.parametrize("args", [(0, 18, 2), (-1, 18, 2), (1000, -1, 2), (1000, 18, -1)])
def test_invalid_assumptions_raise(args):
    with pytest.raises(ValueError):
        rank_markets(demo(), "Tomato", *args)


def test_invalid_truck_capacity_raises():
    with pytest.raises(ValueError):
        Assumptions(1000, 18, 2, truck_capacity_kg=0)


def test_unknown_commodity_raises():
    with pytest.raises(ValueError, match="No records found"):
        rank_markets(demo(), "Mango", 1000, 18, 2)


def test_commodity_match_is_case_insensitive():
    assert len(rank_markets(demo(), "tomato", 1000, 18, 2)) == 5


def test_window_longer_than_history_uses_available_rows():
    df = two_market(days=3)
    out = forecast_by_market(df, "Tomato", window=14).set_index("market")
    assert out.loc["A", "forecast_price"] == pytest.approx(2000.0)
    assert out.loc["A", "observations"] == 3


def test_last_price_method():
    df = two_market(days=5)
    df.loc[df.market == "A", "modal_price_rs_per_quintal"] = [1000, 1100, 1200, 1300, 1400]
    ma = forecast_by_market(df, "Tomato", window=3).set_index("market").loc["A", "forecast_price"]
    last = forecast_by_market(df, "Tomato", window=3, forecast_method="last").set_index("market").loc["A", "forecast_price"]
    assert ma == pytest.approx((1200 + 1300 + 1400) / 3)
    assert last == pytest.approx(1400.0)
    with pytest.raises(ValueError):
        forecast_by_market(df, "Tomato", forecast_method="magic")


# ------------------------------------------------------------ staleness / as_of
def test_stale_market_is_excluded_and_all_stale_raises():
    df = two_market(days=20)
    df = df[~((df.market == "B") & (pd.to_datetime(df.date) > "2026-01-05"))]   # B stops reporting
    out = rank_markets(df, "Tomato", 1000, 20, 2, window=3, max_stale_days=7)
    assert list(out.market) == ["A"]
    kept = rank_markets(df, "Tomato", 1000, 20, 2, window=3, max_stale_days=None)
    assert set(kept.market) == {"A", "B"}
    with pytest.raises(ValueError, match="No market has an observation"):
        rank_markets(df, "Tomato", 1000, 20, 2, window=3, as_of="2026-06-01", max_stale_days=7)


def test_forecast_never_uses_data_after_as_of():
    df = two_market(days=20)
    base = forecast_by_market(df, "Tomato", window=3, as_of="2026-01-10").set_index("market")
    shocked = df.copy()
    shocked.loc[pd.to_datetime(shocked.date) > "2026-01-10", "modal_price_rs_per_quintal"] = 1.0
    again = forecast_by_market(shocked, "Tomato", window=3, as_of="2026-01-10").set_index("market")
    pd.testing.assert_frame_equal(base, again)


# ------------------------------------------------------------------- backtest
def test_backtest_scores_on_next_day_price_not_on_the_forecast():
    df = two_market(days=20)
    # Far market B crashes on 2026-01-11 (index 10). The decision on 2026-01-10 cannot know that.
    df.loc[(df.market == "B") & (df.date == "2026-01-11"), "modal_price_rs_per_quintal"] = 1000.0
    res = backtest_strategies(df, "Tomato", 1000, 20, 2, window=3, min_history=3)
    row = res.daily.set_index("date").loc[pd.Timestamp("2026-01-10")]
    assert row["net_return_market"] == "B"                       # pick made without seeing the crash
    assert row["net_return_net_rs"] == pytest.approx(1000 * 10 * 0.98 - 2000)   # 7800, scored on the crash
    assert row["nearest_net_rs"] == pytest.approx(19760.0)


def test_backtest_prefers_hub_when_it_always_pays_more_after_costs():
    res = backtest_strategies(two_market(), "Tomato", 1000, 20, 2, window=3, min_history=3)
    s = res.summary
    assert s.loc["net_return", "mean_gain_vs_nearest_rs"] == pytest.approx(20540 - 19760)
    assert res.share_days_net_return_differs == pytest.approx(1.0)
    assert s.loc["net_return", "mean_regret_rs"] == pytest.approx(0.0)
    assert s.loc["highest_latest_price", "mean_gain_vs_nearest_rs"] == pytest.approx(20540 - 19760)


def test_backtest_skips_days_where_a_candidate_has_no_next_price():
    df = two_market(days=20)
    df = df[~((df.market == "A") & (df.date == "2026-01-10"))]   # A missing on one day
    res = backtest_strategies(df, "Tomato", 1000, 20, 2, window=3, min_history=3)
    dates = set(res.daily.date)
    assert pd.Timestamp("2026-01-09") not in dates               # next day (10th) missing for A
    assert res.days_skipped > 0
    assert res.days_evaluated + res.days_skipped == 20


def test_backtest_uses_same_cost_model_as_ranking():
    a = Assumptions(1000, 20, 2)
    res = backtest_strategies(two_market(), "Tomato", 1000, 20, 2, window=3, min_history=3)
    rank = rank_markets(two_market(), "Tomato", 1000, 20, 2, window=3, as_of="2026-01-10").set_index("market")
    day = res.daily.set_index("date").loc[pd.Timestamp("2026-01-10")]
    assert day["net_return_net_rs"] == pytest.approx(rank.loc["B", "estimated_net_rs"])   # prices are constant
    assert a.trips == 1


def test_backtest_empty_when_history_too_short():
    res = backtest_strategies(two_market(days=5), "Tomato", 1000, 20, 2)
    assert res.days_evaluated == 0 and res.daily.empty


def test_backtest_on_demo_shows_mechanism_and_is_deterministic():
    r1 = backtest_strategies(demo(), "Tomato", 1000, 18, 2)
    r2 = backtest_strategies(demo(), "Tomato", 1000, 18, 2)
    pd.testing.assert_frame_equal(r1.summary, r2.summary)       # same CI: bootstrap seed is fixed
    assert 0.2 < r1.share_days_net_return_differs < 0.9           # the demo has days where distance wins AND days where the hub wins


def test_sensitivity_grid_shape():
    s = sensitivity_backtest(demo(), "Tomato", 1000, [9, 18, 27], [1, 2, 4])
    assert len(s) == 9
    assert {"mean_gain_vs_nearest_rs", "ci_low", "ci_high"} <= set(s.columns)


# ------------------------------------------------------------- forecast checks
def test_moving_average_vs_last_value_on_constant_series_is_zero_error():
    out = evaluate_moving_average(two_market(), "Tomato")
    assert out["moving_average_rmse"] == pytest.approx(0.0)
    assert out["last_value_rmse"] == pytest.approx(0.0)
    assert out["n_test_predictions"] > 0


def test_arrival_test_detects_a_planted_effect_and_does_not_invent_one(tmp_path):
    spec = importlib.util.spec_from_file_location("generate_demo", ROOT / "data" / "generate_demo.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    cols = list(gen.HEADER)
    planted = pd.DataFrame(gen.generate_rows(arrivals_effect=-3.0), columns=cols)
    none = pd.DataFrame(gen.generate_rows(arrivals_effect=0.0), columns=cols)
    assert evaluate_arrival_signal(planted, "Tomato")["improvement_vs_best_baseline_pct"] >= 2.0
    assert evaluate_arrival_signal(none, "Tomato")["improvement_vs_best_baseline_pct"] < 2.0


def test_arrival_test_handles_tiny_data():
    assert "Not enough" in evaluate_arrival_signal(two_market(days=6), "Tomato")["verdict"]


# ----------------------------------------------------------------- distances
def test_haversine_known_distance():
    # Jaipur to Delhi is roughly 235 km in a straight line.
    assert 225 < float(haversine_km(26.9124, 75.7873, 28.6139, 77.2090)) < 245
    assert float(haversine_km(10, 10, 10, 10)) == pytest.approx(0.0)


def test_add_distance_from_origin_applies_circuity():
    df = pd.DataFrame({"latitude": [28.6139], "longitude": [77.2090]})
    straight = float(haversine_km(26.9124, 75.7873, 28.6139, 77.2090))
    out = add_distance_from_origin(df, 26.9124, 75.7873, circuity=1.3)
    assert out.loc[0, "distance_km"] == pytest.approx(straight * 1.3)
    with pytest.raises(ValueError):
        add_distance_from_origin(df, 26.9, 75.8, circuity=0.9)
    with pytest.raises(ValueError):
        add_distance_from_origin(pd.DataFrame({"x": [1]}), 26.9, 75.8)


# --------------------------------------------------------- generator vs sample
def test_committed_sample_matches_generator():
    spec = importlib.util.spec_from_file_location("generate_demo", ROOT / "data" / "generate_demo.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    committed = (ROOT / "data" / "sample" / "demo_prices.csv").read_text(encoding="utf-8").splitlines()
    assert committed == gen.render_csv(gen.generate_rows()).splitlines()
