#!/usr/bin/env python3
"""Export of the estimated destination-choice models (stage 3, 2026-10-22).

    python3 activity/lib/destination_choice/export_dc.py        # coef_calibrated/dest_choice_mnl.csv, results/*.csv, results/estimation_tables.md

Coefficient file (read by MarylandDestinationChoice, property dest.mnl.file): segment,variable,value with
  mu_size, size_<c> (weight of size component c; the base component 1, components not in the model absent = 0) and every
  linear variable of the final specification (names of dc_model.features / MarylandDestinationChoice.variable).
Estimates: Biogeme (results/biogeme_<segment>.csv) when present, else the PyTorch estimates of the search.
Also written: per-segment estimation table, statistics (LL(0), LL(c), LL(beta), rho2, adjusted rho2, AIC, BIC), specification
search, segmentation and sampling tests, the largest correlations of the estimates, elasticities (full choice set, estimation
half) and trade-off ratios.
"""
import json, os, pickle, sys
import numpy as np
import pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_common as C

RES = f"{C.DCD}/results"; SEG_ALL = [f"{p}_{k}" for p in C.DISC for k in ["primary", "stop"]] + ["WORK_primary"]
LAB = {"d_0_1": "distance 0–1 km (per km)", "d_1_2": "distance 1–2 km", "d_2_5": "distance 2–5 km", "d_5_10": "distance 5–10 km",
       "d_10_20": "distance 10–20 km", "d_20_50": "distance 20–50 km", "d_50_inf": "distance > 50 km",
       "dt_0_1": "detour 0–1 km (per km)", "dt_1_2": "detour 1–2 km", "dt_2_5": "detour 2–5 km", "dt_5_10": "detour 5–10 km", "dt_10_20": "detour 10–20 km",
       "dt_20_inf": "detour > 20 km", "intra": "intrazonal (destination = home zone)", "intra_a": "stop in the home zone", "intra_b": "stop in the primary-destination zone",
       "bc": "Baltimore City", "dcz": "Washington DC", "va": "Virginia", "othst": "Delaware, Pennsylvania, West Virginia", "cbd": "central business district",
       "lnretden": "ln(1 + retail jobs per km²)", "mix": "land-use mix (entropy)", "xcounty": "outside the origin county", "xstate": "outside the origin state",
       "cgt": "car generalized time (min)", "ctime": "car time (min)", "ls": "mode-choice logsum", "ptav_car0": "transit available × no car",
       "mu_size": "μ, ln size", "theta_pop": "θ population (ln weight)", "theta_ret": "θ retail jobs", "theta_off": "θ office jobs", "theta_oth": "θ other jobs", "theta_stu": "θ school enrolment"}
FLAGLAB = {"inc0": "income < $50k", "inc2": "income ≥ $100k", "car0": "no car", "car1": "cars < drivers", "child": "household with children", "kid": "person < 18",
           "senior": "person 65+", "worker": "worker", "am": "AM 6–9", "pm": "PM 15–19", "ev": "evening 19–6", "nonauto": "tour mode not car", "worktour": "work / school tour",
           "inbound": "inbound stop"}


def lab(p):
    if p in LAB: return LAB[p]
    if p.startswith("lnd_") or p.startswith("lndt_"):
        b, x = p.split("_", 1); return f"ln({'distance' if b == 'lnd' else '1 + detour'}) × {FLAGLAB.get(x, x)}"
    return p


def estimates(seg):
    o = pickle.load(open(f"{C.WORK}/search_{seg}.pkl", "rb")); F = o["models"]["F"]; spec = F["spec"]
    f = f"{RES}/biogeme_{seg}.csv"
    if os.path.exists(f):
        b = pd.read_csv(f)
        t = pd.DataFrame({"param": b.Name, "value": b.Value, "rob_se": b["Robust std err."], "rob_t": b["Robust t-stat."], "p": b["Robust p-value"]})
        st = json.load(open(f"{RES}/biogeme_{seg}_stats.json")); src = "Biogeme 3.3.5"
        t = t.set_index("param").loc[spec.params()].reset_index()
    else:
        t = F["table"][["param", "value", "rob_se", "rob_t"]].copy(); t["p"] = 2 * norm.sf(np.abs(t.rob_t)); st = dict(LL=F["LL"], K=F["K"], N=F["N"]); src = "PyTorch"
    return o, spec, t, st, src


