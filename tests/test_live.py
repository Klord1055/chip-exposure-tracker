import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracker.live import apply_live_revenue, latest_annual_revenue, parse_fred_csv, trade_change

FACTS = {"facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [
        {"start": "2023-01-30", "end": "2024-01-28", "val": 60922000000, "form": "10-K", "filed": "2024-02-21"},
        {"start": "2024-01-29", "end": "2025-01-26", "val": 130497000000, "form": "10-K", "filed": "2025-02-26"},
        {"start": "2024-10-28", "end": "2025-01-26", "val": 39331000000, "form": "10-K", "filed": "2025-02-26"},
        {"start": "2025-01-27", "end": "2025-04-27", "val": 44062000000, "form": "10-Q", "filed": "2025-05-28"}]}}}}}


def test_latest_annual_revenue_skips_quarters():
    r = latest_annual_revenue(FACTS)
    assert r["value"] == 130497000000 and r["end"] == "2025-01-26"


def test_latest_annual_revenue_ifrs_eur():
    f = {"facts": {"ifrs-full": {"Revenue": {"units": {"EUR": [
        {"start": "2024-01-01", "end": "2024-12-31", "val": 28263000000, "form": "20-F", "filed": "2025-02-12"}]}}}}}
    r = latest_annual_revenue(f)
    assert r["unit"] == "EUR" and r["value"] == 28263000000


def test_latest_annual_revenue_empty():
    assert latest_annual_revenue({}) is None


def test_parse_fred_both_headers_and_missing():
    a = parse_fred_csv("DATE,EXPCH\n2024-01-01,100\n2024-02-01,.\n2024-03-01,120\n")
    b = parse_fred_csv("observation_date,EXPCH\n2024-01-01,100\n")
    assert list(a["value"]) == [100, 120] and len(b) == 1


def test_apply_live_revenue_converts_eur_and_keeps_share():
    df = pd.DataFrame([{"ticker": "NVDA", "annual_revenue_bn": 1.0, "revenue_period": "old", "china_share": 0.13},
                       {"ticker": "ASML", "annual_revenue_bn": 1.0, "revenue_period": "old", "china_share": 0.41}])
    live = {"NVDA": {"value": 130.5e9, "unit": "USD", "end": "2025-01-26"},
            "ASML": {"value": 28e9, "unit": "EUR", "end": "2024-12-31"}}
    out = apply_live_revenue(df, live, 1.10).set_index("ticker")
    assert out.loc["NVDA", "annual_revenue_bn"] == 130.5
    assert out.loc["ASML", "annual_revenue_bn"] == pytest.approx(30.8)
    assert out.loc["ASML", "china_share"] == 0.41
    assert "live from SEC" in out.loc["NVDA", "revenue_period"]


def test_apply_live_revenue_skips_eur_without_rate():
    df = pd.DataFrame([{"ticker": "ASML", "annual_revenue_bn": 30.6, "revenue_period": "old", "china_share": 0.41}])
    out = apply_live_revenue(df, {"ASML": {"value": 28e9, "unit": "EUR", "end": "2024-12-31"}}, None)
    assert out.iloc[0]["annual_revenue_bn"] == 30.6


def test_trade_change():
    dates = pd.date_range("2020-01-01", periods=60, freq="MS")
    s = pd.DataFrame({"date": dates, "value": [100.0] * 33 + [80.0] * 27})
    r = trade_change(s, "2022-10-01")
    assert r["before"] == 1200 and r["now"] == 960 and r["change"] == pytest.approx(-0.2)
