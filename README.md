# MandiMitra 🌾

**A transparent market-choice assistant for perishable produce.**

MandiMitra explores whether combining historical mandi prices with transport and perishability assumptions can make market choices easier to compare for small-scale produce sellers. It is a hackathon prototype and has not been validated with farmers or live market data.

## Current status
- Runnable Streamlit prototype
- CSV upload with schema validation
- Moving-average price estimate per market
- Transparent estimated net-return calculation
- Comparison with highest-latest-price and nearest-market baselines
- Chronological forecast sanity check against a last-observation baseline
- Synthetic offline demo data, clearly labelled

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Run tests: `pytest -q`

## CSV schema
Required columns: `date`, `market`, `commodity`, `modal_price_rs_per_quintal`, `arrivals_tonnes`, `distance_km`. One row should represent one market/commodity/date. Prices are ₹/quintal; distance is km. Keep provenance and licence information for any uploaded real data.

## Data honesty
The bundled `data/sample/demo_prices.csv` is synthetic and exists only to make the demo run without internet. Do not cite it as actual mandi data or use it to decide a real sale. See `data/ASSUMPTIONS.md`. The official Government of India OGD catalogue for current daily mandi prices is at https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi. Verify download format, update date, licence/terms, and data quality before using it.

## Method
For each market, forecast price using the mean of the most recent N available observations. Estimate gross revenue from the quantity and forecast price, then subtract user-specified transport cost and a user-specified linear value-loss scenario. These assumptions are intentionally visible. Compare forecast performance chronologically against a last-observation baseline before making any accuracy claim.

## Problem hypothesis
Small-scale sellers of perishable produce may lack a simple, accessible way to compare expected net proceeds across nearby markets when price, distance, arrivals, and losses are considered together. This is a hypothesis to validate through interviews and literature; this prototype does not prove that market choice is a primary cause of post-harvest loss.

## Known limitations
- No live price feed or verified route API integration.
- No quality grade, fees, loading/unloading, buyer demand, actual spoilage curve, or market access rules.
- Historical modal prices are not guaranteed sale prices.
- Synthetic data is not evidence of real-world impact.
- Forecast is a baseline, not a sophisticated AI model; it must beat a simple baseline on held-out real data to justify further ML.
- User must independently verify prices, travel, costs, and local conditions.

## Research sources
1. Ministry of Food Processing Industries / PIB, “Post Harvest Food Loss” (20 Dec 2022): https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1885038&lang=2&reg=48
2. MoFPI / NABCONS, *Study to Determine Post Harvest Losses of Agri Produce in India* (2022): https://www.mofpi.gov.in/sites/default/files/study_report_of_post_harvest_losses_0.pdf
3. WRI India, *Tomato Trail: Tracking Food Loss and Food Waste in Madhya Pradesh* (9 Sep 2024): https://wri-india.org/research/tomato-trail-tracking-food-loss-and-food-waste-madhya-pradesh
4. Government of India Open Government Data, *Current Daily Price of Various Commodities from Various Markets (Mandi)*: https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi
5. e-NAM, official overview: https://www.enam.gov.in/web/

## Open source
MIT License. Review third-party data terms separately; this licence applies only to this project's code and original documentation.

## Hackathon checklist
- [ ] Confirm problem through at least 2–3 stakeholder conversations or credible primary research.
- [ ] Download and document a real data sample; keep original file metadata.
- [ ] Compare forecast to baseline on a chronological holdout.
- [ ] Test with a previously unseen market/date input.
- [ ] Update AI usage declaration to match actual use.
- [ ] Add team member names and real contribution/commit history; do not fabricate commits.
- [ ] Push to a public GitHub repository and add required collaborators according to the organiser's actual team-size rules.
- [ ] Record a demo video and create final slides.
