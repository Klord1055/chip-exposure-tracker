import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracker.model import (SCENARIOS, Scenario, exposure_table, monte_carlo, recovery_path,
                           scenario_impact, summary_stats)

DATA = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "companies.csv")


def test_exposure_math_and_sort():
    t = exposure_table(DATA)
    nv = t[t.ticker == "NVDA"].iloc[0]
    assert nv.china_revenue_bn == pytest.approx(130.5 * 0.131)
    assert t.china_share.is_monotonic_decreasing


def test_tiers():
    t = exposure_table(DATA).set_index("ticker")
    assert t.loc["NVDA", "tier"] == "Moderate"
    assert t.loc["KLAC", "tier"] == "Severe"


def test_status_quo_has_no_loss():
    out = scenario_impact(DATA, SCENARIOS["Status quo"])
    assert out.revenue_lost_bn.sum() == 0


def test_segment_loss_rates_applied():
    s = Scenario("t", 0.5, 0.2, 0, "")
    out = scenario_impact(DATA, s).set_index("ticker")
    assert out.loc["NVDA", "loss_rate"] == 0.5
    assert out.loc["ASML", "loss_rate"] == 0.2
    assert out.loc["NVDA", "revenue_lost_bn"] == pytest.approx(130.5 * 0.131 * 0.5)


def test_value_at_risk_formula():
    out = scenario_impact(DATA, SCENARIOS["Full decoupling"], margin=0.5, multiple=20).iloc[0]
    assert out.value_at_risk_bn == pytest.approx(out.revenue_lost_bn * 0.5 * 0.85 * 20)


def test_recovery_path_declines():
    p = recovery_path(10, 0.3)
    assert p[0] == pytest.approx(9.0) and p[-1] == pytest.approx(7.0)
    assert p == sorted(p, reverse=True)


def test_monte_carlo_centers_on_scenario():
    scen = SCENARIOS["Tighter AI chip rules"]
    sims = monte_carlo(DATA, scen, n=20000)
    base = scenario_impact(DATA, scen).revenue_lost_bn.sum()
    st = summary_stats(sims)
    assert st["p5"] < base < st["p95"]
    assert abs(st["mean"] - base) / base < 0.05
