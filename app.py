"""Chip Export Control Exposure Tracker: how much revenue, profit and value chip companies put at risk
as U.S. export controls on China tighten, and how much policy each one can absorb."""
import html
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tracker.model import (POLICY_TIMELINE, SCENARIOS, SEGMENTS, Scenario, breaking_point, clean, exposure_table,
                           monte_carlo, recovery_path, scenario_impact, summary_stats)
from ui import intro, note, GOLD, GREEN, NAVY, RED, setup, takeaway

st.set_page_config(page_title="Chip Export Control Exposure Tracker", page_icon="🔌", layout="wide")
setup()
W = "stretch"
ROOT = Path(__file__).parent
TIER_COLORS = {"Low": GREEN, "Moderate": GOLD, "High": "#C25E00", "Severe": RED}
SEG_COLORS = {"Chip designer": NAVY, "Equipment": "#6B4FA8"}


@st.cache_data
def load() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "companies.csv")


def reset():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


with st.sidebar:
    st.button("Reset to defaults", on_click=reset, width=W)
    st.header("1. Policy scenario")
    pick = st.selectbox("Scenario", list(SCENARIOS), index=1, key="scen",
                        help="Each scenario sets how much China revenue chip designers and equipment makers lose.")
    base = SCENARIOS[pick]
    st.markdown(f"<div style='color:#2B2F36;font-size:0.95rem'>{base.description}</div>", unsafe_allow_html=True)
    k = f"_{pick}"
    ld = st.slider("China sales lost, chip designers", 0, 100, int(base.loss_designer * 100), 5, format="%d%%", key="ld" + k,
                   help="Share of each chip designer's China revenue that disappears in year 1.") / 100
    le = st.slider("China sales lost, equipment makers", 0, 100, int(base.loss_equipment * 100), 5, format="%d%%", key="le" + k,
                   help="Share of each equipment maker's China revenue that disappears in year 1.") / 100
    rc = st.slider("Lost sales resold elsewhere by year 3", 0, 100, int(base.recapture * 100), 5, format="%d%%", key="rc" + k,
                   help="How much of the lost revenue the companies win back from customers in other countries.") / 100
    st.header("2. Financial assumptions")
    margin = st.slider("Operating margin on lost sales", 20, 70, 45, 1, format="%d%%", key="margin",
                       help="Lost sales cost more profit than average sales because fixed costs stay.") / 100
    multiple = st.slider("Earnings multiple", 10.0, 50.0, 25.0, 1.0, format="%.0fx", key="multiple",
                         help="Converts lost yearly profit into lost market value.")
    st.header("3. Breaking point")
    hit = st.slider("Revenue loss you call material", 1, 20, 5, 1, format="%d%%", key="hit",
                    help="The share of total revenue a company could lose before you treat the hit as serious.") / 100

scen = Scenario(pick, ld, le, rc, base.description)
if "companies" not in st.session_state:
    st.session_state["companies"] = load()
df = clean(st.session_state["companies"])

st.title("Chip Export Control Exposure Tracker")
intro("How much revenue, operating profit and market value chip companies put at risk as U.S. export controls on "
           "China tighten. Built as the quantitative companion to my research paper, Nvidia and the Financial Cost of "
           "U.S. China Chip Decoupling. Starting figures come from company filings and earnings releases dated 2024 to early 2025 (see the Period columns); edit any of them.")

if df.empty:
    st.error("The company table has no usable rows. Each row needs a name, a segment, revenue above zero and a China share "
             "between 0 and 1. Press Reset to defaults in the left panel to restore the starting data.")
    st.stop()

imp = scenario_impact(df, scen, margin, multiple)
bp = breaking_point(df, hit)
worst = imp.sort_values("revenue_lost_pct", ascending=False).iloc[0]
total_lost = imp.revenue_lost_bn.sum()
crossed = bp[bp["breaking_point"] <= bp["segment"].map({"Chip designer": ld, "Equipment": le})]

if total_lost > 0:
    detail = (f"Hardest hit: <b>{html.escape(str(worst.company))}</b>, losing <b>{worst.revenue_lost_pct:.1%}</b> of total revenue. "
              f"<b>{len(crossed)} of {len(bp)}</b> companies lose more than {hit:.0%} of total revenue.")
