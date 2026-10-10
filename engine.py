"""MandiMitra decision engine.

Ranks markets by *estimated net proceeds* (forecast price - transport - assumed loss)
and backtests that ranking against simple baselines, using only information that
would have been available on each decision day (no look-ahead).

Design rules
------------
* One cost model.  ``rank_markets`` and ``backtest_strategies`` both call
  ``_net_return`` so the thing you demo is the thing you evaluate.
* One forecast path.  The ranking and the backtest both build a per-market snapshot
  with ``_snapshot(as_of=...)``; the backtest simply moves ``as_of`` through time.
* All cost and loss parameters are user assumptions, not measured facts.
* Demo data is synthetic.  Never treat it as live mandi prices.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

REQUIRED = {"date", "market", "commodity", "modal_price_rs_per_quintal", "arrivals_tonnes", "distance_km"}
PRICE, ARRIVALS, DISTANCE = "modal_price_rs_per_quintal", "arrivals_tonnes", "distance_km"
_NUMERIC = [PRICE, ARRIVALS, DISTANCE]
_KEYS = ["date", "market", "commodity"]

STRATEGY_LABELS = {
    "net_return": "MandiMitra (best estimated net return)",
    "nearest": "Nearest market",
    "highest_latest_price": "Highest latest quoted price",
    "highest_forecast_price": "Highest forecast price (ignores costs)",
}


# --------------------------------------------------------------------------------------
# Data validation
# --------------------------------------------------------------------------------------
def validate_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a price table and return one clean row per (date, market, commodity).

    * Missing required columns raise ``ValueError``.
    * Rows with unparseable/missing values, non-positive prices, negative arrivals or
      negative distances are dropped.
    * Several rows for the same market/commodity/day (e.g. different varieties or grades)
      are merged: price = arrivals-weighted mean (plain mean if arrivals are all zero),
      arrivals = sum, distance = first value.
    """
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in _NUMERIC:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["date", "market", "commodity", *_NUMERIC])
    out["market"] = out["market"].astype(str).str.strip()
    out["commodity"] = out["commodity"].astype(str).str.strip()
    out = out[(out["market"] != "") & (out["commodity"] != "")]
    out = out[(out[PRICE] > 0) & (out[ARRIVALS] >= 0) & (out[DISTANCE] >= 0)]
    if out.empty:
        raise ValueError("No valid price records remain after validation.")
    out["date"] = out["date"].dt.normalize()
    return _aggregate_daily(out)


def _aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    keep = ["date", "market", "commodity", PRICE, ARRIVALS, DISTANCE]
    has_status = "data_status" in df.columns
    if has_status:
        keep.append("data_status")
    df = df[keep]
    if not df.duplicated(_KEYS).any():
        return df.sort_values(["date", "market"]).reset_index(drop=True)

    work = df.assign(_pw=df[PRICE] * df[ARRIVALS])
    spec = dict(
        arr=(ARRIVALS, "sum"),
        pw=("_pw", "sum"),
        pmean=(PRICE, "mean"),
        dist=(DISTANCE, "first"),
    )
    if has_status:
        spec["status"] = ("data_status", "first")
    agg = work.groupby(_KEYS, sort=False).agg(**spec).reset_index()
    price = np.where(agg["arr"] > 0, agg["pw"] / agg["arr"].where(agg["arr"] > 0, 1.0), agg["pmean"])
    out = pd.DataFrame(
        {
            "date": agg["date"],
            "market": agg["market"],
            "commodity": agg["commodity"],
            PRICE: price,
            ARRIVALS: agg["arr"],
            DISTANCE: agg["dist"],
        }
    )
    if has_status:
        out["data_status"] = agg["status"]
    return out.sort_values(["date", "market"]).reset_index(drop=True)


