#!/usr/bin/env python3
"""Collinearity of the final dwelling model (residential_location/r06_dwelling_income.py, final row of r06_fit.csv after the 2026-11-09
re-run: chosen form 'Terms and terms x ln income' minus the terms listed with '-' in its 'spec' column),
estimation half, chosen + 29 sampled dwellings (the draws of r06), unweighted as in the estimation.
    python3 estimation/development/collinearity/c_silo_dwelling.py   ->  dwelling_var_corr.png, dwelling_est_corr.png, dwelling_pairs.csv, dwelling_facts.json"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; RES = os.path.join(os.path.dirname(HERE), "residential")
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.path.insert(0, os.path.join(DEV, "residential_location")); sys.path.insert(0, CODE)
import c_silo_common as CC   # noqa: E402
import r06_dwelling_income as R6   # noqa: E402
DW = R6.DW
from mnl import MNL   # noqa: E402
zratio = CC.zratio

TY = {"SFA": "SFA", "MF234": "MF 2–4", "MF5plus": "MF 5+", "MH": "Mobile home"}
PL = {"bur_lo": "Cost share of income, slope below 30 %", "bur_mid": "Cost share of income, slope 30–50 %", "bur_hi": "Cost share of income, slope above 50 %",
      "lncost": "ln monthly housing cost", "bed_short": "Bedroom shortfall (per bedroom)", "bed_extra": "Bedroom excess (per bedroom)", "new5": "Built in the last five years"}
TL = {"": "Constant", "_x_size": "× (household size − 1, at most 5)", "_x_child": "× children", "_x_ageU35": "× oldest member under 35",
      "_x_age50_64": "× oldest member 50–64", "_x_age65": "× oldest member 65+", "_x_lninc": "× ln income"}


def main():
    DW.build_X = R6.build_X
    fr = pd.read_csv(f"{RES}/r06_fit.csv"); fin = fr[fr.validation_LL.notna()].iloc[0]; spec = set(fin.spec.split(";"))
    assert {"type_inter", "age_bands", "income_slope"} <= spec, spec; print("final", fin.model, sorted(spec), flush=True)
    mv = pd.read_parquet(f"{R6.R4.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R6.R4.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True)
    alt, av = DW.sample_alts(est, pool, 30)                     # first draw of the module RNG, as in r06 main
    X, names = R6.build_X(est, alt, spec); C = np.zeros_like(av); C[:, 0] = True
    LAB = {}
    for v in R6.PRICE: LAB[v] = PL[v]; LAB[f"{v}_x_lninc"] = f"{PL[v]} × ln income"
    for t in TY:
        for s, l in TL.items(): LAB[f"{t}{s}"] = f"{TY[t]}: {l}"
    order = [n for v in R6.PRICE for n in (v, f"{v}_x_lninc")] + [f"{t}{s}" for t in TY for s in TL]
    order = [n for n in order if "-" + n not in spec]
    assert sorted(order) == sorted(names); X = X[:, :, [names.index(v) for v in order]]; names = order

    def run(drop=(), replace=None):
        Xr = X.copy()
        for k, v in (replace or {}).items(): Xr[:, :, names.index(k)] = v
        keep = [i for i, n in enumerate(names) if n not in drop]
        m = MNL(Xr[:, :, keep], [names[i] for i in keep], av, C).fit()
        return dict(LL=m.ll, K=m.k, N=len(est), names=list(m.names), b=m.b, se=m.rse, cov=m.cov_robust)

    base = run(); print("LL", base["LL"], "reported", fin.LL, flush=True); assert abs(base["LL"] - fin.LL) < 0.1
    ix = names.index; inter = {}
    for v in R6.PRICE:
        if f"{v}_x_lninc" in names: inter[f"{v}_x_lninc"] = (v, zratio(X, ix(f"{v}_x_lninc"), ix(v), av), None)
    for t in TY:
        for s in TL:
            if s and f"{t}{s}" in names: inter[f"{t}{s}"] = (t, zratio(X, ix(f"{t}{s}"), ix(t), av), "age" if "_age" in s else None)
    for k, (m, z, _) in inter.items():
        assert np.allclose(X[:, :, ix(k)] * av, X[:, :, ix(m)] * z[:, None] * av, atol=1e-6), k
    sets = [({"bur_lo", "bur_mid"}, "adjacent piecewise segments"), ({"bur_mid", "bur_hi"}, "adjacent piecewise segments"),
            ({"bur_lo", "bur_hi"}, "piecewise segments (non-adjacent)"),
            ({"bur_lo_x_lninc", "bur_mid_x_lninc", "bur_hi_x_lninc"}, "piecewise segments × ln income"),
            ({"bed_short", "bed_extra"}, "piecewise segments (bedrooms relative to need)"),
            ({"bed_short_x_lninc", "bed_extra_x_lninc"}, "piecewise segments × ln income"),
            (set(TY), "members of one band set (structure types)")] + \
           [({f"{t}{s}" for t in TY}, "members of one band set (structure types) × the same household variable") for s in TL if s]
    CC.run_alt_model("dwelling", "Dwelling (residential level 3), final model", X, names, av, np.ones(len(est)), LAB, inter, sets, base,
                     lambda drop, replace: run(drop, replace))


if __name__ == "__main__":
    main()
