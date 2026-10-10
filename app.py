"""MandiMitra Streamlit app: compare markets by estimated net proceeds, then check whether
that ranking would have paid off on the supplied history (backtest)."""
from pathlib import Path

import pandas as pd
import streamlit as st

from engine import (
    STRATEGY_LABELS,
    add_distance_from_origin,
    backtest_strategies,
    evaluate_arrival_signal,
    evaluate_moving_average,
    is_synthetic,
    rank_markets,
    sensitivity_backtest,
    validate_prices,
)

ROOT = Path(__file__).parent
st.set_page_config(page_title="MandiMitra", page_icon="🌾", layout="wide")


def show_table(df, **kwargs):
    """st.dataframe across Streamlit versions (the stretch-width argument was renamed)."""
    for extra in ({"width": "stretch"}, {"use_container_width": True}, {}):
        try:
            return st.dataframe(df, hide_index=True, **extra, **kwargs)
        except TypeError:
            continue


st.title("🌾 MandiMitra")
st.subheader("A transparent market-choice assistant for perishable produce")
st.markdown(
    "Upload a historical price CSV or use the labelled demo data. MandiMitra compares a simple price forecast with "
    "transport and loss assumptions, shows the estimated net-return trade-off, and then **backtests** whether that "
    "ranking would have beaten simple rules on the history you supplied."
)

file = st.file_uploader("Upload historical market prices (CSV)", type=["csv"])
if file is not None:
    raw = pd.read_csv(file)
    source_label = "Uploaded data (user supplied; verify provenance)"
else:
    raw = pd.read_csv(ROOT / "data/sample/demo_prices.csv")
    source_label = "Synthetic demonstration data"

if is_synthetic(raw):
    st.warning(
        "SYNTHETIC DATA: these prices are generated for software demonstration only (see data/ASSUMPTIONS.md). "
        "They are not real or current mandi prices and must not guide an actual sale. Backtest numbers below describe "
        "the generator, not the world."
    )
else:
    st.info("Using uploaded data. Verify its source, units and coverage before drawing conclusions.")

