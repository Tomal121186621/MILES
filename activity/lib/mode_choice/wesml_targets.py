#!/usr/bin/env python3
"""Choice-based sample weights (WESML, Manski & Lerman 1977) of the work tour mode choice: population commute-mode shares by home
county from the ACS 2017-2019 PUMS (the period of the survey), and the weights of the survey's work tours.

    python3 activity/lib/mode_choice/wesml_targets.py      -> results/wesml_targets.csv (stratum x mode: ACS share, survey shares and weights of both halves),
                                     results/wesml_strata.csv (county -> stratum), work/wesml_<half>.parquet (person_id, tour row, weight)

Population (Q).  ACS 2015-2019 5-year person files of DC, MD, VA, WV (inputs/pums_<yr>_5yr/csv_p<st>.zip), interview years 2017,
2018 and 2019 (SERIALNO), household population, workers at work in the reference week (ESR 1, 4; age 16+) who did not work at home
(JWTRNS present, not 11), person weights PWGTP.  Modes as the survey tours are coded (rts_common.MODE_MAP): car, truck or van
(JWTRNS 1) -> a k-person carpool (JWRIP = k) counts 1/k as driver and (k-1)/k as passenger, drove alone = driver; motorcycle (8) ->
car driver; taxicab (7) -> car passenger (the survey counts taxi and ride hailing as car passenger); bus (2) -> BUS; subway (3), long-
distance or commuter rail (4), light rail or streetcar (5) -> TRAIN; walked (10), bicycle (9); ferry (6) and other (12) are dropped.
Geography: 2010 PUMAs; a county is joined with every county it shares a PUMA with (Census 2010 tract-to-PUMA file), so that each
group is a union of whole PUMAs.  Groups with fewer than MIN_TOURS work tours in the estimation half are pooled by state.

Sample (H).  The work tours of each half (work/gc_bio_work_s50.parquet, gc_hold_work_s50.parquet; after the availability drops of
prep_tours.py), unweighted, as estimated (households are sampled exogenously; the household expansion weights are not used).
Weight of a tour of stratum g with chosen mode i:  w = Q(i|g) / H(i|g),  so that the weights sum to the sample size of each
stratum (the geographic stratification of the survey is exogenous and keeps its sample sizes) and the weighted mode shares of each
stratum equal the ACS shares.  A mode the survey does not observe in a stratum cannot be represented; Q is renormalised over the
observed modes of the stratum and the mass that is lost is reported (results/wesml_targets.csv, column q_unobserved).
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, zipfile
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/mode_choice"; WORK = f"{HERE}/work"; RES = f"{HERE}/results"
V = WORKSPACE; ROOT = PROJECT_ROOT
PUMS = f"{ROOT}/inputs/pums_2019_5yr"; XW = f"{V}/data/raw/resloc/2010_Census_Tract_to_2010_PUMA.txt"
ST = {11: "dc", 24: "md", 51: "va", 54: "wv"}
MODES = ["CD", "CP", "BUS", "TRAIN", "WK", "BK"]
MIN_TOURS = 100
COLS = ["SERIALNO", "PUMA", "PWGTP", "AGEP", "ESR", "JWTRNS", "JWRIP", "RELSHIPP"]


def acs_persons(st):
    with zipfile.ZipFile(f"{PUMS}/csv_p{ST[st]}.zip") as z:
        n = [x for x in z.namelist() if x.endswith(".csv")][0]
        with z.open(n) as f: p = pd.read_csv(f, usecols=COLS, dtype={"SERIALNO": str}, low_memory=False)
    p = p[p.SERIALNO.str[:4].astype(int).isin([2017, 2018, 2019])]
    p = p[(p.RELSHIPP.fillna(0) < 37) & p.ESR.isin([1, 4]) & (p.AGEP >= 16) & p.JWTRNS.notna() & (p.JWTRNS != 11)]
    p = p.assign(st=st, pu=p.PUMA.astype(int))
    j = p.JWTRNS.values; k = p.JWRIP.fillna(1).clip(lower=1).values; w = p.PWGTP.values.astype(float)
    m = pd.DataFrame({"CD": w * ((j == 1) / k + (j == 8)), "CP": w * ((j == 1) * (1 - 1 / k) + (j == 7)), "BUS": w * (j == 2),
                      "TRAIN": w * np.isin(j, [3, 4, 5]), "WK": w * (j == 10), "BK": w * (j == 9)}, index=p.index)
    return pd.concat([p[["st", "pu"]], m], axis=1)


def strata(counties, n_est):
    """county -> stratum: union of the counties that share a 2010 PUMA (whole PUMAs); groups with < MIN_TOURS estimation tours
    pooled by state"""
    r = pd.read_csv(XW, dtype=str); r["county"] = (r.STATEFP + r.COUNTYFP).astype(int); r["st"] = r.STATEFP.astype(int); r["pu"] = r.PUMA5CE.astype(int)
    r = r[r.st.isin(ST)]
    par = {}
    def find(x):
        while par.setdefault(x, x) != x: x = par[x]
        return x
    for (st, pu), g in r.groupby(["st", "pu"]):
        c = list(g.county.unique()); [par.__setitem__(find(a), find(c[0])) for a in c]
    grp = {c: find(c) for c in r.county.unique()}
    out = {}
    for c in counties:
        root = grp[c]; mem = sorted(k for k, v in grp.items() if v == root); out[c] = dict(group=root, members=mem)
    n_grp = pd.Series({c: n_est.get(c, 0) for c in counties}).groupby(pd.Series({c: out[c]["group"] for c in counties})).sum()
    rows = []
    for c in counties:
        g = out[c]["group"]; small = n_grp[g] < MIN_TOURS; st = c // 1000
        rows.append(dict(county=c, puma_group=g, puma_group_counties=";".join(map(str, out[c]["members"])),
                         stratum=f"other_{ST[st]}" if small else f"g{g}", n_est_group=int(n_grp[g])))
    s = pd.DataFrame(rows)
    pumas = r.groupby("county").apply(lambda d: sorted(set(zip(d.st, d.pu))), include_groups=False)
    return s, grp, pumas


def main():
    E = pd.read_parquet(f"{WORK}/gc_bio_work_s50.parquet"); H = pd.read_parquet(f"{WORK}/gc_hold_work_s50.parquet")
    counties = sorted(set(E.county.astype(int)) | set(H.county.astype(int)))
    S, grp, pumas = strata(counties, E.county.astype(int).value_counts().to_dict())
    # ACS: PUMA (st, pu) -> stratum through the PUMA group of any survey county (members of a group share all their PUMAs)
    pu2s = {}
    for r in S.itertuples():
        for c in r.puma_group_counties.split(";"):
            for key in pumas[int(c)]: pu2s[key] = r.stratum
    A = pd.concat([acs_persons(st) for st in ST]); A["stratum"] = [pu2s.get(k) for k in zip(A.st, A.pu)]
    A = A[A.stratum.notna()]
    Q = A.groupby("stratum")[MODES].sum(); n_acs = A.groupby("stratum").size(); Q = Q.div(Q.sum(1), axis=0)
    c2s = S.set_index("county").stratum
    rows, W = [], {}
    for half, d in [("est", E), ("hold", H)]:
        d = d.assign(stratum=d.county.astype(int).map(c2s).values)
        Hs = d.groupby("stratum").choice.value_counts(normalize=True).unstack().reindex(columns=MODES).fillna(0.0)
        Hw = (d.assign(x=d.w).groupby(["stratum", "choice"]).x.sum() / d.groupby("stratum").w.sum()).unstack().reindex(columns=MODES).fillna(0.0)
        q = Q.reindex(Hs.index); obs = Hs > 0; lost = (q * ~obs).sum(1); qn = (q * obs).div((q * obs).sum(1), axis=0)
        ratio = (qn / Hs.where(obs)).fillna(0.0)
        wt = np.array([ratio.at[s, m] for s, m in zip(d.stratum, d.choice)])
        W[half] = pd.DataFrame(dict(person_id=d.person_id.values, row=np.arange(len(d)), stratum=d.stratum.values, choice=d.choice.values, wesml=wt))
        W[half].to_parquet(f"{WORK}/wesml_{half}.parquet", index=False)
        for s in Hs.index:
            for m in MODES:
                rows.append(dict(half=half, stratum=s, mode=m, acs=Q.at[s, m] if s in Q.index else np.nan, acs_records=int(n_acs.get(s, 0)),
                                 survey_unweighted=Hs.at[s, m], survey_weighted=Hw.at[s, m], n_tours=int((d.stratum == s).sum()),
                                 n_mode=int(((d.stratum == s) & (d.choice == m)).sum()), q_unobserved=lost[s], weight=ratio.at[s, m]))
        print(f"{half}: N {len(d)}, weights mean {wt.mean():.3f}, min {wt.min():.3f}, max {wt.max():.3f}, Kish n_eff {wt.sum()**2 / (wt**2).sum():.0f}; "
              f"lost ACS mass max {lost.max():.4f}", flush=True)
    T = pd.DataFrame(rows); T.to_csv(f"{RES}/wesml_targets.csv", index=False); S.to_csv(f"{RES}/wesml_strata.csv", index=False)
    x = T[T.half == "est"].pivot_table(index=["stratum", "n_tours"], columns="mode", values=["acs", "survey_unweighted", "weight"])
    pd.set_option("display.width", 250); print((x * 1).round(3).to_string())


if __name__ == "__main__":
    main()
