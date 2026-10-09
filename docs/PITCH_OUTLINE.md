# 10-minute pitch outline

1. **The decision (1 min):** A perishable crop seller needs to choose a market; headline price alone is not net proceeds.
2. **Evidence (1.5 min):** Cite MoFPI/NABCONS loss estimates and WRI Tomato Trail. State clearly that these establish the broader issue, not proof of this tool's impact.
3. **Existing ecosystem (1 min):** AGMARKNET/OGD data and e-NAM already exist; MandiMitra is a complementary decision layer, not a replacement.
4. **Live demo (3 min):** Upload or load sample data, adjust quantity and transport/loss assumptions, compare top-ranked market with nearest/highest-price baselines, show forecast holdout metrics. Start by disclosing that bundled data is synthetic.
5. **Evaluation (1 min):** Explain chronological holdout, baseline comparison, and plan to replace synthetic data with real market records. Do not report unsupported accuracy or impact claims.
6. **Impact & limitations (1 min):** Potential to improve decision quality; needs field validation, real costs, local language/usability testing and verified data.
7. **Open source & next steps (1.5 min):** Show repo, tests, licence, data provenance and contributions. Ask for a pilot partner or mentor feedback.

## Likely jury questions
- What is actually AI here? The current moving average is a transparent forecasting baseline, paired with decision optimisation; no claim of sophisticated AI until evaluated.
- Why not use e-NAM? e-NAM supports trading and price discovery; this prototype tests a complementary seller-specific cost comparison.
- Is the data real? Bundled data is synthetic and clearly marked; real-data validation remains a required next step.
- How do you know it reduces food loss? We do not claim that yet. We first measure decision outputs and conduct user validation; a field study is needed for real impact.
- What happens if forecasts are poor? Compare against the baseline and disclose uncertainty; revert to observed values and avoid recommending a market when data is inadequate.
