"""Chip Export Control Exposure Tracker: measure how much revenue, profit and value
U.S. chip companies put at risk as China export controls tighten."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from tracker.model import (POLICY_TIMELINE, SCENARIOS, SEGMENTS, Scenario, exposure_table,
                           monte_carlo, recovery_path, scenario_impact, summary_stats)

st.set_page_config(page_title="Chip Export Control Exposure Tracker", page_icon="🔌", layout="wide")
ROOT = Path(__file__).parent
NAVY, RED = "#1F2A44", "#C0392B"
TIER_COLORS = {"Low": "#2E8B57", "Moderate": "#C9A227", "High": "#E07B39", "Severe": RED}


@st.cache_data
def load() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "companies.csv")


st.title("Chip Export Control Exposure Tracker")
st.caption("Measures how much revenue, operating profit and market value U.S. linked chip companies put at "
           "risk as export controls on China tighten. Built as the quantitative companion to my research "
           "paper, Nvidia and the Financial Cost of U.S. China Chip Decoupling. Starting figures come from "
           "company filings and earnings releases (see the Source column); edit any of them.")

if "companies" not in st.session_state:
    st.session_state["companies"] = load()

with st.sidebar:
    st.header("Scenario")
    pick = st.selectbox("Policy scenario", list(SCENARIOS), index=1)
    base = SCENARIOS[pick]
    st.caption(base.description)
    ld = st.slider("China revenue lost, chip designers", 0.0, 1.0, base.loss_designer, 0.05)
    le = st.slider("China revenue lost, equipment makers", 0.0, 1.0, base.loss_equipment, 0.05)
    rc = st.slider("Lost sales recaptured elsewhere by year 3", 0.0, 1.0, base.recapture, 0.05)
    st.header("Financial assumptions")
    margin = st.slider("Incremental operating margin on lost sales", 0.20, 0.70, 0.45, 0.01)
    multiple = st.slider("Earnings multiple for value at risk", 10.0, 50.0, 25.0, 1.0)

scen = Scenario(pick, ld, le, rc, base.description)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Exposure", "Scenario impact", "Monte Carlo", "Policy timeline", "Methodology"])

with tab1:
    st.subheader("Who sells the most into China")
    edited = st.data_editor(
        st.session_state["companies"], num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={
            "segment": st.column_config.SelectboxColumn("segment", options=list(SEGMENTS)),
            "china_share": st.column_config.NumberColumn("china_share", min_value=0.0, max_value=1.0, format="%.3f"),
            "annual_revenue_bn": st.column_config.NumberColumn("annual_revenue_bn ($bn)", format="%.1f")},
        key="editor")
    df = edited.dropna(subset=["company", "annual_revenue_bn", "china_share", "segment"])
    exp = exposure_table(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("China revenue, all companies", f"${exp.china_revenue_bn.sum():,.1f}bn")
    c2.metric("Weighted China share", f"{exp.china_revenue_bn.sum() / exp.annual_revenue_bn.sum():.1%}")
    top = exp.iloc[0]
    c3.metric("Most exposed by share", f"{top.company} ({top.china_share:.0%})")
    a, b = st.columns(2)
    fig = px.bar(exp, x="china_share", y="company", orientation="h", color="tier",
                 color_discrete_map=TIER_COLORS, labels={"china_share": "China share of revenue", "company": ""})
    fig.update_layout(height=340, xaxis_tickformat=".0%", margin=dict(t=30, b=10), title="Share of revenue from China")
    fig.update_yaxes(categoryorder="total ascending")
    a.plotly_chart(fig, use_container_width=True)
    fig2 = px.bar(exp.sort_values("china_revenue_bn"), x="china_revenue_bn", y="company", orientation="h",
                  color_discrete_sequence=[NAVY], labels={"china_revenue_bn": "$bn", "company": ""})
    fig2.update_layout(height=340, margin=dict(t=30, b=10), title="China revenue in dollars")
    b.plotly_chart(fig2, use_container_width=True)
    st.info("Share and dollars tell different stories. Equipment makers depend on China for a far larger share "
            "of sales, while NVIDIA's dollar exposure is the largest because its total revenue is so big.")

with tab2:
    st.subheader(f"Year 1 impact: {scen.name}")
    imp = scenario_impact(df, scen, margin, multiple)
    m1, m2, m3 = st.columns(3)
    m1.metric("Revenue lost", f"${imp.revenue_lost_bn.sum():,.1f}bn")
    m2.metric("Operating profit lost", f"${imp.op_profit_lost_bn.sum():,.1f}bn")
    m3.metric("Market value at risk", f"${imp.value_at_risk_bn.sum():,.0f}bn")
    fig = px.bar(imp.sort_values("revenue_lost_pct"), x="revenue_lost_pct", y="company", orientation="h",
                 color="segment", color_discrete_sequence=[NAVY, "#8E7CC3"],
                 labels={"revenue_lost_pct": "Share of total revenue lost", "company": ""})
    fig.update_layout(height=320, xaxis_tickformat=".1%", margin=dict(t=30, b=10), title="Hit to each company's total revenue")
    st.plotly_chart(fig, use_container_width=True)
    show = imp[["company", "segment", "china_revenue_bn", "loss_rate", "revenue_lost_bn", "revenue_lost_pct",
                "op_profit_lost_bn", "value_at_risk_bn"]].rename(columns={
        "company": "Company", "segment": "Segment", "china_revenue_bn": "China revenue ($bn)",
        "loss_rate": "Loss rate", "revenue_lost_bn": "Revenue lost ($bn)", "revenue_lost_pct": "% of total revenue",
        "op_profit_lost_bn": "Op. profit lost ($bn)", "value_at_risk_bn": "Value at risk ($bn)"})
    st.dataframe(show.style.format({"China revenue ($bn)": "{:,.2f}", "Loss rate": "{:.0%}",
                                    "Revenue lost ($bn)": "{:,.2f}", "% of total revenue": "{:.1%}",
                                    "Op. profit lost ($bn)": "{:,.2f}", "Value at risk ($bn)": "{:,.1f}"}),
                 use_container_width=True, hide_index=True)

    st.subheader("Recovery path as sales are redirected")
    rows = []
    for _, r in imp.iterrows():
        for y, v in enumerate(recovery_path(r.revenue_lost_bn, scen.recapture), start=1):
            rows.append({"Year": f"Year {y}", "Company": r.company, "Net revenue lost ($bn)": v})
    path = pd.DataFrame(rows)
    fig3 = px.bar(path, x="Year", y="Net revenue lost ($bn)", color="Company", barmode="stack")
    fig3.update_layout(height=320, margin=dict(t=10, b=10))
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Compare every scenario")
    comp = []
    for s in SCENARIOS.values():
        i = scenario_impact(df, s, margin, multiple)
        comp.append({"Scenario": s.name, "Revenue lost ($bn)": i.revenue_lost_bn.sum(),
                     "Op. profit lost ($bn)": i.op_profit_lost_bn.sum(), "Value at risk ($bn)": i.value_at_risk_bn.sum()})
    st.dataframe(pd.DataFrame(comp).style.format({c: "{:,.1f}" for c in ["Revenue lost ($bn)", "Op. profit lost ($bn)", "Value at risk ($bn)"]}),
                 use_container_width=True, hide_index=True)

with tab3:
    st.subheader("How uncertain is the hit?")
    st.write("Loss rates and China shares are rarely known precisely. Each simulation draws a loss rate around "
             "the scenario value and shifts each company's China share, then adds up the revenue lost.")
    k1, k2 = st.columns(2)
    n = k1.select_slider("Simulations", [1000, 5000, 10000, 25000], 5000)
    sd = k2.slider("China share uncertainty (relative sd)", 0.0, 0.40, 0.15, 0.01)
    if scen.loss_designer == 0 and scen.loss_equipment == 0:
        st.warning("This scenario has no China revenue lost, so there is nothing to simulate. Pick another scenario.")
    else:
        sims = monte_carlo(df, scen, n=n, sd=sd, margin=margin)
        s = summary_stats(sims)
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Mean revenue lost", f"${s['mean']:,.1f}bn")
        q2.metric("Median", f"${s['p50']:,.1f}bn")
        q3.metric("5th percentile", f"${s['p5']:,.1f}bn")
        q4.metric("95th percentile", f"${s['p95']:,.1f}bn")
        h = px.histogram(sims, x="revenue_lost_bn", nbins=60, color_discrete_sequence=[NAVY],
                         labels={"revenue_lost_bn": "Basket revenue lost, year 1 ($bn)"})
        h.add_vline(x=s["p95"], line_dash="dot", line_color=RED, annotation_text="95th pct")
        h.update_layout(height=320, margin=dict(t=10, b=10), yaxis_title="Simulations")
        st.plotly_chart(h, use_container_width=True)

with tab4:
    st.subheader("Key U.S. export control actions")
    st.dataframe(POLICY_TIMELINE, use_container_width=True, hide_index=True)
    st.caption("Summary of public rule changes from the Commerce Department's Bureau of Industry and Security. "
               "The scenarios in this app stress test what the next step could cost.")

with tab5:
    st.markdown((ROOT / "HOW_IT_WORKS.md").read_text())
