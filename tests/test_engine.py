from pathlib import Path
import pandas as pd
from engine import validate_prices, rank_markets, evaluate_moving_average

def sample():
    return pd.read_csv(Path(__file__).parent.parent/"data/sample/demo_prices.csv")

def test_validation_and_sorting():
    df=validate_prices(sample())
    assert len(df)>0
    assert df.date.is_monotonic_increasing

def test_ranking_has_net_return_and_sorted():
    out=rank_markets(sample(),"Tomato",1000,18,2,7)
    assert "estimated_net_rs" in out.columns
    assert out.estimated_net_rs.is_monotonic_decreasing

def test_forecast_evaluation_has_holdout():
    out=evaluate_moving_average(sample(),"Tomato")
    assert out["n_test_predictions"]>0

def test_reject_invalid_quantity():
    try: rank_markets(sample(),"Tomato",0,18,2)
    except ValueError: return
    assert False, "expected ValueError"
