#!/usr/bin/env python3
"""Validation of ABIT 2024 on the final land-use population (fin24), in the form of Roorda, Miller & Habib (2008) and of
3_abit/temporal_2024 (same measures: temporal_2024/t24common.py, measures.measure).

    python3 activity/validation/report_2024.py measures      per-run measures -> final_2024/data/measures/<form>_s<NN>.pkl, data/run_totals.csv
    python3 activity/validation/report_2024.py report        tables/fin24_*.md|csv, figures/fig_fin24_*.pdf|png, the MATSim input choice
    python3 activity/validation/report_2024.py matsim-csv    rewrites the chosen run's legs/activities CSV (ABIT format) for the MATSim converter

Forms: fin24 (attendance from the set's base-year table), fin24_tw (with the ACS 2024 work-at-home input; the form of the MATSim
input).  Model = mean and s.d. (ddof 1) over the 10 replications (ABIT seeds 1-10) on one SILO population (seed 5).
Observed: ACS 2024 1-year (commute), ATUS 2021-24 Maryland diaries, LODES 2022 OD, NHTS 2017 Baltimore CBSA, RTS 2017/18; the
2017/18 model is the survey-household run of the temporal study (mc_base, tour mode choice; survey-population tour runs are not
affected by the gender recode).  Chain-test comparison: data/abit_roorda_tables.csv (settings *_behav)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import glob, os, pickle, sys
import numpy as np, pandas as pd
V = f"{WORKSPACE}"; A3 = f"{V}/3_abit"; T24 = f"{A3}/temporal_2024"
HERE = f"{A3}/final_2024"; RUN = f"{HERE}/run"; MD = f"{HERE}/data/measures"; TAB = f"{HERE}/tables"; FIG = f"{HERE}/figures"
for d in (MD, TAB, FIG): os.makedirs(d, exist_ok=True)
sys.path.insert(0, f"{MILES_HOME}/activity/lib/reporting_2024"); sys.path.insert(0, f"{MILES_HOME}/reports")
import t24common as C                                      # noqa: E402
from measures import measure                               # noqa: E402
SCH = f"{V}/2_silo/schoolchoice/runs/oos_s5/2024"
FORMS = {"fin24": "Base-year attendance", "fin24_tw": "With 2024 telework input"}
# 2026-11-10 (build_abit.py --single-form): one attendance form; the defaults reproduce the record report
SINGLE = False                                   # labels without the telework form (the caller fills both forms with the same runs and drops the duplicates)
POP_LABEL = "the SILO 2024 population of seed 5"  # population named in the footnotes
ROORDA = ("verification_behav", "validation_behav", "chain_behav")   # survey-based settings of Table F7
MB_SRC = (None, "mc_base", "mc_base_tw")          # (directory, prefix base form, prefix telework form) of the 2017/18 model on the survey households; None = temporal_2024/data/measures
def twl(with_tw="ABIT 2024, with 2024 telework input"): return "ABIT 2024" if SINGLE else with_tw
NUM = ["start_time_min", "end_time", "time_min", "distance_m", "start_zone", "end_zone"]


def legs(run):
    l = pd.read_parquet(f"{RUN}/{run}/output/legs_full.parquet", columns=["person_id", "previous_purpose", "start_time_min", "start_zone", "next_purpose", "end_time", "end_zone", "mode", "time_min", "distance_m"])
    for c in NUM + ["person_id"]: l[c] = pd.to_numeric(l[c])
    return l


def persons():
    f = f"{MD}/persons.parquet"
    if os.path.exists(f): return pd.read_parquet(f)
    r = pd.read_parquet(f"{RUN}/fin24_tw_s01/output/persons.parquet")
    pp = pd.read_csv(f"{SCH}/pp_2024.csv", usecols=["id", "hhid", "age", "occupation"], engine="pyarrow"); pp = pp[pp.id.isin(r.person_id)]
    hz = r.dropna(subset=["home_zone"]).groupby("household_id").home_zone.first()
    P = pd.DataFrame({"pid": pp.id.values, "w": 1.0, "age": pp.age.values, "occ": pp.occupation.values})
    P["county"] = pp.hhid.map(hz).map(C.zone_county()).fillna(-1).astype(int).values; P.to_parquet(f, index=False); return P


def survey_counties():
    return set(pd.read_parquet(f"{T24}/data/rts_persons.parquet").county.unique())


def do_measures():
    P = persons(); sc = survey_counties(); tot = []
    for run in sorted(os.path.basename(d) for d in glob.glob(f"{RUN}/fin24*_s??") if os.path.exists(f"{d}/output/legs_full.parquet")):
        f = f"{MD}/{run}.pkl"; l = legs(run)
        n_p = pd.read_parquet(f"{RUN}/{run}/output/persons.parquet").person_id.nunique()
        assert n_p == len(P), f"{run}: {n_p} persons, s01 {len(P)}"
        A = C.acts_from_legs(l)
        if not os.path.exists(f): pickle.dump(measure(P, A, with_flows=True), open(f, "wb"))
        # extras: totals, trip mode shares, chain-test area (survey counties, persons 5+) rates and distance by type (Roorda types)
        pa = P.set_index("pid"); a5 = A[A.pid.map(pa.age).ge(5) & A.pid.map(pa.county).isin(sc)]
        n5 = int(((P.age >= 5) & P.county.isin(sc)).sum()); md5 = A[A.pid.map(pa.age).ge(5) & (A.pid.map(pa.county) // 1000 == 24)]
        r = dict(run=run, form=run.rsplit("_s", 1)[0], seed=int(run[-2:]), persons=len(P), trips=len(A), person_km=float(A.km.sum()),
                 trips_md5=len(md5), persons_md5=int(((P.age >= 5) & (P.county // 1000 == 24)).sum()), km_md5=float(md5.km.sum()), persons_area5=n5)
        for m, s in md5["mode"].map(C.MODEL_MODE).value_counts(normalize=True).items(): r[f"mode_{m}"] = s
        for t in C.TYPES + ["ALL"]:
            at = a5 if t == "ALL" else a5[a5.type == t]; r[f"area_rate_{t}"] = len(at) / n5; r[f"area_km_{t}"] = float(at.km.mean())
        tot.append(r); print(run, "measured", flush=True)
    pd.DataFrame(tot).to_csv(f"{HERE}/data/run_totals.csv", index=False)


# ------------------------------------------------------------------------------------------------ report helpers
def load(prefix, d=MD):
    fs = sorted(glob.glob(f"{d}/{prefix}_s??.pkl"))
    S, H, F = [], [], []
    for i, f in enumerate(fs):
        s, h, fl = pickle.load(open(f, "rb")); S.append(s.assign(rep=i)); H.append(h.assign(rep=i)); F.append(fl.assign(rep=i))
    ag = lambda x, k: pd.concat(x).groupby(k).value.agg(["mean", "std"]).reset_index()
    return dict(n=len(fs), S=ag(S, ["key", "metric", "type"]), H=ag(H, ["key", "metric", "type", "hour"]), F=ag(F, ["key", "home_unit", "work_unit"]))


def sv(M, key, metric, typ="ALL", col="mean"):
    d = M["S"]; r = d[(d.key == key) & (d.metric == metric) & (d.type == typ)]; return float(r[col].iloc[0]) if len(r) else np.nan


def ov(S, key, metric, typ="ALL"):
    r = S[(S.key == key) & (S.metric == metric) & (S.type == typ)]; return float(r.value.iloc[0]) if len(r) else np.nan


def hs(M, key, metric, typ, col="mean"):
    d = M["H"]; return d[(d.key == key) & (d.metric == metric) & (d.type == typ)].set_index("hour")[col].reindex(range(24))


def ohs(Hd, key, metric, typ):
    return Hd[(Hd.key == key) & (Hd.metric == metric) & (Hd.type == typ)].set_index("hour").value.reindex(range(24))


f1 = lambda v: "–" if not np.isfinite(v) else f"{v:,.1f}"
f2 = lambda v: "–" if not np.isfinite(v) else f"{v:.2f}"
f3 = lambda v: "–" if not np.isfinite(v) else f"{v:.3f}"
sg = lambda v, d=1: "–" if not np.isfinite(v) else f"{v:+.{d}f}"
pct = lambda a, b: 100 * (a - b) / b if b else np.nan
ptxt = lambda p: "P < 0.001" if p < 0.001 else f"P = {p:.3f}"


def mdt(title, cols, rows, notes):
    t = [f"#### {title}", "", "| " + " | ".join(cols) + " |", "|" + "|".join(["---"] + ["---:"] * (len(cols) - 1)) + "|"]
    t += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]; return "\n".join(t + [""] + notes + [""])


def report():
    obs = pickle.load(open(f"{T24}/data/measures/obs.pkl", "rb"))
    mbd = MB_SRC[0] or f"{T24}/data/measures"
    M = {f: load(f) for f in FORMS}; MB = {"fin24": load(MB_SRC[1], mbd), "fin24_tw": load(MB_SRC[2], mbd)}
    tot = pd.read_csv(f"{HERE}/data/run_totals.csv")
    acs = pd.read_csv(f"{T24}/data/acs_commute.csv"); acsH = pd.read_csv(f"{T24}/data/acs_commute_hourly.csv"); acsT = pd.read_csv(f"{T24}/data/acs_commute_tt.csv")
    acsM = pd.read_csv(f"{T24}/data/acs_mode.csv"); acsF = pd.read_csv(f"{T24}/data/acs_flows.csv"); lod = pd.read_csv(f"{T24}/data/lodes2022_flows.csv")
    A = lambda v, metric, col="value": float(acs[(acs.vintage == v) & (acs.area == "Maryland") & (acs.metric == metric)][col].iloc[0])
    S24, H24 = obs["atus_md_2021-2024"][0], obs["atus_md_2021-2024"][1]; S19 = obs["atus_md_2017-2019"][0]; a24 = obs["atus_md_2021-2024_commute"]
    rts, rtsH = obs["rts"][0], obs["rts"][1]; nh = obs["nhts"][0]
    kA, kW, kN, k5 = "Maryland|15+", "Maryland|workers", "Baltimore CBSA|5+", "Maryland|5+"
    nA = int(ov(S24, kA, "persons")); nrep = {f: M[f]["n"] for f in M}; md = []; summ = {}
    REP = f"ᵇ Mean (s.d.) of {nrep['fin24_tw']} replications (ABIT seeds 1–10) on {POP_LABEL}, 10 % household sample."

    # ---- F1 frequency and participation vs ATUS
    rows = []
    for f, lab in FORMS.items():
        m, b = M[f], MB[f]; rows.append([f"*{lab}*"] + [""] * 9)
        for t in C.TYPES + ["ALL"]:
            mv, sd, o = sv(m, kA, "acts_per_person", t), sv(m, kA, "acts_per_person", t, "std"), ov(S24, kA, "acts_per_person", t)
            pm, po = sv(m, kA, "participation", t), ov(S24, kA, "participation", t)
            rows.append([C.TLAB[t], f3(mv), f3(sd), f3(o), sg(pct(mv, o)), f1(100 * pm), f1(100 * po), sg(100 * (pm - po)),
                         sg(pct(mv, sv(b, kA, "acts_per_person", t))), sg(pct(o, ov(S19, kA, "acts_per_person", t)))])
    md.append(mdt("Table F1. Activity frequency and participation comparison, ABIT vs ATUS, 2024 (final land-use population)ᵃ",
                  ["Activity type", "Model activities per personᵇ", "s.d.ᵇ", "Observed ATUS 2021–24", "Model ± %", "Model participation (%)", "Observed participation (%)",
                   "Model ± (pp)", "Increase in model 2017/18–2024 (%)", "Increase in observed 2017–19 to 2021–24 (%)"], rows,
                  [f"ᵃ Maryland residents 15+, weekday (model: Monday). ATUS Maryland weekday diaries, n = {nA}. One activity per trip, at its destination. 2017/18 model: ABIT on the RTS survey households (same form).", REP]))

    # ---- F2 commute vs ACS 2024
    am = acsM[(acsM.vintage == "acs2024") & (acsM.area == "Maryland")].set_index("mode"); oh = acsH[(acsH.vintage == "acs2024") & (acsH.area == "Maryland")].set_index("hour").share.reindex(range(24))
    rows = []; ks_dep = {}
    for f, lab in FORMS.items():
        m = M[f]; rows.append([f"*{lab}*"] + [""] * 6)
        def r(l, metric, typ, o, se, sc=1.0, at=np.nan):
            mv, sd = sv(m, kW, metric, typ) * sc, sv(m, kW, metric, typ, "std") * sc; return [l, f1(mv), f1(sd), f1(o), f1(se) if np.isfinite(se) else "–", sg(mv - o), f1(at)]
        rows += [r("Workers with a work activity on the weekday (%)" + (" (input-driven)" if f == "fin24_tw" else ""), "work_share", "WORK", 100 * A("acs2024", "commuting on the reference day, share of workers"),
                   100 * A("acs2024", "commuting on the reference day, share of workers", "se"), 100, 100 * a24["work_share"]),
                 r("Mean departure from home to work (min after midnight)", "commute_dep_mean", "WORK", A("acs2024", "mean departure time from home"), A("acs2024", "mean departure time from home", "se"), 1, a24["dep_mean"]),
                 r("Departing 6:00–8:59 (% of commuters)", "commute_dep_6_9", "WORK", 100 * A("acs2024", "departing 6:00-8:59, share of commuters"), 100 * A("acs2024", "departing 6:00-8:59, share of commuters", "se"), 100),
                 r("Mean travel time to work (min)", "commute_tt_mean", "WORK", A("acs2024", "mean travel time to work"), A("acs2024", "mean travel time to work", "se"), 1, a24["tt_mean"]),
                 r("Median travel time to work (min)", "commute_tt_median", "WORK", A("acs2024", "median travel time to work"), np.nan)]
        rows += [r(f"Mode to work: {mm.lower()} (%)", "commute_mode", mm, 100 * am.loc[mm, "share"], 100 * am.loc[mm, "se"], 100) for mm in C.COMMUTE_MODES]
        hm = hs(m, kW, "commute_dep_share", "WORK"); nz = (hm > 0) | (oh > 0); ks_dep[f] = C.ks_values(100 * hm[nz], 100 * oh[nz])[:2]
        rows.append(["Departure time distribution, KS (Roorda hourly form)", f"D = {ks_dep[f][0]:.3f}", ptxt(ks_dep[f][1]), "", "", "", ""])
    wfh24 = 1 - A("acs2024", "commuting on the reference day, share of workers")
    md.append(mdt("Table F2. Work activity and commute comparison, ABIT vs ACS 2024 and ATUSᵃ",
                  ["Measure", "Modelᵇ", "s.d.ᵇ", "Observed ACS 2024", "ACS s.e.", "Model ± observed", "Observed ATUS 2021–24 Maryland"], rows,
                  [f"ᵃ Maryland residents employed, 16+. Model: Monday; departure = last trip leaving home before the first work activity; travel time from that departure to the work arrival; mode of the trip arriving at work. "
                   f"ACS 2024: at work last week and not working at home (ACS share not commuting, incl. work at home and absent: {100 * wfh24:.1f} %); a k-person carpool counts 1/k driver. "
                   + ("" if SINGLE else "Rows 'with 2024 telework input': the attendance step reads the ACS 2024 work-at-home share by home county; the work-activity share is then input-driven, not a test."), REP]))

    # ---- F3 own-county share vs ACS and LODES
    cg = C.county_group(); lab = cg.drop_duplicates("unit").set_index("unit").unit_label
    own = lambda f_: (f_[f_.home_unit == f_.work_unit].groupby("home_unit").workers.sum() / f_.groupby("home_unit").workers.sum())
    a24f = acsF[acsF.vintage == "acs2024"]; lo = lod.rename(columns={"jobs": "workers"})
    FM = {f: M[f]["F"].rename(columns={"mean": "workers"}).query("key == 'Maryland|workers'") for f in M}
    sh = pd.DataFrame({"model": own(FM["fin24_tw"]), "model_frozen": own(FM["fin24"]), "acs": own(a24f), "lodes": own(lo)})
    order = [cg.unit[c] for c in [24510, 24005, 24003, 24027, 24025, 24013]]; order += [u for u in sorted(set(cg.unit[cg.index // 1000 == 24])) if u not in order]
    rows = [[lab.get(u, u), f1(100 * sh.model.get(u, np.nan)), f1(100 * sh.model_frozen.get(u, np.nan)), f1(100 * sh.acs.get(u, np.nan)), f1(100 * sh.lodes.get(u, np.nan))] for u in order]
    allmd = lambda f_: 100 * float(f_[f_.home_unit == f_.work_unit].workers.sum() / f_.workers.sum()); outst = lambda f_: 100 * float(f_[f_.work_unit // 100000 != 24].workers.sum() / f_.workers.sum())
    rows.append(["Maryland, all residents", f1(allmd(FM["fin24_tw"])), f1(allmd(FM["fin24"])), f1(allmd(a24f)), f1(allmd(lo))])
    rows.append(["Maryland residents working outside Maryland (%)", f1(outst(FM["fin24_tw"])), f1(outst(FM["fin24"])), f1(outst(a24f)), f1(outst(lo))])
    shr = lambda f_: (lambda s: s / s.sum())(f_.groupby(["home_unit", "work_unit"]).workers.sum())
    fit = {}
    for nm, f_ in [("model", FM["fin24_tw"]), ("ACS 2024", a24f)]:
        a, b = shr(f_).align(shr(lo), fill_value=0); fit[nm] = (float(np.corrcoef(a, b)[0, 1]), float(0.5 * np.abs(a - b).sum()))
    md.append(mdt("Table F3. Own-county work share comparison, ABIT vs ACS 2024 and LODES 2022ᵃ",
                  ["Home county (place-of-work area)", "Model, with 2024 telework input (%)ᵇ", "Model, base-year attendance (%)ᵇ", "Observed ACS 2024 (%)", "Observed LODES 2022 (%)"], rows,
                  ["ᵃ Share of workers with a work activity (model, Monday) or of commuters (ACS) / jobs (LODES JT00) of each home area working in the same area. "
                   f"Flow-matrix agreement with LODES (unit pairs): model r = {fit['model'][0]:.3f}, total absolute deviation {fit['model'][1]:.3f}; ACS 2024 r = {fit['ACS 2024'][0]:.3f}, TAD {fit['ACS 2024'][1]:.3f}.", REP]))

    # ---- F4 start time and duration KS vs ATUS, mean durations
    rows = []; ksS = {}
    for f, lab_ in FORMS.items():
        m = M[f]; rows.append([f"*{lab_}*"] + [""] * 7)
        for t in C.TYPES:
            mh, oh_ = 100 * hs(m, kA, "start_share", t).fillna(0), 100 * ohs(H24, kA, "start_share", t).fillna(0); nz = (mh > 0) | (oh_ > 0); d, p, _ = C.ks_values(mh[nz], oh_[nz])
            nn = ohs(H24, kA, "dur_n", t).fillna(0); md_ = hs(m, kA, "dur_mean", t); od_ = ohs(H24, kA, "dur_mean", t).where(nn >= 10); both = md_.notna() & od_.notna()
            dd, pd_ = C.ks_values(md_[both], od_[both])[:2] if both.sum() >= 3 else (np.nan, np.nan); ksS[(f, t)] = (d, p, dd, pd_)
            rows.append([C.TLAB[t], f"{d:.3f}", ptxt(p), "–" if not np.isfinite(dd) else f"{dd:.3f}", "–" if not np.isfinite(pd_) else ptxt(pd_),
                         f1(sv(m, kA, "mean_dur", t)), f1(sv(m, kA, "mean_dur", t, "std")), f1(ov(S24, kA, "mean_dur", t))])
    md.append(mdt("Table F4. Kolmogorov–Smirnov tests of start time and duration by start hour, and mean durations, ABIT vs ATUS 2021–24 Marylandᵃ",
                  ["Activity type", "Start time D", "Start time P", "Duration D", "Duration P", "Model mean duration (min)ᵇ", "s.d.ᵇ", "Observed mean duration (min)"], rows,
                  [f"ᵃ Maryland residents 15+. KS in Roorda et al.'s form on the hourly values (start: hourly shares; duration: hourly mean duration at hours with ≥ 10 diary activities). ATUS n = {nA} diaries; "
                   "ATUS 'return home' and 'other' are reconstructed from stays and are not defined as in a trip diary.", REP]))

    # ---- F5 chains and distance by purpose (Baltimore CBSA 5+) vs RTS, NHTS 2017, 2017/18 model
    m, b = M["fin24_tw"], MB["fin24_tw"]; rows = []
    for t in C.TYPES + ["ALL"]:
        rows.append([f"{C.TLAB[t]}: activities per person", f3(sv(m, kN, "acts_per_person", t)), f3(sv(m, kN, "acts_per_person", t, "std")), f3(sv(M["fin24"], kN, "acts_per_person", t)),
                     f3(sv(b, kN, "acts_per_person", t)), f3(ov(rts, kN, "acts_per_person", t)), f3(ov(nh, kN, "acts_per_person", t))])
    for t in C.TYPES + ["ALL"]:
        rows.append([f"{C.TLAB[t]}: average distance (km)", f2(sv(m, kN, "mean_km", t)), f2(sv(m, kN, "mean_km", t, "std")), f2(sv(M["fin24"], kN, "mean_km", t)),
                     f2(sv(b, kN, "mean_km", t)), f2(ov(rts, kN, "mean_km", t)), f2(ov(nh, kN, "mean_km", t))])
    rows.append(["Trips per home-based chain", f2(sv(m, kN, "trips_per_chain")), f2(sv(m, kN, "trips_per_chain", "ALL", "std")), f2(sv(M["fin24"], kN, "trips_per_chain")),
                 f2(sv(b, kN, "trips_per_chain")), f2(ov(rts, kN, "trips_per_chain")), f2(ov(nh, kN, "trips_per_chain"))])
    for i in range(2, 7):
        lab_ = f"{i}" if i < 6 else "6+"; g = lambda Hd, mod=True: (hs(Hd, kN, "chain_share", "ALL")[i:].sum() if mod else ohs(Hd, kN, "chain_share", "ALL")[i:].sum()) if i == 6 else \
            (hs(Hd, kN, "chain_share", "ALL")[i] if mod else ohs(Hd, kN, "chain_share", "ALL")[i])
        rows.append([f"Chains with {lab_} trips (%)", f1(100 * g(m)), "", f1(100 * g(M["fin24"])), f1(100 * g(b)), f1(100 * g(rtsH, False)), f1(100 * g(obs["nhts"][1], False))])
    md.append(mdt("Table F5. Activity frequency, distance by purpose and trips per chain, Baltimore metropolitan area, ABIT 2024 vs RTS 2017/18 and NHTS 2017ᵃ",
                  ["Measure", "Model 2024, with telework inputᵇ", "s.d.ᵇ", "Model 2024, base-year attendanceᵇ", "Model 2017/18 (survey households)", "Observed RTS 2017/18", "Observed NHTS 2017"], rows,
                  ["ᵃ Residents of the Baltimore–Columbia–Towson CBSA aged 5+, weekdays. No diary of 2024 exists for the area; the surveys are of the base period. Distances: model zone-to-zone car skim; surveys reported trip distance (≤ 300 km).", REP]))

    # ---- F6 trip mode shares (all trips, Maryland 5+)
    modes = ["Car, driver", "Car, passenger", "Bus", "Rail", "Walk", "Bicycle", "Other"]
    rk = pd.read_parquet(f"{T24}/data/rts_persons.parquet"); ra = pd.read_parquet(f"{T24}/data/rts_acts.parquet")
    rp = rk[(rk.age >= 5) & (rk.county // 1000 == 24)]; pidmap = dict(zip(rp.person_id, rp.w))
    rs = ra[ra.pid.isin(rp.person_id)]; rs = rs.assign(w=rs.pid.map(pidmap)); rshare = rs.groupby("mode").w.sum() / rs.w.sum()
    rows = []
    for mm in modes:
        c = f"mode_{mm}"; x = {f: tot[tot.form == f][c] if c in tot else pd.Series([0.0]) for f in FORMS}
        rows.append([mm, f1(100 * x["fin24_tw"].mean()), f2(100 * x["fin24_tw"].std()), f1(100 * x["fin24"].mean()), f1(100 * rshare.get(mm, 0.0))])
    md.append(mdt("Table F6. Trip mode shares, all weekday trips of Maryland residents 5+, ABIT 2024 vs RTS 2017/18ᵃ",
                  ["Mode", "Model 2024, with telework input (%)ᵇ", "s.d.ᵇ", "Model 2024, base-year attendance (%)ᵇ", "Observed RTS 2017/18 (%)"], rows,
                  ["ᵃ Tour mode choice (estimated, behavioural, USDOT value of time). RTS: survey trips of Maryland survey households, person weights. The ACS commute shares are in Table F2.", REP]))

    # ---- F7 chain-test comparison with the survey-population runs (Roorda R1–R3, behavioural model of record)
    R = pd.read_csv(f"{V}/data/abit_roorda_tables.csv"); R = R[(R.variant == "base") & R.setting.isin(list(ROORDA))]
    R = R.assign(rate=R.model_total / R.persons, orate=R.observed_total / R.persons)
    rows = []
    for t in C.TYPES + ["ALL"]:
        g = lambda s, c: float(R[(R.setting == s) & (R.type == t)][c].iloc[0])
        x = tot[tot.form == "fin24_tw"]
        vs, vl, ch = ROORDA
        rows.append([C.TLAB[t], f3(g(vs, "rate")), f3(g(vl, "rate")), f3(g(ch, "rate")), f3(x[f"area_rate_{t}"].mean()), f3(g(vl, "orate")),
                     f2(g(vs, "model_km")), f2(g(vl, "model_km")), f2(g(ch, "model_km")), f2(x[f"area_km_{t}"].mean()), f2(g(vl, "observed_km_zone_skim"))])
    md.append(mdt("Table F7. Chain-test comparison: activities per person and average distance by type, survey-population runs (verification, validation), 2016 synthetic population (chain test) and the 2024 final populationᵃ",
                  ["Activity type", "Verification (est. half)", "Validation (val. half)", "Chain test 2016", "2024 final population, with telework inputᵇ", "Observed RTS (val. half)",
                   "Verification km", "Validation km", "Chain test km", "2024 km", "Observed km (zone skim, val. half)"], rows,
                  ["ᵃ Persons 5+ living in the counties of the survey households; weekday. Verification/validation/chain: behavioural model of record, 10 replications each (data/abit_roorda_tables.csv, base exclusion rule). "
                   "Distances: zone-to-zone car skim on both sides. The 2024 column differs from the chain test by the population (SILO 2024 after the schools step), the land use and the 2024 attendance input.", REP]))

    # ---- F8 replications and the MATSim input
    x = tot[tot.form == "fin24_tw"].copy(); mT, mK = x.trips.median(), x.person_km.median()
    x["dist"] = np.sqrt(((x.trips - mT) / mT) ** 2 + ((x.person_km - mK) / mK) ** 2); pick = x.loc[x.dist.idxmin()]
    rows = [[r.run, f"{int(r.trips):,}", f"{r.person_km:,.0f}", sg(pct(r.trips, mT), 3), sg(pct(r.person_km, mK), 3), f"{r.dist:.5f}" + (" ← chosen" if r.run == pick.run else "")] for r in x.itertuples()]
    y = tot[tot.form == "fin24"]
    md.append(mdt("Table F8. Replications (with 2024 telework input): total weekday trips and person-km, and the MATSim input runᵃ",
                  ["Run", "Trips", "Person-km", "Trips vs median (%)", "Person-km vs median (%)", "Distance to the median"], rows,
                  [f"ᵃ All persons of the 10 % sample (the model area), Monday. Median {mT:,.0f} trips, {mK:,.0f} person-km; mean {x.trips.mean():,.0f} ± {x.trips.std():,.0f} trips, "
                   f"{x.person_km.mean():,.0f} ± {x.person_km.std():,.0f} person-km (coefficient of variation {100 * x.trips.std() / x.trips.mean():.2f} % and {100 * x.person_km.std() / x.person_km.mean():.2f} %). "
                   f"Base-year attendance form: {y.trips.mean():,.0f} ± {y.trips.std():,.0f} trips, {y.person_km.mean():,.0f} ± {y.person_km.std():,.0f} person-km. "
                   "Chosen = smallest Euclidean distance of the relative deviations from the median in trips and person-km."]))
    pd.DataFrame([dict(run=pick.run, trips=pick.trips, person_km=pick.person_km, median_trips=mT, median_person_km=mK, distance=pick.dist,
                       legs_parquet=f"{RUN}/{pick.run}/output/legs_full.parquet", activities_parquet=f"{RUN}/{pick.run}/output/activities_full.parquet")]).to_csv(f"{HERE}/matsim_input_choice.csv", index=False)
    open(f"{TAB}/fin24_tables.md", "w").write("\n\n".join(md))
    summ = dict(ks_dep=ks_dep, ks_start_dur=ksS, flow_fit=fit, pick=pick.run, nrep=nrep); pickle.dump(summ, open(f"{TAB}/fin24_summary.pkl", "wb"))
    figures(M, MB, obs, oh, acsT, am, sh, order, lab, ksS, ks_dep, nA)
    print("chosen MATSim input:", pick.run)


def figures(M, MB, obs, oh, acsT, am, sh, order, lab, ksS, ks_dep, nA):
    import paperstyle as ps; import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    H24 = obs["atus_md_2021-2024"][1]; kA, kW, kN = "Maryland|15+", "Maryland|workers", "Baltimore CBSA|5+"; HO = list(range(4, 24)) + list(range(0, 4)); x = np.arange(24)
    m, mf = M["fin24_tw"], M["fin24"]; MLAB = twl() + " (mean, ±2 s.d.)"; FLAB = "ABIT 2024, base-year attendance"
    TT = {"WORK": "Work activities", "SCHOOL": "School activities", "SHOPPING": "Shopping activities", "OTHER": "Other activities", "HOME": "Return home activities"}

    def bars(ax, mv, sd, o, o_lab=None, w=0.4, xx=x):
        ax.bar(xx - w / 2, mv, w, color=ps.MODEL, yerr=2 * sd, error_kw=dict(lw=0.6, ecolor=ps.INK)); ax.bar(xx + w / 2, o, w, color=ps.OBSERVED)
    # start time
    ps.use(); fig = ps.new_figure(6.6); gs = fig.add_gridspec(3, 2); pos = {"WORK": gs[0, 0], "SHOPPING": gs[1, 0], "OTHER": gs[2, 0], "SCHOOL": gs[0:2, 1], "HOME": gs[2, 1]}
    for t in C.TYPES:
        ax = fig.add_subplot(pos[t]); mv = 100 * hs(m, kA, "start_share", t).fillna(0).loc[HO].values; sd = 100 * hs(m, kA, "start_share", t, "std").fillna(0).loc[HO].values
        o = 100 * ohs(H24, kA, "start_share", t).fillna(0).loc[HO].values; bars(ax, mv, sd, o)
        d, p = ksS[("fin24_tw", t)][:2]; ax.text(0.97, 0.95, f"KS D = {d:.3f}, {ptxt(p)}", transform=ax.transAxes, ha="right", va="top", fontsize=ps.FONT)
        ax.set_xticks(x[::3]); ax.set_xticklabels([str(h) for h in HO[::3]]); ax.set_ylim(0, max(mv.max(), o.max()) * 1.3); ax.set_title(TT[t], fontsize=ps.FONT, fontweight="bold")
        ax.set_xlabel("Activity start time (hh)"); ax.set_ylabel("% of 24 h frequency"); ax.grid(axis="x", visible=False)
    fig.legend(handles=[Patch(facecolor=ps.MODEL, label=MLAB), Patch(facecolor=ps.OBSERVED, label=f"ATUS 2021–2024, Maryland ({nA} diaries)")], loc="outside upper center", ncol=1)
    ps.finish(fig, f"{FIG}/fig_fin24_start")
    # duration by start hour
    ps.use(); fig = ps.new_figure(5.0); gs = fig.add_gridspec(2, 2); xh = np.arange(24) + 4.5
    for i, t in enumerate(["WORK", "SCHOOL", "SHOPPING", "OTHER"]):
        ax = fig.add_subplot(gs[i // 2, i % 2]); mv = hs(m, kA, "dur_mean", t).loc[HO].values; sd = hs(m, kA, "dur_mean", t, "std").loc[HO].values
        nn = ohs(H24, kA, "dur_n", t).fillna(0).loc[HO].values; o = np.where(nn >= 10, ohs(H24, kA, "dur_mean", t).loc[HO].values, np.nan)
        ax.fill_between(xh, mv - 2 * sd, mv + 2 * sd, color=ps.SEED_BAND, lw=0); ax.plot(xh, mv, color=ps.MODEL, lw=1.4); ax.plot(xh, o, color=ps.OBSERVED, lw=1.4, ls=(0, (5, 2.5)), marker="o", ms=2.5)
        dd, pd_ = ksS[("fin24_tw", t)][2:]
        if np.isfinite(dd): ax.text(0.97, 0.95, f"KS D = {dd:.3f}, {ptxt(pd_)}", transform=ax.transAxes, ha="right", va="top", fontsize=ps.FONT)
        ax.set_xlim(4, 28); ax.set_xticks(range(4, 29, 4)); ax.set_xticklabels([str(h % 24) for h in range(4, 29, 4)]); ax.set_ylim(0, np.nanmax(np.r_[mv, o]) * 1.35)
        ax.set_title(TT[t], fontsize=ps.FONT, fontweight="bold"); ax.set_xlabel("Activity start time (hh)"); ax.set_ylabel("Duration (minutes)"); ax.grid(axis="x", visible=False)
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], color=ps.MODEL, lw=1.4, label=MLAB), Line2D([], [], color=ps.OBSERVED, lw=1.4, ls=(0, (5, 2.5)), marker="o", ms=2.5, label=f"ATUS 2021–2024, Maryland ({nA} diaries)")],
               loc="outside upper center", ncol=1)
    ps.finish(fig, f"{FIG}/fig_fin24_duration")
    # commute: departure, travel time, mode
    ps.use(); fig = ps.new_figure(6.0); gs = fig.add_gridspec(3, 1)
    ax = fig.add_subplot(gs[0]); mv = 100 * hs(m, kW, "commute_dep_share", "WORK").fillna(0).values; sd = 100 * hs(m, kW, "commute_dep_share", "WORK", "std").fillna(0).values
    bars(ax, mv, sd, 100 * oh.fillna(0).values); ax.set_xticks(x[::2]); ax.set_xlabel("Departure from home to work (hour)"); ax.set_ylabel("% of commuters")
    ax.text(0.97, 0.95, f"KS D = {ks_dep['fin24_tw'][0]:.3f}, {ptxt(ks_dep['fin24_tw'][1])}", transform=ax.transAxes, ha="right", va="top", fontsize=ps.FONT); ax.grid(axis="x", visible=False)
    ax = fig.add_subplot(gs[1]); ot = acsT[(acsT.vintage == "acs2024") & (acsT.area == "Maryland")].set_index("bin").share.reindex(C.TT_LABELS).fillna(0).values if "bin" in acsT else None
    mt = np.array([sv(m, kW, "commute_tt_share", l) if False else float(m["H"].query("key == @kW and metric == 'commute_tt_share' and type == @l")["mean"].iloc[0]) for l in C.TT_LABELS])
    st = np.array([float(m["H"].query("key == @kW and metric == 'commute_tt_share' and type == @l")["std"].iloc[0]) for l in C.TT_LABELS]); xt = np.arange(len(C.TT_LABELS))
    if ot is None: ot = acs_tt_shares(acsT)
    bars(ax, 100 * mt, 100 * st, 100 * ot, xx=xt); ax.set_xticks(xt); ax.set_xticklabels(C.TT_LABELS); ax.set_xlabel("Travel time to work (min)"); ax.set_ylabel("% of commuters"); ax.grid(axis="x", visible=False)
    ax = fig.add_subplot(gs[2]); xm = np.arange(len(C.COMMUTE_MODES))
    bars(ax, np.array([100 * sv(m, kW, "commute_mode", mm) for mm in C.COMMUTE_MODES]), np.array([100 * sv(m, kW, "commute_mode", mm, "std") for mm in C.COMMUTE_MODES]),
         np.array([100 * am.loc[mm, "share"] for mm in C.COMMUTE_MODES]), xx=xm)
    ax.set_xticks(xm); ax.set_xticklabels(C.COMMUTE_MODES); ax.set_ylabel("% of commuters"); ax.set_xlabel("Mode to work"); ax.grid(axis="x", visible=False)
    fig.legend(handles=[Patch(facecolor=ps.MODEL, label=MLAB), Patch(facecolor=ps.OBSERVED, label="ACS 2024, Maryland commuters")], loc="outside upper center", ncol=1)
    ps.finish(fig, f"{FIG}/fig_fin24_commute")
    # chains and distance by purpose
    ps.use(); fig = ps.new_figure(4.4); gs = fig.add_gridspec(2, 1); rtsH, nhH = obs["rts"][1], obs["nhts"][1]
    ax = fig.add_subplot(gs[0]); xc = np.arange(1, 9); w = 0.27
    ax.bar(xc - w, 100 * hs(m, kN, "chain_share", "ALL").reindex(range(1, 9)).values, w, color=ps.MODEL, yerr=200 * hs(m, kN, "chain_share", "ALL", "std").reindex(range(1, 9)).values, error_kw=dict(lw=0.6))
    ax.bar(xc, 100 * ohs(rtsH, kN, "chain_share", "ALL").reindex(range(1, 9)).values, w, color=ps.OBSERVED); ax.bar(xc + w, 100 * ohs(nhH, kN, "chain_share", "ALL").reindex(range(1, 9)).values, w, color="#b5b3ab")
    ax.set_xticks(xc); ax.set_xticklabels([str(i) for i in range(1, 8)] + ["8+"]); ax.set_xlabel("Trips per home-based chain"); ax.set_ylabel("Share of chains (%)"); ax.grid(axis="x", visible=False)
    ax = fig.add_subplot(gs[1]); xt = np.arange(6); T6 = C.TYPES + ["ALL"]
    ax.bar(xt - w, [sv(m, kN, "mean_km", t) for t in T6], w, color=ps.MODEL, yerr=[2 * sv(m, kN, "mean_km", t, "std") for t in T6], error_kw=dict(lw=0.6))
    ax.bar(xt, [ov(obs["rts"][0], kN, "mean_km", t) for t in T6], w, color=ps.OBSERVED); ax.bar(xt + w, [ov(obs["nhts"][0], kN, "mean_km", t) for t in T6], w, color="#b5b3ab")
    ax.set_xticks(xt); ax.set_xticklabels([C.TLAB[t] for t in T6]); ax.set_ylabel("Average distance (km)"); ax.grid(axis="x", visible=False)
    fig.legend(handles=[Patch(facecolor=ps.MODEL, label=twl() + " (Baltimore CBSA, 5+)"), Patch(facecolor=ps.OBSERVED, label="RTS 2017/18"), Patch(facecolor="#b5b3ab", label="NHTS 2017")],
               loc="outside upper center", ncol=1)
    ps.finish(fig, f"{FIG}/fig_fin24_chains_distance")
    # own-county share (horizontal bars)
    short = lambda s: s if s.count("+") < 2 else f"{s.split(' + ')[0]} + {s.count('+')} more"
    ps.use(); fig = ps.new_figure(4.6); ax = fig.add_subplot(111); yo = np.arange(len(order))[::-1]; w = 0.27
    ax.barh(yo + w, [100 * sh.model.get(u, np.nan) for u in order], w, color=ps.MODEL); ax.barh(yo, [100 * sh.acs.get(u, np.nan) for u in order], w, color=ps.OBSERVED)
    ax.barh(yo - w, [100 * sh.lodes.get(u, np.nan) for u in order], w, color="#b5b3ab"); ax.set_yticks(yo); ax.set_yticklabels([short(str(lab.get(u, u))) for u in order])
    ax.set_xlabel("Workers employed in home area (%)"); ax.grid(axis="y", visible=False)
    fig.legend(handles=[Patch(facecolor=ps.MODEL, label=twl()), Patch(facecolor=ps.OBSERVED, label="ACS 2024"), Patch(facecolor="#b5b3ab", label="LODES 2022")], loc="outside upper center", ncol=3)
    ps.finish(fig, f"{FIG}/fig_fin24_ownshare")


def acs_tt_shares(acsT):
    d = acsT[(acsT.vintage == "acs2024") & (acsT.area == "Maryland")]; c = [c for c in d.columns if c not in ("vintage", "area")]
    lab = [c_ for c_ in c if d[c_].dtype == object][0]; val = [c_ for c_ in c if c_ in ("share", "value")][0]
    return d.set_index(lab)[val].reindex(C.TT_LABELS).fillna(0).values


def matsim_csv():
    import pyarrow.parquet as pq, pyarrow.csv as pc
    run = pd.read_csv(f"{HERE}/matsim_input_choice.csv").run.iloc[0]; o = f"{RUN}/{run}/output"
    for k in ["legs", "activities"]:
        out = f"{o}/{k}_{run}.csv"
        if not os.path.exists(out): pc.write_csv(pq.read_table(f"{o}/{k}_full.parquet"), out, pc.WriteOptions(quoting_style="none"))
        print("wrote", out)


if __name__ == "__main__":
    {"measures": do_measures, "report": report, "matsim-csv": matsim_csv}[sys.argv[1]]()