def is_synthetic(df: pd.DataFrame) -> bool:
    """True if the table carries a ``data_status`` column marking any row as synthetic."""
    return "data_status" in df.columns and bool(df["data_status"].astype(str).str.contains("SYNTH", case=False).any())


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (inputs in degrees; numpy-broadcastable)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2, dtype=float) - np.asarray(lon1, dtype=float))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def add_distance_from_origin(df: pd.DataFrame, origin_lat: float, origin_lon: float, circuity: float = 1.3) -> pd.DataFrame:
    """Add ``distance_km`` from the seller's location to each market's ``latitude``/``longitude``.

    Road distance is approximated as ``circuity`` x straight-line distance. 1.3 is an
    ASSUMPTION; replace it with routed distances (OpenRouteService / OSM) when possible.
    """
    if not {"latitude", "longitude"} <= set(df.columns):
        raise ValueError("Need 'latitude' and 'longitude' columns to compute distances.")
    if circuity < 1:
        raise ValueError("circuity must be >= 1 (road distance cannot be shorter than straight-line distance).")
    out = df.copy()
    lat = pd.to_numeric(out["latitude"], errors="coerce")
    lon = pd.to_numeric(out["longitude"], errors="coerce")
    out["distance_km"] = haversine_km(origin_lat, origin_lon, lat, lon) * circuity
    return out


# --------------------------------------------------------------------------------------
# Cost model (shared by ranking and backtest)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Assumptions:
    quantity_kg: float
    transport_rs_per_km: float
    spoilage_pct_per_100km: float
    truck_capacity_kg: float = 10000.0
    round_trip: bool = False

    def __post_init__(self):
        if not self.quantity_kg > 0:
            raise ValueError("quantity_kg must be positive")
        if self.transport_rs_per_km < 0 or self.spoilage_pct_per_100km < 0:
            raise ValueError("cost and spoilage assumptions must be non-negative")
        if not self.truck_capacity_kg > 0:
            raise ValueError("truck_capacity_kg must be positive")

    @property
    def quintals(self) -> float:
        return self.quantity_kg / 100.0

    @property
    def trips(self) -> int:
        return math.ceil(self.quantity_kg / self.truck_capacity_kg)

    @property
    def legs(self) -> int:
        return 2 if self.round_trip else 1


def _net_return(price, distance_km, a: Assumptions):
    """Return (gross, transport, loss_pct, spoilage_cost, net) for a price/distance (arrays ok).

    modal price is Rs/quintal; transport = distance x Rs/km x trips x legs;
    loss % grows linearly with distance and is capped at 100.
    """
    price = np.asarray(price, dtype=float)
    distance_km = np.asarray(distance_km, dtype=float)
    gross = price * a.quintals
    transport = distance_km * a.transport_rs_per_km * a.trips * a.legs
    loss_pct = np.clip(distance_km / 100.0 * a.spoilage_pct_per_100km, 0.0, 100.0)
    spoilage = gross * loss_pct / 100.0
    return gross, transport, loss_pct, spoilage, gross - transport - spoilage


# --------------------------------------------------------------------------------------
# Per-market series + point-in-time snapshot
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Series:
    market: str
    dates: np.ndarray  # datetime64[ns], ascending
    price: np.ndarray
    arrivals: np.ndarray
    distance: np.ndarray


def _build_series(data: pd.DataFrame, commodity: str) -> list[_Series]:
    sub = data[data["commodity"].str.casefold() == str(commodity).casefold()]
    if sub.empty:
        raise ValueError(f"No records found for commodity: {commodity}")
    series = []
    for market, g in sub.groupby("market", sort=True):
        g = g.sort_values("date")
        series.append(
            _Series(
                market=str(market),
                dates=g["date"].to_numpy(dtype="datetime64[ns]"),
                price=g[PRICE].to_numpy(dtype=float),
                arrivals=g[ARRIVALS].to_numpy(dtype=float),
                distance=g[DISTANCE].to_numpy(dtype=float),
            )
        )
    return series


_SNAP_COLS = ["market", "forecast_price", "latest_price", "arrivals_tonnes", "distance_km", "observations", "days_since_last_obs"]


FORECAST_METHODS = ("ma", "last")


