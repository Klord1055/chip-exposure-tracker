"""Export control exposure model: how much revenue, profit and value a chip company
puts at risk when U.S. controls on China sales tighten. Pure functions, no UI."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SEGMENTS = ("Chip designer", "Equipment")


@dataclass(frozen=True)
class Scenario:
    name: str
    loss_designer: float      # share of China revenue lost by chip designers
    loss_equipment: float     # share of China revenue lost by equipment makers
    recapture: float          # share of lost revenue resold elsewhere by year 3
    description: str


SCENARIOS = {
    "Status quo": Scenario("Status quo", 0.0, 0.0, 0.0,
                           "Current rules hold. No new China revenue is lost."),
    "Tighter AI chip rules": Scenario(
        "Tighter AI chip rules", 0.50, 0.10, 0.40,
        "Licenses required for the remaining China compliant AI chips, light spillover to tools."),
    "Equipment and servicing ban": Scenario(
        "Equipment and servicing ban", 0.25, 0.60, 0.30,
        "Broad limits on selling and servicing fab tools in China, partial chip impact."),
    "Full decoupling": Scenario(
        "Full decoupling", 0.90, 0.90, 0.25,
        "Most U.S. linked China sales stop for chips and tools."),
}


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Keep rows a user can trust: a name, positive revenue, a China share between 0 and 1, a known segment."""
    out = df.copy()
    out["annual_revenue_bn"] = pd.to_numeric(out["annual_revenue_bn"], errors="coerce")
    out["china_share"] = pd.to_numeric(out["china_share"], errors="coerce")
    out = out.dropna(subset=["company", "annual_revenue_bn", "china_share", "segment"])
    out = out[out["company"].astype(str).str.strip() != ""]
    out = out[np.isfinite(out["annual_revenue_bn"]) & (out["annual_revenue_bn"] > 0) & out["china_share"].between(0, 1) & out["segment"].isin(SEGMENTS)]
    return out.reset_index(drop=True)


def breaking_point(df: pd.DataFrame, revenue_hit: float = 0.05) -> pd.DataFrame:
    """Share of China revenue a company must lose before it loses `revenue_hit` of total revenue.
    Exact: loss rate = revenue_hit / china_share. Above 100% means it cannot happen through China alone."""
    out = exposure_table(df)
    with np.errstate(divide="ignore"):
        out["breaking_point"] = np.where(out["china_share"] > 0, revenue_hit / out["china_share"], np.inf)
    return out.sort_values("breaking_point").reset_index(drop=True)


def exposure_table(df: pd.DataFrame) -> pd.DataFrame:
    """China revenue in $bn and an exposure tier for each company."""
    out = df.copy()
    out["china_revenue_bn"] = out["annual_revenue_bn"] * out["china_share"]
    out["tier"] = pd.cut(out["china_share"], [-0.01, 0.10, 0.25, 0.40, 1.0],
                         labels=["Low", "Moderate", "High", "Severe"]).astype(str)
    return out.sort_values("china_share", ascending=False).reset_index(drop=True)


def loss_rate(segment: str, scen: Scenario) -> float:
    return scen.loss_designer if segment == "Chip designer" else scen.loss_equipment


def scenario_impact(df: pd.DataFrame, scen: Scenario, margin: float = 0.45,
                    multiple: float = 25.0) -> pd.DataFrame:
    """Year 1 revenue lost, operating profit lost (at the incremental margin) and
    value at risk (profit lost x earnings multiple, after tax at 15%)."""
    out = exposure_table(df)
    out["loss_rate"] = [loss_rate(s, scen) for s in out["segment"]]
    out["revenue_lost_bn"] = out["china_revenue_bn"] * out["loss_rate"]
    out["revenue_lost_pct"] = out["revenue_lost_bn"] / out["annual_revenue_bn"]
    out["op_profit_lost_bn"] = out["revenue_lost_bn"] * margin
    out["value_at_risk_bn"] = out["op_profit_lost_bn"] * (1 - 0.15) * multiple
    return out


def recovery_path(revenue_lost_bn: float, recapture: float, years: int = 3) -> list[float]:
    """Net revenue still lost each year as sales are redirected to other regions.
    Year 1 is the full loss; recapture ramps in a straight line to its full level by the last year."""
    return [revenue_lost_bn * (1 - recapture * (y - 1) / (years - 1)) for y in range(1, years + 1)]


def monte_carlo(df: pd.DataFrame, scen: Scenario, n: int = 5000, sd: float = 0.15,
                margin: float = 0.45, seed: int = 7) -> pd.DataFrame:
    """Simulate the basket's year 1 revenue and operating profit lost when loss rates
    and China shares are uncertain. Loss rates draw from a beta around the scenario
    value; China shares wobble by +/- sd relative."""
    rng = np.random.default_rng(seed)
    exp = exposure_table(df)
    rev = np.zeros(n)
    for _, r in exp.iterrows():
        mean = loss_rate(r["segment"], scen)
        if mean <= 0:
            continue
        k = 20.0  # concentration: higher means tighter around the mean
        draws = np.ones(n) if mean >= 1 else rng.beta(mean * k, (1 - mean) * k, n)
        share = np.clip(r["china_share"] * (1 + rng.normal(0, sd, n)), 0, 1)
        rev += r["annual_revenue_bn"] * share * draws
    return pd.DataFrame({"revenue_lost_bn": rev, "op_profit_lost_bn": rev * margin})


def summary_stats(sims: pd.DataFrame) -> dict:
    r = sims["revenue_lost_bn"]
    return {"mean": float(r.mean()), "p5": float(r.quantile(0.05)),
            "p50": float(r.median()), "p95": float(r.quantile(0.95))}


POLICY_TIMELINE = pd.DataFrame([
    ("Oct 2022", "Commerce (BIS) restricts exports of advanced AI chips and chipmaking tools to China."),
    ("Oct 2023", "Rules updated to close gaps, covering cut down chips such as NVIDIA's A800 and H800."),
    ("Dec 2024", "New limits on high bandwidth memory and more chipmaking equipment, plus added entity listings."),
    ("Apr 2025", "License requirement placed on NVIDIA's H20 for China; NVIDIA flags a multibillion dollar charge."),
], columns=["Date", "Event"])