try:
    if "distance_km" not in raw.columns and {"latitude", "longitude"} <= set(raw.columns):
        st.markdown("**Your CSV has market coordinates but no distances. Enter the seller's location:**")
        o1, o2, o3 = st.columns(3)
        with o1:
            origin_lat = st.number_input("Seller latitude", value=26.9124, format="%.4f")
        with o2:
            origin_lon = st.number_input("Seller longitude", value=75.7873, format="%.4f")
        with o3:
            circuity = st.number_input("Road-to-straight-line factor (assumption)", min_value=1.0, value=1.3, step=0.05)
        raw = add_distance_from_origin(raw, origin_lat, origin_lon, circuity)

    data = validate_prices(raw)
    st.caption(f"Data source: {source_label} · {len(data):,} valid market-days · {data.market.nunique()} markets")
    commodity = st.selectbox("Commodity", sorted(data.commodity.astype(str).unique()))

    c1, c2, c3 = st.columns(3)
    with c1:
        quantity = st.number_input("Harvest quantity (kg)", min_value=1.0, max_value=100000.0, value=1000.0, step=100.0)
        truck = st.number_input("Truck capacity (kg)", min_value=100.0, value=10000.0, step=500.0)
    with c2:
        transport = st.number_input("Transport cost (₹ per km per truck, one way)", min_value=0.0, value=18.0, step=1.0)
        round_trip = st.checkbox("Count the return trip too", value=False)
    with c3:
        spoil = st.number_input("Assumed value loss per 100 km (%)", min_value=0.0, max_value=100.0, value=2.0, step=0.5)
        max_stale = st.slider("Ignore markets with no price in the last (days)", min_value=1, max_value=30, value=7)

    d1, d2 = st.columns(2)
    with d1:
        window = st.slider("Price averaging window (observations per market)", min_value=3, max_value=14, value=7)
    with d2:
        method_label = st.radio("Price forecast", ["Moving average", "Last observed price"], horizontal=True)
    method = "ma" if method_label == "Moving average" else "last"

    common = dict(truck_capacity_kg=truck, round_trip=round_trip, max_stale_days=max_stale, forecast_method=method)

    # ----------------------------------------------------------------- ranking
    ranked = rank_markets(data, commodity, quantity, transport, spoil, window, **common)
    st.markdown("### Recommended market ranking")
    st.caption(
        "Estimates only. Assumptions are user inputs; actual bids, quality, fees, loading costs, route conditions and "
        "market access can change the outcome. 'Margin vs nearest' is how many ₹/quintal a market's forecast price sits "
        "above (+) or below (−) the price it would need to tie with the nearest market."
    )
    show = ranked[
        ["market", "forecast_price", "latest_price", "days_since_last_obs", "distance_km", "arrivals_tonnes",
         "gross_revenue_rs", "transport_cost_rs", "spoilage_cost_rs", "estimated_net_rs", "price_margin_vs_nearest"]
    ].copy()
    show.columns = [
        "Market", "Price estimate (₹/quintal)", "Latest observed (₹/quintal)", "Days since last price", "Distance (km)",
        "Latest arrivals (tonnes)", "Gross estimate (₹)", "Transport estimate (₹)", "Assumed loss (₹)",
        "Estimated net (₹)", "Margin vs nearest (₹/quintal)",
    ]
    show_table(show.style.format({c: "{:,.2f}" for c in show.columns if c != "Market"}))
    best = ranked.iloc[0]
    st.success(
        f"Highest estimated net return under these assumptions: {best['market']} (₹{best['estimated_net_rs']:,.0f}). "
        "This is not a guaranteed selling price or a live recommendation."
    )
    excluded = set(data[data.commodity.str.casefold() == commodity.casefold()].market) - set(ranked.market)
    if excluded:
        st.caption("Excluded as stale (no recent price): " + ", ".join(sorted(excluded)))

    b1, b2 = st.columns(2)
    with b1:
        st.metric("Highest recent price", str(ranked.loc[ranked.latest_price.idxmax(), "market"]), f"₹{ranked.latest_price.max():,.0f}/quintal")
    with b2:
        st.metric("Nearest market", str(ranked.loc[ranked.distance_km.idxmin(), "market"]), f"{ranked.distance_km.min():,.0f} km")

    # ---------------------------------------------------------------- backtest
    st.markdown("### Would this ranking have paid off? (backtest)")
    st.caption(
        "Each day, every strategy picks a market using only earlier data, then is scored on the next price actually "
        "observed, with the same cost assumptions as above. Only days on which every candidate market reported "
        "are scored, so all strategies face the same days."
    )
    bt = backtest_strategies(data, commodity, quantity, transport, spoil, window, **common)
    if bt.days_evaluated == 0:
        st.info("Not enough overlapping history to run the backtest (needs at least 14 observations per market and next-day prices).")
    else:
        s = bt.summary
        view = s[["label", "mean_realised_net_rs", "mean_regret_rs", "mean_gain_vs_nearest_rs", "ci_low", "ci_high", "share_days_better_than_nearest"]].copy()
        view.columns = ["Strategy", "Mean realised net (₹)", "Mean regret vs best hindsight pick (₹)", "Mean gain vs nearest (₹)", "95% CI low", "95% CI high", "Share of days better than nearest"]
        show_table(view.style.format({c: "{:,.1f}" for c in view.columns[1:6]} | {"Share of days better than nearest": "{:.0%}"}))
        nr = s.loc["net_return"]
        st.write(
            f"Over **{bt.days_evaluated}** scored days ({bt.days_skipped} skipped), the net-return pick differed from the nearest market on "
            f"**{bt.share_days_net_return_differs:.0%}** of days. Mean gain vs nearest: **₹{nr.mean_gain_vs_nearest_rs:,.0f}** per lot "
            f"(95% block-bootstrap CI ₹{nr.ci_low:,.0f} to ₹{nr.ci_high:,.0f})."
        )
        if nr.ci_low <= 0 <= nr.ci_high:
            st.warning("The interval includes zero: on this data the ranking is not distinguishable from simply going to the nearest market.")
        st.caption("The interval comes from a block bootstrap over days; it understates uncertainty if the history is short or unrepresentative. Results are conditional on the cost assumptions entered above.")

        with st.expander("Sensitivity: does the conclusion survive different cost assumptions?"):
            tv = sorted({round(transport * f, 2) for f in (0.5, 1.0, 1.5)})
            sv = sorted({round(spoil * f, 2) for f in (0.5, 1.0, 2.0)})
            sens = sensitivity_backtest(data, commodity, quantity, tv, sv, window, **common)
            show_table(sens)

    # ------------------------------------------------------------ forecast checks
    st.markdown("### Forecast sanity checks")
    metrics = evaluate_moving_average(data, commodity, window)
    m1, m2, m3 = st.columns(3)
    m1.metric("Walk-forward predictions", f"{metrics['n_test_predictions']:,}")
    m2.metric("Moving-average RMSE", f"₹{metrics['moving_average_rmse']:,.2f}")
    m3.metric("Last-value RMSE", f"₹{metrics['last_value_rmse']:,.2f}")
    if not metrics["moving_average_beats_last_value"]:
        st.warning("The moving average did NOT beat the last-observed-price baseline on this data. Consider the 'Last observed price' forecast.")
    sig = evaluate_arrival_signal(data, commodity, window)
    st.markdown("**Do arrivals help predict price?** " + sig["verdict"])
    if sig["n_test"]:
        st.caption(
            f"Holdout RMSE (₹/quintal): best simple baseline {sig['best_baseline_rmse']:.2f} vs best arrivals model {sig['best_arrivals_rmse']:.2f} "
            f"({sig['n_train']} training / {sig['n_test']} test observations). Arrivals are not used in the ranking."
        )
    st.caption(metrics["note"] + " Use real, cleaned historical data before drawing any real-world conclusion.")

    st.markdown("### What this prototype does not know")
    st.write(
        "It does not observe live bids, trader demand, produce grade, mandi fees, loading/unloading, actual road disruptions, "
        "storage availability, or each farmer's selling constraints. Confirm all information locally before acting."
    )
except Exception as e:  # noqa: BLE001 - show the problem to the user instead of a stack trace
    st.error(f"Could not process the data: {e}")
    st.markdown(
        "Required columns: `date`, `market`, `commodity`, `modal_price_rs_per_quintal`, `arrivals_tonnes`, and either `distance_km` "
        "or `latitude` + `longitude`. Optional: `data_status` (rows containing 'SYNTHETIC' trigger the synthetic-data warning)."
    )
