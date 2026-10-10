# Data and assumptions

## 1. The bundled sample is synthetic
`data/sample/demo_prices.csv` is produced by `data/generate_demo.py` (seed 42) and every row has
`data_status=SYNTHETIC_DEMO`. It is NOT official market data, not live, and not evidence about real prices.
Regenerate it with `python data/generate_demo.py`. A test (`test_committed_sample_matches_generator`) fails if the
committed CSV and the script ever drift apart. Market names and distances are invented.

### Generator parameters (all invented unless stated)
| Parameter | Value | Why |
|---|---|---|
| `SEED` | 42 | reproducibility |
| Period / length | 2026-04-01, 180 days, 5 markets, 1 commodity (Tomato) | enough history for a backtest |
| `BASE_PRICE` | ₹1,900 / quintal | arbitrary starting level |
| `TREND_PER_DAY` | ₹0.13 / quintal / day | gentle upward drift |
| `WEEKLY_AMP`, `SEASONAL_AMP` | ₹4.5, ₹5.5 / quintal (7-day and 30-day sine cycles) | mild cyclical variation |
| `PRICE_NOISE_PER_UNIT` × market noise factor (0.7 to 2.1) | noise sd ₹3.5 to ₹10.5 | farther markets are noisier (a guess) |
| Market distances | 12, 20, 32, 55, 75 km | invented |
| Fixed premiums | ₹0, 8, 15, 10 / quintal | invented |
| Hub market `Varanasi Mandi` premium | ₹140 + ₹120·sin(2π·day/45) / quintal | **planted** so the best market changes over time: sometimes the nearest wins, sometimes the far hub wins |
| `ARRIVALS_MEAN`, `ARRIVALS_AMP`, `ARRIVALS_NOISE_SD` | 28 t, 8 t (14-day cycle), 4 t | invented |
| `ARRIVALS_EFFECT` | −₹3 / quintal per tonne of *previous-day* arrivals above the mean | **planted** (think unsold stock carried over) so the arrivals test can be checked |

### What the planted effects are for
They let the tests confirm that the evaluation code (a) finds an effect when one exists and (b) does not invent one
when `--arrivals-effect 0`. Recovering a planted effect shows the pipeline works. It is **not** evidence that real mandis
behave this way, and backtest numbers on this file describe the generator, not the world.

## 2. Recommendation model assumptions
- Modal price is ₹ per quintal (100 kg). Gross estimate = forecast price × quantity in quintals.
- Forecast = trailing moving average of the last N observations per market (default N = 7), or the last observed price.
  Neither is a trained or validated advanced model.
- Transport = distance × ₹/km × number of trucks × (2 if the return trip is counted). Trucks = ceil(quantity / truck capacity).
  The ₹/km figure is a user input, not a sourced rate.
- Value loss = gross × (distance / 100 × loss % per 100 km), capped at 100%. This is a linear scenario, not a biological
  spoilage model; it ignores transit time, queueing and quality grade.
- Markets with no observation in the last `max_stale_days` (default 7) are excluded from the ranking.
- Several rows for one market/commodity/day (varieties, grades) are merged: arrivals-weighted mean price, summed arrivals.
- If a CSV has market `latitude`/`longitude` but no `distance_km`, distance = straight-line distance × 1.3. The 1.3 factor
  is an assumption; use routed distances where possible.
- "Break-even price" = the price a market would need for its net return to equal the nearest market's; "margin" is the
  forecast price minus that break-even.

## 3. Evaluation assumptions
- **Forecast check:** walk-forward, one step ahead; every prediction uses only earlier observations.
- **Decision backtest:** on each day, every strategy chooses a market using only data dated on or before that day, then is
  scored on the first price observed afterwards (default: the next day), with the same cost model as the ranking. Only days
  on which every candidate market reports an outcome are scored, so all strategies face the same days.
  Results are conditional on the cost assumptions entered; they are not measured farmer income.
- **Confidence intervals:** 95% moving-block bootstrap (7-day blocks, 2,000 resamples, fixed seed) of the mean daily gain over
  the nearest market. It understates uncertainty on short or unrepresentative histories.
- **Arrivals test:** pooled regression of price minus a base predictor on previous-day arrival level and change, fitted on the
  first 60% of observations by date and scored on the rest. It must beat the best of {last price, moving average, each with
  its own intercept} by at least 2% RMSE to count as signal. It speaks about the supplied dataset only.

## 4. What real data should replace
Use an official download from the Government of India Open Government Data platform / AGMARKNET, record retrieval date
and licence/terms, retain original source metadata, and document cleaning. Do not scrape a site whose terms prohibit it.
Data portal: https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi

Things to check once you have real data:
- more than one row per market and day (variety/grade): handled by merging, but check the result looks sensible;
- reporting gaps: markets that stop reporting disappear from the ranking after `max_stale_days`;
- units (₹/quintal vs ₹/kg) and the market-name spelling across files;
- whether `distance_km` really refers to your seller's location.
