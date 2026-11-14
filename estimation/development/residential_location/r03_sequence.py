#!/usr/bin/env python3
"""Residential location, level 2 (zone x dwelling type), model development for reporting: blocks added in a fixed order to the
size-only model; a block is kept when the likelihood-ratio test is significant at 5 %, BIC falls and the signs are the expected
ones.  Selection on the estimation half (30 sampled cells, the draws of s05_zone.py); the validation half (full choice set) is
used once, for the final model.  Households with a known age (the age blocks need it), the same sample at every step.
  Z0 size term            Z1 + accessibility (work, non-work)      Z2 + commute, sum of ln(1 + t)      Z3 + commute x ln income
  Z4 + zone price level (ln mean cost, x ln income)                Z5 + accessibility x household (children; no car)
  Z6 + age x non-work accessibility (forms compared by BIC: member 65+, linear, bands under 35 / 50-64 / 65+)
  Z7 + household size x non-work accessibility                     Z8 + household size x ln zone cost
  Z9 + income similarity (share of the household's income group in the zone)
  2026-11-10 (author approval): land-use block after Z4, one candidate per step in this order (zone attributes of r11_zone_landuse.py):
  Z4a ln dwelling density (-), Z4b ln(1 + job density) (-), Z4c ln(1 + retail jobs per km2) (no prior: kept on LR + BIC only),
  Z4d land-use mix (+), Z4e paid-parking share (-); after Z7: Z7b dwelling density x no car (+) and x children (-), one set (only
  when the density is kept).  Signs of the new terms checked automatically; the full-set log-likelihood of the validation half is
  reported for every new step (requested for the report; the selection uses the estimation half only).
    python3 estimation/development/residential_location/r03_sequence.py   ->  r03_fit.csv, r03_coef.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{ESTIMATION_RESULTS}/residential"   # results of this step (data); CODE = this folder
import r01_income_similarity as R1   # noqa: E402  (sets up s05_zone with the final inputs)
import r02_age_hhsize as R2   # noqa: E402
Z = R1.Z
from mnl import MNL, lr_test   # noqa: E402

R2.base_X = R1.hh_cell_X
from rc import ZONE_IDS   # noqa: E402
LU = pd.read_csv(f"{HERE}/zone_landuse_2016.csv").set_index("zone").reindex(ZONE_IDS)
LUA = {k: LU[k].values.astype(float) for k in ["lnddens", "lnjden", "lnretden", "mix", "park"]}
LU_TERMS = list(LUA) + ["lnddens_x_nocar", "lnddens_x_child"]
CHECK_TERMS = LU_TERMS + ["accW_x_nocar"]   # blocks with the automatic sign rule and the validation LL (accW_x_nocar: 2026-11-10)
SIGN = {"lnddens": -1, "lnjden": -1, "mix": 1, "park": -1, "lnddens_x_nocar": 1, "lnddens_x_child": -1, "accW_x_nocar": 1}   # lnretden: no prior


def hh_cell_X(hh, zi, ti, zd, spec):
    X, names = R2.hh_cell_X(hh, zi, ti, zd, spec)
    add = {k: LUA[k][zi] for k in LUA}
    add["lnddens_x_nocar"] = LUA["lnddens"][zi] * float(hh.car == "nocar"); add["lnddens_x_child"] = LUA["lnddens"][zi] * hh.children
    for k in LU_TERMS:
        if k in spec: X = np.column_stack([X, add[k]]); names = names + [k]
    return X, names


Z.hh_cell_X = hh_cell_X
AGE = {"member 65+": ["accN_x_age65"], "linear": ["accN_x_age"], "bands": ["accN_x_ageU35", "accN_x_age50_64", "accN_x_age65"]}
# 2026-11-10 (author): work accessibility dropped (significant wrong sign, -0.19, t -2.5); Z1 = non-work accessibility only, work
# accessibility x no car tested as its own block (Z5w, expected +)
# 2026-11-10 (author, RESPEC_PROTOCOL section 1, silo/CANDIDATES.md): non-work accessibility is a BASE term, kept as the main effect
# of its interactions unless it has the wrong sign with |t| > 2; then a final backward check of the non-base terms with |robust t| <
# 1.96 on the multimodal form (the chosen accessibility of r08), one term (or set: age bands, density x household) at a time, the set
# dropped only when none of its members is significant
BASE_TERMS = {"lnD", "accN"}
SETS = [("accN_x_ageU35", "accN_x_age50_64", "accN_x_age65"), ("lnddens_x_nocar", "lnddens_x_child")]
BLOCKS = [("Z1", "+ non-work accessibility (base term)", [["accN"]]),
          ("Z2", "+ commute, sum of ln(1 + t)", [["commute_log"]]),
          ("Z3", "+ commute x ln income", [["commute_log_x_inc"]]),
          ("Z4", "+ zone price level (ln cost, x ln income)", [["lncost", "lncost_x_inc"]]),
          ("Z4a", "+ ln dwelling density", [["lnddens"]]),
          ("Z4b", "+ ln(1 + job density)", [["lnjden"]]),
          ("Z4c", "+ ln(1 + retail jobs per km2)", [["lnretden"]]),
          ("Z4d", "+ land-use mix", [["mix"]]),
          ("Z4e", "+ paid-parking share", [["park"]]),
          ("Z5", "+ non-work accessibility x children", [["accN_x_child"]]),
          ("Z5w", "+ work accessibility x no car", [["accW_x_nocar"]]),
          ("Z6", "+ age x non-work accessibility", list(AGE.values())),
          ("Z7", "+ household size x non-work accessibility", [["accN_x_hhs"]]),
          ("Z7b", "+ dwelling density x no car, x children", [["lnddens_x_nocar", "lnddens_x_child"]]),
          ("Z8", "+ household size x ln zone cost", [["lncost_x_hhs"]]),
          ("Z9", "+ income similarity", [["sim"]])]


def main():
    h, _ = Z.load_rts(); h = h[h.age_max.notna() & (h.age_max >= 0)]
    zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1])
    est = h[h.half == "estimation"].copy(); val = h[h.half == "validation"].copy(); drawn = Z.draw(est, zd, cells, 30)
    fd_val = Z.draw(val, zd, cells, 30, full=True)
    fit, coef = [], []

    def run(code, label, sp, ref):
        X, names, av, C, ok, _ = Z.build(est, zd, cells, sp, 30, drawn=drawn)
        w = est.wthhfin.values[ok]; w = w / w.mean(); m = MNL(X, names, av, C, weights=w).fit()
        row = dict(step=code, label=label, K=m.k, LL=m.ll, BIC=m.k * np.log(ok.sum()) - 2 * m.ll, converged=m.converged)
        if ref is not None and m.k > ref.k: row.update(zip(["LR", "df", "p"], lr_test(ref.ll, m.ll, m.k - ref.k)))
        t = m.table(); t.insert(0, "step", code); t.insert(1, "label", label); coef.append(t)
        return m, row, t

    cur, row, _ = run("Z0", "size term", ["lnD"], None); row["kept"] = True; fit.append(row); spec = ["lnD"]
    print(row, flush=True)
    for code, label, options in BLOCKS:
        if code == "Z7b" and "lnddens" not in spec:
            fit.append(dict(step=code, label=label + " (not tested: density not in the model)", kept=False)); continue
        best = None
        for o in options:
            lab = label if len(options) == 1 else f"{label}: {[k for k, v in AGE.items() if v == o][0]}"
            m, row, t = run(code, lab, spec + o, cur)
            row["kept"] = False; fit.append(row)
            if any(v in CHECK_TERMS for v in o):   # new blocks: automatic sign rule and the validation full-set LL
                est_ = t.set_index("parameter").estimate; bad = [v for v in o if v in SIGN and np.sign(est_[v]) != SIGN[v]]
                Xf, nf, avf, Cf, okf, _ = Z.build(val, zd, cells, spec + o, 30, full=True, drawn=fd_val)
                row["fullset_LL_validation"] = float(MNL(Xf, nf, avf, Cf).loglik_obs(m.b).sum()); row["sign_bad"] = ";".join(bad)
                row["decision"] = ("not kept: sign" if bad else "not kept: BIC" if row["BIC"] >= cur_bic(cur, est) else "not kept: LR" if row.get("p", 1) >= 0.05 else "kept")
                if bad: print(row, flush=True); print(t[t.parameter.isin(o)].to_string(), flush=True); continue
            print(row, flush=True); print(t[t.parameter.isin(o)].to_string(), flush=True)
            if code == "Z1":   # base term
                tt = t.set_index("parameter"); wrong = tt.estimate["accN"] < 0 and abs(tt.robust_t["accN"]) > 2
                row["decision"] = "not kept: wrong sign, |t| > 2" if wrong else "kept (base term)"
                if not wrong: best = (m, row, o)
                continue
            if row.get("p", 1) < 0.05 and row["BIC"] < (best[1]["BIC"] if best else cur_bic(cur, est)) : best = (m, row, o)
        if best:   # signs checked by hand in r03_coef.csv
            best[1]["kept"] = True; cur, spec = best[0], spec + best[2]
    # final backward check (non-base terms, |robust t| < 1.96), multimodal accessibility
    Z.ACC_FILE = os.environ.get("ACC_MM", Z.ACC_FILE); zdm = Z.zone_data(); cellsm = Z.cells_of_region(zdm[0], zdm[1]); k = 0
    while True:
        X, names, av, C, ok, _ = Z.build(est, zdm, cellsm, spec, 30, drawn=drawn); w = est.wthhfin.values[ok]; mm = MNL(X, names, av, C, weights=w / w.mean()).fit()
        tt = mm.table().set_index("parameter").robust_t.abs()
        units = [tuple(x for x in st if x in spec) for st in SETS if any(x in spec for x in st)] + [(v,) for v in spec if v not in BASE_TERMS and not any(v in st for st in SETS)]
        cand = [(max(tt[x] for x in u), u) for u in units if max(tt[x] for x in u) < 1.96]
        if not cand: break
        _, u = min(cand); k += 1; sp2 = [v for v in spec if v not in u]
        X2, n2, av2, C2, ok2, _ = Z.build(est, zdm, cellsm, sp2, 30, drawn=drawn); m2 = MNL(X2, n2, av2, C2, weights=w / w.mean()).fit()
        lr, df, p = lr_test(m2.ll, mm.ll, mm.k - m2.k)
        fit.append(dict(step=f"B{k}", label="Final check: without " + ", ".join(u) + f" (|t| {max(tt[x] for x in u):.2f}, multimodal form)", K=m2.k, LL=m2.ll,
                        BIC=m2.k * np.log(ok2.sum()) - 2 * m2.ll, LR=lr, df=df, p=p, kept=True, decision="dropped: not significant"))
        print(fit[-1], flush=True); spec = sp2
    m, row, t = run("final", "final model", spec, None)
    for nm, hs in (("estimation", est), ("validation", val)):
        fd = Z.draw(hs, zd, cells, 30, full=True); Xf, nf, avf, Cf, okf, _ = Z.build(hs, zd, cells, spec, 30, full=True, drawn=fd)
        row[f"fullset_LL_{nm}"] = float(MNL(Xf, nf, avf, Cf).loglik_obs(m.b).sum())
    row["spec"] = " ".join(spec); row["kept"] = True; fit.append(row); print(row, flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/r03_fit.csv", index=False); pd.concat(coef).to_csv(f"{HERE}/r03_coef.csv", index=False)


def cur_bic(m, est):
    return m.k * np.log(m.n) - 2 * m.ll if hasattr(m, "n") else np.inf


if __name__ == "__main__":
    main()
