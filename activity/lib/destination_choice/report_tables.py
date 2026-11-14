#!/usr/bin/env python3
"""Markdown tables of ESTIMATION_REPORT.md from destination_choice/results (python3 activity/lib/destination_choice/report_tables.py -> results/tables.md)."""
import json, os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_common as C
from export_dc import lab

RES = f"{C.DCD}/results"
SEGS = [f"{p}_{k}" for k in ["primary", "stop"] for p in C.DISC] + ["WORK_primary"]
SN = {f"{p}_{k}": f"{p.lower()} {'primary destination' if k == 'primary' else 'stop'}" for p in C.DISC + ["WORK"] for k in ["primary", "stop"]}
SN["WORK_primary"] = "work (home → usual workplace)"


def f(x, d=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)): return ""
    return f"{x:,.{d}f}"


def pstr(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def table(rows, cols, align=None):
    L = ["| " + " | ".join(cols) + " |", "|" + "|".join(align or ["---"] + ["---:"] * (len(cols) - 1)) + "|"]
    for r in rows: L.append("| " + " | ".join(str(v) for v in r) + " |")
    return "\n".join(L)


def main():
    E = pd.read_csv(f"{RES}/estimates.csv"); S = pd.read_csv(f"{RES}/statistics.csv").set_index("segment")
    Q = pd.read_csv(f"{RES}/specification_search.csv"); G = pd.read_csv(f"{RES}/segmentation_tests.csv"); M = pd.read_csv(f"{RES}/sampling_tests.csv")
    Rr = pd.read_csv(f"{RES}/ratios.csv").set_index("segment"); Co = pd.read_csv(f"{RES}/correlations.csv")
    El = pd.read_csv(f"{RES}/elasticities.csv").set_index("segment") if os.path.exists(f"{RES}/elasticities.csv") else None
    H = pd.read_csv(f"{RES}/heldout_summary.csv") if os.path.exists(f"{RES}/heldout_summary.csv") else None
    out = []
    # T1 sample sizes and fit
    rows = []
    for s in SEGS:
        if s not in S.index: continue
        r = S.loc[s]
        rows.append([SN[s], f"{int(r.N):,}", int(r.J_sampled), int(r.K), f(r.LL0, 1), f(r.LLc, 1), f(r.LL, 1), f(r.rho2), f(r.rho2_adj), f(r.rho2_c), f(r.AIC, 1), f(r.BIC, 1)])
    out.append("### Table E1. Estimation samples and goodness of fit of the final models (estimation half; sampled choice sets, R = 40 draws)\n")
    out.append(table(rows, ["Segment", "N", "J (max)", "K", "LL(0)", "LL(c)", "LL(β)", "ρ²", "adj. ρ²", "ρ² vs LL(c)", "AIC", "BIC"]))
    out.append("\nLL(0): all utilities zero (with the sampling correction, i.e. the sampled equal-probability model); LL(c): area dummies and intrazonal constant only; "
               "adj. ρ² = 1 − (LL(β) − K)/LL(0).\n")
    # T2 estimates per segment
    for s in SEGS:
        e = E[E.segment == s]
        if len(e) == 0: continue
        rows = [[lab(p), p, f(v, 4), f(se, 4), f(t, 2), pstr(pv)] for p, v, se, t, pv in zip(e.param, e.value, e.rob_se, e.rob_t, e.p)]
        st = S.loc[s]
        out.append(f"\n#### Table E2-{s}. {SN[s]}: estimates (Biogeme 3.3.5, robust standard errors); size base = {st.size_base}"
                   f"{', components ' + st.size_components if isinstance(st.size_components, str) and st.size_components else ''}; "
                   f"test μ = 1: LR = {f(st.mu1_LR, 1)}, p = {pstr(st.mu1_p)}\n")
        out.append(table(rows, ["Variable", "Name", "Estimate", "Robust s.e.", "Robust t", "p"], ["---", "---", "---:", "---:", "---:", "---:"]))
    # T3 specification search
    out.append("\n### Table E3. Specification search (LR test against the previous nested model; S9 / S9t against S8, S9b against S9; F against the model it was reduced from)\n")
    rows = []
    for s in SEGS:
        for _, r in Q[Q.segment == s].iterrows():
            rows.append([SN[s] if r.model == "S1" else "", r.model, r.note, int(r.K), f(r.LL, 1), f(r.AIC, 1), f(r.BIC, 1), r.LR_vs if isinstance(r.LR_vs, str) else "",
                         f(r.LR, 1) if pd.notna(r.LR) else "", f"{int(r.LR_df)}" if pd.notna(r.LR_df) else "", pstr(r.LR_p) if pd.notna(r.LR_p) else ""])
    out.append(table(rows, ["Segment", "Model", "Specification", "K", "LL", "AIC", "BIC", "vs", "LR", "df", "p"], ["---", "---", "---"] + ["---:"] * 8))
    # T4 segmentation
    out.append("\n### Table E4. Segmentation tests: separate models by group (final specification) against the pooled final model\n")
    rows = []
    for s in SEGS:
        for _, r in G[G.segment == s].iterrows():
            if not r.tested or str(r.tested) == "False":
                rows.append([SN[s], r.dimension, r.groups, "", "", "", "", "", "not estimated (a group < 150)"]); continue
            keep = "segment" if (r.AIC_segmented < r.AIC_pooled and r.BIC_segmented < r.BIC_pooled) else "pooled + interactions"
            rows.append([SN[s], r.dimension, r.groups.replace('"', ""), f(r.LR, 1), int(r.df), pstr(r.p), f(r.AIC_segmented - r.AIC_pooled, 1), f(r.BIC_segmented - r.BIC_pooled, 1), keep])
    out.append(table(rows, ["Segment", "Dimension", "Groups (N)", "LR", "df", "p", "ΔAIC", "ΔBIC", "Decision"], ["---", "---", "---"] + ["---:"] * 5 + ["---"]))
    # T5 sampling
    out.append("\n### Table E5. Sensitivity to the number of sampled alternatives and to the sampling protocol (selected coefficients)\n")
    rows = []
    for s in SEGS:
        m = M[M.segment == s]
        if len(m) == 0: continue
        cols = [c for c in ["mu_size", "d_2_5", "d_10_20", "dt_2_5", "dt_10_20", "cgt", "ls", "intra", "intra_a", "xcounty"] if c in m.columns and m[c].notna().any()]
        for _, r in m.iterrows():
            rows.append([SN[s], r.protocol, int(r.R), int(r.J), "; ".join(f"{c} {r[c]:.3f} ({r['se_' + c]:.3f})" for c in cols if pd.notna(r[c]))])
    out.append(table(rows, ["Segment", "Protocol", "R", "J", "Estimates (robust s.e.)"], ["---", "---", "---:", "---:", "---"]))
    # T6 correlations
    out.append("\n### Table E6. Pairs of estimates with |correlation| ≥ 0.6 (robust covariance)\n")
    rows = [[SN[r["segment"]], r["a"], r["b"], f(r["corr"], 2)] for _, r in Co.iterrows() if abs(r["corr"]) >= 0.6]
    out.append(table(rows, ["Segment", "Parameter", "Parameter", "Correlation"], ["---", "---", "---", "---:"]) if rows else "none")
    # T7 elasticities and ratios
    if El is not None:
        out.append("\n### Table E7. Elasticities (full choice set, estimation half) and trade-off ratios\n")
        rows = []
        for s in SEGS:
            if s not in El.index: continue
            e = El.loc[s]; r = Rr.loc[s]
            sz = "; ".join(f"{c[len('elasticity_size_'):]} {e[c]:.3f}" for c in El.columns if c.startswith("elasticity_size_") and pd.notna(e[c]))
            pc = "d_5_10" if s.endswith("primary") else "dt_5_10"
            rows.append([SN[s], f(e.elasticity_impedance), f(e.mean_km, 2), f(e.elasticity_mean_km_car_time), sz, (r.impedance_term if isinstance(r.impedance_term, str) else "logsum only"),
                         f(r.get(f"min_per_km_{pc}"), 2), f(r.get(f"usd_per_km_{pc}"), 2), f(r.km_equiv_double_size_5_10, 2)])
        out.append(table(rows, ["Segment", "Impedance elasticity of P", "Mean km", "Elasticity of mean km to car time", "Size elasticities", "Time term",
                                "min per km (5–10 km)", "$ per km (5–10 km)", "km for twice the size"], ["---", "---:", "---:", "---:", "---", "---", "---:", "---:", "---:"]))
    # T8 held-out
    if H is not None:
        out.append("\n### Table E8. Held-out validation half: predictive log-likelihood and predicted against observed destinations (full choice set)\n")
        rows = []
        for s in SEGS[:-1]:
            for m in ["mnl", "gravity"]:
                h = H[(H.segment == s) & (H.half == "validation") & (H.model == m)]
                if len(h) == 0: continue
                h = h.iloc[0]; name = "estimated MNL" if m == "mnl" else ("former gravity" if s.endswith("primary") else "former corridor rule")
                rows.append([SN[s] if m == "mnl" else "", name, f"{int(h.N):,}", f(h.LL, 1), f(h.LL / h.N, 3), f(h.rho2_vs_uniform), f"{int(h.zero_prob)}",
                             f"{h.mean_km_model:.2f} / {h.mean_km_obs:.2f}", f(h.KS_binned), f(h.CR), f"{100 * h.intrazonal_model:.1f} / {100 * h.intrazonal_obs:.1f}",
                             f"{100 * h['Baltimore City_model']:.1f} / {100 * h['Baltimore City_obs']:.1f}", f"{100 * h['Washington DC_model']:.1f} / {100 * h['Washington DC_obs']:.1f}",
                             f(h.flow_dissimilarity), f"{100 * h.own_county_model:.1f} / {100 * h.own_county_obs:.1f}"])
        out.append(table(rows, ["Segment", "Model", "N", "Predictive LL", "per obs.", "ρ² vs uniform", "obs. with P = 0", "Mean km (model / obs.)", "KS (binned)", "CR",
                                "Intrazonal % (m / o)", "Baltimore City % (m / o)", "DC % (m / o)", "Flow dissimilarity", "Own county % (m / o)"],
                         ["---", "---"] + ["---:"] * 13))
    sim = f"{RES}/sim_summary.csv"
    if os.path.exists(sim):
        T = pd.read_csv(sim)
        out.append("\n### Table E9. Simulated (ABIT, 10 seeds): discretionary trips by destination purpose against the survey, before and after\n")
        rows = []
        for st in ["validation", "chain"]:
            for pur in C.DISC + ["ALL"]:
                for v in ["before", "after"]:
                    r = T[(T.setting == st) & (T.purpose == pur) & (T.variant == v)]
                    if len(r) == 0: continue
                    r = r.iloc[0]
                    rows.append([st if (pur == "SHOPPING" and v == "before") else "", pur.lower() if v == "before" else "", v, f"{r.mean_km:.2f} ± {r.mean_km_sd:.2f}", f"{r.mean_km_obs:.2f}",
                                 f"{r.KS:.3f} ({r.KS_crit_5pct:.3f})", f(r.CR), f"{100 * r.intrazonal:.1f} / {100 * r.intrazonal_obs:.1f}",
                                 f"{100 * r['share_Baltimore City']:.1f} / {100 * r['share_Baltimore City_obs']:.1f}", f"{100 * r['share_Washington DC']:.1f} / {100 * r['share_Washington DC_obs']:.1f}",
                                 f"{100 * r.own_county:.1f} / {100 * r.own_county_obs:.1f}", f(r.flow_dissimilarity)])
        out.append(table(rows, ["Setting", "Purpose", "Model", "Mean km (± s.d. seeds)", "Observed km", "KS D (5 % crit.)", "CR", "Intrazonal % (m / o)",
                                "Baltimore City % (m / o)", "DC % (m / o)", "Own county % (m / o)", "Flow dissimilarity"], ["---", "---", "---"] + ["---:"] * 9))
    open(f"{RES}/tables.md", "w").write("\n".join(out) + "\n"); print(f"wrote {RES}/tables.md")


if __name__ == "__main__":
    main()
