# Data instructions

The committed sample (`sample/demo_prices.csv`) is **synthetic**. Regenerate it with:

```bash
python data/generate_demo.py                       # seed 42, the committed file
python data/generate_demo.py --arrivals-effect 0   # same data without the planted arrivals effect
```

For real evaluation, download a suitable commodity/date/market extract from the official Government of India
OGD/AGMARKNET catalogue: https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi

Convert it to the CSV schema in the root README. Required columns: `date`, `market`, `commodity`,
`modal_price_rs_per_quintal`, `arrivals_tonnes`, and either `distance_km` or `latitude` + `longitude` (the app then asks for the seller's location).

Record: download date, filters, original filename, publisher, licence/terms, unit definitions, date coverage, market
coverage, missingness, and any transformations. Keep original raw data out of git if licensing, size, or terms make
redistribution inappropriate. See `ASSUMPTIONS.md` for every modelling assumption.
