# Chip Export Control Exposure Tracker

A Python and Streamlit app that measures how much revenue, operating profit and market value U.S. linked chip companies (NVIDIA, ASML, Applied Materials, Lam Research, KLA) put at risk as export controls on China tighten. It runs policy scenarios, shows a three year recovery path as sales are redirected, and uses Monte Carlo simulation to show how wide the range of outcomes is.

**Live demo:** https://klord-chip-exposure.streamlit.app

## Why I built it

I wrote a research paper, *Nvidia and the Financial Cost of U.S. China Chip Decoupling*, on what export controls cost NVIDIA and the wider chip supply chain. The paper argues the point in words; this app puts numbers on it. Pick a scenario, change any assumption, and see who loses the most in dollars and as a share of their business.

## What it does

| Tab | Output |
|---|---|
| Exposure | Editable company table, China share and China dollars by company, exposure tiers |
| Breaking point | How much China business each company can lose before it costs a material share of total revenue |
| Scenario impact | Revenue, operating profit and market value at risk, per company hit, three year recovery path, all scenarios side by side |
| Monte Carlo | Distribution of basket revenue lost with 5th to 95th percentile range |
| Policy timeline | Key U.S. export control actions since 2022 |
| Methodology | Every formula used |

## Data

Starting figures come from company 10-K filings, annual results and earnings releases dated 2024 to early 2025. The table lists the revenue period, the China share period and the source for each company. Periods differ (some China shares are from a single quarter), and ASML's China share is of system sales only, so update the table with the latest filings before relying on any number.

## Tech

Python, pandas, NumPy, Plotly, Streamlit, pytest. All logic lives in `tracker/model.py` as pure, tested functions.

## Run it locally

```
pip install -r requirements.txt
streamlit run app.py
pytest -q
```

Not investment advice. Built by Klord Fernandez Cayetano.
