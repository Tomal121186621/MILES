#!/usr/bin/env python3
"""Zone accessibilities consistent with the estimated destination-choice models (stage 3, 2026-10-22).

    python3 pipeline/accessibility.py --year 2016 [--car-skims DIR] [--transit-skims DIR] [--micro DIR] [--schools FILE] [--out FILE]

Defaults: car skims 3_abit/skims (time) with the distance of 3_abit/skims, transit pipeline/test/skims/transit_2024, SILO
microdata 2_silo/input/microData (<Y> = 2016) and 2_silo/input/schools_<Y>.csv; output data/accessibility_<Y>.csv.
For a chain year pass the year's MAST skim directory (3_abit/skims/<tag>/ or pipeline/runs/skims/...) and the SILO scenario's
microData/futureYears directory.

Measures for origin zone i, segment s and purpose p (equations in 3_abit/destination_choice/ESTIMATION_REPORT.md, section 9):
  A          ln sum_j exp(V_ij^{s,p}) with V the estimated MNL of the primary destination of purpose p
             (coef_calibrated/dest_choice_mnl.csv; work: the home -> workplace MNL, destination_choice/results/
             biogeme_WORK_primary.csv): mu ln(1 + S_j) + impedance (piecewise-linear distance, car generalized time,
             interactions with the segment's income and car flags) + zone constants; the full set of 1,588 zones.
  A_usd      A / |beta_cost|, beta_cost = beta_cgt x 60 / VOT_s (utility per dollar; VOT_s = 30 $/h x the income factor of
             MAST's mode model for the segment's income): accessibility in dollars (only differences are meaningful).
  A_ls       the same with the impedance of the logsum specification S9 of the search (lambda x MAST mode-choice logsum
             LS_ij^s = ln sum_m exp(V_ijm^s) of MarylandFullModeChoice: car with the year's car skim, bus_tt / rail_tt00 of
             the transit skims, walk / bike by distance) in place of the generalized time; lambda in the report.
  hansen     sum_j E_j^alpha exp(beta t_ij), E = all jobs, t = car minutes; alpha, beta estimated by maximum likelihood from
             the home -> work choices of the estimation half (destination_choice/results/hansen_work.json); purpose 'work'
             rows only (the column is repeated for the other purposes of the zone and segment).
  nonwork    pooled non-work purpose: ln sum_p pi_p exp(A^{s,p}) over shopping, recreation, accompany and other, pi_p = the
             shares of their primary destinations in the estimation half (weighted).
Segments s: SILO income group of the household (income.brackets.hh.types = 40000, 75000, 125000 since 2026-10-27, the rounded
quartiles of the 2016 Maryland households: 0 = < $40k, 1 = 40-75k, 2 = 75-125k, 3 = 125k+; before: 20000, 40000, 60000, --inc-brackets) x car availability (0 = no car, 1 = cars < drivers, 2 = cars >= drivers).  Representative traveller of
a segment: household income = the median income of the SILO 2016 households of the income group; cars 0 / 1 / 2 with 0 / 2
/ 2 drivers; household size 2.5; age 45; person- and time-of-day flags at their means in the estimation half.
Column contract with 2_silo/resloc (data/accessibility_<Y>.csv): zone, segment, purpose, A, hansen; segment
"<GROUP>_<nocar|carlt|carge>" with GROUP = LOW, MEDIUM, HIGH, VERY_HIGH (SILO income groups); purpose = work, nonwork; A in utils
(higher is better), hansen in jobs (unscaled).  The car classes of resloc are defined by cars against WORKERS; the destination
models use cars against licensed DRIVERS, so carlt is evaluated with the 'cars < drivers' interaction (1 car, 2 drivers).
data/accessibility_<Y>_detail.csv adds inc_group, car_avail, year, the single purposes (shopping, recreation, accompany,
other), A_usd (A / |beta_cost|, dollars), A_ls (logsum specification) and beta_cost.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, json, os, pickle, sys
import numpy as np
import pandas as pd

ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
DCD = f"{MILES_HOME}/activity/lib/destination_choice"; sys.path.insert(0, DCD); sys.path.insert(0, f"{MILES_HOME}/activity/lib")
import dc_common as C   # noqa: E402

PURPOSES = {"work": "WORK", "shopping": "SHOPPING", "recreation": "RECREATION", "accompany": "ACCOMPANY", "other": "OTHER"}
INC_BRACKETS = [40000, 75000, 125000]   # 2026-10-27; overridden by --inc-brackets
INC_NAMES = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]            # SILO HouseholdType income groups (landuse/lib/residential/rc.py)
CAR_NAMES = ["nocar", "carlt", "carge"]                      # no car / fewer cars than workers (resloc) / cars >= workers


def zone_table(micro, schools, year):
    """Zone attributes of the year in the order of dc_common.zones() (pop, ret, off, oth, stu and the derived variables)."""
    z = pd.read_csv(C.ZONE_ATTR).sort_values("id").reset_index(drop=True); z["idx"] = np.arange(len(z))
    pp = pd.read_csv(f"{micro}/pp_{year}.csv", usecols=["hhID"]); dd = pd.read_csv(f"{micro}/dd_{year}.csv", usecols=["hhID", "zone"])
    n = pp.groupby("hhID").size(); dd = dd[dd.hhID > 0].drop_duplicates("hhID"); pop = dd.assign(p=dd.hhID.map(n).fillna(0)).groupby("zone").p.sum()
    z["pop"] = z.id.map(pop).fillna(0).astype(float)
    jj = pd.read_csv(f"{micro}/jj_{year}.csv", usecols=["zone", "type"]); t = jj.type.astype(str).str.upper()
    jj["k"] = np.where(t.str.startswith("RET"), "ret", np.where(t.str.startswith("OFF"), "off", "oth")); c = jj.groupby(["zone", "k"]).size().unstack(fill_value=0)
    for k in ["ret", "off", "oth"]: z[k] = z.id.map(c[k] if k in c else pd.Series(dtype=float)).fillna(0).astype(float)
    z["jobs"] = z.ret + z.off + z.oth
    sc = pd.read_csv(schools, usecols=["zone", "occupancy", "capacity"]); col = "occupancy" if sc.occupancy.sum() > 0 else "capacity"
    z["stu"] = z.id.map(sc.groupby("zone")[col].sum()).fillna(0).astype(float)
    base = C.zones()     # derived columns with the same definitions
    z["state"] = z.countyfips // 1000; z["bc"] = (z.countyfips == 24510).astype(float); z["dcz"] = (z.countyfips == 11001).astype(float)
    z["va"] = (z.state == 51).astype(float); z["othst"] = z.state.isin([10, 42, 54]).astype(float)
    dens = z.jobs / z.area_km2.clip(lower=0.05); z["cbd"] = (dens >= 10000).astype(float); z["lnretden"] = np.log1p(z.ret / z.area_km2.clip(lower=0.05))
    s = z[["pop", "ret", "off", "oth"]].values; sh = s / np.clip(s.sum(1, keepdims=True), 1e-9, None)
    z["mix"] = -(sh * np.log(np.clip(sh, 1e-12, None))).sum(1) / np.log(4); z["intra_km"] = 0.5 * np.sqrt(z.area_km2)
    assert (z.id.values == base.id.values).all()
    return z


def segments(micro, year):
    hh = pd.read_csv(f"{micro}/hh_{year}.csv", usecols=["income"]).income
    g = np.searchsorted(INC_BRACKETS, hh.values, side="right")
    med = {k: float(np.median(hh.values[g == k])) for k in range(4)}
    out = []
    for k in range(4):
        for c, (autos, drivers) in enumerate([(0, 0), (1, 2), (2, 2)]):
            out.append(dict(inc_group=k, car_avail=c, inc_year=med[k], autos=autos, drivers=drivers))
    return out


def model(seg, which):
    """(spec, parameter vector) of a segment: 'F' = the final model (Biogeme estimates), 'S9' = the logsum specification."""
    o = pickle.load(open(f"{C.WORK}/search_{seg}.pkl", "rb")); m = o["models"][which]; spec = m["spec"]
    x = dict(zip(m["table"].param, m["table"].value))
    f = f"{DCD}/results/biogeme_{seg}.csv"
    if which == "F" and os.path.exists(f): b = pd.read_csv(f); x = dict(zip(b.Name, b.Value))
    return spec, np.array([x[p] for p in spec.params()])


def records(seg_row, flags_mean, nz):
    inc = seg_row["inc_year"]
    r = pd.DataFrame({"rec": np.arange(nz), "home_idx": np.arange(nz), "anchor_b": -1, "kind": "primary", "position": "", "tour_purpose": "",
                      "inc_month": inc / 12.0, "inc_cls": 0 if inc < 50000 else 1 if inc < 100000 else 2, "car_cls": seg_row["car_avail"],
                      "autos": seg_row["autos"], "drivers": seg_row["drivers"], "children": 0, "age": 45.0, "male": 0.5, "lic": 1.0 if seg_row["autos"] > 0 else 0.0,
                      "hhsize": 2.5, "occ": 0, "tod": 1, "mode_auto": 1.0})
    return r


def accessibility(spec, x, purpose, rec, sk, flags_mean):
    """ln sum_j exp(V_ij) for all origins; person / time flags replaced by their sample means (V is linear in them)."""
    import dc_model as M, torch
    nz = len(rec); th = torch.tensor(x); out = np.zeros(nz)
    for i0 in range(0, nz, 300):
        sub = rec.iloc[i0:i0 + 300]; alts = np.broadcast_to(np.arange(nz), (len(sub), nz)).copy()
        D = M.Data(sub, alts, np.zeros(alts.shape), np.zeros(alts.shape), spec, purpose, sk)
        # mean person flags: rebuild the interaction columns with the mean flag values
        for k, nm in enumerate(spec.linear):
            if (nm.startswith("lnd_") or nm.startswith("lndt_")) and nm.split("_", 1)[1] in flags_mean:
                base = np.log(np.maximum(sk["d"][sub.home_idx.values[:, None], alts], 1e-6))
                D.X[:, :, k] = torch.tensor(base * flags_mean[nm.split("_", 1)[1]])
        with torch.no_grad(): V = M.utility(th, spec, D)
        out[i0:i0 + len(sub)] = torch.logsumexp(V, 1).numpy()
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--year", type=int, default=2016); ap.add_argument("--car-skims", default=C.SKIM_CAR)
    ap.add_argument("--transit-skims", default=C.SKIM_TRANSIT); ap.add_argument("--micro", default=f"{V}/2_silo/input/microData")
    ap.add_argument("--schools", default=None); ap.add_argument("--out", default=None); ap.add_argument("--inc-brackets", default=None)
    a = ap.parse_args(); y = a.year
    if a.inc_brackets: INC_BRACKETS[:] = [int(x) for x in a.inc_brackets.split(",")]
    schools = a.schools or f"{V}/2_silo/input/schools_{y}.csv"
    if not os.path.exists(schools): schools = f"{V}/2_silo/input/schools_2016.csv"
    z = zone_table(a.micro, schools, y); C._cache["z"] = z           # the year's zone attributes for every utility variable
    sk = C.skims(a.car_skims, a.transit_skims); nz = len(z)
    est = pd.read_parquet(f"{C.WORK}/dc_records_estimation.parquet")
    import dc_model as M
    fm = {k: float(v.mean()) for k, v in M.chooser(est[est.kind == "primary"]).items() if k in ["child", "kid", "senior", "worker", "am", "pm", "ev"]}
    prim = est[est.kind == "primary"]; pi = prim.groupby("purpose").w.sum(); pi = (pi / pi.sum()).to_dict()
    hj = json.load(open(f"{DCD}/results/hansen_work.json"))
    t = sk["t"].astype(float); hansen = (np.power(z.jobs.values, hj["alpha"])[None, :] * np.exp(hj["beta"] * t)).sum(1)
    rows = []
    for s in segments(a.micro, y):
        rec = records(s, fm, nz); fl = dict(fm)
        fl.update(inc0=float(rec.inc_cls.iloc[0] == 0), inc2=float(rec.inc_cls.iloc[0] == 2), car0=float(s["car_avail"] == 0), car1=float(s["car_avail"] == 1))
        vf = np.clip((max(1.0, s["inc_year"] / 12.0) / C.VOT_REF) ** C.VOT_ELAST, C.VOT_MIN, C.VOT_MAX)
        Ap = {}
        for pname, pur in PURPOSES.items():
            seg = f"{pur}_primary"
            if not os.path.exists(f"{C.WORK}/search_{seg}.pkl"): continue
            spec, x = model(seg, "F"); A = accessibility(spec, x, pur, rec, sk, fl)
            g = "cgt" if "cgt" in spec.linear else "ctime" if "ctime" in spec.linear else None
            bc = x[spec.params().index(g)] * 60.0 / (C.MC_VOT[0] * vf) if g else np.nan
            spec9, x9 = model(seg, "S9"); A9 = accessibility(spec9, x9, pur, rec, sk, fl)
            Ap[pname] = (A, A9)
            for i in range(nz):
                rows.append((int(z.id.values[i]), y, s["inc_group"], s["car_avail"], f"{INC_NAMES[s['inc_group']]}_{CAR_NAMES[s['car_avail']]}", pname, A[i], A[i] / abs(bc) if g else np.nan, A9[i], bc, hansen[i]))
        nw = [p for p in ["shopping", "recreation", "accompany", "other"] if p in Ap]
        if nw:
            w = np.array([pi[PURPOSES[p]] for p in nw]); w = w / w.sum()
            for k, lab in [(0, "A"), (1, "A_ls")]:
                M_ = np.stack([Ap[p][k] for p in nw]); mx = M_.max(0); Ap[f"nonwork_{lab}"] = mx + np.log((w[:, None] * np.exp(M_ - mx)).sum(0))
            spec, x = model("SHOPPING_primary", "F"); g = "cgt" if "cgt" in spec.linear else "ctime"
            bc = x[spec.params().index(g)] * 60.0 / (C.MC_VOT[0] * vf)
            for i in range(nz):
                rows.append((int(z.id.values[i]), y, s["inc_group"], s["car_avail"], f"{INC_NAMES[s['inc_group']]}_{CAR_NAMES[s['car_avail']]}", "nonwork", Ap["nonwork_A"][i], Ap["nonwork_A"][i] / abs(bc), Ap["nonwork_A_ls"][i], bc, hansen[i]))
        print(f"segment i{s['inc_group']}_c{s['car_avail']} done", flush=True)
    out = pd.DataFrame(rows, columns=["zone", "year", "inc_group", "car_avail", "segment", "purpose", "A", "A_usd", "A_ls", "beta_cost", "hansen"])
    f = a.out or f"{V}/data/accessibility_{y}.csv"
    out.to_csv(f.replace(".csv", "_detail.csv"), index=False, float_format="%.6g")
    out[out.purpose.isin(["work", "nonwork"])][["zone", "segment", "purpose", "A", "hansen"]].to_csv(f, index=False, float_format="%.6g")
    print(f"wrote {f} (contract: zone, segment, purpose = work / nonwork, A, hansen) and {f.replace('.csv', '_detail.csv')}: {len(out)} rows")


if __name__ == "__main__":
    main()
