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
| Live trade data | Monthly U.S. goods exports to and imports from China from the Federal Reserve, with each export control action marked |
| Methodology | Every formula used |

## Data

Live and free, with no API keys:

- **Annual revenue:** pulled from each company's latest 10-K or 20-F through the SEC EDGAR company facts API. ASML reports in euros, so its revenue is converted at the latest Federal Reserve exchange rate.
- **U.S. goods trade with China:** monthly exports (EXPCH) and imports (IMPCH) from FRED, the Federal Reserve Bank of St. Louis, based on Census data.

Successful pulls are cached for a day. If a source can't be reached, the app says so and uses the saved filing figures.

China shares come from each company's geographic disclosure in filings and earnings releases. The table lists the period and source for each one. The SEC's free data does not split revenue by country, so update these shares when new filings come out. Some are from a single quarter. ASML's share counts only system sales.

## Tech

Python, pandas, NumPy, Plotly, Streamlit, pytest. All logic lives in `tracker/model.py` as pure, tested functions.

## Run it locally

```
pip install -r requirements.txt
streamlit run app.py
pytest -q
```

Not investment advice. Built by Klord Fernandez Cayetano.
