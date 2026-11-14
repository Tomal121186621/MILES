#!/usr/bin/env python3
"""Observed journey-to-work benchmarks from the ACS PUMS (Maryland residents in households and group quarters excluded):

    python3 -I activity/lib/reporting_2024/bench_acs.py      -> temporal_2024/data/acs_commute.csv, acs_commute_hourly.csv, acs_commute_tt.csv,
                                    acs_mode.csv, acs_flows.csv

Vintages: 'acs2024'   ACS 2024 1-year (data/raw/pums_2024_1yr)
          'acs2017_19' the 2017, 2018 and 2019 interview years of the ACS 2015-2019 5-year file (SERIALNO year), the period of the
                       base survey (travel days Oct 2017 - Jul 2019); weights PWGTP of the 5-year file (shares only)
          'acs2020_24' ACS 2020-2024 5-year (inputs/pums_2024_5yr), larger sample, centred on 2022
Areas: Maryland, Baltimore region (six BMC jurisdictions; their 2020 PUMAs nest in the counties).
Workers: ESR 1, 2, 4, 5 (employed, at work or with a job but not at work), age 16+.  Worked from home: JWTRNS 11 among
workers at work last week (ESR 1, 4).  Departure time (JWDP), travel time (JWMNP) and mode (JWTRNS): commuters (JWTRNS
present, not 11).  Standard errors: successive-difference replication with the 80 replicate weights (1-year and 5-year files).
County-to-county flows: home unit (county / place-of-work PUMA group) x POWPUMA of commuters living in Maryland.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import t24common as C

COLS = ["SERIALNO", "PUMA", "PWGTP", "AGEP", "ESR", "JWTRNS", "JWRIP", "JWMNP", "JWDP", "POWSP", "POWPUMA", "RELSHIPP", "TYPEHUGQ"] + [f"PWGTP{r}" for r in range(1, 81)]
VINT = {"acs2024": (f"{C.PUMS1}/csv_pmd.zip", None), "acs2017_19": (f"{C.PUMS5_2019}/csv_pmd.zip", [2017, 2018, 2019]),
        "acs2020_24": (f"{C.PUMS5_2024}/csv_pmd.zip", None)}


def load(v):
    f, yrs = VINT[v]; p = C.read_pums_persons(f, COLS, yrs)
    p = p[p.RELSHIPP.fillna(0) < 37] if "RELSHIPP" in p else p        # household population (37/38 = group quarters)
    g = C.geo_lookup(); g = g[g.state == 24]
    if v == "acs2017_19":     # 2010 PUMAs: county from the 2010 tract-to-PUMA file (PUMAs nest in counties except groups)
        r = pd.read_csv(f"{C.RAW}/resloc/2010_Census_Tract_to_2010_PUMA.txt", dtype=str); r = r[r.STATEFP == "24"]
        pc = r.groupby("PUMA5CE").COUNTYFP.agg(lambda s: s.value_counts().index[0] if s.nunique() == 1 else "multi")
        p["county"] = p.PUMA.map(lambda x: 24000 + int(pc[f"{int(x):05d}"]) if pc.get(f"{int(x):05d}", "multi") != "multi" else -1)
    else:
        pc = g.groupby("puma").county.agg(lambda s: s.iloc[0] if s.nunique() == 1 else -1); p["county"] = p.PUMA.map(pc).fillna(-1).astype(int)
    p["balt"] = p.county.isin(C.BALTIMORE)
    p["worker"] = p.ESR.isin([1, 2, 4, 5]) & (p.AGEP >= 16); p["at_work"] = p.ESR.isin([1, 4]) & (p.AGEP >= 16)
    p["wfh"] = p.at_work & (p.JWTRNS == 11); p["commuter"] = p.JWTRNS.notna() & (p.JWTRNS != 11) & p.at_work
    return p


def measures(v, p, area):
    rows, hours, tts, modes = [], [], [], []
    wk = p[p.worker]; aw = p[p.at_work]; cm = p[p.commuter].copy()
    jd = C.jwdp_minutes(); cm["dep"] = cm.JWDP.map(lambda c: jd[int(c)][0] if pd.notna(c) else np.nan)
    cm["dep_mid"] = cm.JWDP.map(lambda c: (jd[int(c)][0] + jd[int(c)][1]) / 2 if pd.notna(c) else np.nan)
    def share(mask_col, base):
        return lambda d, w: float((d[mask_col] * d[w]).sum() / d[w].sum())
    def add(metric, val, se, n, unit=""):
        rows.append(dict(vintage=v, area=area, metric=metric, value=val, se=se, n_records=n, unit=unit))
    add("workers", float(wk.PWGTP.sum()), np.nan, len(wk), "persons (weighted)")
    add("share of workers at work last week", float(aw.PWGTP.sum() / wk.PWGTP.sum()), C.sdr_se(lambda d, w: d[w][d.at_work].sum() / d[w].sum(), wk), len(wk))
    add("worked from home, share of workers at work", float(aw.PWGTP[aw.wfh].sum() / aw.PWGTP.sum()), C.sdr_se(lambda d, w: d[w][d.wfh].sum() / d[w].sum(), aw), len(aw))
    add("commuting on the reference day, share of workers", float(cm.PWGTP.sum() / wk.PWGTP.sum()),
        C.sdr_se(lambda d, w: d[w][d.commuter].sum() / d[w].sum(), wk), len(wk), "at work and not at home")
    add("mean travel time to work", float(np.average(cm.JWMNP, weights=cm.PWGTP)), C.sdr_se(lambda d, w: np.average(d.JWMNP, weights=d[w]), cm), len(cm), "min")
    o = np.argsort(cm.JWMNP.values); cw = np.cumsum(cm.PWGTP.values[o]) / cm.PWGTP.sum()
    add("median travel time to work", float(cm.JWMNP.values[o][np.searchsorted(cw, 0.5)]), np.nan, len(cm), "min")
    add("mean departure time from home", float(np.average(cm.dep_mid, weights=cm.PWGTP)), C.sdr_se(lambda d, w: np.average(d.dep_mid, weights=d[w]), cm), len(cm), "min after midnight")
    add("departing 6:00-8:59, share of commuters", float(cm.PWGTP[(cm.dep >= 360) & (cm.dep < 540)].sum() / cm.PWGTP.sum()),
        C.sdr_se(lambda d, w: d[w][(d.dep >= 360) & (d.dep < 540)].sum() / d[w].sum(), cm), len(cm))
    hs = C.hourly_shares(cm.dep, cm.PWGTP); se_h = C.sdr_se(lambda d, w: C.hourly_shares(d.dep, d[w]).values, cm)
    for h in range(24): hours.append(dict(vintage=v, area=area, hour=h, share=hs[h], se=se_h[h]))
    b = pd.cut(cm.JWMNP, C.TT_BINS, right=False, labels=C.TT_LABELS)
    ts = cm.PWGTP.groupby(b, observed=False).sum() / cm.PWGTP.sum()
    se_t = C.sdr_se(lambda d, w: (d[w].groupby(pd.cut(d.JWMNP, C.TT_BINS, right=False, labels=C.TT_LABELS), observed=False).sum() / d[w].sum()).values, cm)
    for i, l in enumerate(C.TT_LABELS): tts.append(dict(vintage=v, area=area, bin=l, share=ts[l], se=se_t[i]))
    ms = C.acs_mode_shares(cm); se_m = C.sdr_se(lambda d, w: C.acs_mode_shares(d, w).values, cm)
    for i, m in enumerate(ms.index): modes.append(dict(vintage=v, area=area, mode=m, share=ms[m], se=se_m[i]))
    return rows, hours, tts, modes


def flows(v, p):
    """Commuters living in Maryland: home unit -> work unit (POWSP*100000 + POWPUMA)."""
    cg = C.county_group(); g = C.geo_lookup()
    pu = g[g.state == 24].groupby("puma").county.first().map(cg.unit)          # 2020 PUMA -> home unit (PUMAs nest in units)
    cm = p[p.commuter & p.POWSP.notna()].copy()
    cm["home_unit"] = cm.PUMA.map(pu); cm["work_unit"] = np.where(cm.POWPUMA.notna(), cm.POWSP.astype(int) * 100000 + cm.POWPUMA.fillna(0).astype(int), -1)
    f = cm.groupby(["home_unit", "work_unit"]).PWGTP.sum().rename("workers").reset_index(); f["vintage"] = v
    f["n_records"] = cm.groupby(["home_unit", "work_unit"]).size().values
    return f


if __name__ == "__main__":
    R, H, T, M, F = [], [], [], [], []
    for v in VINT:
        p = load(v); print(v, len(p), "household persons", flush=True)
        for area, sub in [("Maryland", p), ("Baltimore region", p[p.balt])]:
            r, h, t, m = measures(v, sub, area); R += r; H += h; T += t; M += m
        if v != "acs2017_19": F.append(flows(v, p))
    pd.DataFrame(R).to_csv(f"{C.OUT}/acs_commute.csv", index=False); pd.DataFrame(H).to_csv(f"{C.OUT}/acs_commute_hourly.csv", index=False)
    pd.DataFrame(T).to_csv(f"{C.OUT}/acs_commute_tt.csv", index=False); pd.DataFrame(M).to_csv(f"{C.OUT}/acs_mode.csv", index=False)
    pd.concat(F).to_csv(f"{C.OUT}/acs_flows.csv", index=False)
    print(pd.DataFrame(R).pivot_table(index="metric", columns=["area", "vintage"], values="value").round(3).to_string())
