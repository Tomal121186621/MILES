#!/usr/bin/env python3
"""Unit check of the schools step of the chain (landuse/schools/assign_schools.py with --coefficients
2_silo/schoolchoice/apply/school_choice_coefficients_respec.csv) against the estimation utility of the final school models (l07,
school_likelihood Design 'full'):
for 60 students per segment of the estimation half, every (student, possible home zone) row, a synthetic person file places one student
of the same type (car availability, income group, sex, band) at that home zone; assign_schools.py --dump-utilities writes V_hkj = mu ln S_hkj +
sum b x over all school zones of the band (no shadow prices), compared with V_hj of the estimation code (mu ln S + X b).
    python3 landuse/checks/check_school_location.py <scratch dir>   ->  c04_school_check.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, subprocess
import numpy as np, pandas as pd
V = f"{WORKSPACE}"; SCD = f"{V}/2_silo/schoolchoice"   # school-choice data (apply/, work/)
HERE = f"{V}/side_experiments/respec_2026-11/engine_check"; SCR = sys.argv[1] if len(sys.argv) > 1 else HERE   # outputs (workspace)
L = f"{ESTIMATION_RESULTS}/locations"
sys.path.insert(0, f"{MILES_HOME}/landuse/schools"); import school_likelihood as G; import school_stepwise as S4   # noqa: E402
SEGB = {"k8": "k8", "hs": "hs", "col": "college"}; AGE = {"elementary": 8, "middle": 12, "high": 15, "postsec": 20}; INC = {1: 20000, 2: 57500, 3: 100000, 4: 200000}


def v64(D, c, r, A):
    """estimation utility of row r over zones A recomputed in double precision (school_likelihood holds times, terms and sizes in float32)"""
    import school_common as SC
    if "T64" not in G.__dict__:
        sk = pd.read_csv(f"{V}/2_silo/input/skims/auto_peak_time.csv.gz"); zi = SC.zidx(); T = np.full((G.NZ, G.NZ), np.nan)
        T[zi[sk.FROM].values, zi[sk.TO].values] = sk.VALUE.values; G.T64 = T; G.M64 = {}
    seg = D.seg; i = D.rec[r]; h = D.h[r]; b = D.band[i]; t = G.T64[h, A]
    if seg == "col": NK = np.stack([G.SIZE[b].get(k, np.zeros(G.NZ))[A] for k in D.comps]).astype(float)
    else:
        if b not in G.M64:
            Ab = pd.read_parquet(f"{SC.W}/sabs_home_school.parquet"); Ab = Ab[Ab.band == b]
            cap = pd.read_parquet(f"{SC.W}/school_points.parquet").set_index("id").capacity; M = np.zeros((G.NZ, G.NZ))
            np.add.at(M, (G.zi[Ab.zone].values, G.zi[Ab.school_zone].values), (Ab.a * Ab.school_id.map(cap)).values); G.M64[b] = M
        pub = G.SIZE[b]["pub"][A].astype(float); pin = np.minimum(G.M64[b][h, A], pub)
        NK = np.stack([pub - pin, pin, G.SIZE[b].get("priv", np.zeros(G.NZ))[A].astype(float)])
    w = np.array([1.0] + [np.exp(c.get(f"g_{k}", 0.0)) for k in D.comps[1:]]); Sz = (w[:, None] * NK).sum(0)
    P = D.P; pv = {"car0": float(P.car_seg.values[i] == 0), "carlow": float(P.car_seg.values[i] == 1), "g1": float(P.g.values[i] == 1),
                   "g3": float(P.g.values[i] == 3), "g4": float(P.g.values[i] == 4), "female": float(P.female.values[i])}
    cc = (G.CT[A] != G.CT[h]).astype(float); pubsh = np.where(NK.sum(0) > 0, (NK[0] + NK[1]) / np.maximum(NK.sum(0), 1e-9), 0) if seg != "col" else 0
    base = {"t": t, "lt": np.log1p(t), "intra": (A == h).astype(float), "cc": cc, "cs": (G.ST[A] != G.ST[h]).astype(float), "ccpub": cc * pubsh}
    v = c["mu_size"] * np.log(Sz + 1e-12)
    for k, bk in c.items():
        if not k.startswith("b_"): continue
        q = k[2:].split("X"); x = base[q[0]]
        for z in q[1:]: x = x * pv[z]
        v = v + bk * x
    return v


def est_V(seg, rng):
    c = pd.read_csv(f"{L}/l07_school_{SEGB[seg]}_coef.csv"); c = c[c.step == "final"].drop_duplicates("param", keep="last").set_index("param").coef
    spec = [k for k in c.index if k.startswith("b_")]
    terms = [k[2:].replace("X", "*") for k in spec]; sabs = "g_pub_in" in c.index
    D = G.Design(seg, "estimation", "full"); M = G.Model(D, terms, [], sabs); th = np.array([c[n] for n in M.names])
    mu = th[0]; g = th[1:1 + M.ng]; b = th[1 + M.ng:1 + M.ng + M.K]
    lw = np.zeros((len(D.comps), D.R))
    for j, k in enumerate(M.gidx): lw[k] += g[j]
    Sz = (np.exp(lw)[:, :, None] * D.NK).sum(0); Vm = mu * np.log(Sz + 1e-12) + D.corr + np.tensordot(b, M.Xs, axes=1)
    Vm = np.where(D.av, Vm, -np.inf)
    stu = np.sort(rng.choice(D.N, 60, replace=False)); rows = np.flatnonzero(np.isin(D.rec, stu)); P = D.P
    out = []
    for r in rows:
        i = D.rec[r]; ok = np.isfinite(Vm[r])
        out.append(pd.DataFrame(dict(seg=seg, row=r, band=P.band.values[i], cs=int(P.car_seg.values[i]), g=int(P.g.values[i]), female=int(P.female.values[i]),
                                     home_zone=G.z.zone.values[D.h[r]], school_zone=G.z.zone.values[D.A[r][ok]], V_est=Vm[r][ok],
                                     V_est64=v64(D, c.to_dict(), r, D.A[r][ok]))))
    return pd.concat(out), terms


def main():
    rng = np.random.default_rng(20261109); E, need = [], {}
    for seg in ("k8", "hs", "col"):
        e, t = est_V(seg, rng); E.append(e); need[seg] = " ".join(t)
    E = pd.concat(E); R = E.drop_duplicates(["seg", "row"]).reset_index(drop=True)
    # synthetic population: one household per (student row), the student + licensed adults for the car availability
    pp, hh, dd = [], [], []; pid = 1
    for i, r in R.iterrows():
        h = i + 1; autos, drivers = {0: (0, 1), 1: (1, 2), 2: (2, 1)}[r.cs]
        dd.append(dict(id=h, zone=r.home_zone)); hh.append(dict(id=h, dwelling=h, autos=autos, income=INC[r.g]))
        pp.append(dict(id=pid, hhID=h, age=AGE[r.band], gender=2 if r.female else 1, occupation=3, driversLicense="False", income=0)); pid += 1
        for _ in range(drivers):
            pp.append(dict(id=pid, hhID=h, age=40, gender=1, occupation=1, driversLicense="True", income=INC[r.g] / drivers)); pid += 1
    for n, x in (("pp", pp), ("hh", hh), ("dd", dd)): pd.DataFrame(x).to_csv(f"{SCR}/c04_{n}.csv", index=False)
    out = f"{SCR}/c04_dump.csv"
    r = subprocess.run(["python3", f"{MILES_HOME}/landuse/schools/assign_schools.py", "--pp", f"{SCR}/c04_pp.csv", "--hh", f"{SCR}/c04_hh.csv", "--dd", f"{SCR}/c04_dd.csv",
                        "--schools", f"{V}/2_silo/input/schools_2016.csv", "--year", "2016", "--out", f"{SCR}/c04_out", "--align", "0",
                        "--coefficients", f"{SCD}/apply/school_choice_coefficients_respec.csv", "--dump-utilities", out], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stdout[-3000:] + r.stderr[-3000:])
    Dm = pd.read_csv(out)
    # assign_schools.py types: car availability only if a car term is used, income group only if an income term, sex only if a sex term
    E["k_cs"] = np.where(E.seg.map(lambda s: "car" in need[s]), E.cs, 0); E["k_g"] = np.where(E.seg.map(lambda s: "*g" in need[s]), E.g, 0)
    E["k_f"] = np.where(E.seg.map(lambda s: "female" in need[s]), E.female, 0)
    m = E.merge(Dm.rename(columns={"cs": "k_cs", "g": "k_g", "female": "k_f"}), on=["band", "k_cs", "k_g", "k_f", "home_zone", "school_zone"], how="left")
    res = []
    for seg, x in m.groupby("seg"):
        miss = int(x.V.isna().sum()); d = (x.V_est - x.V).abs()
        res.append(dict(part=f"school {seg}", n=int(x.V.notna().sum()), missing_in_sc10=miss, max_abs_diff=float(d.max()),
                        max_abs_diff_estimation_in_double=float((x.V_est64 - x.V).abs().max()), est_float32_vs_double=float((x.V_est64 - x.V_est).abs().max())))
    extra = len(Dm) - int(m.V.notna().sum())
    print(pd.DataFrame(res).to_string(index=False), "\nassign_schools.py zones not in the estimation choice sets:", extra)
    pd.DataFrame(res).to_csv(f"{HERE}/c04_school_check.csv", index=False)


if __name__ == "__main__":
    main()
