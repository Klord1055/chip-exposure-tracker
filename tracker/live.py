"""Free live data, no API keys: SEC EDGAR company facts (latest annual revenue) and FRED (U.S. trade with
China, euro exchange rate). Parsing is separate from downloading so it can be tested offline. Every fetch
fails soft: callers get None and fall back to the saved filing figures."""
from __future__ import annotations

import io
from datetime import date

import pandas as pd

SEC_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
# The SEC asks automated users to identify themselves with a name and contact email.
SEC_HEADERS = {"User-Agent": "Klord Fernandez Cayetano kfernandezcayetano@gmail.com", "Accept-Encoding": "gzip, deflate"}

CIKS = {"NVDA": 1045810, "ASML": 937966, "AMAT": 6951, "LRCX": 707549, "KLAC": 319201}
REVENUE_TAGS = [("us-gaap", "Revenues", "USD"),
                ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
                ("us-gaap", "SalesRevenueNet", "USD"),
                ("ifrs-full", "Revenue", "EUR")]
ANNUAL_FORMS = {"10-K", "20-F", "40-F"}
FRED_SERIES = {"EXPCH": "U.S. goods exports to China", "IMPCH": "U.S. goods imports from China",
               "DEXUSEU": "U.S. dollars per euro"}


def latest_annual_revenue(facts: dict) -> dict | None:
    """Most recent full fiscal year revenue in a company facts JSON. Looks across the common revenue tags
    and keeps only annual report figures that cover roughly twelve months."""
    best = None
    for taxonomy, tag, unit in REVENUE_TAGS:
        rows = facts.get("facts", {}).get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit, [])
        for r in rows:
            if r.get("form") not in ANNUAL_FORMS or not r.get("start") or not r.get("end"):
                continue
            days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
            if not 340 <= days <= 380:
                continue
            cand = dict(value=float(r["val"]), unit=unit, end=r["end"], filed=r.get("filed", ""),
                        form=r["form"], tag=tag)
            if best is None or (cand["end"], cand["filed"]) > (best["end"], best["filed"]):
                best = cand
    return best


def parse_fred_csv(text: str) -> pd.DataFrame:
    """FRED CSV to a date indexed series. Handles both the DATE and observation_date header styles and the
    '.' FRED uses for missing values."""
    df = pd.read_csv(io.StringIO(text))
    date_col = df.columns[0]
    val_col = df.columns[1]
    out = pd.DataFrame({"date": pd.to_datetime(df[date_col], errors="coerce"),
                        "value": pd.to_numeric(df[val_col], errors="coerce")}).dropna()
    return out.sort_values("date").reset_index(drop=True)


def apply_live_revenue(companies: pd.DataFrame, live: dict, usd_per_eur: float | None) -> pd.DataFrame:
    """Swap in live annual revenue where the SEC returned a newer figure. China shares are left as filed,
    because the SEC's free API does not break revenue out by country."""
    out = companies.copy()
    for i, row in out.iterrows():
        rev = live.get(str(row.get("ticker", "")))
        if not rev:
            continue
        value = rev["value"]
        if rev["unit"] == "EUR":
            if not usd_per_eur:
                continue
            value *= usd_per_eur
        out.at[i, "annual_revenue_bn"] = round(value / 1e9, 2)
        label = f"FY ended {pd.Timestamp(rev['end']):%b %Y}"
        if rev["unit"] == "EUR":
            label += f" (EUR at {usd_per_eur:.2f})"
        out.at[i, "revenue_period"] = label + ", live from SEC"
    return out


def trade_change(series: pd.DataFrame, since: str = "2022-10-01") -> dict | None:
    """Trailing 12 month total now versus the 12 months before `since`."""
    if series is None or len(series) < 24:
        return None
    s = series.set_index("date")["value"]
    before = s[(s.index < since) & (s.index >= pd.Timestamp(since) - pd.DateOffset(months=12))].sum()
    now = s.iloc[-12:].sum()
    if before <= 0:
        return None
    return dict(before=before, now=now, change=now / before - 1, through=s.index[-1])


# Network calls. Kept thin so the rest is testable without the internet.
def fetch_sec_revenue(ticker: str, timeout: float = 6.0) -> dict | None:
    try:
        import requests
        r = requests.get(SEC_URL.format(cik=CIKS[ticker]), headers=SEC_HEADERS, timeout=timeout)
        r.raise_for_status()
        return latest_annual_revenue(r.json())
    except Exception:  # noqa: BLE001  any failure means fall back to filed figures
        return None


BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                 "Chrome/124.0 Safari/537.36", "Accept": "text/csv,text/plain,*/*"}
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=1&format=csvdata"


def fetch_fred(series: str, timeout: float = 6.0) -> pd.DataFrame | None:
    try:
        import requests
        r = requests.get(FRED_URL.format(series=series), timeout=timeout, headers=BROWSER_HEADERS)
        r.raise_for_status()
        out = parse_fred_csv(r.text)
        return out if len(out) else None
    except Exception:  # noqa: BLE001
        return None


def parse_ecb_fx(text: str) -> float | None:
    """Latest USD per EUR from the ECB's csvdata format (OBS_VALUE column)."""
    df = pd.read_csv(io.StringIO(text))
    if "OBS_VALUE" not in df.columns or df.empty:
        return None
    v = pd.to_numeric(df["OBS_VALUE"], errors="coerce").dropna()
    return float(v.iloc[-1]) if len(v) else None


def fetch_ecb_fx(timeout: float = 6.0) -> float | None:
    try:
        import requests
        r = requests.get(ECB_URL, timeout=timeout, headers=BROWSER_HEADERS)
        r.raise_for_status()
        return parse_ecb_fx(r.text)
    except Exception:  # noqa: BLE001
        return None


def load_snapshot(path) -> dict:
    """Saved copy of the FRED trade series, used when FRED cannot be reached. The first line is a comment
    that holds the pull date and the euro rate."""
    with open(path) as f:
        header = f.readline()
        df = pd.read_csv(f, parse_dates=["date"])
    fx = float(header.rsplit(":", 1)[1]) if ":" in header else None
    series = {s: df[["date", s]].rename(columns={s: "value"}) for s in ("EXPCH", "IMPCH")}
    return dict(series=series, fx=fx, through=df["date"].max())