def _snapshot(series: list[_Series], as_of, window: int, max_stale_days: int | None, method: str = "ma") -> pd.DataFrame:
    """Per-market forecast using ONLY observations dated on or before ``as_of``.

    method "ma" = trailing moving average of the last ``window`` observations;
    method "last" = the last observed price.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if method not in FORECAST_METHODS:
        raise ValueError(f"forecast_method must be one of {FORECAST_METHODS}")
    t = np.datetime64(pd.Timestamp(as_of), "ns")
    rows = []
    for s in series:
        n = int(np.searchsorted(s.dates, t, side="right"))
        if n == 0:
            continue
        stale = int((t - s.dates[n - 1]) / np.timedelta64(1, "D"))
        lo = max(0, n - window)
        rows.append(
            {
                "market": s.market,
                "forecast_price": float(s.price[n - 1]) if method == "last" else float(s.price[lo:n].mean()),
                "latest_price": float(s.price[n - 1]),
                "arrivals_tonnes": float(s.arrivals[n - 1]),
                "distance_km": float(s.distance[n - 1]),
                "observations": n,
                "days_since_last_obs": stale,
            }
        )
    snap = pd.DataFrame(rows, columns=_SNAP_COLS)
    if max_stale_days is not None:
        snap = snap[snap["days_since_last_obs"] <= max_stale_days]
    return snap.reset_index(drop=True)


def _cost_table(snap: pd.DataFrame, a: Assumptions) -> pd.DataFrame:
    out = snap.copy()
    gross, transport, loss_pct, spoilage, net = _net_return(out["forecast_price"], out["distance_km"], a)
    out["gross_revenue_rs"] = gross
    out["transport_cost_rs"] = transport
    out["estimated_loss_pct"] = loss_pct
    out["spoilage_cost_rs"] = spoilage
    out["estimated_net_rs"] = net
    return out


def _sort_by_net(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["estimated_net_rs", "distance_km", "market"], ascending=[False, True, True]).reset_index(drop=True)


def _latest_date(series: list[_Series]):
    return max(pd.Timestamp(s.dates[-1]) for s in series)


# --------------------------------------------------------------------------------------
# Public: forecast + ranking
# --------------------------------------------------------------------------------------
def forecast_by_market(df: pd.DataFrame, commodity: str, window: int = 7, as_of=None, max_stale_days: int | None = None, forecast_method: str = "ma") -> pd.DataFrame:
    """Per-market price forecast (moving average by default): a baseline, not a claim of advanced AI."""
    series = _build_series(validate_prices(df), commodity)
    return _snapshot(series, as_of if as_of is not None else _latest_date(series), window, max_stale_days, forecast_method)


def rank_markets(
    df: pd.DataFrame,
    commodity: str,
    quantity_kg: float,
    transport_rs_per_km: float,
    spoilage_pct_per_100km: float,
    window: int = 7,
    *,
    truck_capacity_kg: float = 10000.0,
    round_trip: bool = False,
    as_of=None,
    max_stale_days: int | None = 7,
    forecast_method: str = "ma",
) -> pd.DataFrame:
    """Rank fresh markets by estimated net return.

    Adds ``break_even_price`` and ``price_margin_vs_nearest`` (Rs/quintal): the price the
    market would need to tie with the nearest market, and how far its forecast price sits
    above (+) or below (-) that. Markets whose last observation is more than
    ``max_stale_days`` before ``as_of`` are excluded (pass ``None`` to keep them).
    """
    a = Assumptions(quantity_kg, transport_rs_per_km, spoilage_pct_per_100km, truck_capacity_kg, round_trip)
    series = _build_series(validate_prices(df), commodity)
    when = as_of if as_of is not None else _latest_date(series)
    snap = _snapshot(series, when, window, max_stale_days, forecast_method)
    if snap.empty:
        raise ValueError(f"No market has an observation within {max_stale_days} days of {pd.Timestamp(when).date()} for {commodity}.")
    out = _sort_by_net(_cost_table(snap, a))

    ref = out.loc[out["distance_km"].idxmin()]  # nearest market is the reference
    denom = a.quintals * (1.0 - out["estimated_loss_pct"] / 100.0)
    needed = np.where(denom > 0, (ref["estimated_net_rs"] + out["transport_cost_rs"]) / denom.where(denom > 0, 1.0), np.inf)
    out["break_even_price"] = needed
    out["price_margin_vs_nearest"] = out["forecast_price"] - out["break_even_price"]
    return out


# --------------------------------------------------------------------------------------
# Decision-level backtest (no look-ahead)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class BacktestResult:
    daily: pd.DataFrame
    summary: pd.DataFrame
    days_evaluated: int
    days_skipped: int
    share_days_net_return_differs: float


def _block_bootstrap_ci(diff: np.ndarray, block: int = 7, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% moving-block bootstrap CI for the mean of a daily series (blocks keep serial correlation)."""
    diff = np.asarray(diff, dtype=float)
    n = len(diff)
    if n == 0:
        return (float("nan"), float("nan"))
    if n == 1:
        return (float(diff[0]), float(diff[0]))
    block = max(1, min(block, n))
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(n / block)
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]
    means = diff[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


@dataclass(frozen=True)
class _Day:
    """Everything known on one decision day, plus the price observed afterwards."""

    t: pd.Timestamp
    markets: np.ndarray  # str
    forecast: np.ndarray
    latest: np.ndarray
    distance: np.ndarray
    realised: np.ndarray


def _prepare_days(
    series: list[_Series],
    window: int,
    min_history: int,
    max_stale_days: int | None,
    outcome_window_days: int,
    forecast_method: str,
) -> tuple[list[_Day], int]:
    """Build the decision days. Independent of cost assumptions, so it can be reused across a sensitivity grid."""
    all_dates = np.unique(np.concatenate([s.dates for s in series]))
    by_market = {s.market: s for s in series}
    horizon = np.timedelta64(int(outcome_window_days), "D")
    days, skipped = [], 0
    for t in all_dates:
        snap = _snapshot(series, t, window, max_stale_days, forecast_method)
        snap = snap[snap["observations"] >= min_history].reset_index(drop=True)
        if len(snap) < 2:
            skipped += 1
            continue
        # Realised outcome: each candidate's first observation after t, within the window.
        # A day is used only if EVERY candidate has one, so all strategies are scored on the same
        # days and nothing about tomorrow's availability influences the pick.
        realised = []
        for m in snap["market"]:
            s = by_market[m]
            i = int(np.searchsorted(s.dates, t, side="right"))
            if i < len(s.dates) and (s.dates[i] - t) <= horizon:
                realised.append(float(s.price[i]))
        if len(realised) != len(snap):
            skipped += 1
            continue
        days.append(
            _Day(
                t=pd.Timestamp(t),
                markets=snap["market"].to_numpy(dtype=str),
                forecast=snap["forecast_price"].to_numpy(dtype=float),
                latest=snap["latest_price"].to_numpy(dtype=float),
                distance=snap["distance_km"].to_numpy(dtype=float),
                realised=np.asarray(realised, dtype=float),
            )
        )
    return days, skipped


def _score_days(days: list[_Day], skipped: int, a: Assumptions) -> BacktestResult:
    rows = []
    for d in days:
        net_forecast = _net_return(d.forecast, d.distance, a)[4]
        net_realised = _net_return(d.realised, d.distance, a)[4]
        # Same tie-break as the ranking: higher net, then nearer, then market name.
        pick_net = int(np.lexsort((d.markets, d.distance, -net_forecast))[0])
        picks = {
            "net_return": pick_net,
            "nearest": int(np.lexsort((d.markets, d.distance))[0]),
            "highest_latest_price": int(np.lexsort((d.markets, d.distance, -d.latest))[0]),
            "highest_forecast_price": int(np.lexsort((d.markets, d.distance, -d.forecast))[0]),
        }
        row = {"date": d.t, "n_candidates": len(d.markets), "oracle_net_rs": float(net_realised.max())}
        for k, i in picks.items():
            row[f"{k}_market"] = str(d.markets[i])
            row[f"{k}_net_rs"] = float(net_realised[i])
        rows.append(row)

    daily = pd.DataFrame(rows)
    if daily.empty:
        summary = pd.DataFrame(columns=["strategy", "label", "mean_realised_net_rs", "mean_regret_rs", "mean_gain_vs_nearest_rs", "ci_low", "ci_high", "share_days_better_than_nearest"])
        return BacktestResult(daily, summary, 0, skipped, float("nan"))

    out_rows = []
    nearest = daily["nearest_net_rs"].to_numpy()
    oracle = daily["oracle_net_rs"].to_numpy()
    for k, label in STRATEGY_LABELS.items():
        net = daily[f"{k}_net_rs"].to_numpy()
        diff = net - nearest
        lo, hi = _block_bootstrap_ci(diff)
        out_rows.append(
            {
                "strategy": k,
                "label": label,
                "mean_realised_net_rs": float(net.mean()),
                "mean_regret_rs": float((oracle - net).mean()),
                "mean_gain_vs_nearest_rs": float(diff.mean()),
                "ci_low": lo,
                "ci_high": hi,
                "share_days_better_than_nearest": float((diff > 1e-9).mean()),
            }
        )
    summary = pd.DataFrame(out_rows).set_index("strategy", drop=False)
    differs = float((daily["net_return_market"] != daily["nearest_market"]).mean())
    return BacktestResult(daily, summary, len(daily), skipped, differs)


def _backtest_series(series, a, window, min_history, max_stale_days, outcome_window_days, forecast_method="ma") -> BacktestResult:
    days, skipped = _prepare_days(series, window, min_history, max_stale_days, outcome_window_days, forecast_method)
    return _score_days(days, skipped, a)


def backtest_strategies(
    df: pd.DataFrame,
    commodity: str,
    quantity_kg: float,
    transport_rs_per_km: float,
    spoilage_pct_per_100km: float,
    window: int = 7,
    *,
    truck_capacity_kg: float = 10000.0,
    round_trip: bool = False,
    min_history: int = 14,
    max_stale_days: int | None = 7,
    outcome_window_days: int = 1,
    forecast_method: str = "ma",
) -> BacktestResult:
    """Would picking the best-estimated-net market have paid off?

    For every decision day t, each strategy picks a market using only data dated <= t.
    It is then scored on the price actually observed afterwards (first observation within
    ``outcome_window_days``), using the same cost model. Results are conditional on the cost
    assumptions you pass in; they are not measured farmer income.
    """
    a = Assumptions(quantity_kg, transport_rs_per_km, spoilage_pct_per_100km, truck_capacity_kg, round_trip)
    series = _build_series(validate_prices(df), commodity)
    return _backtest_series(series, a, window, min_history, max_stale_days, outcome_window_days, forecast_method)


def sensitivity_backtest(
    df: pd.DataFrame,
    commodity: str,
    quantity_kg: float,
    transport_values,
    spoilage_values,
    window: int = 7,
    *,
    truck_capacity_kg: float = 10000.0,
    round_trip: bool = False,
    min_history: int = 14,
    max_stale_days: int | None = 7,
    outcome_window_days: int = 1,
    forecast_method: str = "ma",
) -> pd.DataFrame:
    """Re-run the backtest over a grid of cost assumptions to see whether the conclusion survives."""
    series = _build_series(validate_prices(df), commodity)
    days, skipped = _prepare_days(series, window, min_history, max_stale_days, outcome_window_days, forecast_method)
    rows = []
    for t in transport_values:
        for s in spoilage_values:
            a = Assumptions(quantity_kg, float(t), float(s), truck_capacity_kg, round_trip)
            res = _score_days(days, skipped, a)
            if res.days_evaluated == 0:
                rows.append({"transport_rs_per_km": t, "spoilage_pct_per_100km": s, "days_evaluated": 0})
                continue
            nr = res.summary.loc["net_return"]
            rows.append(
                {
                    "transport_rs_per_km": t,
                    "spoilage_pct_per_100km": s,
                    "days_evaluated": res.days_evaluated,
                    "share_days_pick_differs_from_nearest": res.share_days_net_return_differs,
                    "mean_gain_vs_nearest_rs": nr["mean_gain_vs_nearest_rs"],
                    "ci_low": nr["ci_low"],
                    "ci_high": nr["ci_high"],
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Price-forecast checks (walk-forward, one step ahead)
# --------------------------------------------------------------------------------------
def _rmse(e) -> float:
    e = np.asarray(e, dtype=float)
    return float(np.sqrt(np.mean(e**2))) if len(e) else float("nan")


def evaluate_moving_average(df: pd.DataFrame, commodity: str, window: int = 7, min_history: int = 14) -> dict:
    """Walk-forward one-step-ahead RMSE: trailing moving average vs last observed price."""
    series = _build_series(validate_prices(df), commodity)
    actual, ma, last = [], [], []
    for s in series:
        for i in range(max(min_history, window), len(s.price)):
            actual.append(s.price[i])
            ma.append(s.price[i - window : i].mean())
            last.append(s.price[i - 1])
    actual, ma, last = map(np.asarray, (actual, ma, last))
    ma_rmse, last_rmse = _rmse(actual - ma), _rmse(actual - last)
    return {
        "n_test_predictions": int(len(actual)),
        "moving_average_rmse": ma_rmse,
        "last_value_rmse": last_rmse,
        "moving_average_beats_last_value": bool(len(actual) and ma_rmse < last_rmse),
        "note": "Walk-forward one-step-ahead evaluation on the supplied data; each prediction uses only earlier observations.",
    }


def evaluate_arrival_signal(df: pd.DataFrame, commodity: str, window: int = 7, min_history: int = 14, train_frac: float = 0.6) -> dict:
    """Do recent arrivals help predict tomorrow's price beyond the best simple baseline?

    For two base predictors (moving average and last observed price) we fit
        price_t - base_t = b0 + b1 * (arrivals_{t-1} - mean arrivals over the window)
                              + b2 * (arrivals_{t-1} - arrivals_{t-2})
    once, on the earliest ``train_frac`` of observations (pooled over markets, split by DATE),
    and score it on the later ones. To avoid crediting arrivals for effects that a simple bias
    correction already captures, the arrivals models are compared with the BEST of: last price,
    moving average, and each of those plus its own intercept. This measures THIS dataset only.
    """
    series = _build_series(validate_prices(df), commodity)
    rows = []
    for s in series:
        for i in range(max(min_history, window, 2), len(s.price)):
            rows.append(
                (
                    s.dates[i],
                    s.price[i],
                    s.price[i - window : i].mean(),
                    s.price[i - 1],
                    s.arrivals[i - 1] - s.arrivals[i - window : i].mean(),
                    s.arrivals[i - 1] - s.arrivals[i - 2],
                )
            )
    empty = {
        "n_train": 0,
        "n_test": 0,
        "last_value_rmse": float("nan"),
        "moving_average_rmse": float("nan"),
        "last_bias_corrected_rmse": float("nan"),
        "ma_bias_corrected_rmse": float("nan"),
        "last_arrivals_rmse": float("nan"),
        "ma_arrivals_rmse": float("nan"),
        "best_baseline_rmse": float("nan"),
        "best_arrivals_rmse": float("nan"),
        "improvement_vs_best_baseline_pct": float("nan"),
        "arrivals_level_coef_rs_per_tonne": float("nan"),
        "arrivals_change_coef_rs_per_tonne": float("nan"),
        "verdict": "Not enough observations to test whether arrivals help.",
    }
    if len(rows) < 40:
        return empty

    arr = pd.DataFrame(rows, columns=["date", "actual", "ma", "last", "x_level", "x_change"]).sort_values("date", kind="stable").reset_index(drop=True)
    cut = arr["date"].iloc[max(0, int(len(arr) * train_frac) - 1)]
    train = (arr["date"] <= cut).to_numpy()
    test = ~train
    if train.sum() < 20 or test.sum() < 10:
        return empty

    X = np.column_stack([np.ones(len(arr)), arr["x_level"].to_numpy(), arr["x_change"].to_numpy()])
    fits = {}
    for name in ("ma", "last"):
        y = (arr["actual"] - arr[name]).to_numpy()
        beta, *_ = np.linalg.lstsq(X[train], y[train], rcond=None)
        fits[name] = {
            "base": _rmse(y[test]),
            "bias": _rmse(y[test] - y[train].mean()),
            "arrivals": _rmse(y[test] - X[test] @ beta),
            "beta": beta,
        }
    best_baseline = min(fits["ma"]["base"], fits["ma"]["bias"], fits["last"]["base"], fits["last"]["bias"])
    best_name = min(("ma", "last"), key=lambda k: fits[k]["arrivals"])
    best_arrivals = fits[best_name]["arrivals"]
    improvement = 100.0 * (1.0 - best_arrivals / best_baseline) if best_baseline > 0 else 0.0

    if improvement >= 2.0:
        verdict = f"Arrivals add signal beyond the best simple baseline on this dataset (holdout RMSE {improvement:.1f}% lower)."
    else:
        verdict = "Arrivals do not beat the best simple baseline on this dataset; they are not used in the ranking."
    return {
        "n_train": int(train.sum()),
        "n_test": int(test.sum()),
        "last_value_rmse": fits["last"]["base"],
        "moving_average_rmse": fits["ma"]["base"],
        "last_bias_corrected_rmse": fits["last"]["bias"],
        "ma_bias_corrected_rmse": fits["ma"]["bias"],
        "last_arrivals_rmse": fits["last"]["arrivals"],
        "ma_arrivals_rmse": fits["ma"]["arrivals"],
        "best_baseline_rmse": best_baseline,
        "best_arrivals_rmse": best_arrivals,
        "improvement_vs_best_baseline_pct": float(improvement),
        "arrivals_level_coef_rs_per_tonne": float(fits[best_name]["beta"][1]),
        "arrivals_change_coef_rs_per_tonne": float(fits[best_name]["beta"][2]),
        "verdict": verdict,
    }
