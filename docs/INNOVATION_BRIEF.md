# MandiMitra: A transparent market-choice assistant for perishable produce

**COMMIT FOR GOOD | Round 1 Innovation Brief (draft for team review)**

## 1. Problem discovery
Small-scale producers selling perishable crops must make time-sensitive marketing decisions. A market with a higher quoted/modal price may not yield the highest proceeds after transport expense and potential quality/value loss are considered. Historical market prices and arrivals are available through public data systems, but the practical decision still requires combining market signals with a farmer's own location, harvest size, and cost assumptions.

**Problem statement (hypothesis):** Small-scale sellers of perishable produce may struggle to compare nearby markets on expected net proceeds because market price information is separated from distance and seller-specific costs; this can lead to avoidable travel expense or weaker selling decisions.

This framing is intentionally narrower than claiming that poor market choice causes India's post-harvest losses. That causal link needs direct validation.

## 2. Problem validation and significance
The Ministry of Food Processing Industries reported, based on the NABCONS 2022 study, estimated post-harvest losses of 4.87–11.61% for vegetables overall; tomato was estimated at 11.61% and guava at 15.05% in the crop-level reporting. Source: PIB, 20 Dec 2022, https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1885038&lang=2&reg=48 and report https://www.mofpi.gov.in/sites/default/files/study_report_of_post_harvest_losses_0.pdf. These are broad crop-loss estimates, not evidence that MandiMitra's proposed intervention will reduce those losses.

WRI India's 2024 *Tomato Trail* study examined food loss and waste in Madhya Pradesh and identified farm and retail levels as critical loss points. It recommends improved access to information on prices, supply, demand and weather, diversification of marketing channels, and direct engagement with supply-chain stakeholders. Source: https://wri-india.org/research/tomato-trail-tracking-food-loss-and-food-waste-madhya-pradesh. This supports investigating decision-support tools, while also showing that the causes of loss are multi-factorial.

The Government of India's Open Government Data portal publishes daily market price records generated through AGMARKNET, including minimum, maximum and modal prices: https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi. Data availability, licence/terms, regional coverage and update reliability must be checked before evaluation.

**Validation still required:** interview farmers, FPO representatives or market intermediaries; determine what decisions they currently make, what information they already use, and whether travel-cost-adjusted comparisons would change their choices. The team must not present interviews as completed unless they actually occur.

## 3. Existing solutions and gap
- **AGMARKNET / OGD price records:** public market-price information helps users observe price and arrival patterns. The record itself does not automatically calculate a seller-specific net return after travel and loss assumptions. Verify current portal features before describing this as a definitive product gap.
- **e-NAM:** the Government's electronic national agriculture market connects participating APMC mandis and supports price discovery, online trading and access to market information. It is a substantial existing solution, not something MandiMitra replaces. Official overview: https://www.enam.gov.in/web/; farmer benefits: https://www.enam.gov.in/web/stakeholders-Involved/farmers.
- **Research and advisory interventions:** WRI India's Tomato Trail study recommends a broader food-systems approach and improved access to price, supply and weather information. A simple app cannot solve infrastructure, bargaining power, storage, grading, or market-access constraints.

**Proposed gap to test:** a lightweight, explainable comparison that brings historical prices, market distance, harvest quantity and explicitly adjustable cost/loss assumptions into one decision view for a specific local crop-market context. This is a hypothesis about usability and integration, not a claim that no comparable product exists. A systematic competitor scan is required before asserting novelty.

## 4. Proposed solution and AI approach
MandiMitra accepts a CSV of historical market prices and basic market distances. It estimates each market's near-term price using a transparent trailing moving average, then calculates an estimated net-return scenario:

- gross estimate = forecast modal price per quintal × harvest quantity in quintals;
- transport cost = distance × user-entered cost per kilometre;
- assumed value-loss penalty = gross estimate × user-entered loss percentage scaled linearly by distance;
- estimated net = gross estimate − transport cost − assumed value-loss penalty.

The interface ranks markets, shows the inputs and assumptions, and compares the result with simple alternatives such as nearest market and highest latest observed price. Forecast error is evaluated on chronological holdout predictions against a last-observation baseline. The first version prioritises transparent decision support over a black-box model. The moving average is a baseline and should not be called advanced AI; a more complex model is justified only if it improves performance on held-out real data.

## 5. Innovation and differentiator
The proposed differentiator is not a chatbot or a claim to predict prices perfectly. It is a small, reproducible, explainable decision workflow that turns open market observations into a seller-specific comparison and makes uncertain assumptions visible. The team will test whether this view adds value beyond price-only and distance-only choices.

## 6. Prototype, evaluation and impact measurement
The current prototype runs locally with a clearly labelled synthetic demo dataset. It supports CSV upload, data validation, market ranking, a forecast sanity check, and visible caveats. The synthetic sample exists only to test the software; it is not evidence about real market conditions.

Evaluation plan: (1) obtain and document real AGMARKNET/OGD data for one crop and a bounded set of markets; (2) use a chronological holdout to compare moving-average forecasts against the last-observation baseline; (3) compare recommendations against nearest-market and highest-latest-price heuristics across several user-defined cost scenarios; (4) run an unseen-input test; (5) seek feedback from potential users. Report estimated net-return differences as scenario outputs, not realised farmer income or reduced waste. Longer-term impact requires field trials and measurement.

## 7. AI usage declaration
AI tools assisted with brainstorming, scaffolding, documentation and test design. The team must accurately identify the tools actually used, review all output, and describe any suggestions it rejected or modified. One rejected direction was making a generic LLM chatbot the core product: the team chose a transparent calculation and ranking workflow instead. Update this declaration to reflect the team's actual work before submission.

## References
- Ministry of Food Processing Industries / PIB (2022), *Post Harvest Food Loss*. https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1885038&lang=2&reg=48
- NABCONS (2022), *Study to Determine Post Harvest Losses of Agri Produce in India*. https://www.mofpi.gov.in/sites/default/files/study_report_of_post_harvest_losses_0.pdf
- WRI India (2024), *Tomato Trail: Tracking Food Loss and Food Waste in Madhya Pradesh*. https://wri-india.org/research/tomato-trail-tracking-food-loss-and-food-waste-madhya-pradesh
- Government of India OGD, *Current Daily Price of Various Commodities from Various Markets (Mandi)*. https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi
- e-NAM, official platform overview. https://www.enam.gov.in/web/