else:
    detail = "No China revenue is lost in this scenario. Pick a tighter scenario or move the sliders to test one."
st.markdown(
    f"<div style='padding:16px 20px;border-radius:10px;border:2px solid {NAVY};background:#FFFFFF'>"
    f"<div style='font-size:15px;color:#2B2F36;font-weight:600'>SCENARIO: {html.escape(pick.upper())}</div>"
    f"<div style='font-size:30px;font-weight:800;color:{NAVY};line-height:1.25'>${total_lost:,.1f}bn of revenue at risk in year 1</div>"
    f"<div style='font-size:18px;color:#111'>{detail}</div></div>", unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Revenue lost, year 1", f"${total_lost:,.1f}bn")
m2.metric("Operating profit lost", f"${imp.op_profit_lost_bn.sum():,.1f}bn")
m3.metric("Market value at risk", f"${imp.value_at_risk_bn.sum():,.1f}bn",
          help="Year 1 profit lost, after 15% tax, times the earnings multiple. Before any recovery.")
yr3 = sum(recovery_path(r.revenue_lost_bn, rc)[-1] for _, r in imp.iterrows())
m4.metric("Still lost in year 3", f"${yr3:,.1f}bn", f"{yr3 / total_lost - 1:+.0%} vs year 1" if total_lost else None, delta_color="inverse")

tabs = st.tabs(["Exposure", "Breaking point", "Scenario impact", "Monte Carlo", "Policy timeline", "Methodology"])

with tabs[0]:
    st.subheader("Who sells the most into China")
    edited = st.data_editor(
        st.session_state["companies"], num_rows="dynamic", width=W, hide_index=True, key="editor",
        column_config={
            "company": st.column_config.TextColumn("Company"),
            "ticker": st.column_config.TextColumn("Ticker"),
            "segment": st.column_config.SelectboxColumn("Segment", options=list(SEGMENTS)),
            "annual_revenue_bn": st.column_config.NumberColumn("Annual revenue ($bn)", min_value=0.0, format="%.1f"),
            "china_share": st.column_config.NumberColumn("China share (0 to 1)", min_value=0.0, max_value=1.0, format="%.3f"),
            "revenue_period": st.column_config.TextColumn("Revenue period"),
            "share_period": st.column_config.TextColumn("China share period"),
            "source": st.column_config.TextColumn("Source")})
    if not edited.equals(st.session_state["companies"]):
        st.session_state["companies"] = edited
        st.rerun()
    dropped = len(edited.dropna(how="all")) - len(df)
    if dropped > 0:
        st.warning(f"{dropped} row{'s' if dropped > 1 else ''} left out: each row needs a name, segment, revenue above zero and a China share from 0 to 1.")
    exp = exposure_table(df)
    a, b = st.columns(2)
    fig = px.bar(exp.sort_values("china_share"), x="china_share", y="company", orientation="h", color="tier",
                 color_discrete_map=TIER_COLORS, text=exp.sort_values("china_share")["china_share"].map("{:.0%}".format),
                 labels={"china_share": "China share of revenue", "company": "", "tier": "Exposure"})
    fig.update_traces(textposition="outside", textfont=dict(size=14))
    fig.update_layout(height=360, xaxis_tickformat=".0%", margin=dict(t=40, b=10), title="Share of revenue from China")
    a.plotly_chart(fig, width=W, theme=None)
    e2 = exp.sort_values("china_revenue_bn")
    fig2 = px.bar(e2, x="china_revenue_bn", y="company", orientation="h", color_discrete_sequence=[NAVY],
                  text=e2["china_revenue_bn"].map("${:,.1f}bn".format), labels={"china_revenue_bn": "$bn", "company": ""})
    fig2.update_traces(textposition="outside", textfont=dict(size=14))
    fig2.update_layout(height=360, margin=dict(t=40, b=10), title="China revenue in dollars")
    b.plotly_chart(fig2, width=W, theme=None)
    top_share, top_dollar = exp.iloc[0], exp.sort_values("china_revenue_bn").iloc[-1]
    e = lambda x: html.escape(str(x))
    if len(exp) == 1:
        msg = f"<b>{e(top_share.company)}</b> earns {top_share.china_share:.0%} of revenue (${top_share.china_revenue_bn:,.1f}bn) from China. Add rows to compare companies."
    elif top_share.company == top_dollar.company:
        msg = f"<b>{e(top_share.company)}</b> is the most exposed on both counts: {top_share.china_share:.0%} of sales and ${top_dollar.china_revenue_bn:,.1f}bn."
    else:
        msg = (f"<b>{e(top_share.company)}</b> depends on China the most ({top_share.china_share:.0%} of sales), while "
               f"<b>{e(top_dollar.company)}</b> has the most dollars there (${top_dollar.china_revenue_bn:,.1f}bn).")
    msg += f" Weighted across all companies, China is {exp.china_revenue_bn.sum() / exp.annual_revenue_bn.sum():.1%} of revenue."
    msg += " ASML's share is of system sales only, so its China dollars may be slightly overstated."  if "ASML" in set(exp.ticker) else ""
    takeaway(msg)

with tabs[1]:
    st.subheader(f"How much China business can each company lose before it costs {hit:.0%} of total revenue?")
    show = bp.copy()
    show["bp_plot"] = show["breaking_point"].clip(upper=1.05)
    show["label"] = np.where(show["breaking_point"] > 1, "Cannot reach", show["breaking_point"].map("{:.0%}".format))
    show["scenario_loss"] = show["segment"].map({"Chip designer": ld, "Equipment": le})
    bf = go.Figure()
    bf.add_bar(y=show["company"], x=show["bp_plot"], orientation="h", text=show["label"], textposition="outside",
               marker_color=[RED if r.breaking_point <= r.scenario_loss else NAVY for r in show.itertuples()],
               textfont=dict(size=14), name="Breaking point", hovertemplate="%{y}: %{text}<extra></extra>")
    bf.add_scatter(y=show["company"], x=show["scenario_loss"], mode="markers", name=f"{pick} loss rate",
                   marker=dict(symbol="line-ns", size=30, line=dict(width=4, color=GOLD)))
    bf.update_layout(height=120 + 50 * len(show), xaxis_tickformat=".0%", xaxis_range=[0, 1.15], margin=dict(t=10, b=10),
                     xaxis_title="Share of China revenue lost", yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(bf, width=W, theme=None)
    first = bp.iloc[0]
    if first.breaking_point > 1:
        takeaway(f"No company here can lose {hit:.0%} of total revenue through China alone. The most exposed, "
                 f"<b>{html.escape(str(first.company))}</b>, has {first.china_share:.0%} of sales in China.")
    else:
        takeaway(f"<b>{html.escape(str(first.company))}</b> breaks first: losing just <b>{first.breaking_point:.0%}</b> of its China sales costs "
                 f"{hit:.0%} of total revenue. Red bars are companies this scenario already pushes past the line; the gold mark is the scenario's loss rate. "
                 "Change the material loss level in the left panel to test a stricter or looser line.")

with tabs[2]:
    st.subheader(f"Year 1 impact: {pick}")
    s2 = imp.sort_values("revenue_lost_pct")
    fig = px.bar(s2, x="revenue_lost_pct", y="company", orientation="h", color="segment", color_discrete_map=SEG_COLORS,
                 text=s2["revenue_lost_pct"].map("{:.1%}".format),
                 labels={"revenue_lost_pct": "Share of total revenue lost", "company": "", "segment": "Segment"})
    fig.update_traces(textposition="outside", textfont=dict(size=14))
    fig.update_layout(height=330, xaxis_tickformat=".1%", margin=dict(t=40, b=10), title="Hit to each company's total revenue")
    st.plotly_chart(fig, width=W, theme=None)
    table = imp[["company", "segment", "china_revenue_bn", "loss_rate", "revenue_lost_bn", "revenue_lost_pct",
                 "op_profit_lost_bn", "value_at_risk_bn"]].rename(columns={
        "company": "Company", "segment": "Segment", "china_revenue_bn": "China revenue ($bn)", "loss_rate": "Loss rate",
        "revenue_lost_bn": "Revenue lost ($bn)", "revenue_lost_pct": "% of total revenue",
        "op_profit_lost_bn": "Op. profit lost ($bn)", "value_at_risk_bn": "Value at risk ($bn)"})
    st.dataframe(table.style.format({"China revenue ($bn)": "{:,.2f}", "Loss rate": "{:.0%}", "Revenue lost ($bn)": "{:,.2f}",
                                     "% of total revenue": "{:.1%}", "Op. profit lost ($bn)": "{:,.2f}", "Value at risk ($bn)": "{:,.1f}"}),
                 width=W, hide_index=True)
    st.download_button("Download scenario results (CSV)", table.to_csv(index=False), f"export_control_{pick.replace(' ', '_')}.csv")

    st.subheader("Recovery as sales are redirected")
    rows = [{"Year": f"Year {y}", "Company": r.company, "Net revenue lost ($bn)": v}
            for _, r in imp.iterrows() for y, v in enumerate(recovery_path(r.revenue_lost_bn, rc), start=1)]
    fig3 = px.bar(pd.DataFrame(rows), x="Year", y="Net revenue lost ($bn)", color="Company", barmode="stack",
                  color_discrete_sequence=[NAVY, "#6B4FA8", GOLD, GREEN, RED, "#2B2F36", "#0E7490", "#9D174D"])
    fig3.update_layout(height=330, margin=dict(t=10, b=10))
    st.plotly_chart(fig3, width=W, theme=None)
    takeaway(f"Year 1 is the full hit. With {rc:.0%} of lost sales resold elsewhere by year 3, the annual hit falls from <b>${total_lost:,.1f}bn</b> to "
             f"<b>${yr3:,.1f}bn</b>.")

    st.subheader("Every scenario side by side")
    comp = []
    for s in SCENARIOS.values():
        i = scenario_impact(df, s, margin, multiple)
        comp.append({"Scenario": s.name, "Revenue lost ($bn)": i.revenue_lost_bn.sum(),
                     "Op. profit lost ($bn)": i.op_profit_lost_bn.sum(), "Value at risk ($bn)": i.value_at_risk_bn.sum()})
    st.dataframe(pd.DataFrame(comp).style.format({c: "{:,.1f}" for c in ["Revenue lost ($bn)", "Op. profit lost ($bn)", "Value at risk ($bn)"]}),
                 width=W, hide_index=True)

with tabs[3]:
    st.subheader("How wide is the range of outcomes?")
    k1, k2 = st.columns(2)
    n = k1.select_slider("Simulations", [1000, 5000, 10000, 25000], 5000)
    sd = k2.slider("Uncertainty in China share", 0, 40, 15, 1, format="±%d%%",
                   help="How far each company's true China share could be from the table, in relative terms.") / 100
    if ld == 0 and le == 0:
        st.info("This scenario loses no China revenue, so there is no range to simulate. Choose another scenario or move the sliders.")
    else:
        sims = monte_carlo(df, scen, n=n, sd=sd, margin=margin)
        s = summary_stats(sims)
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Average revenue lost", f"${s['mean']:,.1f}bn")
        q2.metric("Median", f"${s['p50']:,.1f}bn")
        q3.metric("Good case (5th pct)", f"${s['p5']:,.1f}bn")
        q4.metric("Bad case (95th pct)", f"${s['p95']:,.1f}bn")
        h = px.histogram(sims, x="revenue_lost_bn", nbins=60, color_discrete_sequence=[NAVY],
                         labels={"revenue_lost_bn": "Revenue lost across all companies, year 1 ($bn)"})
        h.add_vline(x=s["p95"], line_dash="dot", line_width=3, line_color=RED, annotation_text="Bad case", annotation_font=dict(color=RED, size=14))
        h.update_layout(height=330, margin=dict(t=30, b=10), yaxis_title="Simulations")
        st.plotly_chart(h, width=W, theme=None)
        takeaway(f"Nine times out of ten the year 1 hit, before any recovery, lands between <b>${s['p5']:,.1f}bn</b> and <b>${s['p95']:,.1f}bn</b>. "
                 "Plan for the bad case, not the average.")

with tabs[4]:
    st.subheader("Key U.S. export control actions")
    st.dataframe(POLICY_TIMELINE, width=W, hide_index=True)
    st.markdown("<div class='note' style='margin-top:4px'>Timeline runs through April 2025, matching the period of the company data.</div>", unsafe_allow_html=True)
    takeaway("Each step since 2022 widened what needs a license to sell into China. The scenarios in this app price out what the next step could cost.")

with tabs[5]:
    st.markdown((ROOT / "HOW_IT_WORKS.md").read_text())
