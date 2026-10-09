"""Generate reproducible synthetic demonstration prices; not real mandi data."""
from datetime import date, timedelta
import csv, math, random
from pathlib import Path

SEED = 42
MARKETS = [
    ("Prayagraj Mandi", 12, 0.0, 0.7),
    ("Phaphamau Mandi", 20, 8.0, 1.1),
    ("Kaushambi Mandi", 32, 15.0, 1.5),
    ("Varanasi Mandi", 75, 22.0, 2.1),
    ("Mirzapur Mandi", 55, 10.0, 1.7),
]
START = date(2026, 7, 1)
DAYS = 90


def main():
    rng = random.Random(SEED)
    rows = []
    for mi, (market, distance, base, noise) in enumerate(MARKETS):
        for i in range(DAYS):
            day = START + timedelta(days=i)
            trend = 0.13 * i
            weekly = 4.5 * math.sin(2 * math.pi * i / 7 + mi * 0.3)
            seasonal = 5.5 * math.sin(2 * math.pi * i / 30 + mi * 0.5)
            price = max(350, round(1900 + base + trend + weekly + seasonal + rng.gauss(0, noise * 5), 2))
            arrivals = max(1, round(28 + 8 * math.sin(2 * math.pi * i / 14 + mi) + rng.gauss(0, 4), 2))
            rows.append([day.isoformat(), market, "Tomato", price, arrivals, distance, "SYNTHETIC_DEMO"])
    out = Path(__file__).parent / "sample" / "demo_prices.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "market", "commodity", "modal_price_rs_per_quintal", "arrivals_tonnes", "distance_km", "data_status"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} synthetic rows to {out}")


if __name__ == "__main__":
    main()
