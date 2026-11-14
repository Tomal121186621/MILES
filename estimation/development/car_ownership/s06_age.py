#!/usr/bin/env python3
"""Car ownership: the full age range instead of the member-65+ dummy, on the final model (step 5).  Age of the householder
(PUMS RELP = 0), which SILO also stores (every person's age and the household head).
  A1  householder age, linear            A2  age and age squared
  A3  age bands covering all ages: under 30, 45-64, 65+ (reference 30-44)
  A4  A3 with the member-65+ dummy kept
Unweighted MNL as in step 5; BIC on the estimation sample and log-likelihood of the hold-out 20 %.
    python3 estimation/development/car_ownership/s06_age.py   ->  s06_age.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, zipfile
import numpy as np, pandas as pd
from mnl import fit, probs, design
from s04_form import REST, pieces
from s01_data import ROOT

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder


def head_age():
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_pmd.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        P = pd.read_csv(zf.open(n), usecols=["SERIALNO", "RELP", "AGEP"], low_memory=False, dtype={"SERIALNO": str})
    return P[P.RELP == 0].drop_duplicates("SERIALNO").set_index("SERIALNO").AGEP


def oldest_age():
    """2026-11-09: age of the OLDEST member of the household (all persons), the age SILO can compute (it stores no householder);
    the final model is re-estimated with it (s08_oldest_age.py)"""
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_pmd.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        P = pd.read_csv(zf.open(n), usecols=["SERIALNO", "AGEP"], low_memory=False, dtype={"SERIALNO": str})
    return P.groupby("SERIALNO").AGEP.max()


def prep(d, md, ha):
    for c in ["workers", "nonworking_adults", "children"]: d[c] = d[c].clip(upper=6)
    d["inc_x_dens"] = d.ln_income * (d.ln_density - md); a = d.serial.map(ha).astype(float)
    d["age10"] = (a - 45) / 10; d["age10_sq"] = d.age10 ** 2
    d["age_u30"] = (a < 30).astype(float); d["age45_64"] = ((a >= 45) & (a < 65)).astype(float); d["age65"] = (a >= 65).astype(float)
    return d


def main():
    ha = head_age(); h = pd.read_parquet(f"{HERE}/hh.parquet")
    e = h[h.half == "estimation"].reset_index(drop=True); o = h[h.half == "holdout"].reset_index(drop=True)
    md = e.ln_density.mean(); e = prep(e, md, ha); o = prep(o, md, ha)
    print("householder age missing:", int(e.age10.isna().sum()), int(o.age10.isna().sum()))
    e = e[e.age10.notna()].reset_index(drop=True); o = o[o.age10.notna()].reset_index(drop=True)
    V = REST + pieces(e) + ["inc_x_dens"]; pieces(o); no65 = [v for v in V if v != "any_65plus"]
    runs = [("final model (member 65+)", V), ("A1 age linear", no65 + ["age10"]), ("A2 age + age squared", no65 + ["age10", "age10_sq"]),
            ("A3 age bands", no65 + ["age_u30", "age45_64", "age65"]), ("A4 age bands + member 65+", V + ["age_u30", "age45_64", "age65"])]
    rows = []
    for lab, vs in runs:
        r = fit(e, vs); ho = float(np.log(probs(r["b"], design(o, vs))[np.arange(len(o)), o.cars.values]).sum())
        row = dict(model=lab, K=r["K"], LL=r["LL"], BIC=r["BIC"], holdout_LL=ho)
        for n, b, s in zip(r["names"], r["b"], r["se"]):
            v, alt = n.split("|")
            if v.startswith("age") or v == "any_65plus": row[f"{v}|{alt}"] = f"{b:+.3f} ({b / s:.1f})"
        rows.append(row); print(row, flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/s06_age.csv", index=False)


if __name__ == "__main__":
    main()