def coef_rows(seg, spec, t):
    v = t.set_index("param").value; rows = [dict(segment=seg, variable="mu_size", value=float(v["mu_size"])), dict(segment=seg, variable=f"size_{spec.size_base}", value=1.0)]
    for c in spec.size_comps: rows.append(dict(segment=seg, variable=f"size_{c}", value=float(np.exp(v[f"theta_{c}"]))))
    for k in spec.linear: rows.append(dict(segment=seg, variable=k, value=float(v[k])))
    return rows


def elasticities(seg, spec, x):
    """Probability-weighted point elasticities on the full choice set of the estimation half: impedance (all distance and time
    variables scaled by 1 %), car time alone, and each size component; mean distance response to car time + 10 %."""
    import dc_model as M
    from estimate_dc import load
    pur = seg.split("_")[0]; rec, cand = load("estimation", seg); sk = C.skims()
    sk_d = dict(sk); sk_d["d"] = sk["d"] * 1.01; sk_d["draw"] = sk["draw"] * 1.01; sk_d["t"] = sk["t"] * 1.01
    sk_t = dict(sk); sk_t["t"] = sk["t"] * 1.10
    out = dict(segment=seg); acc = dict(e_imp=0.0, e_time=0.0, km0=0.0, km1=0.0, n=0); es = {c: 0.0 for c in [spec.size_base] + spec.size_comps}
    import torch
    th = torch.tensor(x)
    for sub, P, _ in M.predict_full(rec.sample(min(len(rec), 3000), random_state=3).reset_index(drop=True), cand, spec, x, pur, sk, chunk=750):
        cs = cand[cand.rec.isin(sub.rec)]; alts, lnc, logb = M.full_sets(sub, cs)
        V0 = M.utility(th, spec, M.Data(sub, alts, lnc, logb, spec, pur, sk)).numpy()
        Vd = M.utility(th, spec, M.Data(sub, alts, lnc, logb, spec, pur, sk_d)).numpy()
        Vt = M.utility(th, spec, M.Data(sub, alts, lnc, logb, spec, pur, sk_t)).numpy()
        acc["e_imp"] += float((P * (Vd - V0) / 0.01 * (1 - P)).sum()); acc["n"] += len(sub)
        P1 = np.exp(Vt - Vt.max(1, keepdims=True)); P1 /= P1.sum(1, keepdims=True)
        o = sub.home_idx.values; prev = np.where(sub.position.values == "in", sub.anchor_b.values, o) if (sub.kind == "stop").all() else o
        dist = sk["d"][prev].astype(float); acc["km0"] += float((P * dist).sum()); acc["km1"] += float((P1 * dist).sum())
        Z = C.zones(); w = {spec.size_base: 1.0, **{c: float(np.exp(x[spec.params().index(f"theta_{c}")])) for c in spec.size_comps}}
        S = sum(w[c] * Z[c].values for c in w); mu = x[spec.params().index("mu_size")] if spec.mu_fixed is None else spec.mu_fixed
        for c in w: es[c] += float((P * (mu * w[c] * Z[c].values / (1 + S))[None, :] * (1 - P)).sum())
    out["elasticity_impedance"] = acc["e_imp"] / acc["n"]
    out["mean_km"] = acc["km0"] / acc["n"]; out["elasticity_mean_km_car_time"] = (acc["km1"] / acc["km0"] - 1) / 0.10
    for c, v in es.items(): out[f"elasticity_size_{c}"] = v / acc["n"]
    return out


def ratios(seg, spec, t):
    v = t.set_index("param").value; r = dict(segment=seg)
    g = "cgt" if "cgt" in v else "ctime" if "ctime" in v else None
    beta_cost = v[g] * 60.0 / C.MC_VOT[0] if g else np.nan        # utility per $ at the reference VOT (30 $/h)
    r["impedance_term"] = g or ""; r["beta_cost_per_usd"] = beta_cost
    for p in [k for k in spec.linear if k.startswith("d_") or k.startswith("dt_")]:
        r[f"usd_per_km_{p}"] = v[p] / beta_cost if g else np.nan
        r[f"min_per_km_{p}"] = v[p] / v[g] if g else np.nan
    mu = v["mu_size"]; pc = "d_5_10" if "d_5_10" in v else "dt_5_10" if "dt_5_10" in v else None
    r["km_equiv_double_size_5_10"] = float(-mu * np.log(2) / v[pc]) if pc else np.nan
    return r


