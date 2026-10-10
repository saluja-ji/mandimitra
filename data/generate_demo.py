"""Generate reproducible SYNTHETIC demonstration prices. This is not real mandi data.

Every parameter below is an invented modelling choice, documented in data/ASSUMPTIONS.md.
The generator plants two effects on purpose so the evaluation code can be tested:

1. A far "hub" market whose price premium swings over time, so that sometimes the nearest
   market is the best choice after costs and sometimes the hub is.
2. A negative effect of YESTERDAY's arrivals on today's price (ARRIVALS_EFFECT, Rs/quintal
   per tonne above the mean; think unsold stock carried over), so we can check that the
   arrivals test detects an effect when one exists (and, with --arrivals-effect 0, that it
   does not invent one).

Planting an effect shows the pipeline can recover it. It is NOT evidence that real mandis
behave this way.

Usage:  python data/generate_demo.py [--seed 42] [--days 180] [--arrivals-effect -3.0]
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
START = date(2026, 4, 1)
DAYS = 180
BASE_PRICE = 1900.0          # Rs/quintal, starting level (invented)
TREND_PER_DAY = 0.13         # Rs/quintal per day (invented)
WEEKLY_AMP = 4.5             # Rs/quintal weekly cycle amplitude (invented)
SEASONAL_AMP = 5.5           # Rs/quintal 30-day cycle amplitude (invented)
ARRIVALS_MEAN = 28.0         # tonnes/day (invented)
ARRIVALS_AMP = 8.0           # tonnes, 14-day cycle amplitude (invented)
ARRIVALS_NOISE_SD = 4.0      # tonnes (invented)
ARRIVALS_EFFECT = -3.0       # Rs/quintal per tonne of previous-day arrivals above ARRIVALS_MEAN (planted)
PRICE_NOISE_PER_UNIT = 5.0   # Rs/quintal noise sd = this x market noise factor (invented)
HUB_NAME = "Varanasi Mandi"
HUB_PREMIUM_MEAN = 140.0     # Rs/quintal (invented)
HUB_PREMIUM_AMP = 120.0      # Rs/quintal (invented)
HUB_PREMIUM_PERIOD = 45      # days (invented)

# (market, distance_km, fixed premium Rs/quintal, noise factor): ALL invented
MARKETS = [
    ("Prayagraj Mandi", 12, 0.0, 0.7),
    ("Phaphamau Mandi", 20, 8.0, 1.1),
    ("Kaushambi Mandi", 32, 15.0, 1.5),
    (HUB_NAME, 75, 0.0, 2.1),
    ("Mirzapur Mandi", 55, 10.0, 1.7),
]

HEADER = ["date", "market", "commodity", "modal_price_rs_per_quintal", "arrivals_tonnes", "distance_km", "data_status"]


def generate_rows(seed: int = SEED, days: int = DAYS, start: date = START, arrivals_effect: float = ARRIVALS_EFFECT) -> list[list]:
    rng = random.Random(seed)
    rows = []
    for mi, (market, distance, premium, noise) in enumerate(MARKETS):
        prev_arrivals = ARRIVALS_MEAN
        for i in range(days):
            day = start + timedelta(days=i)
            arrivals = max(1.0, round(ARRIVALS_MEAN + ARRIVALS_AMP * math.sin(2 * math.pi * i / 14 + mi) + rng.gauss(0, ARRIVALS_NOISE_SD), 2))
            if market == HUB_NAME:
                premium = HUB_PREMIUM_MEAN + HUB_PREMIUM_AMP * math.sin(2 * math.pi * i / HUB_PREMIUM_PERIOD)
            price = (
                BASE_PRICE
                + premium
                + TREND_PER_DAY * i
                + WEEKLY_AMP * math.sin(2 * math.pi * i / 7 + mi * 0.3)
                + SEASONAL_AMP * math.sin(2 * math.pi * i / 30 + mi * 0.5)
                + arrivals_effect * (prev_arrivals - ARRIVALS_MEAN)
                + rng.gauss(0, noise * PRICE_NOISE_PER_UNIT)
            )
            rows.append([day.isoformat(), market, "Tomato", round(max(350.0, price), 2), arrivals, distance, "SYNTHETIC_DEMO"])
            prev_arrivals = arrivals
    return rows


def render_csv(rows: list[list]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows)
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--arrivals-effect", type=float, default=ARRIVALS_EFFECT)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "sample" / "demo_prices.csv")
    args = ap.parse_args()
    rows = generate_rows(args.seed, args.days, START, args.arrivals_effect)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_csv(rows), encoding="utf-8", newline="")
    print(f"Wrote {len(rows)} synthetic rows to {args.out} (seed={args.seed})")


if __name__ == "__main__":
    main()
