#!/usr/bin/env python3
"""Work-based subtours of the TASHA generator (3 November 2026): outings from the usual workplace that return to it, estimated on
the ESTIMATION half of the 2017/18 RTS and tested on the hold-out half.  No calibration constant.

    ~/.venvs/biogeme/bin/python activity/lib/tasha_estimation/estimate_subtours.py estimate   -> results/wbs_*.csv, results/tasha_subtour.csv
    python3 activity/lib/tasha_estimation/estimate_subtours.py check RUN...                     -> outings per work episode and subtour trips: survey vs runs

Definition (build_distributions.subtours): a work episode at the usual workplace (PW / SW), one or more discretionary episodes
(no home, work or school episode between) and again a PW / SW episode.  The work episode is merged to the end of its last
continuation; the generator schedules the outing inside it.

Components
  1  generation   binary logit (Biogeme) of at least one outing during a merged work episode of a worker with a usual workplace;
                  nested specifications W1..W4 with LR tests and BIC, then backward elimination of the terms with |robust t| <
                  1.96 (the constant and the work-duration terms are kept); hold-out log-likelihood against the constant-only model.
  2  outing mode  binary logit (Biogeme) of walking on the outing against keeping the mode of the work tour (the car stays at the
                  workplace when the person walks); variables: mode of the work tour, distance from the workplace to the first
                  stop (zone skim), workplace density.
  3  distributions of the estimation half: outings per episode given at least one (1, 2+), stops per outing (1, 2, 3), purpose of
                  a stop (shopping, recreation, other, accompany; joint stops taken as individual) by departure band, departure
                  from the workplace (15-min bins), stop duration by purpose (the duration bins of build_distributions.py), the time at
                  work before the departure and after the return (5th percentiles: the minimum work pieces).
  The destination of a stop is not estimated here: the first stop uses the estimated primary MNL of its purpose with the workplace
  in place of home (MarylandDestinationChoice.selectAnchoredZoneMnl), a further stop the sequential stop MNL between the previous
  stop and the workplace.
Variables of the generation model (all known to MAST when the work episode is scheduled):
  sp_0_4, sp_4_7, sp_7_inf  merged work duration in hours, piecewise linear (knots 4, 7)
  arr_early, arr_late, sw   arrival before 7:00, from 10:00 (base 7-10); secondary work episode (arrival from 15:00)
  age_u30, age_55p, female, inc_low (< $50k), inc_high (>= $100k), car0, carshort (fewer cars than licensed drivers), kids (< 16)
  lnacc2   ln(1 + retail and other jobs within 2 km of the workplace, zone skim, intrazonal 0.5 sqrt(area))
  cbd_w    workplace zone with >= 10,000 jobs per km2;  lncomm  ln(1 + home-workplace km)
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, json
import numpy as np
import pandas as pd
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import te_common as T                     # noqa: E402
import dc_common as C                     # noqa: E402
import build_distributions as TD          # noqa: E402
from rts_common import RTS, MODE_MAP      # noqa: E402

A3 = C.A3; BIO = f"{T.WORK}/biogeme_wbs"
STOPT = {"JO_REC": "IO_REC", "JO_OTH": "IO_OTH", "JS": "IS"}
PURP = ["IS", "IO_REC", "IO_OTH", "IO_ACC"]
GEN_STEPS = [("W1", ["const", "sp_0_4", "sp_4_7", "sp_7_inf"], "constant + work duration"),
             ("W2", ["arr_early", "arr_late", "sw"], "+ arrival time"),
             ("W3", ["age_u30", "age_55p", "female", "inc_low", "inc_high", "car0", "carshort", "kids"], "+ person and household"),
             ("W4", ["lnacc2", "cbd_w", "lncomm"], "+ workplace accessibility, commute distance")]
GEN_KEEP = {"const", "sp_0_4", "sp_4_7", "sp_7_inf"}
MODE_STEPS = [("M1", ["const", "tm_cd", "tm_cp"], "constant + work-tour mode"), ("M2", ["lnkm"], "+ ln(1 + km) workplace -> stop"),
              ("M3", ["lnretden_w", "cbd_w"], "+ workplace density")]
MODE_KEEP = {"const", "tm_cd", "tm_cp"}


def zone_tables():
    z = C.zones(); sk = C.skims(); d = sk["d"]
    near = (d <= 2.0).astype(np.float32)
    acc = np.log1p(near @ (z.ret.values + z.oth.values).astype(np.float32))
    return z, d, acc


def data(half):
    """Merged work episodes of workers with a usual workplace (one row each) and the outings (one row each)."""
    f = f"{T.WORK}/wbs_{half}.parquet"; fo = f"{T.WORK}/wbs_out_{half}.parquet"
    if os.path.exists(f) and os.path.exists(fo): return pd.read_parquet(f), pd.read_parquet(fo)
    e = T.episodes(half).sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    e = TD.subtours(e)
    mode = pd.read_csv(f"{RTS}/rts_trips_clean.csv", usecols=["tripid", "travel_mode"]).set_index("tripid").travel_mode.map(MODE_MAP)
    e["mode"] = e.tripid.map(mode)
    # mode of the work tour = mode of the trip to the (first) work episode
    pm = pd.read_csv(f"{A3}/survey_pop/{half}/persons_map.csv"); pp = pd.read_csv(f"{A3}/survey_pop/{half}/pp.csv").set_index("id"); hh = pd.read_csv(f"{A3}/survey_pop/{half}/hh.csv").set_index("id")
    pm = pm.drop_duplicates("person_id").set_index("person_id")
    pid = e.person_id.map(pm.id); hid = pid.map(pp.hhID)
    hp = pp.groupby("hhID").agg(drivers=("driversLicense", lambda x: x.astype(str).eq("True").sum()), minage=("age", "min"), inc=("income", "sum"))
    z, d, acc = zone_tables(); m = C.id2idx()
    w = e[e.type.isin(["PW", "SW"]) & ~e.wbs_cont & e.seg.eq("worker_usual")].copy()
    w["span"] = np.where(w.wbs_n > 0, w.merged_dur, w.dur)
    w = w[w.span.notna() & (w.span > 0) & (w.wz > 0) & (w.hz > 0)].copy()
    ii = pid.loc[w.index]; hi = hid.loc[w.index]
    X = pd.DataFrame(index=w.index)
    h = w.span.values / 60.0
    X["const"] = 1.0; X["sp_0_4"] = np.minimum(h, 4); X["sp_4_7"] = np.clip(h - 4, 0, 3); X["sp_7_inf"] = np.maximum(h - 7, 0)
    X["arr_early"] = (w.arr_min < 420).astype(float); X["arr_late"] = (w.arr_min >= 600).astype(float); X["sw"] = w.type.eq("SW").astype(float)
    age = ii.map(pp.age).values; X["age_u30"] = (age < 30).astype(float); X["age_55p"] = (age >= 55).astype(float)
    X["female"] = ii.map(pp.gender).eq(2).astype(float).values
    inc = hi.map(hp.inc).values; X["inc_low"] = (inc < 50000).astype(float); X["inc_high"] = (inc >= 100000).astype(float)
    cars = hi.map(hh.autos).values; drv = hi.map(hp.drivers).values
    X["car0"] = (cars <= 0).astype(float); X["carshort"] = ((cars > 0) & (cars < drv)).astype(float); X["kids"] = (hi.map(hp.minage).values < 16).astype(float)
    wi = m[w.wz.values]; hz = m[w.hz.values]
    X["lnacc2"] = acc[wi]; X["cbd_w"] = z.cbd.values[wi]; X["lncomm"] = np.log1p(d[hz, wi])
    X["y"] = (w.wbs_n > 0).astype(float).values; X["nsub"] = w.wbs_n.values; X["w"] = w.wttrdfin.values
    X["person_id"] = w.person_id.values; X["arr"] = w.arr_min.values; X["span"] = w.span.values
    # outings: stops between the root (or the previous continuation) and the next continuation
    rows = []
    for r, g in e[e.wbs | e.wbs_cont].groupby("wbs_root"):
        root = e.loc[r]; prev_end = root.arr_min + root.dur if np.isfinite(root.dur) else np.nan; stops = []; prev_z = root.dz
        for k, x in g.iterrows():
            if x.wbs: stops.append(x); continue
            # x = continuation: one outing = stops so far
            if stops:
                s0 = stops[0]
                rows.append(dict(root=r, person_id=root.person_id, half=half, n_stops=len(stops), leave=s0.dep_min, ret=x.arr_min,
                                 before=s0.dep_min - root.arr_min, purposes=";".join(STOPT.get(s.type, s.type) for s in stops),
                                 durs=";".join(str(s.dur) for s in stops), zones=";".join(str(s.dz) for s in stops), wz=root.wz, hz=root.hz,
                                 mode=s0["mode"], w=root.wttrdfin, cont_dur=x.dur, cont_arr=x.arr_min))
            stops = []
    o = pd.DataFrame(rows)
    # work-tour mode: the mode of the trip arriving at the root
    o["tour_mode"] = o.root.map(e["mode"])
    tot = e.groupby("person_id").size()
    w.to_parquet(f"{T.WORK}/wbs_w_{half}.parquet")
    X.to_parquet(f); o.to_parquet(fo)
    return X, o


def biogeme_logit(df, cols, name):
    import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
    from biogeme.expressions import Beta, Variable as Xv
    V1 = sum((Beta(c, 0, None, None, 0) * Xv(c) for c in cols), start=0) if cols else 0
    U = {1: V1, 0: 0}; AV = {1: 1, 0: 1}
    d = db.Database(name, df[cols + ["y"]].astype(float))
    os.makedirs(BIO, exist_ok=True); cwd = os.getcwd(); os.chdir(BIO)
    try:
        m = bio.BIOGEME(d, models.loglogit(U, AV, Xv("y")), save_iterations=False, generate_html=False, generate_yaml=False); m.model_name = name
        r = m.estimate()
    finally: os.chdir(cwd)
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))
    t = t.set_index("Name").reindex(cols)
    return dict(LL=float(r.final_loglikelihood), K=int(r.number_of_free_parameters), N=len(df), table=t, conv=bool(r.algorithm_has_converged))


def ll_of(df, cols, beta):
    v = df[cols].values @ np.array([beta[c] for c in cols]); p = 1 / (1 + np.exp(-v)); y = df.y.values
    return float(np.sum(y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1)))), p


def search(est, val, steps, keep, tag):
    rows = []; cols = []; prev = None
    for name, add, note in steps:
        cols = cols + [c for c in add if c == "const" or est[c].std() > 0]
        r = biogeme_logit(est, cols, f"{tag}_{name}")
        row = dict(model=name, note=note, K=r["K"], N=r["N"], LL=r["LL"], AIC=2 * r["K"] - 2 * r["LL"], BIC=np.log(r["N"]) * r["K"] - 2 * r["LL"])
        if prev is not None:
            st = 2 * (r["LL"] - prev["LL"]); df = r["K"] - prev["K"]; row.update(LR=st, LR_df=df, LR_p=float(chi2.sf(st, df)))
        b = r["table"]["Value"].to_dict(); row["LL_holdout"] = ll_of(val, cols, b)[0]
        rows.append(row); prev = r; prev["cols"] = list(cols)
    full = prev; cols = list(full["cols"]); elim = []
    while True:
        t = full["table"]["Robust t-stat."].drop([c for c in keep if c in full["table"].index]).abs()
        t = t[t < 1.96]
        if len(t) == 0: break
        dvar = t.idxmin(); cols = [c for c in cols if c != dvar]
        r = biogeme_logit(est, cols, f"{tag}_elim_{dvar}"); elim.append(dict(dropped=dvar, t=float(full["table"].loc[dvar, "Robust t-stat."]), LL_before=full["LL"], LL_after=r["LL"])); r["cols"] = cols; full = r
    rc = biogeme_logit(est, ["const"], f"{tag}_const")
    st = 2 * (prev["LL"] - full["LL"]); df = prev["K"] - full["K"]
    b = full["table"]["Value"].to_dict()
    rows.append(dict(model="F", note="final (backward elimination)", K=full["K"], N=full["N"], LL=full["LL"], AIC=2 * full["K"] - 2 * full["LL"],
                     BIC=np.log(full["N"]) * full["K"] - 2 * full["LL"], LR=st, LR_df=df, LR_p=float(chi2.sf(st, df)) if df > 0 else np.nan,
                     LL_holdout=ll_of(val, cols, b)[0], LL_const=rc["LL"], LL_const_holdout=ll_of(val, ["const"], rc["table"]["Value"].to_dict())[0]))
    return pd.DataFrame(rows), full, pd.DataFrame(elim)


def hist(x, w, edges):
    h, _ = np.histogram(x, bins=edges, weights=w); return h / h.sum()


def estimate():
    est, oe = data("estimation"); val, ov = data("validation")
    print(f"work episodes: estimation {len(est):,} ({est.y.mean():.3f} with an outing, weighted {np.average(est.y, weights=est.w):.3f}); "
          f"hold-out {len(val):,} ({val.y.mean():.3f}, weighted {np.average(val.y, weights=val.w):.3f})")
    s, full, el = search(est, val, GEN_STEPS, GEN_KEEP, "wbs_gen")
    s.to_csv(f"{T.RES}/wbs_gen_search.csv", index=False); el.to_csv(f"{T.RES}/wbs_gen_elimination.csv", index=False)
    tab = full["table"].reset_index().rename(columns={"Name": "variable", "Value": "value"}); tab.to_csv(f"{T.RES}/wbs_gen_estimates.csv", index=False)
    print(s.round(2).to_string()); print(tab.round(3).to_string())
    # predicted vs observed shares by group (both halves)
    cols = list(full["cols"]); b = full["table"]["Value"].to_dict(); chk = []
    for half, d in [("estimation", est), ("validation", val)]:
        p = ll_of(d, cols, b)[1]; d = d.assign(p=p, spb=pd.cut(d.span / 60, [0, 4, 7, 9, 24]).astype(str), arrb=pd.cut(d.arr / 60, [0, 7, 8, 9, 10, 24], right=False).astype(str))
        chk.append(dict(half=half, group="all", level="all", N=len(d), obs=np.average(d.y, weights=d.w), pred=np.average(d.p, weights=d.w)))
        for g in ["spb", "arrb", "cbd_w", "female", "age_u30"]:
            for lev, x in d.groupby(g): chk.append(dict(half=half, group=g, level=str(lev), N=len(x), obs=np.average(x.y, weights=x.w), pred=np.average(x.p, weights=x.w)))
    chk = pd.DataFrame(chk); chk.to_csv(f"{T.RES}/wbs_gen_check.csv", index=False); print(chk.round(3).to_string())

    # outing mode: walk vs the mode of the work tour
    z, d, acc = zone_tables(); m = C.id2idx()
    def mdata(o):
        o = o[o.tour_mode.notna() & o["mode"].notna()].copy()
        z1 = o.zones.str.split(";").str[0].astype(int); ok = (z1 > 0) & (o.wz > 0); o = o[ok.values].copy(); z1 = z1[ok.values]
        X = pd.DataFrame({"const": 1.0, "tm_cd": o.tour_mode.eq("CAR_DRIVER").astype(float).values, "tm_cp": o.tour_mode.eq("CAR_PASSENGER").astype(float).values,
                          "lnkm": np.log1p(d[m[o.wz.values], m[z1.values]]), "lnretden_w": z.lnretden.values[m[o.wz.values]], "cbd_w": z.cbd.values[m[o.wz.values]],
                          "y": o["mode"].eq("WALK").astype(float).values, "w": o.w.values})
        return X
    me, mv = mdata(oe), mdata(ov)
    sm_, fm, elm = search(me, mv, MODE_STEPS, MODE_KEEP, "wbs_mode")
    sm_.to_csv(f"{T.RES}/wbs_mode_search.csv", index=False); elm.to_csv(f"{T.RES}/wbs_mode_elimination.csv", index=False)
    tm = fm["table"].reset_index().rename(columns={"Name": "variable", "Value": "value"}); tm.to_csv(f"{T.RES}/wbs_mode_estimates.csv", index=False)
    print(sm_.round(2).to_string()); print(tm.round(3).to_string())

    # distributions (estimation half, trip weights)
    out = [dict(key="gen." + r.variable, value=r.value) for r in tab.itertuples()] + [dict(key="mode." + r.variable, value=r.value) for r in tm.itertuples()]
    y1 = est[est.y > 0]
    out.append(dict(key="n.outings", value=";".join(f"{v:.6g}" for v in hist(np.minimum(y1.nsub, 2), y1.w, [0.5, 1.5, 2.5]))))
    out.append(dict(key="n.stops", value=";".join(f"{v:.6g}" for v in hist(np.minimum(oe.n_stops, 3), oe.w, [0.5, 1.5, 2.5, 3.5]))))
    edges = np.arange(0, 1441, 15); lv = oe.leave.values % 1440
    out.append(dict(key="leave", value=";".join(f"{v:.6g}" for v in hist(lv, oe.w, edges))))
    # purpose of the stops by departure band (before 11, 11-14, from 14)
    sp = oe.assign(p=oe.purposes.str.split(";"), dd=oe.durs.str.split(";")).explode(["p", "dd"])
    sp["dd"] = pd.to_numeric(sp.dd, errors="coerce"); sp["band"] = np.select([sp.leave < 660, sp.leave < 840], ["0", "1"], "2")
    for b_, g in sp.groupby("band"):
        h = g.groupby("p").w.sum().reindex(PURP).fillna(0); out.append(dict(key=f"purpose.{b_}", value=";".join(f"{v:.6g}" for v in h / h.sum())))
    de = np.array(TD.DUR_EDGES, float)
    for p_ in PURP:
        g = sp[sp.p.eq(p_) & sp.dd.notna() & (sp.dd >= 1)]
        if len(g) < 30: g = sp[sp.dd.notna() & (sp.dd >= 1)]
        out.append(dict(key=f"dur.{p_}", value=";".join(f"{v:.6g}" for v in hist(g.dd.values, g.w.values, de))))
    out.append(dict(key="dur.edges", value=";".join(str(int(x)) for x in TD.DUR_EDGES)))
    oo = oe[oe.cont_dur.notna()]
    out.append(dict(key="min.before", value=f"{float(np.percentile(oe.before.dropna(), 5)):.0f}"))
    out.append(dict(key="min.after", value=f"{float(np.percentile(oo.cont_dur, 5)):.0f}"))
    out.append(dict(key="acc.km", value="2"))
    pd.DataFrame(out).to_csv(f"{T.RES}/tasha_subtour.csv", index=False)
    summ = dict(outings_est=len(oe), outings_val=len(ov), stops_mean=float(np.average(oe.n_stops, weights=oe.w)),
                walk_share_est=float(np.average(me.y, weights=me.w)), min_before=out[-3]["value"], min_after=out[-2]["value"])
    json.dump(summ, open(f"{T.RES}/wbs_summary.json", "w"), indent=1); print(summ)


if __name__ == "__main__":
    if sys.argv[1] == "estimate": estimate()
