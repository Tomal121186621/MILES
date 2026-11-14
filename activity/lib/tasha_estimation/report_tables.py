#!/usr/bin/env python3
"""Markdown tables of the estimated components of the model of record (stage 3 finalisation, 2026-10-23), from results/.

    python3 activity/lib/tasha_estimation/report_tables.py   -> results/estimation_tables.md, ESTIMATION_REPORT.md (= ESTIMATION_REPORT_HEAD.md + the tables)
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; RES = f"{HERE}/results"
LAB = {"WORK_wbwork": "Work business, worker with a usual workplace (anchors home and workplace)", "WORK_wbhome": "Work business, other persons (from home)",
       "WORK_wahb": "Work trips of at-home workers (from home)", "EDUCATION_nonstud": "School of persons without a school record (from home)",
       "EDUCATION_daycare": "Daycare / preschool, persons under 5 (from home)"}


def f(v, d=3): return "" if pd.isna(v) else f"{v:,.{d}f}"


def md(df, cols, heads):
    L = ["| " + " | ".join(heads) + " |", "|" + "|".join(["---"] + ["---:"] * (len(heads) - 1)) + "|"]
    for _, r in df.iterrows(): L.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(L) + "\n"


def main():
    out = []
    # ---- locations
    st = pd.concat([pd.read_csv(f"{RES}/loc_stats_{s}.csv") for s in LAB], ignore_index=True)
    st["segment_label"] = st.segment.map(LAB)
    for c in ["LL0", "LLc", "LL", "AIC", "BIC"]: st[c] = st[c].map(lambda v: f(v, 1))
    for c in ["rho2", "rho2_c"]: st[c] = st[c].map(lambda v: f(v, 3))
    out.append("### Table L1. Anchored location MNLs: estimation samples and fit (estimation half; sampled choice sets, R = 40)\n")
    out.append(md(st, ["segment_label", "form", "N", "K", "size_base", "LL0", "LLc", "LL", "rho2", "rho2_c", "AIC", "BIC"],
                  ["Segment", "Impedance form", "N", "K", "Size base", "LL(0)", "LL(c)", "LL(β)", "ρ² vs 0", "ρ² vs c", "AIC", "BIC"]))
    fo = pd.read_csv(f"{RES}/loc_wbwork_forms.csv")
    fo["form"] = fo.form.map({"primary": "distance from the workplace", "stop": "detour between home and workplace"})
    for c in ["LL_full", "LL_per_obs", "km_from_home"]: fo[c] = fo[c].map(lambda v: f(v, 3 if c == "LL_per_obs" else 1 if c == "LL_full" else 2))
    out.append("\n### Table L2. Work business of a worker with a usual workplace: the two impedance forms on the full choice set\n")
    out.append(md(fo, ["form", "half", "N", "K", "LL_full", "LL_per_obs", "km_from_home"], ["Form", "Half", "N", "K", "LL (full set)", "LL per record", "Predicted km from home"]))
    for s in LAB:
        t = pd.read_csv(f"{RES}/loc_estimates_{s}.csv")
        t = t.assign(value=t.value.map(f), rob_se=t.rob_se.map(f), rob_t=t.rob_t.map(lambda v: f(v, 2)))
        out.append(f"\n#### Table L3-{s}. {LAB[s]}: estimates (robust standard errors)\n")
        out.append(md(t, ["param", "value", "rob_se", "rob_t"], ["Parameter", "Estimate", "Robust s.e.", "Robust t"]))
    h = pd.read_csv(f"{RES}/loc_heldout.csv"); h["segment"] = h.segment.map(LAB)
    for c in ["LL_per_obs", "LL_band_per_obs"]: h[c] = h[c].map(f)
    for c in ["km_from_home_obs", "km_from_home_mnl", "km_from_home_band"]: h[c] = h[c].map(lambda v: f(v, 2))
    out.append("\n### Table L4. Held-out test (full choice set): predictive log-likelihood per record and mean zone-skim distance from home, estimated MNL against the band model it replaces\n")
    out.append(md(h, ["segment", "half", "N", "LL_per_obs", "LL_band_per_obs", "km_from_home_obs", "km_from_home_mnl", "km_from_home_band"],
                  ["Segment", "Half", "N", "LL/record MNL", "LL/record band model", "km observed", "km MNL", "km band model"]))
    # ---- complexity, sequential stops
    cx = pd.read_csv(f"{RES}/cx_tests.csv"); e = pd.read_csv(f"{RES}/cx_estimates.csv"); e = e[e.param == "lnd_multi"].set_index("segment")
    cx["beta"] = cx.segment.map(e.value).map(f); cx["se"] = cx.segment.map(e.rob_se).map(f); cx["t"] = cx.segment.map(e.rob_t).map(lambda v: f(v, 2))
    for c in ["share_multi"]: cx[c] = cx[c].map(lambda v: f(v, 2))
    for c in ["LL_F", "LL_FX", "LR", "BIC_F", "BIC_FX"]: cx[c] = cx[c].map(lambda v: f(v, 1))
    cx["p"] = cx.p.map(lambda v: "< 0.001" if v < 0.001 else f(v))
    out.append("\n### Table C1. Primary destinations: ln(distance) × tour with stops added to the final specifications (estimation half)\n")
    out.append(md(cx, ["segment", "N", "share_multi", "beta", "se", "t", "LL_F", "LL_FX", "LR", "p", "BIC_F", "BIC_FX"],
                  ["Segment", "N", "Share of tours with stops (weighted)", "β ln d × stops", "Robust s.e.", "t", "LL(F)", "LL(F + term)", "LR (1 df)", "p", "BIC(F)", "BIC(F + term)"]))
    ch = pd.read_csv(f"{RES}/cx_heldout.csv")
    for c in ["km_obs", "km_pred"]: ch[c] = ch[c].map(lambda v: f(v, 2))
    out.append("\n### Table C2. Held-out test: mean zone-skim distance of the primary destination from home by tour type, pooled model against the model with the term\n")
    out.append(md(ch, ["segment", "half", "model", "tour", "N", "km_obs", "km_pred"], ["Segment", "Half", "Model", "Tour", "N", "km observed", "km predicted"]))
    sq = pd.read_csv(f"{RES}/seq_heldout.csv")
    for c in ["km_leg_obs", "km_leg_pooled_F", "km_leg_sequential"]: sq[c] = sq[c].map(lambda v: f(v, 2))
    out.append("\n### Table S1. Stops: mean zone-skim distance of the leg to the stop (from the previous location), observed and predicted (full choice set)\n")
    out.append(md(sq, ["segment", "half", "position", "N", "km_leg_obs", "km_leg_pooled_F", "km_leg_sequential"],
                  ["Segment", "Half", "Position", "N", "km observed", "pooled anchors (home, primary)", "sequential anchors"]))
    se = pd.read_csv(f"{RES}/seq_estimates.csv")
    for s, t in se.groupby("segment", sort=False):
        t = t.assign(value=t.value.map(f), rob_se=t.rob_se.map(f), rob_t=t.rob_t.map(lambda v: f(v, 2)))
        out.append(f"\n#### Table S2-{s}. {s} with sequential anchors: estimates (N = {int(t.N.iloc[0]):,}, LL = {t.LL.iloc[0]:,.1f})\n")
        out.append(md(t, ["param", "value", "rob_se", "rob_t"], ["Parameter", "Estimate", "Robust s.e.", "Robust t"]))
    # ---- return home
    rs = pd.read_csv(f"{RES}/rh_search.csv")
    for c in ["LL", "AIC", "BIC", "LR"]: rs[c] = rs[c].map(lambda v: f(v, 1))
    for c in ["rho2_0", "rho2_c", "LR_p"]: rs[c] = rs[c].map(f)
    out.append("\n### Table H1. Return home, specification A (with the slack between the episodes): search (estimation half, pairs with a feasible return)\n")
    out.append(md(rs, ["model", "note", "K", "N", "LL", "rho2_0", "AIC", "BIC", "LR", "LR_p"], ["Model", "Content", "K", "N", "LL", "ρ² vs 0", "AIC", "BIC", "LR", "p"]))
    for lab, fn in [("A (with the slack; not used)", "rh_estimates.csv"), ("B (model of record; no outcome-dependent gap)", "rh_nogap_estimates.csv")]:
        t = pd.read_csv(f"{RES}/{fn}"); t = t.assign(value=t.value.map(f), rob_se=t.rob_se.map(f), rob_t=t.rob_t.map(lambda v: f(v, 2)))
        out.append(f"\n#### Table H2-{lab[0]}. Return-home logit, specification {lab}: estimates (robust s.e.)\n")
        out.append(md(t, ["variable", "value", "rob_se", "rob_t"], ["Variable", "Estimate", "Robust s.e.", "Robust t"]))
    for lab, fn in [("A", "rh_heldout.csv"), ("B", "rh_nogap_heldout.csv")]:
        t = pd.read_csv(f"{RES}/{fn}"); t = t[t.group.isin(["all", "ptype", "nepc", "slb"])]
        t = t.assign(obs=t.obs.map(f), pred=t.pred.map(f))
        out.append(f"\n### Table H3-{lab}. Return-home share of consecutive out-of-home pairs, observed and predicted (specification {lab}; estimation and validation halves)\n")
        out.append(md(t, ["group", "level", "half", "N", "obs", "pred"], ["Group", "Level", "Half", "Pairs", "Observed", "Predicted"]))
    # ---- attendance
    a = pd.read_csv(f"{RES}/attendance_estimates.csv"); a = a.assign(value=a.value.map(lambda v: f(v, 4)), boot_se=a.boot_se.map(lambda v: f(v, 4)), t=a.t.map(lambda v: f(v, 1)))
    out.append("\n### Table A1. Work attendance: estimates (estimation half; household-cluster bootstrap, 200 replications)\n")
    out.append(md(a, ["parameter", "value", "boot_se", "t", "n"], ["Parameter", "Estimate", "Bootstrap s.e.", "t", "Persons"]))
    af = pd.read_csv(f"{RES}/attendance_fit.csv")
    af = af.assign(observed=af.observed.map(lambda v: f(v, 4)), predicted=af.predicted.map(lambda v: f(v, 4)), predicted_2024_shares=af.predicted_2024_shares.map(lambda v: f(v, 4)))
    out.append("\n### Table A2. Work attendance of usual-workplace workers: observed and predicted (ACS 2017-19 shares; last column: the same persons with the ACS 2024 shares)\n")
    out.append(md(af, ["half", "group", "persons", "observed", "predicted", "predicted_2024_shares"], ["Half", "Group", "Persons", "Observed", "Predicted", "Predicted, 2024 shares"]))
    open(f"{RES}/estimation_tables.md", "w").write("\n".join(out)); print("wrote results/estimation_tables.md")
    # the report: the text of ESTIMATION_REPORT_HEAD.md followed by the generated tables
    open(f"{HERE}/ESTIMATION_REPORT.md", "w").write(open(f"{HERE}/ESTIMATION_REPORT_HEAD.md").read() + "\n" + "\n".join(out)); print("wrote ESTIMATION_REPORT.md")


if __name__ == "__main__":
    main()
