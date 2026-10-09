"""MandiMitra decision engine. Uses user-provided historical market observations.
Demo data is synthetic; never treat it as live mandi prices."""
from __future__ import annotations
import pandas as pd
REQUIRED = {"date", "market", "commodity", "modal_price_rs_per_quintal", "arrivals_tonnes", "distance_km"}

def validate_prices(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED - set(df.columns)
    if missing: raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ["modal_price_rs_per_quintal", "arrivals_tonnes", "distance_km"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["date", "market", "commodity", "modal_price_rs_per_quintal", "arrivals_tonnes", "distance_km"])
    out = out[(out.modal_price_rs_per_quintal > 0) & (out.arrivals_tonnes >= 0) & (out.distance_km >= 0)]
    if out.empty: raise ValueError("No valid price records remain after validation.")
    return out.sort_values("date")

def forecast_by_market(df: pd.DataFrame, commodity: str, window: int = 7) -> pd.DataFrame:
    """Forecast with a transparent trailing moving average; this is a baseline, not a claim of advanced AI."""
    data = validate_prices(df)
    data = data[data.commodity.astype(str).str.casefold() == commodity.casefold()]
    if data.empty: raise ValueError(f"No records found for commodity: {commodity}")
    result=[]
    for market, g in data.groupby("market"):
        g=g.sort_values("date")
        latest=g.iloc[-1]
        forecast=float(g.tail(min(window,len(g)))["modal_price_rs_per_quintal"].mean())
        result.append({"market":market,"forecast_price":forecast,"latest_price":float(latest.modal_price_rs_per_quintal),"arrivals_tonnes":float(latest.arrivals_tonnes),"distance_km":float(latest.distance_km),"observations":len(g)})
    return pd.DataFrame(result)

def rank_markets(df: pd.DataFrame, commodity: str, quantity_kg: float, transport_rs_per_km: float, spoilage_pct_per_100km: float, window: int=7) -> pd.DataFrame:
    """Rank by estimated net return; all cost/loss parameters are user assumptions, not sourced facts."""
    if quantity_kg <= 0: raise ValueError("quantity_kg must be positive")
    if transport_rs_per_km < 0 or spoilage_pct_per_100km < 0: raise ValueError("cost and spoilage assumptions must be non-negative")
    out=forecast_by_market(df, commodity, window)
    out["gross_revenue_rs"] = out.forecast_price * (quantity_kg / 100.0) # modal price is per quintal
    out["transport_cost_rs"] = out.distance_km * transport_rs_per_km
    out["estimated_loss_pct"] = (out.distance_km / 100.0 * spoilage_pct_per_100km).clip(upper=100)
    out["spoilage_cost_rs"] = out.gross_revenue_rs * out.estimated_loss_pct / 100.0
    out["estimated_net_rs"] = out.gross_revenue_rs - out.transport_cost_rs - out.spoilage_cost_rs
    return out.sort_values("estimated_net_rs", ascending=False).reset_index(drop=True)

def evaluate_moving_average(df: pd.DataFrame, commodity: str, window: int=7, min_history: int=14) -> dict:
    """Chronological holdout evaluation vs last-observation baseline. No random split / leakage."""
    data=validate_prices(df)
    data=data[data.commodity.astype(str).str.casefold()==commodity.casefold()]
    actual=[]; pred_ma=[]; pred_last=[]
    for _,g in data.groupby("market"):
        vals=g.sort_values("date")["modal_price_rs_per_quintal"].tolist()
        for i in range(max(min_history,window),len(vals)):
            actual.append(vals[i]); pred_ma.append(sum(vals[i-window:i])/window); pred_last.append(vals[i-1])
    def rmse(a,p): return (sum((x-y)**2 for x,y in zip(a,p))/len(a))**0.5 if a else float("nan")
    return {"n_test_predictions":len(actual),"moving_average_rmse":rmse(actual,pred_ma),"last_value_rmse":rmse(actual,pred_last),"note":"Chronological one-step-ahead evaluation on supplied data; demo CSV is synthetic."}
