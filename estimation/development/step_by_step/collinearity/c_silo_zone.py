#!/usr/bin/env python3
"""Collinearity of the final zone x structure-type model (residential/r08_zone_multimodal.py, multimodal accessibility chosen;
spec of r03_fit.csv 'final'), estimation half, chosen + 29 sampled cells (the draws of r08, made first with the car-based zone data),
household weights wthhfin as in the estimation.  Env ACC_CAR / ACC_MM as in residential/run_residential_chain.sh (set here if absent).
    python3 c_silo_zone.py   ->  zone_var_corr.png, zone_est_corr.png, zone_pairs.csv, zone_facts.json"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); SB = os.path.dirname(HERE); RES = os.path.join(SB, "residential")
A = os.path.join(SB, "accessibility_new")
os.environ.setdefault("ACC_CAR", f"{A}/accessibility_2016_new.csv"); os.environ.setdefault("ACC_MM", f"{A}/accessibility_2016_new_multimodal.csv")
sys.path.insert(0, RES); sys.path.insert(0, HERE)
import c_silo_common as CC   # noqa: E402
import r08_zone_multimodal as R8   # noqa: E402  (imports r03 -> r01, r02: s05_zone with the final inputs)
Z = R8.Z
from mnl import MNL   # noqa: E402

LAB = {"lnD": "ln dwellings of the structure type in the zone (θ)", "accW": "Work accessibility", "accW_x_nocar": "Work accessibility × no car",
       "accN": "Non-work accessibility", "accN_x_child": "Non-work accessibility × children", "accN_x_ageU35": "Non-work accessibility × oldest member under 35",
       "accN_x_age50_64": "Non-work accessibility × oldest member 50–64", "accN_x_age65": "Non-work accessibility × oldest member 65+",
       "accN_x_hhs": "Non-work accessibility × (household size − 1, at most 5)", "commute_log": "Sum over workers of ln(1+t)",
       "lncost": "ln mean monthly housing cost of the zone", "lncost_x_inc": "ln zone cost × ln income",
       "lncost_x_hhs": "ln zone cost × (household size − 1, at most 5)", "sim": "Share of same-income households in the zone",
       # 2026-11-10 land-use block
       "lnddens": "ln dwelling density (per acre)", "lnretden": "ln(1 + retail jobs per km²)", "lnddens_x_nocar": "ln dwelling density × no car",
       "lnddens_x_child": "ln dwelling density × children"}
ORDER = list(LAB)


zratio = CC.zratio


def main():
    fr = pd.read_csv(f"{RES}/r08_fit.csv"); fin = fr[fr.chosen == True].iloc[0]; assert fin.model == "multimodal accessibility"   # noqa: E712
    spec = pd.read_csv(f"{RES}/r03_fit.csv").query("step == 'final'").spec.iloc[0].split()
    h, _ = Z.load_rts(); h = h[h.age_max.notna() & (h.age_max >= 0)]; est = h[h.half == "estimation"].copy()
    Z.ACC_FILE = os.environ["ACC_CAR"]; zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1]); drawn = Z.draw(est, zd, cells, 30)
    Z.ACC_FILE = os.environ["ACC_MM"]; zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1])
    X, names, av, C, ok, _ = Z.build(est, zd, cells, spec, 30, drawn=drawn)
    w = est.wthhfin.values[ok]; w = w / w.mean()
    order = [v for v in ORDER if v in names]; idx = [names.index(v) for v in order]; assert sorted(names) == sorted(order), set(names) - set(order); X = X[:, :, idx]; names = order

    def run(drop=(), replace=None):
        Xr = X.copy()
        for k, v in (replace or {}).items(): Xr[:, :, names.index(k)] = v
        keep = [i for i, n in enumerate(names) if n not in drop]
        m = MNL(Xr[:, :, keep], [names[i] for i in keep], av, C, weights=w).fit()
        return dict(LL=m.ll, K=m.k, N=int(ok.sum()), names=list(m.names), b=m.b, se=m.rse, cov=m.cov_robust)

    base = run(); print("LL", base["LL"], "reported", fin.LL, flush=True); assert abs(base["LL"] - fin.LL) < 0.1
    ix = names.index
    PAIRS = {"accW_x_nocar": ("accW", None), "accN_x_child": ("accN", None), "accN_x_ageU35": ("accN", "age"), "accN_x_age50_64": ("accN", "age"),
             "accN_x_age65": ("accN", "age"), "accN_x_hhs": ("accN", None), "lncost_x_inc": ("lncost", None), "lncost_x_hhs": ("lncost", None),
             "lnddens_x_nocar": ("lnddens", None), "lnddens_x_child": ("lnddens", None)}
    # 2026-11-10: an interaction whose main term is not in the model (work accessibility dropped) has no recovered person variable
    inter = {k: (m, zratio(X, ix(k), ix(m), av), g) for k, (m, g) in PAIRS.items() if k in names and m in names}
    inter = {k: v for k, v in inter.items() if k in names}
    for k, (m, z, _) in inter.items():   # the recovered person variable reproduces the interaction column
        assert np.allclose(X[:, :, ix(k)] * av, X[:, :, ix(m)] * z[:, None] * av, atol=1e-6), k
    CC.run_alt_model("zone", "Zone × structure type (residential level 2), final model", X, names, av, w, LAB, inter, [], base,
                     lambda drop, replace: run(drop, replace))


if __name__ == "__main__":
    main()
