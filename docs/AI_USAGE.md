# AI usage declaration

**Status: partly complete. Each team member must finish their row before submission.**

## What AI was used for
- Brainstorming the project direction and drafting the Round 1 brief and pitch outline.
- Scaffolding the first prototype (Streamlit app, moving-average engine, basic tests, synthetic data generator).
- A code review and rewrite on 10 October 2026 (Claude, Anthropic): decision-level backtest with no look-ahead, break-even
  price, staleness filter, truck capacity, arrivals test, expanded test suite, README and assumptions documentation.

## What AI is NOT in the product
The application contains no language model and no trained machine-learning model. The forecast is a moving average (or the
last observed price); the only fitted model is a small linear regression used to test whether arrivals carry signal. A language model was
deliberately not added: an LLM wrapper would not change a selling decision.

## Per-member account (to be completed by the team)
| Member | Tools actually used | What I wrote or changed myself | Suggestions I rejected or modified |
|---|---|---|---|
| _name_ | _e.g. Claude, ChatGPT_ | _…_ | _…_ |
| _name_ | | | |
| _name_ | | | |

Every member must be able to explain every part of the code in the defence call. Do not submit this file with the table empty.
