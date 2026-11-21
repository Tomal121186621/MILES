#!/usr/bin/env python3
"""Coefficient set with one attraction variable per destination model (2026-11-17): a copy of coef_respec_v2_C (the set of the current 2024 runs) with dest_choice_mnl.csv
rebuilt from side_experiments/respec_2026-11/step_by_step/size_logs/final_single_coef.csv (s_single.py, chosen variants in
final_single_fit.csv).  The engine's size term mu_size ln(1 + sum_c w_c x_c) with the one variable at weight 1 and mu_size = beta is
beta ln(1 + x); ln(zone area) is the zone variable lnarea (MarylandDestinationChoice, 2026-11-17).  Pooled models: the engine has no
scale, so every coefficient of purpose p is scale_p x the V-unit estimate (as build_coef_respec.pooled_primary).  Stops: the
sequential-anchor coefficients are also those of the two-anchor form (_stop), the logsum 'ls' is the engine's 'lstour'.
    python3 activity/build_parameters_single_attraction.py   ->  WORKSPACE/3_abit/coef_respec_v3 (its dest_choice_mnl.csv is activity/parameters/dest_choice_mnl.csv)"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, re, shutil, hashlib, json
import numpy as np, pandas as pd
A3 = f"{WORKSPACE}/3_abit"; V = WORKSPACE   # coefficient sets are built in the workspace
SRC, OUT = f"{A3}/coef_respec_v2_C", f"{A3}/coef_respec_v3"
FIN = f"{V}/side_experiments/respec_2026-11/step_by_step/size_logs/final_single_coef.csv"
LIN_OK = re.compile(r"^(d_\d+_(\d+|inf)|dt_\d+_(\d+|inf)|d|dt|lnd|lndt|lnd_\w+|lndt_\w+|ctime|cgt|ls|lstour|intra|intra_a|intra_b|bc|dcz|va|othst|cbd|mix|lnarea|xcounty|xstate|ptav|ptav_car0)$")
ABBR = {"SHOPPING": "S", "RECREATION": "R", "ACCOMPANY": "A", "OTHER": "O", "l02_nonstud": "N", "l01_daycare": "D"}
STOP = {"s_shop": "SHOPPING", "s_rec": "RECREATION", "s_acc": "ACCOMPANY", "s_oth": "OTHER"}
LOC = {"l03_wahb": "WORK_wahb", "l04_wbhome": "WORK_wbhome", "l05_wbwork": "WORK_wbwork_stop", "l06_outing_dest": "OTHER_wbs"}
POOLSEG = {"SHOPPING": "SHOPPING_primary", "RECREATION": "RECREATION_primary", "ACCOMPANY": "ACCOMPANY_primary", "OTHER": "OTHER_primary",
           "l02_nonstud": "EDUCATION_nonstud", "l01_daycare": "EDUCATION_daycare"}


def rows_of(seg, coefs, scale=1.0, rename=None):
    lx = [k for k in coefs if k.startswith("lnx_")]; assert len(lx) == 1, (seg, lx)
    out = [(seg, "mu_size", scale * coefs[lx[0]]), (seg, f"size_{lx[0][4:]}", 1.0)]
    for k, v in coefs.items():
        if k in lx: continue
        k = (rename or {}).get(k, k); assert LIN_OK.match(k), f"{seg}: {k} not in the engine"
        out.append((seg, k, scale * v))
    return out


def main():
    c = pd.read_csv(FIN); rows = []
    for m, p in STOP.items():
        d = c[c.model == m].set_index("param").coef.to_dict()
        for seg in (f"{p}_seq_stop", f"{p}_stop"): rows += rows_of(seg, d, rename={"ls": "lstour"})
    for m, seg in LOC.items(): rows += rows_of(seg, c[c.model == m].set_index("param").coef.to_dict())
    for m in ("dp", "lp_edu"):
        d = c[c.model == m]; P = [p for p in d.purpose.unique() if p in POOLSEG]
        for p in P:
            sc = d[(d.purpose == p) & (d.param == "scale")].coef; sc = float(sc.iloc[0]) if len(sc) else 1.0
            mine = d[(d.param != "scale") & ((d.purpose == p) | (d.purpose == "shared") | d.purpose.apply(lambda g: ABBR[p] in g.split("+")))]
            assert not mine.param.duplicated().any(), (p, mine[mine.param.duplicated()].param.tolist())
            rows += rows_of(POOLSEG[p], mine.set_index("param").coef.to_dict(), sc)
    dm = pd.DataFrame(rows, columns=["segment", "variable", "value"])
    old = pd.read_csv(f"{SRC}/dest_choice_mnl.csv"); assert set(old.segment) == set(dm.segment), set(old.segment) ^ set(dm.segment)
    if os.path.exists(OUT): shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT); dm.to_csv(f"{OUT}/dest_choice_mnl.csv", index=False)
    rp = f"{OUT}/run_params.csv"; txt = open(rp).read(); open(rp, "w").write(txt.replace(SRC + "/", OUT + "/"))   # files of the set point into it
    sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
    json.dump(dict(source=SRC, estimates=FIN, estimates_sha256=sha(FIN), dest_choice_mnl_sha256=sha(f"{OUT}/dest_choice_mnl.csv")),
              open(f"{OUT}/SINGLE_STATE.json", "w"), indent=1)
    print(f"{OUT}: dest_choice_mnl {len(dm)} rows, {dm.segment.nunique()} segments (old {len(old)} rows)")
    print(dm[dm.variable.isin(["mu_size", "lnarea"]) | dm.variable.str.startswith("size_")].pivot(index="segment", columns="variable", values="value").round(3).to_string())


if __name__ == "__main__":
    main()
