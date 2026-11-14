#!/usr/bin/env python3
"""Re-specification of the TAZ destination models against within-choice-set collinearity (2026-10-28; suffix _tazr).

    python3 activity/lib/tasha_estimation/respec_dc_taz.py search primary|stop      -> results/respec_candidates_<kind>_tazr.csv, work/respec_<seg>_tazr.pkl
    python3 activity/lib/tasha_estimation/respec_dc_taz.py final  primary|stop      -> results/{cx,seq}_estimates_tazr.csv, {cx,seq}_heldout_tazr.csv,
                                                         dest_choice_primary_cx_tazr.csv, dest_choice_stop_seq_tazr.csv,
                                                         collin_<seg>_tazr.csv, vif_<seg>_tazr.csv
    python3 activity/lib/tasha_estimation/respec_dc_taz.py biosub primary|stop N    -> Biogeme data of a subsample (biogeme_dc_taz.py with TAZ_BIO_SUFFIX=_tazr_sub)

Starting point: the TAZ re-estimates (estimate_dc_taz.py; same records, sampling R = 40, seed 2026, location mixture, optimiser).
Collinearity found there (collin_<seg>_taz.csv): primaries cgt ~ d_50_inf (0.93); stops ls ~ dt_20_inf (-0.91..-0.97), cgt ~
dt_20_inf (0.98), cgt ~ ls (-0.92 / -0.94); shopping stop dt_5_10 ~ dt_10_20 (0.80).
Candidates (every combination; nothing else of the specification changes):
  primaries  far range: separate pieces | d_20_inf (20-50 and > 50 km one slope) | d_10_inf (10 km and beyond one slope);
             car generalized time kept | dropped
  stops      far range: separate | dt_10_inf | dt_5_inf (shopping also dt_5_20 + dt_20_inf); logsum kept | dropped;
             car generalized time kept | dropped (recreation, other errands)
Rule: among the candidates with every within-set |r| <= 0.85 and every VIF < 10 among the kept terms, the smallest BIC (estimation
half); the predictive LL per observation on the validation half (full choice set, TAZ records) is reported for every candidate
and must not contradict the choice.  Warm start: the TAZ re-estimates (a merged piece starts at the slope of its first piece).
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, pickle, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import estimate_dc_taz as Z       # noqa: E402  (sets the threads, wraps dc_model)
import dc_taz_engine as X         # noqa: E402
import dc_model as M              # noqa: E402
import dc_common as C             # noqa: E402
import estimate_dc as E           # noqa: E402
from estimate_complexity import multi_flag, final_spec   # noqa: E402
from estimate_stops_seq import with_seq                  # noqa: E402
import torch                      # noqa: E402

RES, WORK = Z.RES, Z.WORK
RMAX, VMAX = 0.85, 10.0


def base(seg):
    pur, kind = seg.split("_"); spec, _ = final_spec(seg)
    lin = spec.linear + (["lnd_multi"] if kind == "primary" else [])
    t = pd.read_csv(f"{RES}/{'cx' if kind == 'primary' else 'seq'}_estimates_taz.csv"); t = t[t.segment == seg]
    return pur, kind, lin, spec.size_base, spec.size_comps, dict(zip(t.param, t.value))


def merge(lin, pieces, new):
    out = []
    for v in lin:
        if v in pieces:
            if new not in out: out.append(new)
        else: out.append(v)
    return out


def candidates(seg, lin):
    pur, kind = seg.split("_"); out = []
    if kind == "primary":
        tops = {"separate": lin, "d_20_inf": merge(lin, ["d_20_50", "d_50_inf"], "d_20_inf"), "d_10_inf": merge(lin, ["d_10_20", "d_20_50", "d_50_inf"], "d_10_inf")}
        for tn, tl in tops.items():
            for cg in ([True, False] if "cgt" in lin else [True]):
                l = [v for v in tl if cg or v != "cgt"]; out.append((f"far={tn}; cgt={'kept' if cg else 'dropped'}", l))
    else:
        tops = {"separate": lin, "dt_10_inf": merge(lin, ["dt_10_20", "dt_20_inf"], "dt_10_inf"), "dt_5_inf": merge(lin, ["dt_5_10", "dt_10_20", "dt_20_inf"], "dt_5_inf")}
        if pur == "SHOPPING": tops["dt_5_20"] = merge(lin, ["dt_5_10", "dt_10_20"], "dt_5_20")
        for tn, tl in tops.items():
            for ls in [True, False]:
                for cg in ([True, False] if "cgt" in lin else [True]):
                    l = [v for v in tl if (ls or v != "ls") and (cg or v != "cgt")]
                    out.append((f"far={tn}; ls={'kept' if ls else 'dropped'}" + (f"; cgt={'kept' if cg else 'dropped'}" if "cgt" in lin else ""), l))
    return out


def start(spec, xb):
    x = {}
    for p in spec.params():
        if p in xb: x[p] = xb[p]
        elif p.startswith("d_") or p.startswith("dt_"):
            pre, lo, _ = p.split("_"); k = [q for q in xb if q.startswith(f"{pre}_{lo}_")]; x[p] = xb[k[0]] if k else -0.1
    return x


def load(seg, half):
    rec, cand, cfg = Z.load_taz(half, seg)
    if seg.endswith("primary"): rec["multi"] = multi_flag(rec, half)
    return rec, cand, cfg


def search(kind):
    sk = C.skims(); rows = []
    for p_ in C.DISC:
        seg = f"{p_}_{kind}"; pur, _, lin, sb, sc, xb = base(seg)
        rec, cand, cfg = load(seg, "estimation"); sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026)
        rv, cv, gv = load(seg, "validation"); keep = {}
        for name, l in candidates(seg, lin):
            spec = M.Spec("R", l, sb, sc, note=name)
            r = X.fit(spec, rec, cfg, *sets, pur, sk, x0=start(spec, xb)); D = r.pop("D")
            R, vif = X.collinearity(D, spec, r); del D
            A = R.values - np.eye(len(R)); i, j = np.unravel_index(np.abs(A).argmax(), A.shape)
            h = X.heldout(rv, cv, gv, spec, r["x"].numpy(), pur, sk, obs="mix")
            N = len(rec)
            row = dict(segment=seg, candidate=name, K=r["K"], LL=r["LL"], BIC=np.log(N) * r["K"] - 2 * r["LL"], N=N, max_abs_r=float(np.abs(A).max()),
                       max_r_pair=f"{R.index[i]}~{R.columns[j]}", max_VIF=float(vif.drop("ln_size", errors="ignore").max()), max_VIF_term=vif.drop("ln_size", errors="ignore").idxmax(),
                       VIF_ln_size=float(vif.get("ln_size", np.nan)), heldout_LL_obs=float(h["LL"].mean()), heldout_KS=X.ks(h["tld_pred"], h["tld_obs"]),
                       converged=r["converged"], maxgrad=r["maxgrad"], terms=" ".join(l))
            rows.append(row); keep[name] = dict(spec=spec, table=r["table"], x=r["x"].numpy(), LL=r["LL"], K=r["K"], cov=r["cov"])
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items() if k != "terms"}, flush=True)
            pd.DataFrame(rows).to_csv(f"{RES}/respec_candidates_{kind}_tazr.csv", index=False)
        pickle.dump(keep, open(f"{WORK}/respec_{seg}_tazr.pkl", "wb"))
    D = pd.DataFrame(rows)
    D["feasible"] = (D.max_abs_r <= RMAX) & (D.max_VIF < VMAX)
    D["chosen"] = False
    for seg, g in D.groupby("segment"):
        f = g[g.feasible]
        k = f.BIC.idxmin() if len(f) else g.assign(v=(g.max_abs_r - RMAX).clip(lower=0) + (g.max_VIF / VMAX - 1).clip(lower=0)).sort_values(["v", "BIC"]).index[0]
        D.loc[k, "chosen"] = True
    b = D[D.candidate.str.startswith("far=separate") & ~D.candidate.str.contains("dropped")].set_index("segment")
    D["dBIC_vs_taz"] = D.BIC - D.segment.map(b.BIC); D["dheldout_LL_vs_taz"] = D.heldout_LL_obs - D.segment.map(b.heldout_LL_obs)
    D.to_csv(f"{RES}/respec_candidates_{kind}_tazr.csv", index=False); print(D[D.chosen].drop(columns="terms").round(4).to_string())


def chosen(seg):
    kind = seg.split("_")[1]; D = pd.read_csv(f"{RES}/respec_candidates_{kind}_tazr.csv"); c = D[(D.segment == seg) & D.chosen].iloc[0]
    k = pickle.load(open(f"{WORK}/respec_{seg}_tazr.pkl", "rb"))[c.candidate]; return c, k


def final(kind):
    sk = C.skims(); tabs, ho, coef = [], [], []
    for p_ in C.DISC:
        seg = f"{p_}_{kind}"; pur = p_; c, k = chosen(seg); spec = k["spec"]; xv = k["x"]
        sseg = seg if kind == "primary" else seg.replace("_stop", "_seq_stop")
        tabs.append(k["table"].assign(segment=seg, N=int(c.N), LL=k["LL"], candidate=c.candidate))
        coef += Z.coef_rows(sseg, spec, k["table"].set_index("param").value)
        rec, cand, cfg = load(seg, "estimation"); sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026)
        D = X.MixData(rec, cfg, *sets, spec, pur, sk)
        R, vif = X.collinearity(D, spec, dict(table=k["table"])); del D
        R.to_csv(f"{RES}/collin_{seg}_tazr.csv"); vif.to_csv(f"{RES}/vif_{seg}_tazr.csv")
        for half in ["estimation", "validation"]:
            rn, cn, gn = load(seg, half)
            runs = [("TAZ re-specified", rn, cn, gn, "mix")]
            if half == "validation":
                ro, co = E.load(half, seg)
                if kind == "primary": ro["multi"] = multi_flag(ro, half)
                else: ro = with_seq(ro); co = co[co.rec.isin(ro.rec)]; ro["male"] = 1.0 - ro.male
                runs.append(("TAZ re-specified coef on tract records", ro, co, X.single_cfg(ro), "pt"))
            for lab, r_, c_, g_, om in runs:
                h = X.heldout(r_, c_, g_, spec, xv, pur, sk, obs=om)
                grp = [("simple", r_.multi.values == 0), ("with stops", r_.multi.values == 1)] if kind == "primary" else [("out", r_.position.values == "out"), ("in", r_.position.values == "in")]
                for g, m in grp + [("all", np.ones(len(r_), bool))]:
                    w = r_.w.values; ok = m & np.isfinite(h["km_obs"])
                    ho.append(dict(segment=seg, half=half, model=lab, data="TAZ" if om == "mix" else "tract", group=g, N=int(m.sum()), LL_per_obs=float(h["LL"][m].mean()),
                                   km_obs=float(np.average(h["km_obs"][ok], weights=w[ok])), km_pred=float(np.average(h["km_pred"][m], weights=w[m])),
                                   KS=X.ks(h["tld_pred"], h["tld_obs"]) if g == "all" else np.nan))
                print("  ", ho[-1], flush=True)
        pre = "cx" if kind == "primary" else "seq"
        pd.concat(tabs).to_csv(f"{RES}/{pre}_estimates_tazr.csv", index=False); pd.DataFrame(ho).to_csv(f"{RES}/{pre}_heldout_tazr.csv", index=False)
        pd.DataFrame(coef).to_csv(f"{RES}/dest_choice_{'primary_cx' if kind == 'primary' else 'stop_seq'}_tazr.csv", index=False)


def biosub(kind, n):
    sk = C.skims()
    for p_ in C.DISC:
        seg = f"{p_}_{kind}"; pur = p_; c, k = chosen(seg); spec = k["spec"]
        rec, cand, cfg = load(seg, "estimation")
        rec = rec.sample(min(n, len(rec)), random_state=7).reset_index(drop=True); cand = cand[cand.rec.isin(rec.rec)]; cfg = cfg[cfg.rec.isin(rec.rec)]
        sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026)
        x0 = dict(zip(k["table"].param, k["table"].value))
        r = X.fit(spec, rec, cfg, *sets, pur, sk, x0=x0); r.pop("D")
        pre = "cx" if kind == "primary" else "seq"
        r["table"].assign(segment=seg, N=len(rec), LL=r["LL"]).to_csv(f"{RES}/{pre}_estimates_{seg}_taz_tazr_sub.csv", index=False)
        X.bio_export(f"{WORK}/bio_{seg}_taz_tazr_sub", spec, rec, cfg, *sets, pur, sk, {})
        print(seg, "sub N", len(rec), "LL", round(r["LL"], 4), flush=True)


if __name__ == "__main__":
    cmd, kind = sys.argv[1], sys.argv[2]
    if cmd == "search": search(kind)
    elif cmd == "final": final(kind)
    else: biosub(kind, int(sys.argv[3]))
