#!/usr/bin/env python3
"""Residential location, level 1 (region), model development for reporting: blocks added in a fixed order, main effects before
their interactions; a block is kept when the likelihood-ratio test is significant at 5 %, BIC falls and the signs are the expected
ones.  Selection on the estimation half (the region data of s06_region.py, logsums of the current zone and dwelling models); the
validation half is used once, for the final model.
  S0 car time (piecewise)   S1 + same region, same state   S2 + ln dwellings   S3 level-2 logsum replaces ln dwellings
  S4 + level-3 logsum       S5 + commute, x ln income      S6 + crime          S7 + school learning growth
  S8 + crime x children     S9 + school learning growth x children
School learning growth: SEDA 4.1 county change in achievement per grade (cs_mn_grd_eb, grades 3-8, pooled 2009-2018, all
students), weighted by assessments over the region's counties and by dwellings over its zones, as for crime.  The growth
rate rather than the mean level, since mean achievement mainly reflects the socio-economic composition of the students (Reardon 2019).
  S10 has no car time 20-60 min x age (collinearity/silo_notes.md: est r 0.89 with previous county x age, dBIC -8.8).
  Final check: kept terms with reversed sign and |robust t| < 1.96 dropped jointly (LR); a member of a band set (BANDS) only with
  its whole set.
  J  car time x income with common inclusive values: (a) car-time pieces x ln income, (b) car-time pieces by income group;
     same rule (car time negative in every group, ln-income interaction positive), lower BIC among those that pass
  I  last kept model with income-specific inclusive values, car time, origin share and commute
  C  (only if I passes the rule but has an inclusive-value parameter above 1) I with those fixed at 1
  A  final model + county constants (calibration only; county-wide terms dropped)
    python3 estimation/development/residential_location/r05_region_sequence.py [newiv]   ->  r05_fit.csv, r05_coef.csv
  newiv: inclusive values of the re-specified zone and dwelling parts (county_data_*.pkl of r07_county_iv.py)"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/residential"   # results of this step (data); CODE = this folder
RL = f"{TERP_HOME}/landuse/lib/residential"; sys.path.insert(0, RL)   # residential-location code
RL_DATA = f"{WORKSPACE}/2_silo/resloc"                                   # its data folder (tables/)
from rc import WORK, RAW   # noqa: E402
from mnl import MNL, lr_test   # noqa: E402
import s06_region as RG   # noqa: E402
import s07_region_validation as RV   # noqa: E402

TAG = "final"
SIGN = {"d1": -1, "d2": -1, "d3": -1, "same_region": 1, "lnD_region": 1, "IV_B": 1, "IV_A": 1, "commute_log": -1,
        "crime": -1, "growth": 1, "crime_x_child": -1, "growth_x_child": 1,
        "same_x_age": 1, "same_x_ageU35": -1, "same_x_age50_64": 1, "same_x_age65": 1, "d1_x_lninc": 1, "d2_x_lninc": 1, "d3_x_lninc": 1,
        "m1_x_lninc": 1, "m2_x_lninc": 1, "m3_x_lninc": 1, "lnt_x_lninc": 1}
BANDS = [("same_x_ageU35", "same_x_age50_64", "same_x_age65")]
TIMEV = ["d1", "d2", "d3", "m1", "m2", "m3", "lnt"]
BASE = [("S0", "Car time to the region (piecewise linear)", ["d1", "d2", "d3"]),
        ("S1", "+ same region, same state", ["same_region", "same_state"]),
        ("S2", "+ region size (ln dwellings)", ["lnD_region"])]
BLOCKS = [("S4", "+ level-3 logsum", ["IV_A"]),
          ("S5", "+ commute ($\\ln(1+t)$, $\\times$ ln income)", ["commute_log", "commute_log_x_inc"]),
          ("S6", "+ crime", ["crime"]),
          ("S7", "+ school learning growth", ["growth"]),
          ("S8", "+ crime $\\times$ children", ["crime_x_child"]),
          ("S9", "+ school learning growth $\\times$ children", ["growth_x_child"]),
          ("S10", "+ age $\\times$ previous county", [["same_x_age"], ["same_x_ageU35", "same_x_age50_64", "same_x_age65"]]),
          ("S11", "+ household size $\\times$ previous county and car time 20--60\\,min", ["same_x_hhs", "d2_x_hhs"])]
AGEFORM = {"same_x_age": "linear", "same_x_ageU35": "bands"}
INTER = ["IV_B", "IV_A", "d1", "d2", "d3", "same_region", "commute_log"]
REGIONWIDE = ["crime", "growth", "lnD_region"]


def add_growth(D):
    """school learning growth per region (same aggregation as the mean-achievement term of s06_region.py)"""
    z, R = RG.region_frame()
    seda = pd.read_csv(f"{RAW}/seda_county_pool_cs_4.1.csv"); seda = seda[seda.subgroup == "all"].set_index("sedacounty")
    def gr(f):
        s = seda.reindex(RG.COMBINED.get(f, [f])).dropna(subset=["cs_mn_grd_eb"]); return np.average(s.cs_mn_grd_eb, weights=s.tot_asmts)
    z["growth"] = z.COUNTYFIPS.map({f: gr(f) for f in z.COUNTYFIPS.unique()})
    g = z.groupby("region").apply(lambda x: np.average(x.growth, weights=x.dwellings + 1e-9)).reindex(D["regs"]).values
    child = (D["h"].n_child.values > 0)[:, None]
    D["F"]["growth"] = np.tile(g, (len(D["h"]), 1)); D["F"]["growth_x_child"] = D["F"]["growth"] * child
    # age of the oldest member and household size, with the previous county and the car time 20-60 min to another county
    a = D["h"].age_max.values.astype(float)
    x = {"age": (a - 50) / 10, "ageU35": (a < 35) * 1.0, "age50_64": ((a >= 50) & (a < 65)) * 1.0, "age65": (a >= 65) * 1.0,
         "hhs": np.minimum(D["h"].NP.values, 6) - 1.0}
    D["lninc"] = np.log(np.maximum(D["h"].income.values, 5000) / 50000)
    for k, v in x.items():
        D["F"][f"same_x_{k}"] = D["F"]["same_region"] * v[:, None]; D["F"][f"d2_x_{k}"] = D["F"]["d2"] * v[:, None]
    # car time as one smooth term, and the share of the origin area in counties bordering county r (zone polygons, 2_silo/input/zones.shp)
    tx = D["F"]["d1"] + D["F"]["d2"] + D["F"]["d3"]
    D["F"]["lnt"] = np.log1p(tx); D["F"]["lnt_x_age"] = D["F"]["lnt"] * x["age"][:, None]
    # car time to the nearest zone of county r with dwellings (instead of the dwelling-weighted mean over its zones)
    tz = D["om"] @ CAR                                   # (N, zones): origin area -> zone
    tmin = np.stack([tz[:, ZREG == r][:, DWZ[ZREG == r]].min(axis=1) for r in D["regs"]], axis=1)
    tm = tmin * (1 - D["F"]["same_region"])
    D["F"]["m1"] = np.minimum(tm, 20); D["F"]["m2"] = np.clip(tm - 20, 0, 40); D["F"]["m3"] = np.maximum(tm - 60, 0)
    D["F"]["m2_x_age"] = D["F"]["m2"] * x["age"][:, None]
    for v in TIMEV: D["F"][f"{v}_x_lninc"] = D["F"][v] * D["lninc"][:, None]
    D["F"]["adjacent"] = D["om"] @ ADJ[np.searchsorted(D["regs"], ZREG)][:, np.searchsorted(D["regs"], D["regs"])] * (1 - D["F"]["same_region"])
    return D


def adjacency():
    """county x county: 1 if the counties share a boundary (zones dissolved by county, touching within 50 m)"""
    import geopandas as gpd
    g = gpd.read_file(f"{WORKSPACE}/2_silo/input/zones.shp")[["id", "geometry"]]
    z = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone").region
    g["region"] = g.id.map(z); c = g.dropna(subset=["region"]).dissolve("region").buffer(50)
    regs = np.sort(z.unique()); c = c.reindex(regs)
    A = np.array([[float(i != j and c.iloc[i].intersects(c.iloc[j])) for j in range(len(regs))] for i in range(len(regs))])
    return A


ADJ = adjacency()
CAR = RG.read_skim(RG.SKIM_CAR); CAR = np.where(np.isnan(CAR), 300.0, CAR)
DWZ = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone").dwellings.reindex(RG.ZONE_IDS).fillna(0).values > 0
ZREG = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone").region.reindex(RG.ZONE_IDS).values


def fit(D, vs, asc=False, inter=False, cap=False, start=None, fix=None):
    g = D["h"].inc_group.values
    X, names = RG.design(D, vs, asc=asc, inter={v: g for v in (INTER if inter is True else inter) if v in vs} if inter else None)
    fixed = dict(fix or {})
    for _ in range(4):
        keep = [i for i, n in enumerate(names) if n not in fixed]
        off = np.zeros(D["av"].shape)
        for n, val in fixed.items():
            off += val * X[:, :, names.index(n)]
        b0 = None if start is None else np.array([start.get(names[i], 0.0) for i in keep])
        m = MNL(X[:, :, keep], [names[i] for i in keep], D["av"], D["C"], weights=D["w"], offset=off).fit(b0=b0)
        viol = [n for n, b in zip(m.names, m.b) if n.startswith(("IV_A", "IV_B")) and b > 1.0] if cap else []
        if not viol:
            break
        fixed.update({n: 1.0 for n in viol})
    m.fixed, m.all_names = fixed, names
    return m


def sign_ok(m, only=None):
    """wrong-signed coefficients among the terms in `only` (the block just added; all terms when None)"""
    bad = []
    for n, b in zip(m.names, m.b):
        base = next((v for v in sorted(SIGN, key=len, reverse=True) if n == v or n.startswith(v + "_") and n[len(v) + 1:].isupper()), None)
        if base and (only is None or base in only) and np.sign(b) != SIGN[base]:
            bad.append(n)
    return bad


def main():
    src = (lambda t: f"{HERE}/county_data_{t}.pkl") if "newiv" in sys.argv else (lambda t: f"{WORK}/region_data_{t}_{TAG}.pkl")
    De = add_growth(pickle.load(open(src("est"), "rb"))); Dv = add_growth(pickle.load(open(src("val"), "rb")))
    rows, coefs = [], []

    def rec(step, lab, m, ref, dec, lr=True):
        s = m.stats(lab); s.update(step=step, decision=dec, fixed_at_1=";".join(m.fixed))
        if ref is not None and lr:
            t = lr_test(ref.ll, m.ll, abs(m.k - ref.k)) if m.k > ref.k else lr_test(m.ll, ref.ll, ref.k - m.k)
            s.update(LR=t[0], df=t[1], p=t[2])
        rows.append(s)
        t = m.table(); t["step"] = step; coefs.append(t)
        print(step, lab, f"K {m.k} LL {m.ll:.1f} BIC {s['BIC']:.1f}", dec, {n: round(b, 3) for n, b in zip(m.names, m.b) if not n.startswith("asc_")}, flush=True)

    vs, cur = [], None
    for step, lab, add in BASE:
        vs = vs + add; m = fit(De, vs); rec(step, lab, m, cur, "kept"); cur = m
    v3 = [v for v in vs if v != "lnD_region"] + ["IV_B"]; m = fit(De, v3)
    b2, b3 = cur.stats()["BIC"], m.stats()["BIC"]
    if b3 < b2 and not sign_ok(m, ["IV_B"]):
        rec("S3", "Level-2 logsum replaces region size", m, None, "kept (non-nested, BIC)"); vs, cur = v3, m
    else:
        rec("S3", "Level-2 logsum replaces region size", m, None, "not kept: sign" if sign_ok(m, ["IV_B"]) else "not kept: BIC")
    for step, lab, adds in BLOCKS:
        alts = adds if isinstance(adds[0], list) else [adds]; best, res = None, []
        for k, add in enumerate(alts):
            m = fit(De, vs + add); lr, _, p = lr_test(cur.ll, m.ll, m.k - cur.k); bad = sign_ok(m, add)
            bic = m.stats()["BIC"] < cur.stats()["BIC"]
            dec = "kept" if p < 0.05 and bic and not bad else "not kept: sign" if bad else "not kept: BIC" if not bic else "not kept: LR"
            res.append((k, add, m, dec + (f" ({', '.join(bad)})" if bad else "")))
            if dec == "kept" and (best is None or m.stats()["BIC"] < best[2].stats()["BIC"]): best = (k, add, m)
        for k, add, m, dec in res:
            if len(alts) > 1:
                dec = "chosen" if best and k == best[0] else ("not chosen: BIC" if dec == "kept" else dec)
                rec(step + "abc"[k], lab + ": " + AGEFORM.get(add[0], ""), m, cur, dec)
            else:
                rec(step, lab, m, cur, dec)
        if best:
            vs, cur = vs + best[1], best[2]
    # final check: a kept term whose sign reversed after later blocks and is not significant is dropped (car-time pieces excepted)
    t = cur.table().set_index("parameter")
    rev = [v for v in vs if v in SIGN and not v.startswith("d") and np.sign(t.estimate[v]) != SIGN[v] and abs(t.robust_t[v]) < 1.96]
    rev = list(dict.fromkeys(x for v in rev for x in next((b for b in BANDS if v in b), (v,)) if x in vs))   # band sets whole
    if rev:
        m = fit(De, [v for v in vs if v not in rev]); _, _, p = lr_test(m.ll, cur.ll, cur.k - m.k)
        dec = "kept" if p >= 0.05 or m.stats()["BIC"] < cur.stats()["BIC"] else "not kept: LR"
        rec("R", "Without " + ", ".join(rev) + " (sign reversed, not significant)", m, cur, dec)
        if dec == "kept":
            vs, cur = [v for v in vs if v not in rev], m
    # lambda_A at 1 (upper bound): kept if the data do not reject it
    if "IV_A" in vs:
        m = fit(De, vs, fix={"IV_A": 1.0}); _, _, p = lr_test(m.ll, cur.ll, 1)
        dec = "kept (restriction)" if p >= 0.05 else "not kept: restriction rejected"
        rec("L", "Inclusive value of the dwelling part fixed at 1", m, cur, dec); m.k_free = m.k
        if p >= 0.05:
            cur, LFIX = m, {"IV_A": 1.0}
        else:
            LFIX = None
    # car-time form (non-nested alternatives, BIC; the car-time slope may not rise with time)
    agei = [v for v in vs if v.startswith("d2_x_")]
    forms = [("Car time: piecewise (under 20, 20--60, over 60\\,min)", vs),
             ("Car time: $\\ln(1 + t)$", [v for v in vs if v not in ("d1", "d2", "d3") and v not in agei] + ["lnt"] + [v.replace("d2_x_", "lnt_x_") for v in agei]),
             ("Car time: piecewise + adjacent county", vs + ["adjacent"]),
             ("Car time to the nearest part of the county: piecewise", [v for v in vs if v not in ("d1", "d2", "d3") and v not in agei] + ["m1", "m2", "m3"] + [v.replace("d2_x_", "m2_x_") for v in agei]),
             ("Car time to the nearest part of the county: piecewise + adjacent county", [v for v in vs if v not in ("d1", "d2", "d3") and v not in agei] + ["m1", "m2", "m3", "adjacent"] + [v.replace("d2_x_", "m2_x_") for v in agei]),
             ("Car time beyond 20\\,min only (no time effect under 20\\,min)", [v for v in vs if v != "d1"]),
             ("Car time beyond 20\\,min only + adjacent county", [v for v in vs if v != "d1"] + ["adjacent"])]
    res = []
    for k, (lab, v) in enumerate(forms):
        m = cur if k == 0 else fit(De, v, fix=LFIX); t = m.table().set_index("parameter")
        ok = all(t.estimate.get(x, -1) <= 0 or abs(t.robust_t.get(x, 0)) < 1.96 for x in ("d1", "lnt", "m1"))
        res.append((k, lab, v, m, ok))
    good = [r for r in res if r[4]]; best = min(good or res[:1], key=lambda r: r[3].stats()["BIC"])
    for k, lab, v, m, ok in res:
        rec("T" + "abcdefg"[k], lab, m, None, "chosen" if k == best[0] else ("not chosen: car time rises with time" if not ok else "not chosen: BIC"))
    vs, cur = best[2], best[3]; INTER.extend(["lnt", "m1", "m2", "m3"])
    # income-specific coefficients: kept by the same rule, provided the inclusive-value parameters lie in (0, 1]; when they do
    # not, the restricted model (parameters above 1 fixed at 1) is kept only if the data do not reject the restriction
    fin, inter = cur, False
    tv = [v for v in TIMEV if v in vs]; res = []
    for k, (lab, add, it) in enumerate([("car time $\\times$ ln income", [f"{v}_x_lninc" for v in tv], False), ("car time by income group", [], tv)]):
        m = fit(De, vs + add, inter=it, fix=LFIX); lr, _, p = lr_test(cur.ll, m.ll, m.k - cur.k)
        bad = sign_ok(m, tv + add); bic = m.stats()["BIC"] < cur.stats()["BIC"]
        dec = "kept" if p < 0.05 and bic and not bad else "not kept: sign" if bad else "not kept: BIC" if not bic else "not kept: LR"
        res.append((k, lab, add, it, m, dec + (f" ({', '.join(bad)})" if bad else "")))
    good = [r for r in res if r[5] == "kept"]; best = min(good, key=lambda r: r[4].stats()["BIC"]) if good else None
    for k, lab, add, it, m, dec in res:
        rec("J" + "ab"[k], "Car time $\\times$ income, common inclusive values: " + lab, m, cur, "chosen" if best and k == best[0] else ("not chosen: BIC" if dec == "kept" else dec))
    if best:
        vs, cur, fin, inter = vs + best[2], best[4], best[4], (best[3] or False)
    mi = fit(De, vs, inter=True); lr, _, p = lr_test(cur.ll, mi.ll, mi.k - cur.k)
    over = [n for n, b in zip(mi.names, mi.b) if n.startswith(("IV_A", "IV_B")) and b > 1]
    ok = p < 0.05 and mi.stats()["BIC"] < cur.stats()["BIC"]
    rec("I", "Income-specific inclusive values, car time, origin share and commute", mi, cur,
        "not kept: BIC" if not ok else "not kept: inclusive value above 1" if over else "kept")
    if ok and not over:
        fin, inter = mi, True
    elif ok:
        mc = fit(De, vs, inter=True, cap=True); _, _, pc = lr_test(mc.ll, mi.ll, len(mc.fixed))
        rec("C", "Previous step with inclusive-value parameters fixed at 1 where the estimate exceeds 1", mc, mi,
            "not kept: restriction rejected" if pc < 0.05 else "kept (restriction)")
        if pc >= 0.05:
            fin, inter = mc, True
    va = [v for v in vs if v not in REGIONWIDE]
    ma = fit(De, va, asc=True, inter=inter, start=dict(zip(fin.names, fin.b))); rec("A", "Final model + county constants (county-wide terms dropped)", ma, fin, "not kept: calibration only")
    # validation half, once, final model
    b = np.array([fin.fixed.get(n, np.nan) for n in fin.all_names]); b[[fin.all_names.index(n) for n in fin.names]] = fin.b
    X = RV.X_of(Dv, fin.all_names); _, _, ll = MNL(X, fin.all_names, Dv["av"], Dv["C"], weights=Dv["w"])._logs(b)
    print("final", [r["step"] for r in rows if r["LL"] == fin.ll][0], "validation LL", float((Dv["w"] * ll).sum()), "N", len(Dv["h"]), flush=True)
    f = pd.DataFrame(rows); f["final"] = f.LL == fin.ll; f["val_LL_final"] = np.where(f.final, float((Dv["w"] * ll).sum()), np.nan)
    f.to_csv(f"{HERE}/r05_fit.csv", index=False); pd.concat(coefs).to_csv(f"{HERE}/r05_coef.csv", index=False)

if __name__ == "__main__":
    main()
