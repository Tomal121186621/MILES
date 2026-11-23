#!/usr/bin/env python3
"""Mode of each trip (leg) within a transit tour (3 November 2026): DAYMAP chooses one mode per tour (MarylandTourNestedModeChoice)
and gave it to every leg; in the 2017/18 RTS only about 60 % of the linked trips of transit tours are by transit.  This script builds
the legs of the observed transit tours, estimates a multinomial logit of the leg mode on the ESTIMATION half and tests it on the
hold-out half.  Nothing is fitted to counts or ridership.

    ~/.venvs/biogeme/bin/python activity/lib/tasha_estimation/estimate_transit_legs.py data       -> work/tlegs_<half>.parquet, results/tleg_data_*.csv
    ~/.venvs/biogeme/bin/python activity/lib/tasha_estimation/estimate_transit_legs.py estimate   -> results/tleg_*.csv, results/tasha_transit_legs.csv
    python3 activity/lib/tasha_estimation/estimate_transit_legs.py check RUN_GLOB...                -> leg modes of transit tours and trip shares, survey vs runs

Tours (mode_choice/prep_tours.py, the data of the tour mode choice): home-based chains of the typed episodes; the tour is a transit
tour when any of its trips is by rail or bus (rts_common.MODE_MAP: private bus is bus; school bus, paratransit, taxi and ride hailing
are car passenger).  Both survey regions (BMC and TPB).
Legs: the trips of the chain, linked around the change-mode activity (17): a trip that ends at activity 17 is joined with the
following trip(s) into one linked trip with the main mode (transit > car driver > car passenger > bike > walk); a leg touching a
work-based outing (build_distributions.subtours: to an outing stop, or from it back to the workplace) is left out, because DAYMAP gives
the outing legs their own model (MarylandTashaGenerator.outingModes).
Dependent variable: TR (transit, the tour's transit mode), WK walk, CP car passenger, CD car driver, BK bike.

Variables (all known to DAYMAP when the leg mode is drawn; zone skims of the tour mode choice, mc_common.los / mode_choice/export/los):
  first, last          leg from home (first) / back home (last); base: intermediate leg (between two out-of-home activities)
  main                 the leg starts or ends at the main activity of the tour
  lnkm                 ln(1 + km), car-distance skim between the zones of the leg (intrazonal 0.5 sqrt(area))
  ttr                  transit minutes of the leg / 10 (walk access; bus-only skim of a bus tour, rail path of a train tour, else
                       the faster of the two; regional prior where the raptor skim has no path), period of the departure
  peak                 departure in AM (6-9) or PM (15-19)
  wash                 home zone in the Washington region (WMATA counties)
  work, school         main activity of the tour is work / school (base: other purposes)
  cars0, carshort, lic, age_u18, age_65p
Availability: TR when the leg has a transit path (zones differ and the period skim or the prior has one); WK up to WALK_MAX km;
BK up to BIKE_MAX km; CP always; CD only on the first and the last leg, with a licence, age 16+ and a household car (rule below).
Car-driver rule (from the data, results/tleg_cd_pattern.csv): car-driver legs of transit tours are almost all the first or the last
leg (the car is at home); in DAYMAP a car-driver first leg forces the last leg to car driver and vice versa (the car must come back)
when the drawn modes disagree -> see MarylandTashaGenerator.transitLegModes.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, json
import numpy as np
import pandas as pd
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; A3 = os.path.dirname(HERE)
sys.path.insert(0, CODE); sys.path.insert(0, f"{MILES_HOME}/activity/lib/mode_choice"); sys.path.insert(0, f"{MILES_HOME}/activity/lib")
sys.path.insert(0, f"{MILES_HOME}/activity/distributions")
import te_common as T                     # noqa: E402
import build_distributions as TD          # noqa: E402
import mc_common as M                     # noqa: E402
from rts_common import RTS, MODE_MAP      # noqa: E402

BIO = f"{T.WORK}/biogeme_tleg"
ALTS = ["TR", "WK", "CP", "CD", "BK"]
HIER = ["TR", "CD", "CP", "BK", "WK"]
MAP = {"BUS": "TR", "TRAIN": "TR", "WALK": "WK", "CAR_PASSENGER": "CP", "CAR_DRIVER": "CD", "BIKE": "BK"}
WALK_MAX, BIKE_MAX = 8.0, 30.0


def legs(half):
    f = f"{T.WORK}/tlegs_{half}.parquet"
    if os.path.exists(f): return pd.read_parquet(f)
    tours = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet")
    tt = tours[tours.choice.isin(["TW", "TD"])].reset_index(drop=True)
    e = T.episodes(half).sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    e = TD.subtours(e)
    fl = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", low_memory=False, usecols=["tripid", "travel_mode", "transit_access_mode", "transit_egress_mode"]).drop_duplicates("tripid").set_index("tripid")
    e = e.set_index("tripid"); e["mode"] = fl.travel_mode.reindex(e.index).map(MODE_MAP).map(MAP)
    e["acc"] = fl.transit_access_mode.reindex(e.index); e["egr"] = fl.transit_egress_mode.reindex(e.index)
    rows = []; nmerge = 0
    for k, t in tt.iterrows():
        ids = list(t.tripids); c = e.loc[ids]
        # main episode: the trip that arrives at it (same rule as prep_tours: dest zone and type of the main)
        main_trip = None
        for tid, r in c.iterrows():
            if r.type == t.type and r.dz == t.mz and r.arr_min == t.start: main_trip = tid; break
        # link around change-mode activity 17
        linked = []; cur = []
        for tid, r in c.iterrows():
            cur.append((tid, r))
            if r.d_activity == 17 and not r.is_home: continue
            linked.append(cur); cur = []
        if cur: linked.append(cur)
        n = len(linked)
        for q, g in enumerate(linked):
            if len(g) > 1: nmerge += 1
            ms = [x[1]["mode"] for x in g]
            if any(pd.isna(m) for m in ms): mode = None
            else: mode = next(h for h in HIER if h in ms)
            r0, r1 = g[0][1], g[-1][1]
            pv = linked[q - 1][-1] if q > 0 else None
            # from the main activity, or from the continuation of the main work episode after an outing (DAYMAP splits the work episode)
            prev_main = pv is not None and (pv[0] == main_trip or (bool(pv[1].wbs_cont) and t.type in ("PW", "SW") and pv[1].dz == t.mz))
            to_main = g[-1][0] == main_trip
            # outing leg: to an outing stop, or from an outing stop (back to the workplace or to the next outing stop)
            prev_wbs = q > 0 and bool(linked[q - 1][-1][1].wbs)
            sub = bool(r1.wbs) or (prev_wbs and (bool(r1.wbs_cont) or bool(r1.wbs)))
            oz = t.hz if q == 0 else r0.oz; dz = t.hz if q == n - 1 else r1.dz
            rows.append(dict(tour=k, person_id=t.person_id, household_id=t.household_id, q=q, n=n, first=float(q == 0), last=float(q == n - 1),
                             main=float(to_main or prev_main), mode=mode, merged=len(g) > 1, outing=sub, oz=oz, dz=dz, hz=t.hz, mz=t.mz,
                             dep=r0.dep_min, arr=r1.arr_min, tour_choice=t.choice, rail=bool(t.rail), purpose=t.purpose, segment=t.segment,
                             d_act=int(r1.d_activity), o_act=int(r0.o_activity), dist_rep=r1.distance, age=t.age, lic=t.lic, autos=t.autos,
                             drivers=t.drivers, county=t.county, w=t.w, n_trips=len(g), tripid0=g[0][0]))
    L = pd.DataFrame(rows)
    z = M.C.zones(); idx = M.C.id2idx()
    L["o"] = np.where(L.oz >= 0, idx[np.clip(L.oz.values, 0, None)], -1); L["d"] = np.where(L.dz >= 0, idx[np.clip(L.dz.values, 0, None)], -1)
    L["h"] = idx[L.hz.values]
    L.attrs["merged"] = nmerge
    L.to_parquet(f, index=False)
    return L


def leg_los(o, d, dep, tour_rail):
    """km, transit minutes (walk access; bus tour: bus-only schedule, train tour: rail path, else the faster) and availability"""
    Lm = M.los(); o = np.asarray(o); d = np.asarray(d); p = M.period(np.asarray(dep)); n = len(o)
    km = Lm["d"][o, d].astype(float)
    t = np.full(n, np.nan)
    for pi, P in enumerate(M.PERIODS):
        s = p == pi
        if not s.any(): continue
        W = Lm[("walk", P)]; a, b = o[s], d[s]
        tb = W["bus"][a, b].astype(float); tb = np.where(np.isfinite(tb), tb, Lm["prior_bus"][a, b])
        tr = np.where(W["rail"][a, b] >= 0.5, W["all"][a, b], np.nan).astype(float); tr = np.where(np.isfinite(tr), tr, Lm["prior_train"][a, b])
        x = np.where(tour_rail[s], np.where(np.isfinite(tr), tr, tb), np.where(np.isfinite(tb), tb, tr))
        t[s] = x
    ok = np.isfinite(t) & (o != d)
    return km, np.where(ok, t, 0.0), ok, p


def features(L):
    """model variables of the legs with known zones and mode, outing legs excluded; lagged modes over the non-outing legs"""
    L = L[~L.outing].sort_values(["tour", "q"]).copy()
    L["prev"] = L.groupby("tour")["mode"].shift(1).fillna("NONE")
    L["first_mode"] = L.groupby("tour")["mode"].transform("first")
    L = L[(L.o >= 0) & (L.d >= 0) & L["mode"].notna()].copy()
    km, ttr, ok, p = leg_los(L.o.values, L.d.values, L.dep.values, L.rail.values)
    X = pd.DataFrame(index=L.index)
    X["first"] = L["first"]; X["last"] = L["last"]; X["mid"] = 1.0 - L["first"] - L["last"]; X["main"] = L["main"]
    X["lnkm"] = np.log1p(km); X["km"] = km; X["ttr"] = ttr / 10.0; X["nopath"] = (~ok).astype(float)
    X["peak"] = np.isin(p, [0, 2]).astype(float)
    X["wash"] = M.wmata_zone()[L.h.values].astype(float)
    X["work"] = L.segment.eq("work").astype(float); X["school"] = L.segment.eq("school").astype(float)
    X["cars0"] = (L.autos <= 0).astype(float); X["carshort"] = ((L.autos > 0) & (L.autos < L.drivers)).astype(float)
    X["lic"] = L.lic.astype(float); X["age_u18"] = (L.age < 18).astype(float); X["age_65p"] = (L.age >= 65).astype(float)
    X["stops"] = (L.n > 2).astype(float); X["rail"] = L.rail.astype(float).values
    X["prevCD"] = L.prev.eq("CD").astype(float); X["prevCP"] = L.prev.eq("CP").astype(float); X["prevWK"] = L.prev.eq("WK").astype(float)
    X["firstCD"] = (L["last"].eq(1) & L.first_mode.eq("CD") & L["first"].eq(0)).astype(float)
    elig = (L.lic > 0) & (L.age >= 16) & (L.autos > 0)
    X["av_TR"] = 1.0; X["av_WK"] = (km <= WALK_MAX).astype(float); X["av_BK"] = (km <= BIKE_MAX).astype(float); X["av_CP"] = 1.0
    X["av_CD"] = elig.astype(float)
    X["y"] = L["mode"].map({a: i + 1 for i, a in enumerate(ALTS)}).values
    X["mode"] = L["mode"].values; X["w"] = L.w.values; X["tour"] = L.tour.values; X["q"] = L.q.values; X["n"] = L.n.values
    X["county"] = L.county.values; X["tour_choice"] = L.tour_choice.values; X["segment"] = L.segment.values
    ch = np.array([X[f"av_{m}"].iat[i] > 0 for i, m in enumerate(X["mode"].values)])
    X["chosen_av"] = ch
    return X


BMC = [24003, 24005, 24013, 24025, 24027, 24510]


def data():
    out = []
    for half in ["estimation", "validation"]:
        L = legs(half); X = features(L)
        out.append(dict(half=half, tours=L.tour.nunique(), trips=int(L.n_trips.sum()), legs=len(L), linked_around_17=int(L.merged.sum()), outing_legs=int(L.outing.sum()),
                        zone_unknown=int(((L.o < 0) | (L.d < 0)).sum()), model_legs=len(X), chosen_unavailable=int((~X.chosen_av).sum()),
                        **{f"n_{a}": int(X["mode"].eq(a).sum()) for a in ALTS},
                        share_TR=float(X["mode"].eq("TR").mean()), share_TR_w=float(np.average(X["mode"].eq("TR"), weights=X.w)),
                        share_TR_bmc_w=float(np.average(X["mode"].eq("TR")[X.county.isin(BMC)], weights=X.w[X.county.isin(BMC)]))))
        print(out[-1]); print(X[~X.chosen_av]["mode"].value_counts().to_dict())
    pd.DataFrame(out).to_csv(f"{T.RES}/tleg_data_summary.csv", index=False)
    # car-driver patterns: mode sequence of the tours with a car-driver leg (both halves)
    L = pd.concat([legs("estimation"), legs("validation").assign(tour=lambda d: d.tour + 10 ** 6)]); L = L[~L.outing]
    seq = L.sort_values(["tour", "q"]).groupby("tour")["mode"].apply("-".join)
    cd = seq[seq.str.contains("CD")]
    pat = cd.value_counts().rename("tours").reset_index().rename(columns={"index": "sequence", "mode": "sequence"})
    pat.to_csv(f"{T.RES}/tleg_cd_pattern.csv", index=False)
    f, l = seq.str.split("-").str[0], seq.str.split("-").str[-1]
    stat = dict(tours=len(seq), tours_with_cd=len(cd), first_cd=int((f == "CD").sum()), last_cd=int((l == "CD").sum()), both=int(((f == "CD") & (l == "CD")).sum()),
                p_last_cd_given_first_cd=float(((f == "CD") & (l == "CD")).sum() / max(1, (f == "CD").sum())), p_last_cd=float((l == "CD").mean()),
                mid_cd_legs=int((L["mode"].eq("CD") & L["first"].eq(0) & L["last"].eq(0)).sum()), cd_legs=int(L["mode"].eq("CD").sum()))
    json.dump(stat, open(f"{T.RES}/tleg_cd_stats.json", "w"), indent=1); print(stat)


# ------------------------------------------------------------------------------------------------ estimation
# (variable, alternative): utility term b_<var>_<alt> * var; TR is the reference (its own terms: ttr, nopath)
STEPS = [("L0", [("ASC", a) for a in ["WK", "CP", "CD", "BK"]], "alternative constants"),
         ("L1", [("first", a) for a in ["WK", "CP", "CD"]] + [("last", a) for a in ["WK", "CP", "CD"]] + [("main", a) for a in ["WK", "CP", "CD"]], "+ leg position, main activity"),
         ("L2", [("km", "WK"), ("km", "BK"), ("lnkm", "CP"), ("lnkm", "CD"), ("ttr", "TR"), ("nopath", "TR")], "+ leg distance, transit time / no transit path"),
         ("L3", [("prevCD", "CD"), ("firstCD", "CD"), ("prevCP", "CP"), ("prevWK", "WK")], "+ mode of the previous leg, car-driver first leg on the last leg"),
         ("L4", [("cars0", "CP"), ("carshort", "CP"), ("carshort", "CD"), ("age_u18", "CP"), ("age_65p", "CP"), ("age_65p", "WK"), ("lic", "CP")], "+ person and household"),
         ("L5", [("work", a) for a in ["WK", "CP", "CD"]] + [("school", "CP"), ("school", "WK"), ("peak", "CP"), ("peak", "WK"), ("peak", "CD"), ("wash", "WK"), ("wash", "CP"), ("wash", "CD"), ("rail", "CD")],
          "+ tour purpose, peak period, Washington region, train tour")]
KEEP = {("ASC", a) for a in ["WK", "CP", "CD", "BK"]}


def pname(t): return f"{t[0]}_{t[1]}"


def utilities(terms, X=None):
    """numpy utilities (n x 5) of a parameter dict {name: value}"""
    raise NotImplementedError


def biogeme_mnl(df, terms, name):
    import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
    from biogeme.expressions import Beta, Variable as Xv
    V = {i + 1: 0 for i in range(len(ALTS))}
    for v, a in terms:
        b = Beta(pname((v, a)), 0, None, None, 0); k = ALTS.index(a) + 1
        V[k] = V[k] + (b if v == "ASC" else b * Xv(v))
    AV = {i + 1: Xv(f"av_{a}") for i, a in enumerate(ALTS)}
    cols = sorted({v for v, a in terms if v != "ASC"} | {f"av_{a}" for a in ALTS} | {"y"})
    d = db.Database(name, df[cols].astype(float).reset_index(drop=True))
    os.makedirs(BIO, exist_ok=True); cwd = os.getcwd(); os.chdir(BIO)
    try:
        m = bio.BIOGEME(d, models.loglogit(V, AV, Xv("y")), save_iterations=False, generate_html=False, generate_yaml=False); m.model_name = name
        r = m.estimate()
    finally: os.chdir(cwd)
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))
    t = t.set_index("Name").reindex([pname(x) for x in terms])
    return dict(LL=float(r.final_loglikelihood), K=int(r.number_of_free_parameters), N=len(df), table=t, conv=bool(r.algorithm_has_converged), terms=list(terms))


def probs(df, terms, beta):
    U = np.zeros((len(df), len(ALTS)))
    for v, a in terms:
        U[:, ALTS.index(a)] += beta[pname((v, a))] * (1.0 if v == "ASC" else df[v].values)
    av = np.stack([df[f"av_{a}"].values > 0 for a in ALTS], 1)
    U = np.where(av, U, -np.inf); U -= U.max(1, keepdims=True); P = np.exp(U); P /= P.sum(1, keepdims=True)
    return P


def ll_of(df, terms, beta):
    P = probs(df, terms, beta); y = df.y.values.astype(int) - 1
    return float(np.log(np.clip(P[np.arange(len(df)), y], 1e-300, 1)).sum()), P


def ll_zero(df):
    nav = sum(df[f"av_{a}"].values > 0 for a in ALTS); return float(-np.log(nav).sum())


def search(est, val):
    rows = []; terms = []; prev = None
    for name, add, note in STEPS:
        terms = terms + [t for t in add if t[0] == "ASC" or est[t[0]].std() > 0]
        r = biogeme_mnl(est, terms, f"tleg_{name}")
        row = dict(model=name, note=note, K=r["K"], N=r["N"], LL=r["LL"], AIC=2 * r["K"] - 2 * r["LL"], BIC=np.log(r["N"]) * r["K"] - 2 * r["LL"])
        if prev is not None:
            st = 2 * (r["LL"] - prev["LL"]); df = r["K"] - prev["K"]; row.update(LR=st, LR_df=df, LR_p=float(chi2.sf(st, df)))
        row["LL_holdout"] = ll_of(val, terms, r["table"]["Value"].to_dict())[0]
        rows.append(row); prev = r; print(row, flush=True)
    full = prev; terms = list(full["terms"]); elim = []
    while True:
        t = full["table"]["Robust t-stat."].drop([pname(k) for k in KEEP]).abs(); t = t[t < 1.96]
        if len(t) == 0: break
        dv = t.idxmin(); terms = [x for x in terms if pname(x) != dv]
        r = biogeme_mnl(est, terms, f"tleg_elim_{dv}")
        elim.append(dict(dropped=dv, t=float(full["table"].loc[dv, "Robust t-stat."]), LL_before=full["LL"], LL_after=r["LL"])); full = r
    c = biogeme_mnl(est, sorted(KEEP, key=lambda x: ALTS.index(x[1])), "tleg_const")
    st = 2 * (prev["LL"] - full["LL"]); df = prev["K"] - full["K"]
    b = full["table"]["Value"].to_dict(); l0 = ll_zero(est)
    rows.append(dict(model="F", note="final (backward elimination, |robust t| < 1.96)", K=full["K"], N=full["N"], LL=full["LL"], AIC=2 * full["K"] - 2 * full["LL"],
                     BIC=np.log(full["N"]) * full["K"] - 2 * full["LL"], LR=st, LR_df=df, LR_p=float(chi2.sf(st, df)) if df > 0 else np.nan,
                     LL_holdout=ll_of(val, terms, b)[0], LL_const=c["LL"], LL_const_holdout=ll_of(val, c["terms"], c["table"]["Value"].to_dict())[0],
                     LL_zero=l0, LL_zero_holdout=ll_zero(val), N_holdout=len(val),
                     LR_vs_const=2 * (full["LL"] - c["LL"]), LR_vs_const_df=full["K"] - c["K"], LR_vs_const_p=float(chi2.sf(2 * (full["LL"] - c["LL"]), full["K"] - c["K"])),
                     rho2_zero=1 - full["LL"] / l0, rho2_const=1 - full["LL"] / c["LL"], rho2bar_zero=1 - (full["LL"] - full["K"]) / l0))
    return pd.DataFrame(rows), full, pd.DataFrame(elim), c


def estimate():
    est = features(legs("estimation")); val = features(legs("validation"))
    est = est[est.chosen_av].reset_index(drop=True); val = val[val.chosen_av].reset_index(drop=True)
    s, full, el, c = search(est, val)
    s.to_csv(f"{T.RES}/tleg_search.csv", index=False); el.to_csv(f"{T.RES}/tleg_elimination.csv", index=False)
    tab = full["table"].reset_index().rename(columns={"Name": "variable", "Value": "value"}); tab.to_csv(f"{T.RES}/tleg_estimates.csv", index=False)
    pd.set_option("display.width", 200); print(s.round(3).to_string()); print(el.round(3).to_string()); print(tab.round(3).to_string())
    # predicted vs observed shares (unweighted and weighted), both halves, by group
    terms = full["terms"]; b = full["table"]["Value"].to_dict(); chk = []
    for half, d in [("estimation", est), ("validation", val)]:
        P = probs(d, terms, b); d = d.assign(pos=np.where(d["first"] > 0, "first", np.where(d["last"] > 0, "last", "intermediate")), bmc=d.county.isin(BMC).map({True: "BMC", False: "TPB"}),
                                             kmb=pd.cut(d.km, [-1, 1, 3, 10, 1e9], labels=["<1", "1-3", "3-10", "10+"]).astype(str), all="all")
        for g in ["all", "pos", "bmc", "kmb", "segment", "tour_choice"]:
            for lev, x in d.groupby(g):
                ii = x.index.values; row = dict(half=half, group=g, level=str(lev), N=len(x))
                for k, a in enumerate(ALTS):
                    row[f"obs_{a}"] = float(np.average(x["mode"].eq(a), weights=x.w)); row[f"pred_{a}"] = float(np.average(P[ii, k], weights=x.w))
                chk.append(row)
    chk = pd.DataFrame(chk); chk.to_csv(f"{T.RES}/tleg_check.csv", index=False); print(chk[["half", "group", "level", "N", "obs_TR", "pred_TR", "obs_WK", "pred_WK", "obs_CD", "pred_CD", "obs_CP", "pred_CP"]].round(3).to_string())
    out = [dict(key=r.variable, value=r.value) for r in tab.itertuples()] + [dict(key="walk.max.km", value=WALK_MAX), dict(key="bike.max.km", value=BIKE_MAX)]
    pd.DataFrame(out).to_csv(f"{T.RES}/tasha_transit_legs.csv", index=False)
    pd.DataFrame([dict(variable=pname(t), value=c["table"]["Value"][pname(t)]) for t in c["terms"]]).to_csv(f"{T.RES}/tleg_const_estimates.csv", index=False)
    print("written", f"{T.RES}/tasha_transit_legs.csv")


# ------------------------------------------------------------------------------------------------ check on the survey households
REGION = {24003: "Baltimore region", 24005: "Baltimore region", 24013: "Baltimore region", 24025: "Baltimore region", 24027: "Baltimore region",
          24510: "Baltimore region", 11001: "Washington DC", 24031: "Montgomery + Prince George's", 24033: "Montgomery + Prince George's"}
for _c in [51013, 51059, 51107, 51153, 51510, 51600, 51610, 51683, 51685]: REGION[_c] = "Northern Virginia"
GROUP = {"BUS": "TR", "TRAIN": "TR", "WALK": "WK", "CAR_PASSENGER": "CP", "CAR_DRIVER": "CD", "BIKE": "BK"}


def chain_shares(df, wcol):
    """df: person_id, home (destination is home), m (TR/WK/...), weight; home-based chains in trip order; transit chain = any TR leg"""
    df = df.copy(); df["chain"] = df.groupby("person_id")["home"].transform(lambda h: h.shift(1, fill_value=False).cumsum())
    tr = df.groupby(["person_id", "chain"])["m"].transform(lambda m: (m == "TR").any())
    x = df[tr]
    return {f"in_transit_tours_{a}": float(np.average(x["m"].eq(a), weights=x[wcol])) for a in ALTS} | {"legs_in_transit_tours": len(x)}


def check(tags=("sched", "legmode"), half="validation"):
    import glob
    pm = pd.read_csv(f"{A3}/survey_pop/{half}/persons_map.csv")
    reg = pm.set_index("id").county.map(REGION).fillna("other"); wt = pm.set_index("id").w
    rows = []
    # observed: trips of the half's households, trip weights; modes rts_common.MODE_MAP (private bus = bus); also rail + public bus only
    hh = set(pm.household_id)
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv", usecols=["person_id", "household_id", "tripno", "d_activity", "travel_mode", "wttrdfin"], low_memory=False)
    t = t[t.household_id.isin(hh)].sort_values(["person_id", "tripno"])
    t["m"] = t.travel_mode.map(MODE_MAP).map(GROUP); t = t[t["m"].notna()].copy(); t["home"] = t.d_activity.eq(1)
    t["region"] = t.person_id.map(pm.drop_duplicates("person_id").set_index("person_id").county).map(REGION).fillna("other")
    t["tr78"] = t.travel_mode.isin([7, 8])
    for rg, g in [("all", t)] + list(t.groupby("region")):
        r = dict(source="observed", tag="RTS 2017/18", region=rg, trips=len(g), transit_7_8_only=float(np.average(g.tr78, weights=g.wttrdfin)))
        r |= {f"trips_{a}": float(np.average(g["m"].eq(a), weights=g.wttrdfin)) for a in ALTS}
        r |= chain_shares(g, "wttrdfin"); rows.append(r)
    for tag in tags:
        fs = sorted(glob.glob(f"{A3}/run_survey/svy_{half[:3]}_{tag}_s*/output/legs_svy_{half[:3]}_{tag}_s*.csv"))
        per = []
        for f in fs:
            L = pd.read_csv(f, usecols=["person_id", "next_purpose", "mode"]); L["m"] = L["mode"].map(GROUP); L = L[L["m"].notna()].copy()
            L["home"] = L.next_purpose.eq("HOME"); L["w"] = L.person_id.map(wt).fillna(1.0); L["region"] = L.person_id.map(reg).fillna("other")
            for rg, g in [("all", L)] + list(L.groupby("region")):
                r = dict(source="ABIT", tag=tag, region=rg, rep=f, trips=len(g)) | {f"trips_{a}": float(np.average(g["m"].eq(a), weights=g.w)) for a in ALTS}
                r |= chain_shares(g, "w"); per.append(r)
        P = pd.DataFrame(per); num = [c for c in P.columns if c not in ("source", "tag", "region", "rep")]
        m = P.groupby("region")[num].mean().reset_index(); sd = P.groupby("region")[num].std().add_suffix("_sd").reset_index()
        m = m.merge(sd[["region", "trips_TR_sd", "in_transit_tours_TR_sd"]], on="region"); m["source"] = "ABIT"; m["tag"] = f"{tag} ({len(fs)} reps)"
        rows += m.to_dict("records")
        # tour modes of the tour mode choice (unchanged by the leg model)
        tm = pd.concat([pd.read_csv(f.replace(f"legs_svy", "mc_tours").rsplit("/", 1)[0] + "/mc_tours.csv", usecols=["alt"]) for f in fs])
        print(tag, "tour modes:", (tm.alt.value_counts(normalize=True) * 100).round(2).to_dict())
    R = pd.DataFrame(rows); R.to_csv(f"{T.RES}/tleg_validation_{half}.csv", index=False)
    pd.set_option("display.width", 250)
    print(R[["source", "tag", "region", "trips", "trips_TR", "transit_7_8_only", "trips_WK", "trips_CD", "trips_CP", "in_transit_tours_TR", "in_transit_tours_WK", "in_transit_tours_CD", "in_transit_tours_CP"]].round(4).to_string())
    return R


if __name__ == "__main__":
    if sys.argv[1] == "check": check(); sys.exit()
    if sys.argv[1] == "data": data()
    elif sys.argv[1] == "estimate": estimate()
