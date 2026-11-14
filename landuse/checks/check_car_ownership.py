#!/usr/bin/env python3
"""Unit check of the engine's re-specified car-ownership utilities (CarOwnershipRespec.main, the function CarOwnershipModelMd calls
under car.ownership.spec = respec) against X beta of the final model, on 3,000 households of the estimation sample (raw PUMS variables
in, the engine builds the variables).  Also:
  location  the engine's PUMA accessibility gain and density (CarOwnershipModelMd.updateLocation logic on the respec location file and
            data/accessibility_2016.csv, base-year stock = 2016 so the density ratio is 1) against hh.parquet, by PUMA
  age       2026-11-09: the model is re-estimated with the oldest member's age (s08_oldest_age.py), the engine's definition
    python3 landuse/checks/check_car_ownership.py <scratch dir>   ->  c02_car_check.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, zipfile, subprocess
import numpy as np, pandas as pd
V = f"{WORKSPACE}"; ROOT = PROJECT_ROOT
HERE = f"{V}/side_experiments/respec_2026-11/engine_check"; SCR = sys.argv[1] if len(sys.argv) > 1 else HERE   # outputs (workspace)
C = f"{ESTIMATION_RESULTS}/car_ownership"; INP = f"{V}/2_silo/input"   # estimation results (data)
sys.path.insert(0, f"{MILES_HOME}/estimation/development/car_ownership")   # estimation code (mnl, s04_form, s06_age)
from mnl import probs, design   # noqa: E402
from s06_age import head_age, oldest_age, prep   # noqa: E402
from s04_form import pieces   # noqa: E402
JAVA = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip() + "/bin/java"
CP = f"{V}/2_silo/engine/useCases/maryland/target/classes"
GROUPS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]


def main():
    cf = pd.read_csv(f"{INP}/car_ownership_estimated_coefficients.csv"); md = float(cf.query("alternative == 0").value.iloc[0])
    Vs = pd.read_csv(f"{C}/s07_fit.csv").query("step == 'final'").spec.iloc[0].split()
    d = pd.read_parquet(f"{C}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True); ha = oldest_age(); hh_age = head_age(); d0 = d.copy()   # 2026-11-09: the model uses the oldest member   # d0: counts before the caps of prep()
    d = prep(d, d.ln_density.mean(), ha); pieces(d)
    b = np.concatenate([[cf.query(f"alternative == {a} and variable == 'asc'").value.iloc[0]] +
                        [cf.query(f"alternative == {a} and variable == '{v}'").value.iloc[0] for v in Vs] for a in (1, 2, 3)])
    X = design(d, Vs); K = X.shape[1]; U = X @ b.reshape(K, 3, order="F")
    rng = np.random.default_rng(20261109); idx = np.sort(rng.choice(len(d), 3000, replace=False)); s = d.iloc[idx]
    typ = np.select([s.sfd == 1, s.multifamily == 1, s.sfa == 1], ["SFD", "MF234", "SFA"], "MH")
    raw = pd.DataFrame({"id": idx, "workers": d0.workers.values[idx], "persons16": d0.adults16.values[idx], "children": d0.children.values[idx], "size": s.hhsize.values,
                        "income": s.income_k.values * 1000, "age": s.serial.map(ha).values, "type": typ, "bedrooms": s.bedrooms.values,
                        "ln_density": s.ln_density.values, "acc_gain": s.acc_gain.values})
    # counts before the caps of prep(): the engine applies the caps itself (CarOwnershipRespec.vars)
    fi = f"{SCR}/c02_in.csv"; fo = f"{SCR}/c02_out.csv"; raw.to_csv(fi, index=False)
    r = subprocess.run([JAVA, "-cp", CP, "de.tum.bgu.msm.models.CarOwnershipRespec", f"{INP}/car_ownership_estimated_coefficients.csv", fi, fo], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr)
    j = pd.read_csv(fo); j["V_py"] = U[j.id.values, j.alt.values - 1]; diff = (j.V - j.V_py).abs()
    res = [dict(part="utilities", n=len(j), max_abs_diff=float(diff.max()), note=f"{len(idx)} households x 3 alternatives")]
    print(res[-1], flush=True)
    # location variables by the engine rule
    pf = pd.read_csv(f"{INP}/car_ownership_puma_attributes.csv"); acc = pd.read_csv(f"{V}/data/accessibility_2016.csv"); acc = acc[acc.purpose == "nonwork"]
    gmax = 0.0; dmax = 0.0
    for g in GROUPS:
        ac = pf.zone.map(acc[acc.segment == f"{g}_carge"].set_index("zone").A); an = pf.zone.map(acc[acc.segment == f"{g}_nocar"].set_index("zone").A)
        gc = (ac * pf.hu).groupby(pf.puma).sum() / pf.hu.where(ac.notna(), 0).groupby(pf.puma).sum()
        gn = (an * pf.hu).groupby(pf.puma).sum() / pf.hu.where(an.notna(), 0).groupby(pf.puma).sum()
        gain = gc - gn
        inc = d.income_k * 1000; grp = np.array(GROUPS)[np.searchsorted([40000, 75000, 125000], inc.values, side="right")]
        m = grp == g; gmax = max(gmax, float((d.acc_gain[m] - d.puma7[m].map(gain)).abs().max()))
    dens = pf.drop_duplicates("puma").set_index("puma").density_2016
    dmax = float((d.ln_density - np.log(d.puma7.map(dens))).abs().max())
    res.append(dict(part="location: accessibility gain by PUMA", n=int(d.puma7.nunique()), max_abs_diff=gmax, note="engine rule vs hh.parquet"))
    res.append(dict(part="location: ln density by PUMA (base year)", n=int(d.puma7.nunique()), max_abs_diff=dmax, note="engine rule vs hh.parquet"))
    print(res[-2:], flush=True)
    # age (2026-11-09): the model is estimated with the oldest member, the engine's definition; share of households where it differs
    # from the householder, for the record
    res.append(dict(part="age definition: oldest member in estimation and engine", n=len(d), max_abs_diff=0.0,
                    note=f"oldest member differs from the PUMS householder in {(d.serial.map(ha) != d.serial.map(hh_age)).mean():.1%} of households"))
    pd.DataFrame(res).to_csv(f"{HERE}/c02_car_check.csv", index=False)


if __name__ == "__main__":
    main()
