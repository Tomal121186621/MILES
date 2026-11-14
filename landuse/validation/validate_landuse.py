#!/usr/bin/env python3
"""Stage-2 validation of a SILO run, every simulated year, by county (region) and by PUMA, against observed data (VALIDATION.md):
  A population totals by region and year vs Census Population Estimates (data/silo_target_population_by_region.csv)
  B composition by Maryland county (age bands, sex, employed 16+, household size, cars, income class 2016 $, tenure proxy n/a)
    vs the ACS PUMS 5-year file centred on the year (year Y -> vintage Y+2, capped at 2024), by PUMA aggregated to county by zone weights
  C event rates by year (births per woman 15-50, deaths, marriages, divorces, moves, job starts/quits) from the year-to-year microdata
  D2 dwellings built in calendar year y-1 (row labelled y) by Maryland county vs units permitted in y-1 (Building Permits Survey)
  D jobs by region and type vs LODES (data/silo_target_jobs_by_region_type_year.csv); vacant share of jobs vs the Maryland JOLTS
    job-openings rate (data/raw/jolts)
  B2 statewide (Maryland): employed share by age band x sex, workers per household, persons 18-34 in non-family households living
    with others (roommates; cohabiting couples excluded) - ACS PUMS as in B
  E workplaces and commutes of Maryland residents with a job: share employed in the home county (jobs in Maryland) vs LODES OD
    (home and work in Maryland, data/silo_target_lodes_own_county.csv; 2024 vs LODES 2023), car peak travel time home zone -> job
    zone (mean, median) vs the ACS travel time to work JWMNP of commuters (all modes, door to door; data/silo_target_commute_acs.csv)
  F mover flows: share of moving households staying in their region and correlation of the region-to-region flows with the ACS
    county-to-county flows 2016-20 aggregated to regions (siloResults/relocation; data/silo_target_region_flows_acs.csv)
Usage: python3 landuse/validation/validate_landuse.py <scenario_name> [first_year last_year]   -> data/silo_validation_<scenario>.parquet (long table) and a summary"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, zipfile, os, sys, re
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; S = f"{V}/2_silo"
scen = sys.argv[1]; OUT = f"{S}/run/base/scenOutput/{scen}/microData"; y0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2016; y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2026
z = pd.read_csv(f"{S}/input/zoneSystem.csv").set_index("ZoneId"); CPI = {2016: 1.0, 2017: 1.021, 2018: 1.046, 2019: 1.065, 2020: 1.078, 2021: 1.129, 2022: 1.219, 2023: 1.269, 2024: 1.307, 2025: 1.342, 2026: 1.375}
rows = []
def add(section, year, geo, table, bin_, model, observed): rows.append(dict(section=section, year=int(year), geo=str(geo), table=table, bin=str(bin_), model=float(model), observed=float(observed)))
def md_pop(year):
    """2026-10-28: Maryland population of July 1 on the series of the population controls (2010-2020 intercensal estimates up to 2019,
    vintage 2025 from 2020); the components of change (births, deaths: full years) stay those of vintage 2020 up to 2020."""
    if year <= 2019:
        d = pd.read_csv(f"{V}/data/raw/pep/intercensal_2010_2020/cc-est2020int-agesex-24.csv", encoding="latin-1")
        return float(d[(d.SUMLEV == 50) & (d.YEAR == year - 2008)].POPESTIMATE.sum())
    d = pd.read_csv(f"{V}/data/raw/pep/co-est2025-alldata.csv", encoding="latin-1", dtype={"STATE": str}); d = d[(d.SUMLEV == 50) & (d.STATE == "24")]
    return float(d[f"POPESTIMATE{year}"].sum())

def yfile(y, kind):
    """State of the population at the start of year y.  The engine's results monitor writes the microdata at the END of each
    simulated year Y under the label Y (scenOutput/<scen>/microData/{dd,jj,pp}_Y.csv, hh_Y.csv in microData/futureYears/), i.e.
    the file labelled Y is the state at the start of Y+1; the final-year file in futureYears repeats the last one.  The base year
    is the input microdata."""
    if y == 2016:
        # 2026-10-28: the base files the scenario read (e.g. a microData_rtswp/ directory with re-assigned workplaces)
        ip = f"{S}/run/base/scenOutput/{scen}/inputProperties.properties"; key = {"pp": "person", "hh": "household", "dd": "dwelling", "jj": "job"}[kind] + ".file.ascii"
        if os.path.exists(ip):
            for line in open(ip):
                if line.split("=")[0].strip() == key and "=" in line:
                    f = f"{S}/run/base/{line.split('=', 1)[1].strip()}_{y}.csv"
                    if os.path.exists(f): return f
        return f"{S}/input/microData/{kind}_{y}.csv"
    for d in [f"{OUT}", f"{OUT}/futureYears"]:
        if os.path.exists(f"{d}/{kind}_{y - 1}.csv"): return f"{d}/{kind}_{y - 1}.csv"
    return None
def ydir(y): return os.path.dirname(yfile(y, "hh")) if yfile(y, "hh") and yfile(y, "pp") and yfile(y, "dd") and yfile(y, "jj") else None
def load_year(y):
    hh = pd.read_csv(yfile(y, "hh")); dd = pd.read_csv(yfile(y, "dd"), usecols=["id", "zone", "hhID"]); pp = pd.read_csv(yfile(y, "pp")); jj = pd.read_csv(yfile(y, "jj"), usecols=["zone", "personId", "type"])
    pp.columns = [c if c != "hhid" else "hhID" for c in pp.columns]; pp["relationShip"] = pp.relationShip.astype(str).str.upper()
    hh = hh.merge(dd.rename(columns={"id": "dwelling"})[["dwelling", "zone"]], on="dwelling", how="left"); hh["region"] = hh.zone.map(z.Region); hh["county"] = hh.zone.map(z.COUNTYFIPS); hh["puma"] = hh.zone.map(z.PUMA_10 % 100000); hh["st"] = hh.zone.map(z.STFIPS)
    pp = pp.merge(hh[["id", "dwelling", "region", "county", "puma", "st"]].rename(columns={"id": "hhID"}), on="hhID", how="left"); jj["region"] = jj.zone.map(z.Region)
    return hh, pp, jj
def puma10(D, v):
    """PUMS PUMA codes on the 2010 PUMA geography (the zone table carries PUMA_10). The 2018-22 file has PUMA10 (-9 for the
    2021-22 samples) and PUMA20; files from 2019-23 on carry only 2020 PUMAs in PUMA, mapped to 2010 PUMAs by the zone table's
    PUMA_20 -> PUMA_10 correspondence (data/puma20_to_puma10.csv, built from the Census 2020 PUMA shapefile; 2010 PUMAs that are
    split or merged in 2020 are allocated by the share of households in each piece)."""
    if "PUMA" in D and v <= 2021: return D
    if "PUMA10" in D: D = D[D.PUMA10 != -9].copy(); D["PUMA"] = D.PUMA10; return D
    xw = pd.read_csv(f"{V}/data/puma20_to_puma10.csv")   # columns puma20, puma10, share
    D = D.merge(xw, left_on="PUMA", right_on="puma20", how="inner"); wcol = "PWGTP" if "PWGTP" in D else "WGTP"
    D[wcol] = D[wcol] * D.share; D["PUMA"] = D.puma10; return D
def pums(vintage):
    v = min(max(int(vintage), 2017), 2024); P, H = {}, {}
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_{v}_5yr/csv_pmd.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]; P = pd.read_csv(zf.open(n), usecols=lambda c: c in ["SERIALNO", "PUMA", "PUMA10", "PUMA20", "PWGTP", "RELP", "RELSHIPP", "AGEP", "SEX", "ESR", "ADJINC"], low_memory=False)
    P = puma10(P, v); gq = P.RELP.isin([16, 17]) if "RELP" in P else P.RELSHIPP.isin([37, 38]); P = P[~gq]
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_{v}_5yr/csv_hmd.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]; H = pd.read_csv(zf.open(n), usecols=lambda c: c in ["SERIALNO", "PUMA", "PUMA10", "PUMA20", "WGTP", "NP", "TYPE", "TYPEHUGQ", "VEH", "HINCP", "ADJINC", "HHT"], low_memory=False)
    H = puma10(H, v); tcol = "TYPE" if "TYPE" in H else "TYPEHUGQ"; H = H[(H[tcol] == 1) & (H.NP > 0)].copy()
    _e = P[P.ESR.isin([1, 2, 4, 5])]; _w = _e.share if "share" in _e else pd.Series(1.0, index=_e.index)   # files on 2020 PUMAs: a person appears once per PUMA piece with its share
    H["workers"] = H.SERIALNO.map(_w.groupby(_e.SERIALNO).sum().round()).fillna(0).values   # employed persons in the household
    P = P.merge(H[["SERIALNO", "HHT", "NP"]].drop_duplicates("SERIALNO"), on="SERIALNO", how="left"); H["inc16"] = H.HINCP.fillna(0) * H.ADJINC / 1e6 / CPI[min(v, 2026)]   # ADJINC expresses income in the dollars of the vintage's final year v; deflated to 2016 $
    return P, H, v
avail = [y for y in range(y0, y1 + 1) if y == 2016 or ydir(y)]; print("years available:", avail)
Tpop = pd.read_csv(f"{V}/data/silo_target_population_by_region.csv"); Tjob = pd.read_csv(f"{V}/data/silo_target_jobs_by_region_type_year.csv")
prev = None
for y in avail:
    hh, pp, jj = load_year(y)
    # A totals
    per = pp.groupby("region").size(); t = Tpop[Tpop.year == y].set_index("region").persons_pep
    base_ratio = (load_year(2016)[1].groupby("region").size() / Tpop[Tpop.year == 2016].set_index("region").persons_pep) if y != 2016 else None
    for r, n in per.items():
        if r in t.index: add("A totals", y, r, "persons vs PEP (ratio to 2016 ratio = growth tracking)", "persons", n, t[r] * (base_ratio[r] if base_ratio is not None and r in base_ratio.index else n / t[r] if y == 2016 else 1))
    # B composition, Maryland counties, vs PUMS centred on y
    P, H, v = pums(y + 2); md_p = pp[pp.st == 24]; md_h = hh[hh.st == 24]
    inc_edges = [-1e9, 25e3, 50e3, 75e3, 100e3, 150e3, 1e12]
    comp = [("age band", lambda d: np.digitize(d.age, [18, 35, 65]), lambda q: np.digitize(q.AGEP, [18, 35, 65]), range(4), "p"),
            ("sex", lambda d: d.gender, lambda q: q.SEX, [1, 2], "p"),
            ("employed (16+)", lambda d: (d.occupation == 1).astype(int), lambda q: q.ESR.isin([1, 2, 4, 5]).astype(int), [0, 1], "p16"),
            ("household size", lambda d: d.hhSize.clip(upper=5), lambda q: q.NP.clip(upper=5), range(1, 6), "h"),
            ("cars", lambda d: d.autos.clip(upper=3), lambda q: q.VEH.fillna(0).clip(upper=3).astype(int), range(4), "h"),
            ("income class (2016 $)", lambda d: pd.cut(d.income, inc_edges, labels=False), lambda q: pd.cut(q.inc16, inc_edges, labels=False), range(6), "h"),   # model incomes are in 2016 $ (real wage growth only)
            ("adults 18-34 living with parents", lambda d: ((d.relationShip == "CHILD") & d.age.between(18, 34)).astype(int), lambda q: (q.RELP.isin([2, 3, 4]) if "RELP" in q else q.RELSHIPP.isin([25, 26, 27])).astype(int), [0, 1], "p1834")]
    # county <- PUMA: ACS values by PUMA weighted to counties by the share of each county's households in each PUMA (zone table)
    zw = z[z.STFIPS == 24].groupby(["COUNTYFIPS", z.PUMA_10[z.STFIPS == 24] % 100000]).size().rename("n").reset_index(); zw.columns = ["county", "puma", "n"]
    # household income in SILO is per household (hh.income? no: pp.income) -> household income = sum of persons
    hinc = md_p.groupby("hhID").income.sum(); md_h = md_h.assign(income=md_h.id.map(hinc).fillna(0))
    for name, fm, fo, order, kind in comp:
        # Maryland statewide (household- or person-weighted), geo "24"
        if kind == "h":
            m_ = pd.Series(np.asarray(fm(md_h))).value_counts(normalize=True); o_ = pd.Series(H.WGTP.values).groupby(np.asarray(fo(H))).sum(); o_ = o_ / o_.sum()
        else:
            dm_, qq_ = (md_p[md_p.age >= 16], P[P.AGEP >= 16]) if kind == "p16" else (md_p[md_p.age.between(18, 34)], P[P.AGEP.between(18, 34)]) if kind == "p1834" else (md_p, P)
            m_ = pd.Series(np.asarray(fm(dm_))).value_counts(normalize=True); o_ = pd.Series(qq_.PWGTP.values).groupby(np.asarray(fo(qq_))).sum(); o_ = o_ / o_.sum()
        for b in order: add("B composition", y, "24", f"{name} [PUMS {v}]", b, m_.get(b, 0), o_.get(b, 0))
        for cty, g in zw.groupby("county"):
            if kind == "h":
                dm = md_h[md_h.county == cty]; m = pd.Series(np.asarray(fm(dm))).value_counts(normalize=True)
                qq = H[H.PUMA.isin(g.puma)]; w = qq.WGTP.values * qq.PUMA.map(g.set_index("puma").n).fillna(0).values; o = pd.Series(w).groupby(np.asarray(fo(qq))).sum(); o = o / o.sum()
            else:
                dm = md_p[md_p.county == cty]; qq = P[P.PUMA.isin(g.puma)]
                if kind == "p16": dm = dm[dm.age >= 16]; qq = qq[qq.AGEP >= 16]
                if kind == "p1834": dm = dm[dm.age.between(18, 34)]; qq = qq[qq.AGEP.between(18, 34)]
                m = pd.Series(np.asarray(fm(dm))).value_counts(normalize=True); w = qq.PWGTP.values * qq.PUMA.map(g.set_index("puma").n).fillna(0).values; o = pd.Series(w).groupby(np.asarray(fo(qq))).sum(); o = o / o.sum()
            for b in order: add("B composition", y, cty, f"{name} [PUMS {v}]", b, m.get(b, 0), o.get(b, 0))
    # B2 statewide: employed share by age band x sex, workers per household, young adults in roommate households
    bands = [(16, 19), (20, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, 74), (75, 120)]
    for sx, sn in [(1, "male"), (2, "female")]:
        for a0, a1 in bands:
            dm = md_p[(md_p.gender == sx) & md_p.age.between(a0, a1)]; qq = P[(P.SEX == sx) & P.AGEP.between(a0, a1)]
            add("B2 statewide", y, "24", "employed share by age and sex", f"{sn} {a0}-{min(a1, 99) if a1 < 120 else '+'}".replace("-+", "+"), (dm.occupation == 1).mean(), (qq.PWGTP * qq.ESR.isin([1, 2, 4, 5])).sum() / qq.PWGTP.sum())
    wk = md_h.id.map(md_p[md_p.occupation == 1].groupby("hhID").size()).fillna(0).clip(upper=3); m_ = wk.value_counts(normalize=True); o_ = H.groupby(H.workers.clip(upper=3)).WGTP.sum(); o_ = o_ / o_.sum()
    for b in range(4): add("B2 statewide", y, "24", "workers per household", f"{b}{'+' if b == 3 else ''}", m_.get(b, 0), o_.get(b, 0))
    # roommates: persons 18-34 without partner/child role whose household has neither a married nor a child-role member, share in households of 2+ persons;
    # ACS: persons 18-34 in non-family households (HHT 4-7), cohabiting partners and their householders excluded, share with NP >= 2
    fam = md_p.relationShip.isin(["MARRIED", "CHILD"]).groupby(md_p.hhID).any(); y34 = md_p[md_p.age.between(18, 34) & (md_p.relationShip == "SINGLE") & ~md_p.hhID.map(fam).fillna(True).astype(bool)]
    rel = P.RELP if "RELP" in P else P.RELSHIPP; partner = rel.isin([13] if "RELP" in P else [22, 24]); hd = rel.eq(0 if "RELP" in P else 20)
    hh_part = set(P.SERIALNO[partner]); q = P[P.AGEP.between(18, 34) & P.HHT.isin([4, 5, 6, 7]) & ~partner & ~(hd & P.SERIALNO.isin(hh_part))]
    add("B2 statewide", y, "24", "persons 18-34 in non-family households living with others", "share", (y34.hhID.map(md_h.set_index("id").hhSize) >= 2).mean(), (q.PWGTP * (q.NP >= 2)).sum() / q.PWGTP.sum())
    # E workplaces and commute times of Maryland residents with a job
    if "SK" not in globals():
        sk = pd.read_csv(f"{S}/input/skims/auto_peak_time.csv.gz"); sk.columns = ["f", "t", "v"]; SK = sk.set_index(["f", "t"]).v
        LOD = pd.read_csv(f"{V}/data/silo_target_lodes_own_county.csv"); ACSC = pd.read_csv(f"{V}/data/silo_target_commute_acs.csv").set_index("vintage")
    jz = pd.read_csv(yfile(y, "jj"), usecols=["id", "zone"]).set_index("id").zone
    w = md_p[(md_p.occupation == 1) & (md_p.workplace > 0)].copy(); w["hz"] = w.hhID.map(md_h.set_index("id").zone); w["jz"] = w.workplace.map(jz); w = w.dropna(subset=["hz", "jz"])
    w["jc"] = w.jz.map(z.COUNTYFIPS); w["js"] = w.jz.map(z.STFIPS); wm = w[w.js == 24]; lo = LOD[LOD.year == min(y, 2023)].set_index("county").own_county_share
    add("E commute", y, "24", f"share of Maryland-resident jobs in Maryland located in the home county [LODES {min(y, 2023)}]", "share", (wm.jc == wm.county).mean(), lo.get(24, np.nan))
    for c, g in wm.groupby("county"): add("E commute", y, int(c), f"share of Maryland-resident jobs in Maryland located in the home county [LODES {min(y, 2023)}]", "share", (g.jc == g.county).mean(), lo.get(int(c), np.nan))
    tt = SK.reindex(pd.MultiIndex.from_arrays([w.hz.astype(int).values, w.jz.astype(int).values])).values; tt = tt[np.isfinite(tt)]
    ac = ACSC.loc[min(y + 2, 2024)]
    add("E commute", y, "24", f"travel time to work, mean (model: car peak skim; ACS {min(y + 2, 2024)}: JWMNP all modes)", "min", tt.mean(), ac.mean_min)
    add("E commute", y, "24", f"travel time to work, median (model: car peak skim; ACS {min(y + 2, 2024)}: JWMNP all modes)", "min", np.median(tt), ac.median_min)
    add("E commute", y, "24", f"share of Maryland-resident workers employed in Maryland [ACS {min(y + 2, 2024)} POWSP]", "share", (w.js == 24).mean(), ac.work_in_md)
    # D vacant jobs vs the JOLTS job-openings rate (Maryland)
    if "JOLTS" not in globals():
        import json as _j; _d = _j.load(open(f"{V}/data/raw/jolts/jolts_openings_rate_md_us_2016_2024.json"))
        _m = [s_ for s_ in _d["Results"]["series"] if s_["seriesID"] == "JTS000000240000000JOR"][0]["data"]
        JOLTS = pd.DataFrame([(int(x["year"]), float(x["value"])) for x in _m if x["period"] != "M13"], columns=["year", "r"]).groupby("year").r.mean() / 100
    add("D jobs", y, "all regions", "vacant share of jobs vs JOLTS openings rate (Maryland)", "share", (jj.personId <= 0).mean(), JOLTS.get(min(y, 2024), np.nan))
    # F mover flows of the households that moved in calendar year y-1 (siloResults/relocation/relocation<y-1>.csv[.gz])
    rl = [f"{S}/run/base/scenOutput/{scen}/siloResults/relocation/relocation{y - 1}.csv{e}" for e in [".gz", ""]]; rl = [f for f in rl if os.path.exists(f)]
    if rl and y > 2016:
        if "FLO" not in globals(): FLO = pd.read_csv(f"{V}/data/silo_target_region_flows_acs.csv")
        rr = pd.read_csv(rl[0], usecols=["oldZone", "newZone"]); rr["o"] = rr.oldZone.map(z.Region); rr["d"] = rr.newZone.map(z.Region); rr = rr.dropna()
        regs = np.sort(z.Region.unique()); idx = pd.MultiIndex.from_product([regs, regs]); m = rr.groupby(["o", "d"]).size().reindex(idx, fill_value=0).values.astype(float); m /= m.sum()
        ob = FLO[FLO.period == "2016_2020"].set_index(["orig", "dest"]).flow.reindex(idx, fill_value=0).values.astype(float); ob /= ob.sum(); off = idx.get_level_values(0) != idx.get_level_values(1)
        add("F flows", y, "all regions", "moving households staying in their region [ACS flows 2016-20]", "share", m[~off].sum(), ob[~off].sum())
        add("F flows", y, "all regions", "correlation of region-to-region mover flows with the ACS flows 2016-20 (all pairs)", "r", np.corrcoef(m, ob)[0, 1], 1.0)
        add("F flows", y, "all regions", "correlation of region-to-region mover flows with the ACS flows 2016-20 (between regions)", "r", np.corrcoef(m[off], ob[off])[0, 1], 1.0)
        md_o = rr.oldZone.map(z.STFIPS) == 24; obo = FLO[FLO.period == "2016_2020"]; st = dict(zip(z.Region, z.STFIPS))
        obm = obo[obo.orig.map(st) == 24]; add("F flows", y, "24", "Maryland movers moving to another state [ACS flows 2016-20]", "share", (rr[md_o].newZone.map(z.STFIPS) != 24).mean(), obm[obm.dest.map(st) != 24].flow.sum() / obm.flow.sum())
    # C event rates from year-to-year changes (persons present both years), Maryland, with observed targets:
    #   births, deaths: Census PEP components of change (BIRTHS<y>, DEATHS<y>, Maryland counties summed) per women 15-50 / per person
    #   marriages, divorces, moves: PUMS 5-year file centred on the year (MARHM, MARHD, MV = moved within the last 12 months)
    if prev is not None:
        p0, p1 = prev[1].set_index("id"), pp.set_index("id"); both = p0.index.intersection(p1.index)
        md0 = p0[p0.st == 24]; md1 = p1[p1.st == 24]; bmd = md0.index.intersection(md1.index)
        women = md0[(md0.gender == 2) & md0.age.between(15, 50)]; births = int((md1.age == 0).sum())
        ye = y - 1   # events between the states at the start of y-1 and the start of y happen in calendar year y-1
        pepf = "co-est2020-alldata.csv" if ye <= 2020 else "co-est2025-alldata.csv"
        pe = pd.read_csv(f"{V}/data/raw/pep/{pepf}", encoding="latin-1", dtype={"STATE": str}); pe = pe[(pe.SUMLEV == 50) & (pe.STATE == "24")]
        ob = float(pe[f"BIRTHS{ye}"].sum()); od = float(pe[f"DEATHS{ye}"].sum()); opop = md_pop(ye)
        with zipfile.ZipFile(f"{ROOT}/inputs/pums_{v}_5yr/csv_pmd.zip") as zf:
            n_ = [x for x in zf.namelist() if x.endswith(".csv")][0]; Q = pd.read_csv(zf.open(n_), usecols=lambda c: c in ["PWGTP", "AGEP", "SEX", "MARHM", "MARHD", "MAR", "MIG", "RELP", "RELSHIPP"], low_memory=False)
        Q = Q[~(Q.RELP.isin([16, 17]) if "RELP" in Q else Q.RELSHIPP.isin([37, 38]))]; ad = Q[Q.AGEP >= 18]; w = ad.PWGTP
        obs_marr = (w * (ad.MARHM == 1)).sum() / w.sum(); obs_div = (w * (ad.MARHD == 1)).sum() / (w * (ad.MAR == 1)).sum(); Q1 = Q[Q.AGEP >= 1]; obs_mov = (Q1.PWGTP * (Q1.MIG != 1)).sum() / Q1.PWGTP.sum()   # MIG is not asked for persons under 1
        add("C events", y, "Maryland", "births per woman 15-50", "rate", births / max(len(women), 1), ob / max(float(((Q.SEX == 2) & Q.AGEP.between(15, 50)).mul(Q.PWGTP).sum()), 1))
        add("C events", y, "Maryland", "persons leaving Maryland (deaths, out-migration, moves to other states)", "rate", 1 - len(bmd) / len(md0), np.nan)   # diagnostic of the regional-control churn; deaths are validated from the engine's event counts (C2)
        add("C events", y, "Maryland", "new marriages share of adults", "rate", ((md0.loc[bmd, "relationShip"] != "MARRIED") & (md1.loc[bmd, "relationShip"] == "MARRIED") & (md0.loc[bmd, "age"] >= 18)).sum() / (md0.loc[bmd, "age"] >= 18).sum(), obs_marr)
        add("C events", y, "Maryland", "divorces share of married", "rate", ((md0.loc[bmd, "relationShip"] == "MARRIED") & (md1.loc[bmd, "relationShip"] != "MARRIED")).sum() / max((md0.loc[bmd, "relationShip"] == "MARRIED").sum(), 1), obs_div)
        add("C events", y, "Maryland", "job starts share of non-employed adults", "rate", ((md0.loc[bmd, "occupation"] != 1) & (md1.loc[bmd, "occupation"] == 1) & (md0.loc[bmd, "age"] >= 18)).sum() / max(((md0.loc[bmd, "occupation"] != 1) & (md0.loc[bmd, "age"] >= 18)).sum(), 1), np.nan)
        add("C events", y, "Maryland", "job quits share of employed", "rate", ((md0.loc[bmd, "occupation"] == 1) & (md1.loc[bmd, "occupation"] != 1)).sum() / max((md0.loc[bmd, "occupation"] == 1).sum(), 1), np.nan)
        h0, h1 = prev[0].set_index("id"), hh.set_index("id"); hb = h0.index.intersection(h1.index); hb = hb[h0.loc[hb, "st"] == 24]
        # moves, person-based like the ACS (MIG != 1: did not live in this house one year ago, persons aged 1+): a Maryland
        # resident aged 1+ at the start of y moved if they were not in the model area at the start of y-1 (in-migrant) or
        # their dwelling changed (residential move, new household formed by leaving home, divorce or marriage)
        r1 = md1[md1.age >= 1]; ex = r1.index.isin(p0.index); dw0 = p0.dwelling.reindex(r1.index).values
        add("C events", y, "Maryland", "persons who moved share (persons aged 1+)", "rate", float((~ex | (dw0 != r1.dwelling.values)).mean()), obs_mov)
        add("C events", y, "Maryland", "households moved share (households present both years; diagnostic)", "rate", (h0.loc[hb, "dwelling"] != h1.loc[hb, "dwelling"]).mean(), np.nan)
    # C2 event counts as written by the engine (scenOutput/<scen>/resultFile.csv, section "Count of simulated events", per year)
    rf = f"{S}/run/base/scenOutput/{scen}/resultFile.csv"
    if os.path.exists(rf) and y > 2016:
        blocks = open(rf).read().split("Year "); blk = [b for b in blocks if b.startswith(f"{y - 1}\n")]
        if blk:
            ev = dict(re.findall(r"^(\w+Event),(\d+)$", blk[0], flags=re.M)); n_md_prev = len(prev[1]) if prev is not None else len(pp)
            for k, v_ in ev.items(): add("C2 engine events", y, "all regions", k, "count", int(v_), np.nan)
            pe_ = pd.read_csv(f"{V}/data/raw/pep/{'co-est2020-alldata.csv' if y - 1 <= 2020 else 'co-est2025-alldata.csv'}", encoding="latin-1", dtype={"STATE": str}); pe_ = pe_[(pe_.SUMLEV == 50) & (pe_.STATE == "24")]
            add("C events", y, "all regions", "deaths share of persons (engine events; observed: Maryland)", "rate", int(ev.get("DeathEvent", 0)) / n_md_prev, float(pe_[f"DEATHS{y - 1}"].sum()) / md_pop(y - 1))
    # D2 construction: new dwellings (ids above the previous year's maximum) by Maryland county vs permitted units (BPS)
    if prev is not None and os.path.exists(f"{V}/data/silo_target_permits_by_county_year.csv"):
        d1 = pd.read_csv(yfile(y, "dd"), usecols=["id", "zone"]); d0max = pd.read_csv(yfile(y - 1, "dd"), usecols=["id"]).id.max()
        new = d1[d1.id > d0max]; new["county"] = new.zone.map(z.COUNTYFIPS); nb = new.groupby("county").size()
        perm = pd.read_csv(f"{V}/data/silo_target_permits_by_county_year.csv"); perm = perm[perm.year == min(y - 1, 2024)].set_index("county").units_total   # dwellings built in calendar year y-1 vs units permitted in y-1 (before 2026-10-23: permits of y)
        for c in perm.index: add("D2 construction", y, c, "new dwellings vs permitted units", "units", nb.get(c, 0), perm[c])
    # D jobs
    jb = jj[jj.personId > 0].groupby(["region", "type"]).size()
    tj = Tjob[Tjob.year == min(y, 2023)].set_index("region")
    for (r, t_), n in jb.items():
        if r in tj.index: add("D jobs", y, r, f"filled jobs vs LODES {min(y, 2023)}", t_, n, tj.at[r, t_])
    prev = (hh, pp)
R = pd.DataFrame(rows); R["diff_pp"] = (R.model - R.observed) * 100; R["ratio"] = R.model / R.observed; os.makedirs(f"{V}/data", exist_ok=True)
R.to_parquet(f"{V}/data/silo_validation_{scen}.parquet", index=False)
for y in avail:
    B = R[(R.section == "B composition") & (R.year == y)]; A = R[(R.section == "A totals") & (R.year == y)]
    print(f"{y}: totals by region ratio median {A.ratio.median():.3f} (range {A.ratio.min():.3f}-{A.ratio.max():.3f}); composition cells within ±5 pp {(B.diff_pp.abs() <= 5).mean():.1%} of {len(B)}; worst {B.assign(a=B.diff_pp.abs()).nlargest(3, 'a')[['geo', 'table', 'bin', 'diff_pp']].round(1).values.tolist()}")
for sec in ["B2 statewide", "E commute", "F flows"]:
    X = R[(R.section == sec) & R.geo.isin(["24", "all regions", "Maryland"])]
    if len(X): print(X.pivot_table(index=["table", "bin"], columns="year", values=["model", "observed"]).round(4).to_string())
C = R[R.section == "C events"]
if len(C): print(C.pivot_table(index="table", columns="year", values=["model", "observed"]).round(4).to_string())
E = R[(R.section == "C2 engine events") & (R["bin"] == "count")]
if len(E): print(E.pivot_table(index="table", columns="year", values="model").astype(int).to_string())