def md(df, fmt):
    cols = list(df.columns); L = ["| " + " | ".join(cols) + " |", "|" + "|".join("---:" if c not in ("variable", "model", "note", "dimension", "groups", "protocol", "description") else "---" for c in cols) + "|"]
    for _, r in df.iterrows(): L.append("| " + " | ".join(fmt.get(c, "{}").format(r[c]) if not (isinstance(r[c], float) and np.isnan(r[c])) else "" for c in cols) + " |")
    return "\n".join(L)


def main(segs=SEG_ALL, with_elasticities=True):
    rows, tabs, stats, search, segm, samp, corr, el, ra = [], [], [], [], [], [], [], [], []
    for seg in segs:
        if not os.path.exists(f"{C.WORK}/search_{seg}.pkl"): print(f"{seg}: no search"); continue
        o, spec, t, st, src = estimates(seg)
        if seg != "WORK_primary": rows += coef_rows(seg, spec, t)
        t = t.assign(segment=seg, description=t.param.map(lab), source=src); tabs.append(t)
        LL0, LLc, LL, K, N = o["LL0"], o["LLc"], st["LL"], st.get("K", len(t)), st.get("N", o["N"])
        stats.append(dict(segment=seg, N=N, J_sampled=o["J"], K=K, LL0=LL0, LLc=LLc, LL=LL, rho2=1 - LL / LL0, rho2_adj=1 - (LL - K) / LL0,
                          rho2_c=1 - LL / LLc, AIC=2 * K - 2 * LL, BIC=np.log(N) * K - 2 * LL, mu1_LR=o["mu1"]["LR"], mu1_p=o["mu1"]["p"], size_base=spec.size_base,
                          size_components=" ".join(spec.size_comps), source=src))
        for r in o["rows"]: search.append(dict(segment=seg, **{k: r.get(k) for k in ["model", "note", "K", "LL", "rho2", "rho2_adj", "AIC", "BIC", "LR_vs", "LR", "LR_df", "LR_p"]}))
        for r in o["segmentation"]: segm.append(dict(segment=seg, **{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()}))
        sm = o["sampling"].copy(); sm.insert(0, "segment", seg); samp.append(sm)
        cm = o["models"]["F"]["corr"]; names = list(cm.index)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                c = cm.iloc[i, j]
                if np.isfinite(c) and abs(c) >= 0.6: corr.append(dict(segment=seg, a=names[i], b=names[j], corr=float(c)))
        x = t.set_index("param").loc[spec.params()].value.values
        if with_elasticities: el.append(elasticities(seg, spec, x))
        ra.append(ratios(seg, spec, t))
        print(f"{seg}: exported ({src})", flush=True)
    cf = pd.DataFrame(rows); cf.to_csv(f"{C.COEF}/dest_choice_mnl.csv", index=False)
    pd.concat(tabs).to_csv(f"{RES}/estimates.csv", index=False); pd.DataFrame(stats).to_csv(f"{RES}/statistics.csv", index=False)
    pd.DataFrame(search).to_csv(f"{RES}/specification_search.csv", index=False); pd.DataFrame(segm).to_csv(f"{RES}/segmentation_tests.csv", index=False)
    pd.concat(samp).to_csv(f"{RES}/sampling_tests.csv", index=False); pd.DataFrame(corr).to_csv(f"{RES}/correlations.csv", index=False)
    if el: pd.DataFrame(el).to_csv(f"{RES}/elasticities.csv", index=False)
    pd.DataFrame(ra).to_csv(f"{RES}/ratios.csv", index=False)
    print(f"wrote {C.COEF}/dest_choice_mnl.csv ({len(cf)} rows) and {RES}/*.csv")


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 else SEG_ALL, with_elasticities="--no-elasticities" not in sys.argv)
