from pathlib import Path
import pandas as pd
import streamlit as st
from engine import validate_prices, rank_markets, evaluate_moving_average

ROOT=Path(__file__).parent
st.set_page_config(page_title="MandiMitra", page_icon="🌾", layout="wide")
st.title("🌾 MandiMitra")
st.subheader("A transparent market-choice assistant for perishable produce")
st.warning("Demo mode: bundled prices are SYNTHETIC and for software demonstration only. They are not real or current mandi prices and must not guide an actual sale.")
st.markdown("Upload a historical price CSV or use the labelled demo data. MandiMitra compares a simple price forecast with travel and spoilage assumptions, then shows the estimated net-return trade-off.")
file=st.file_uploader("Upload historical market prices (CSV)", type=["csv"])
if file is not None:
    raw=pd.read_csv(file); source_label="Uploaded data (user supplied; verify provenance)"
else:
    raw=pd.read_csv(ROOT/"data/sample/demo_prices.csv"); source_label="Synthetic demonstration data"
try:
    data=validate_prices(raw)
    st.caption(f"Data source: {source_label} · {len(data):,} valid rows")
    commodities=sorted(data.commodity.astype(str).unique())
    commodity=st.selectbox("Commodity",commodities)
    c1,c2,c3=st.columns(3)
    with c1: quantity=st.number_input("Harvest quantity (kg)",min_value=1.0,max_value=100000.0,value=1000.0,step=100.0)
    with c2: transport=st.number_input("Transport cost (₹ per km, total trip)",min_value=0.0,value=18.0,step=1.0)
    with c3: spoil=st.number_input("Assumed value loss per 100 km (%)",min_value=0.0,max_value=100.0,value=2.0,step=0.5)
    window=st.slider("Price averaging window (observations per market)",min_value=3,max_value=14,value=7)
    ranked=rank_markets(data,commodity,quantity,transport,spoil,window)
    st.markdown("### Recommended market ranking")
    st.caption("Estimates only. Assumptions are user inputs; actual bids, quality, fees, loading costs, route conditions and market access can change the outcome.")
    show=ranked[["market","forecast_price","latest_price","distance_km","arrivals_tonnes","gross_revenue_rs","transport_cost_rs","spoilage_cost_rs","estimated_net_rs"]].copy()
    show.columns=["Market","Avg. price estimate (₹/quintal)","Latest observed (₹/quintal)","Distance (km)","Latest arrivals (tonnes)","Gross estimate (₹)","Transport estimate (₹)","Assumed loss estimate (₹)","Estimated net (₹)"]
    st.dataframe(show.style.format({c:"{:,.2f}" for c in show.columns if c!="Market"}),use_container_width=True,hide_index=True)
    best=ranked.iloc[0]
    st.success(f"Highest estimated net return under these assumptions: {best['market']} (₹{best['estimated_net_rs']:,.0f} estimated). This is not a guaranteed selling price or a live recommendation.")
    st.markdown("### Compare against simple baselines")
    b1,b2=st.columns(2)
    with b1: st.metric("Highest recent price",str(ranked.loc[ranked.latest_price.idxmax(),"market"]),f"₹{ranked.latest_price.max():,.0f}/quintal")
    with b2: st.metric("Nearest market",str(ranked.loc[ranked.distance_km.idxmin(),"market"]),f"{ranked.distance_km.min():,.0f} km")
    st.markdown("### Forecast sanity check")
    metrics=evaluate_moving_average(data,commodity,window)
    m1,m2,m3=st.columns(3)
    m1.metric("Holdout predictions",f"{metrics['n_test_predictions']:,}")
    m2.metric("Moving-average RMSE",f"₹{metrics['moving_average_rmse']:,.2f}")
    m3.metric("Last-value RMSE",f"₹{metrics['last_value_rmse']:,.2f}")
    st.caption(metrics["note"]+" Use real, cleaned historical data before drawing any real-world conclusion.")
    st.markdown("### What this prototype does not know")
    st.write("It does not observe live bids, trader demand, produce grade, mandi fees, loading/unloading, actual road disruptions, storage availability, or each farmer's selling constraints. Confirm all information locally before acting.")
except Exception as e:
    st.error(f"Could not process the uploaded CSV: {e}")
    st.markdown("Required columns: `date`, `market`, `commodity`, `modal_price_rs_per_quintal`, `arrivals_tonnes`, `distance_km`.")
