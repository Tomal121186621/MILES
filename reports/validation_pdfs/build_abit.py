#!/usr/bin/env python3
"""Validation of the activity model (stage 3, ABIT), in the structure of Roorda, Miller and Habib's validation of TASHA.

    python3 reports/validation_pdfs/build_abit.py [--runs RUN ...] [--chosen RUN] [--run-dir DIR] [--verification SET] [--validation SET] [--chain SET]
                          [--survey-runs PREFIX] [--two-forms --runs-base RUN ...] [--out PDF] [--work DIR]

Defaults: the final runs of the re-specified model (3_abit/final_2024/run_respec, fin24_s01 ... s10, one attendance form, settings
verification_respec / validation_respec / chain_respec, survey-household runs svy_respec, work directory work/abit_respec).
The earlier two-form build stays reachable:  --two-forms --run-dir 3_abit/final_2024/run --runs fin24_tw_s01 ... --runs-base fin24_s01 ...
    --verification verification_sched --validation validation_sched --chain chain_behav --survey-runs "" --work work/abit

--runs        replication runs of the 2024 population (folders of --run-dir)
--runs-base   (two forms only) replication runs with the base-year attendance
--chosen      the replication given to the assignment stage (default: the smallest sum of squared relative deviations from the mean of the
              replications in <run-dir>/matsim_input_choice.csv; without that file the one closest to the median in trips and person-km)
--verification, --validation, --chain
              names of the survey-based settings in data/abit_roorda_*.csv (survey households of the estimation half, of the held-out half,
              and the synthetic 2016 population)
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, glob, os, pickle, re, shutil, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("--runs", nargs="+", default=[f"fin24_s{i:02d}" for i in range(1, 11)])
ap.add_argument("--runs-base", nargs="+", default=None)
ap.add_argument("--chosen", default=None)
ap.add_argument("--run-dir", default=f"{V}/3_abit/final_2024/run_respec")
ap.add_argument("--verification", default="verification_respec")
ap.add_argument("--validation", default="validation_respec")
ap.add_argument("--chain", default="chain_respec")
ap.add_argument("--reuse", action="store_true", help="reuse the tables and figures of the work directory")
ap.add_argument("--single-form", action="store_true", default=True, help="one attendance form (the base year, no telework input): the replications of --runs only (default)")
ap.add_argument("--two-forms", dest="single_form", action="store_false", help="the earlier build with the telework form (--runs) and the base-year form (--runs-base)")
ap.add_argument("--pop-label", default="the 2024 SILO population", help="population named in the table footnotes (single form)")
ap.add_argument("--survey-runs", default="svy_respec", help="prefix of the survey-household runs of the 2017/18 comparison columns (run_survey/<prefix>_est_sNN, _val_sNN; single form); empty for none")
ap.add_argument("--chosen-rule", default=None, help="sentence describing the rule that picked --chosen (single form)")
ap.add_argument("--out", default=f"{OUTDIR}/abit_validation.pdf")
ap.add_argument("--work", default=f"{OUTDIR}/work/abit_respec")
a = ap.parse_args()
if a.runs_base is None: a.runs_base = list(a.runs) if a.single_form else [f"fin24_s{i:02d}" for i in range(1, 11)]
if not a.survey_runs: a.survey_runs = None
WORK = os.path.abspath(a.work); FIG = f"{WORK}/fig"; MDIR = f"{WORK}/measures"; TABD = f"{WORK}/tables"
for d in (FIG, MDIR, TABD, f"{WORK}/data", f"{FIG}/_copy"): os.makedirs(d, exist_ok=True)
sys.path.insert(0, f"{MILES_HOME}/activity/validation"); sys.path.insert(0, f"{MILES_HOME}/activity/lib/reporting_2024")
import paperstyle as ps
import report_2024 as fr
import tasha_stage3 as ts
OLD_MD = fr.MD
fr.RUN = os.path.abspath(a.run_dir); fr.HERE = WORK; fr.TAB = TABD; fr.FIG = FIG; fr.MD = MDIR
fr.load.__defaults__ = (MDIR,)
ts.OUT = FIG; ts.PAPERFIG = f"{FIG}/_copy"; ts.TABDIR = f"{WORK}/_t"
C = fr.C

# ------------------------------------------------------------------ per-run measures (cached by file time)
if os.path.exists(f"{OLD_MD}/persons.parquet") and not os.path.exists(f"{MDIR}/persons.parquet"): shutil.copy(f"{OLD_MD}/persons.parquet", f"{MDIR}/persons.parquet")
P = fr.persons(); sc = fr.survey_counties(); tot = []
for form, runs in ([("fin24", a.runs)] if a.single_form else [("fin24_tw", a.runs), ("fin24", a.runs_base)]):
    for i, run in enumerate(runs, 1):
        name = f"{form}_s{i:02d}"; lf = f"{fr.RUN}/{run}/output/legs_full.parquet"; pk = f"{MDIR}/{name}.pkl"; tf = f"{MDIR}/{name}_totals.pkl"
        old = f"{OLD_MD}/{name}.pkl"
        fresh = lambda f: os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(lf)
        if not fresh(pk) and run == name and fresh(old): shutil.copy(old, pk)
        if fresh(pk) and fresh(tf): tot.append(pickle.load(open(tf, "rb"))); continue
        l = fr.legs(run); n_p = pd.read_parquet(f"{fr.RUN}/{run}/output/persons.parquet").person_id.nunique()
        assert n_p == len(P), f"{run}: {n_p} persons, expected {len(P)}"
        A = C.acts_from_legs(l); pickle.dump(fr.measure(P, A, with_flows=True), open(pk, "wb"))
        pa = P.set_index("pid"); a5 = A[A.pid.map(pa.age).ge(5) & A.pid.map(pa.county).isin(sc)]
        n5 = int(((P.age >= 5) & P.county.isin(sc)).sum()); md5 = A[A.pid.map(pa.age).ge(5) & (A.pid.map(pa.county) // 1000 == 24)]
        r = dict(run=name, source=run, form=form, seed=i, persons=len(P), trips=len(A), person_km=float(A.km.sum()), trips_md5=len(md5), persons_md5=int(((P.age >= 5) & (P.county // 1000 == 24)).sum()),
                 km_md5=float(md5.km.sum()), persons_area5=n5)
        for m, s in md5["mode"].map(C.MODEL_MODE).value_counts(normalize=True).items(): r[f"mode_{m}"] = s
        for t in C.TYPES + ["ALL"]:
            at = a5 if t == "ALL" else a5[a5.type == t]; r[f"area_rate_{t}"] = len(at) / n5; r[f"area_km_{t}"] = float(at.km.mean())
        pickle.dump(r, open(tf, "wb")); tot.append(r); print("measured", run, flush=True)
TOT = pd.DataFrame(tot); TOT.to_csv(f"{WORK}/data/run_totals.csv", index=False)
if a.single_form:
    # one attendance form: the report code expects two; the second is filled with the same measures (internal) and every duplicated
    # column / block is removed from the tables below; the 2017/18 columns come from the survey-household runs of the same model
    for i in range(1, len(a.runs) + 1): shutil.copy(f"{MDIR}/fin24_s{i:02d}.pkl", f"{MDIR}/fin24_tw_s{i:02d}.pkl")
    TOT = pd.concat([TOT, TOT.assign(form="fin24_tw")], ignore_index=True); TOT.to_csv(f"{WORK}/data/run_totals.csv", index=False)
    fr.SINGLE = True; fr.POP_LABEL = a.pop_label; fr.ROORDA = (a.verification, a.validation, a.chain)
    if a.survey_runs:
        sys.path.insert(0, f"{MILES_HOME}/activity/lib/reporting_2024"); import measures as TM
        PB = TM.persons("rts")
        for s_ in range(1, 11):
            pk = f"{MDIR}/mcb_s{s_:02d}.pkl"
            if os.path.exists(pk): continue
            parts = []
            for h, off in [("est", 0), ("val", 100_000_000)]:
                nm = f"{a.survey_runs.replace('svy_', f'svy_{h}_')}_s{s_:02d}"
                l = pd.read_csv(f"{V}/3_abit/run_survey/{nm}/output/legs_{nm}.csv", usecols=["person_id", "previous_purpose", "start_time_min", "start_zone", "next_purpose", "end_time", "end_zone", "mode", "time_min", "distance_m"])
                ac = C.acts_from_legs(l); ac["pid"] += off; parts.append(ac)
            pickle.dump(fr.measure(PB, pd.concat(parts, ignore_index=True), with_flows=True), open(pk, "wb")); print("measured survey households", s_, flush=True)
        fr.MB_SRC = (MDIR, "mcb", "mcb")
if not (a.reuse and os.path.exists(f"{TABD}/fin24_tables.md")): fr.report()                                           # tables (markdown), figures, chosen replication -> work directory
md = open(f"{TABD}/fin24_tables.md").read()
if a.single_form:
    def drop_cols(blk, names):
        L = blk.split("\n"); hi = next(i for i, l in enumerate(L) if l.startswith("|")); hdr = [c.strip() for c in L[hi].strip().strip("|").split("|")]
        idx = [k for k, h in enumerate(hdr) if any(h.startswith(n) for n in names)]
        if not idx: return blk
        for i, l in enumerate(L):
            if l.startswith("|"):
                c = l.strip().strip("|").split("|"); L[i] = "|" + "|".join(x for k, x in enumerate(c) if k not in idx) + "|"
        return "\n".join(L)
    blks = md.split("#### "); out = []
    for b in blks:
        if not b.strip(): out.append(b); continue
        b = drop_cols(b, ["Model 2024, base-year attendance", "Model, base-year attendance"])
        L = b.split("\n"); keep = []; skip = False
        for l in L:
            if l.startswith("| *With 2024 telework input*"): skip = True; continue
            if l.startswith("| *Base-year attendance*"): continue
            if skip and not l.startswith("|"): skip = False
            if not skip: keep.append(l)
        b = "\n".join(keep)
        for x, y in [("Model 2024, with telework input", "Model 2024"), ("Model, with 2024 telework input", "Model 2024"), ("2024 final population, with telework input", "2024 population"),
                     (" (with 2024 telework input)", ""), ("behavioural model of record", "the model"), (" (input-driven)", ""), (" and the 2024 attendance input", "")]: b = b.replace(x, y)
        out.append(b)
    md = "#### ".join(out); open(f"{TABD}/fin24_tables_single.md", "w").write(md)

# ------------------------------------------------------------------ markdown tables -> rows
def parse_tables(md):
    out = {}
    for blk in md.split("#### ")[1:]:
        lines = blk.strip().splitlines(); key = re.match(r"Table (F\d)", lines[0]).group(1)
        rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines if l.startswith("|")]
        out[key] = (rows[0], rows[2:])
    return out


def cell(s):
    s = s.replace("ᵃ", "").replace("ᵇ", "").strip()
    s = tx(s).replace("±", "$\\pm$").replace("–", "--") if s not in ("–",) else "--"
    s = re.sub(r"\\textasciicircum\{\}", "", s); return s.replace("-", "\u2212") if re.fullmatch(r"-\d[\d.,]*", s) else s


def md_table(key, caption, note, colspec=None, small="\\footnotesize", fix_rows=None):
    hdr, rows = parse_tables(md)[key]; body = []; mids = []
    if fix_rows: rows = fix_rows(hdr, rows)
    for r in rows:
        if r[0].startswith("*") and r[0].endswith("*") and not any(r[1:]):
            mids.append(len(body)); body.append([f"\\multicolumn{{{len(hdr)}}}{{l}}{{\\emph{{{tx(r[0].strip('*'))}}}}}"]); continue
        body.append([cell(c) for c in r])
    rows_ = [b if len(b) == len(hdr) else b for b in body]
    # multicolumn rows must have one cell only
    tex_rows = [r for r in rows_]
    w0 = 0.2 if len(hdr) < 10 else 0.16; wr = (0.99 - w0) / (len(hdr) - 1) - 0.0145
    colspec = colspec or (f"L{{{w0}\\textwidth}}" + f"R{{{wr:.3f}\\textwidth}}" * (len(hdr) - 1))
    small = "\\scriptsize"
    ABBR = [("Model $\\pm$ \\%", "Model $-$ obs. (\\%)"), ("Model $\\pm$ (pp)", "Model $-$ obs. (pp)"), ("Model $\\pm$ observed", "Model $-$ obs."), ("Roorda hourly form", "hourly form"),
            ("participation", "partic."), ("Observed", "Obs."), ("observed", "obs."), ("Increase in", "Change,"), ("2017/18--2024", "2017/18 to 2024"), ("2017--19 to 2021--24", "2017--19 to 2021--24"), ("Verification", "Verif."), ("Validation", "Valid."), ("population", "pop."), ("replications", "repl."), ("activities", "activ."), ("distance", "dist."), ("Change, model 2017/18 to 2024", "Change, model"), ("Change, obs. 2017--19 to 2021--24", "Change, obs.")]
    def hcell(h):
        h = cell(h)
        for x, y in ABBR: h = h.replace(x, y)
        return h
    doc.table([hcell(h) for h in hdr], tex_rows, colspec, caption, note=note, small=small, midrules=tuple(mids))


doc = Doc("Validation of the activity model", "Stage 3 of the Baltimore chain: ABIT", WORK)
nrep = len(a.runs); nrep_b = len(a.runs_base)
D0 = TOT[TOT.form == "fin24_tw"]
SAMPLE = thousands(int(D0.persons.iloc[0])); SAMPLE_MD = thousands(int((P.county // 1000 == 24).sum()))

# ------------------------------------------------------------------ data and targets
rts = pd.read_csv(f"{DATA}/abit_roorda_tables.csv"); rts = rts[(rts.variant == "base")]
pv = int(rts[(rts.setting == a.verification) & (rts.type == "ALL")].persons.iloc[0]); pl = int(rts[(rts.setting == a.validation) & (rts.type == "ALL")].persons.iloc[0])
pc = int(rts[(rts.setting == a.chain) & (rts.type == "ALL")].persons.iloc[0])
doc.section("Data and targets")
doc.para("The activity model generates the daily activity chains of every person: the activities, their start times and durations, their locations, and the mode of each trip. "
         "It is validated in three steps, in the form that Roorda, Miller and Habib used for the Toronto activity model.")
doc.para(f"Verification: the model is run on the households of the estimation half of the 2017/18 Regional Travel Survey ({thousands(pv)} persons aged 5 and over) and compared with the "
         f"travel of the same households. Validation: the model is run on the households of the held-out half ({thousands(pl)} persons), which was not used to estimate or calibrate the coefficients. "
         f"The held-out half was, however, used to compare model variants during development, so the validation tables are not a strictly untouched hold-out. "
         f"Chain test: the model is run on the synthetic population of 2016 ({thousands(pc)} persons in the counties of the survey households) and compared with the held-out half. "
         f"The chain test adds the error of the synthetic population to that of the activity model. Each setting is the mean of {nrep} replications that differ in the random seed.")
doc.para(f"The 2024 comparison runs the model on the 2024 synthetic population of the whole model area (six states, 96 PUMAs; {SAMPLE} persons, a 10\\% sample) for {nrep} replications. "
         f"The population is that of one land-use run, the run closest to the mean of the land-use runs. Maryland residents are {SAMPLE_MD} of these persons, and the 2024 tables are limited to them "
         "(or to the Baltimore metropolitan area where stated). One replication is passed to the traffic assignment (Table 17). "
         "Observed data: ACS 2024 one-year PUMS (commute and place of work), "
         "the American Time Use Survey 2021 to 2024, Maryland diaries (activities, start times, durations), LODES 2022 origin--destination flows (work location), the National Household Travel Survey 2017 and the 2017/18 Regional Travel Survey "
         "(Baltimore area). The 2017 national survey is used because it is the latest with the metropolitan area of the household; the land-use validation compares with LODES 2023, a difference of one year that is small next to the gap between LODES and the ACS (Section 6). "
         + ("Work attendance is that of the base year." if a.single_form else "The model is shown with two forms of work attendance: the base-year attendance, and the attendance set by the 2024 share of workers working at home."))
doc.para("Activity types follow the survey form: work, school, shopping, other (recreation, accompanying and other errands) and return home. Each trip defines one activity, at its destination. "
         "In the verification, validation and chain test, distance is the zone-to-zone car distance on the road network, for the model and for the survey. "
         "In the 2024 comparison with the two surveys (Table 14) the surveys give the reported trip distance; every table states its distance measure.")

# ------------------------------------------------------------------ survey based tests
ts_data = None
class D(ts.Data):
    def __init__(self):
        T = pd.read_csv(f"{ts.DATA}/abit_roorda_tables.csv"); T = T[T.variant == "base"]
        self.K = pd.read_csv(f"{ts.DATA}/abit_roorda_ks.csv"); self.C = pd.read_parquet(f"{ts.DATA}/abit_roorda_curves.parquet")
        self.N = pd.read_csv(f"{ts.DATA}/abit_roorda_duration_counts.csv"); self.E = pd.read_csv(f"{ts.DATA}/abit_roorda_extra.csv")
        mp = {a.verification: "verification", a.validation: "validation", a.chain: "chain"}
        def rel(df): df = df[df.setting.isin(mp)].copy(); df["setting"] = df.setting.map(mp); return df
        self.T, self.K, self.C, self.E = rel(T), rel(self.K), rel(self.C), rel(self.E); self.variants = [("", "ABIT")]
Dt = D()
SETS = [("verification", "Verification (estimation half)"), ("validation", "Validation (held-out half)"), ("chain", "Chain test (synthetic 2016 population)")]
doc.section("Activity participation and frequency")
for s, lab in SETS:
    rows = []
    for ty in ts.TYPES + ["ALL"]:
        r = Dt.row(s, ty)
        rows.append([ts.TROW[ty], thousands(r.model_total), thousands(r.model_total_sd), thousands(r.observed_total), num(r["diff_pct"], 1, sign=True), num(r.model_km, 2), num(r.model_km_sd, 2),
                     num(r.observed_km, 2), num(r.diff_km_pct, 1, sign=True)])
    n = int(Dt.row(s, "ALL").persons)
    doc.table(["Activity type", hd("Model", "activities"), hd("S.d. of", "replications"), hd("Survey", "activities"), hd("Difference", "(\\%)"), hd("Model", "distance (km)"), hd("S.d. of", "replications"),
               hd("Survey", "distance (km)"), hd("Difference", "(\\%)")], rows, "lrrrrrrrr", f"Activity frequency and distance, model against survey: {lab.lower()}.",
              note=f"Persons aged 5 and over: {thousands(n)}. Activities are totals over these persons on a weekday; the survey total is the weighted count scaled to the simulated persons. "
                   f"Model: mean and standard deviation over {nrep} replications. Distance: average zone-to-zone car distance to the activity.")
# by person type and area
E = Dt.E
def grp_table(tabname, s, title, first):
    d = E[(E.setting == s) & (E.table == tabname)]; rows = []
    for g in dict.fromkeys(d.group):
        x = d[d.group == g].set_index("metric"); al = x.loc["activities_per_person_ALL"]; km = x.loc["avg_km"]
        rows.append([tx(g), thousands(al.persons_model), num(al.model, 2), num(al.model_sd, 2), num(al.observed, 2), num((al.model / al.observed - 1) * 100, 1, sign=True),
                     num(km.model, 2), num(km.observed, 2), num((km.model / km.observed - 1) * 100, 1, sign=True)])
    doc.table([first, "Persons", hd("Model", "activities", "per person"), hd("S.d. of", "replications"), hd("Survey", "activities", "per person"), hd("Difference", "(\\%)"), hd("Model", "distance (km)"),
               hd("Survey", "distance (km)"), hd("Difference", "(\\%)")], rows, "lrrrrrrrr", title)
doc.section("Results by person type and by area")
for s, lab in SETS[1:]:
    grp_table("ptype", s, f"Activities per person and average distance by person type, {lab.split(' (')[0].lower()}.", "Person type")
    grp_table("area", s, f"Activities per person and average distance by area of residence, {lab.split(' (')[0].lower()}.", "Area")
# activity types by person type
rows = []
d = E[(E.setting == "validation") & (E.table == "ptype")]
for g in dict.fromkeys(d.group):
    r = [tx(g)]
    for ty in ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME"]:
        x = d[(d.group == g) & (d.metric == f"activities_per_person_{ty}")].iloc[0]; r += [num(x.model, 3), num(x.observed, 3)]
    rows.append(r)
hdr = ["Person type"] + [h for t in ["Work", "School", "Shopping", "Other", "Return home"] for h in (hd(t, "model"), hd(t, "survey"))]
doc.table(hdr, rows, "l" + "rr" * 5, "Activities per person by type of activity and person type, validation.", note="Model: mean of the replications. Survey: held-out half.")
def pt(setting, g, metric="activities_per_person_ALL"):
    x = E[(E.setting == setting) & (E.table == "ptype") & (E.group == g) & (E.metric == metric)].iloc[0]; return x
def ptd(setting, g, metric="activities_per_person_ALL"): x = pt(setting, g, metric); return 100 * (x.model / x.observed - 1)
def share(setting, g, col):
    d = E[(E.setting == setting) & (E.table == "ptype") & (E.metric == "activities_per_person_ALL")]; return 100 * d.set_index("group")[col][g] / d[col].sum()
doc.para(f"Person types. Most types are within 4\\% in activities per person in the validation. Students aged 18 and over make "
         f"{num(ptd('validation', 'student 18+'), 1, sign=True)}\\% more activities than surveyed (validation) and {num(ptd('chain', 'student 18+'), 1, sign=True)}\\% in the chain test, "
         f"and travel {num(ptd('validation', 'student 18+', 'avg_km'), 1, sign=True)}\\% farther; they are the smallest group ({thousands(pt('validation', 'student 18+').persons_obs)} survey persons). "
         f"Non-workers travel {num(ptd('validation', 'non-worker', 'avg_km'), 1, sign=True)}\\% farther in the validation. In the chain test, retirees make {num(ptd('chain', 'retiree'), 1, sign=True)}\\% more activities "
         f"and students aged 5 to 17 travel {num(ptd('chain', 'student 5-17', 'avg_km'), 1, sign=True)}\\% less far.")
doc.para(f"Chain test. Shopping rises to {num(Dt.row('chain', 'SHOPPING').diff_pct, 1, sign=True)}\\% and other activities to {num(Dt.row('chain', 'OTHER').diff_pct, 1, sign=True)}\\% in the chain test, against "
         f"{num(Dt.row('verification', 'SHOPPING').diff_pct, 1, sign=True)}\\% and {num(Dt.row('verification', 'OTHER').diff_pct, 1, sign=True)}\\% in the verification. The synthetic population has more non-workers "
         f"({share('chain', 'non-worker', 'persons_model'):.1f}\\% of persons against {share('validation', 'non-worker', 'persons_obs'):.1f}\\% of the survey persons) and students aged 18 and over "
         f"({share('chain', 'student 18+', 'persons_model'):.1f}\\% against {share('validation', 'student 18+', 'persons_obs'):.1f}\\%), and fewer retirees "
         f"({share('chain', 'retiree', 'persons_model'):.1f}\\% against {share('validation', 'retiree', 'persons_obs'):.1f}\\%). Non-workers make the most shopping and other activities, so part of the increase "
         f"comes from this mix of person types; the rest comes from the higher activity rates of retirees and students in the synthetic population.")

doc.section("Start times, durations, chains and distance")
rows = []
for s, lab in SETS:
    for fg, fl in [("start_time", "Start time"), ("duration", "Duration by start hour")]:
        r = [lab.split(" (")[0], fl]
        for ty in ts.TYPES:
            k = Dt.ks(s, fg, ty); r.append(f"{k.D_hourly:.2f} / {k.P_hourly:.2f}" if k is not None else "--")
        rows.append(r)
doc.table(["Setting", "Measure"] + [ts.TROW[t] for t in ts.TYPES], rows, "llrrrrr", "Kolmogorov--Smirnov test of the hourly distributions: statistic D and probability P.",
          note="Test in the form of the original validation, on the 24 hourly values of start time share and mean duration, model against survey. With 24 values, D can only take multiples of 1/24, "
               "and the test has little power: P values near one do not show a close fit.", midrules=(2, 4))
fails = [(lab.split(" (")[0].lower(), ts.TROW[ty].lower(), Dt.ks(s, "duration", ty).P_hourly) for s, lab in SETS for ty in ts.TYPES if Dt.ks(s, "duration", ty) is not None and Dt.ks(s, "duration", ty).P_hourly < 0.06]
doc.para("Because the hourly form compares only 24 values, the same statistic recurs across settings (for example the shopping start time and the work duration), and a P value near one says little. "
         "The test rejects or nearly rejects the duration by start hour in " + "; ".join(f"{a_}, {b_} (P = {c_:.2f})" for a_, b_, c_ in fails) + ". "
         "These are the activities with the fewest survey observations per hour, and the curves differ mainly in the late evening (Figures 2, 6 and 10). "
         "A test on the individual activities with their sample sizes would have more power; it is not part of the original form and is not reported here.")
for s, lab in SETS:
    doc.figure(ts.fig_start(Dt, s) and f"{FIG}/fig_t3_start_{s}.pdf", f"Activity start times, {lab.lower()}: share of the activities of the day by start hour. Text in each panel: Kolmogorov--Smirnov statistic D and probability P.")
    doc.figure(ts.fig_duration(Dt, s) and f"{FIG}/fig_t3_duration_{s}.pdf", f"Average activity duration by start hour, {lab.lower()}. The arrow marks the hours in which 90\\% of the starts of the type occur. "
               f"Curves end at the first night hour with fewer than {ts.MIN_ACT} survey activities; the last hours shown rest on few activities.")
    ts.fig_chains(Dt, s); ts.fig_distance(Dt, s)
    doc.figure(f"{FIG}/fig_t3_chains_{s}.pdf", f"Share of home-based chains by number of trips, {lab.lower()}.")
    doc.figure(f"{FIG}/fig_t3_distance_{s}.pdf", f"Average distance to the activity by start hour, {lab.lower()}.")

# ------------------------------------------------------------------ 2024
TB = parse_tables(md)
def tv(key, row, col):
    hdr, rows = TB[key]; r = next(r for r in rows if r[0].startswith(row)); v = r[col].replace("ᵃ", "").replace("ᵇ", "").replace("+", "").replace(",", "").strip()
    try: return float(v.replace("−", "-"))
    except ValueError: return np.nan
doc.section("Activities of Maryland residents, 2024")
doc.para(f"The tables and figures of this section compare the {nrep} replications on the 2024 population with 2024 data and with the surveys of the base period. "
         f"Values are means over the replications with their standard deviation. Replications differ only in the random seed.")
nA = int(re.search(r"n = (\d+)", md).group(1))
md_table("F1", "Activity frequency and participation, model against the American Time Use Survey, Maryland residents aged 15 and over.",
         f"Weekday; the model day is a Monday. Survey: Maryland weekday diaries 2021 to 2024, {nA} diaries. Model values are means over {nrep} replications. "
         "Change, model: from the 2017/18 model on the survey households to the 2024 model. Change, obs.: from the diaries of 2017--19 to those of 2021--24.", small="\\scriptsize")
acs = pd.read_csv(f"{V}/3_abit/temporal_2024/data/acs_commute.csv"); A1 = lambda v, m: float(acs[(acs.vintage == v) & (acs.area == "Maryland") & (acs.metric == m)].value.iloc[0])
wfh24, wfh17 = A1("acs2024", "worked from home, share of workers at work"), A1("acs2017_19", "worked from home, share of workers at work")
wp_m, wp_o = tv("F1", "Work", 5), tv("F1", "Work", 6); se_p = 100 * np.sqrt(wp_o / 100 * (1 - wp_o / 100) / nA)
doc.para(f"Work-day excess. The model has {tv('F1', 'Work', 4):.1f}\\% more work activities per person than the time use survey, and work participation is {wp_m:.1f}\\% against {wp_o:.1f}\\% "
         f"({wp_m - wp_o:.0f} points above). This is a limitation of the model for 2024: it keeps the work attendance of the 2017/18 survey and has no post-2020 working from home. "
         f"In the ACS, {100 * wfh24:.1f}\\% of the Maryland workers at work worked from home in 2024, against {100 * wfh17:.1f}\\% in 2017--2019. The time use survey has only {nA} Maryland diaries, so its participation "
         f"has a sampling error of about {se_p:.0f} points; the gap is still several times larger. Return home and all activities are too high for the same reason. "
         "Forecasts for 2024 and later therefore overstate work trips and the morning and evening peaks that they form.")
md_table("F4", "Start time and duration tests and mean durations, model against the American Time Use Survey.",
         f"Maryland residents aged 15 and over. Kolmogorov--Smirnov test on hourly values: start time share, and mean duration at hours with at least 10 diary activities. Survey: {nA} diaries. "
         "Return home and other activities are reconstructed from stays in the diary and are not defined as in a trip diary.")
doc.para(f"Durations. The mean work duration is {tv('F4', 'Work', 5):.0f} min in the model against {tv('F4', 'Work', 7):.0f} min in the time use survey ({num(100 * (tv('F4', 'Work', 5) / tv('F4', 'Work', 7) - 1), 0, sign=True)}\\%). "
         "Part of this is likely definition: in the time use diary a work episode runs from arrival to departure including breaks at the workplace, while the model splits the day at every trip, so a lunch trip cuts "
         f"the work activity in two. Other activities last {tv('F4', 'Other', 5):.0f} min against {tv('F4', 'Other', 7):.0f} min, and their duration profile is rejected (D = {tv('F4', 'Other', 3):.2f}); the time use survey "
         "builds these episodes from stays, which merges short stops. The school start time is rejected (D = "
         f"{tv('F4', 'School', 1):.2f}, Figure 13); the school sample of the diaries is small.")
doc.figure(f"{FIG}/fig_fin24_start.pdf", "Activity start times, model and the American Time Use Survey: share of the activities of the day by start hour. Error bars: two standard deviations of the replications.")
doc.figure(f"{FIG}/fig_fin24_duration.pdf", "Average activity duration by start hour, model and the American Time Use Survey. Shaded: two standard deviations of the replications.")
doc.section("Commute and work location, 2024")
md_table("F2", "Work activity and commute, model against the American Community Survey 2024 and the time use survey.",
         "Employed Maryland residents aged 16 and over. Departure: last trip leaving home before the first work activity. Mode: mode of the trip arriving at work. "
         "ACS 2024: one-year PUMS. Workers with a work activity, ACS: share of the employed who were at work in the reference week and did not work at home, so they travelled to work at least once that week. "
         "The ACS does not observe the day; the time use survey gives the share of workers with work on the diary day. Travel time: ACS JWMNP of the workers who travelled to work, all modes; "
         "model: from the last departure from home to the arrival at work, from the zone-to-zone skim."
         + ("" if a.single_form else " In the form with the 2024 telework input, the share of workers with a work activity follows the input and is not a test."))
mt = MS_ = pd.read_csv(f"{fr.RUN}/mode_shares_vs_rts.csv") if os.path.exists(f"{fr.RUN}/mode_shares_vs_rts.csv") else None
def mtour(mode, col): return float(mt[(mt.level == "tour") & (mt.segment == "work") & (mt["mode"] == mode)][col].iloc[0])
doc.para(f"The two observed shares of workers with a work activity differ because they measure different things: {tv('F2', 'Workers', 3):.1f}\\% of the ACS workers travelled to work at least once in the "
         f"reference week, while {tv('F2', 'Workers', 6):.1f}\\% of the time-use workers worked on a given weekday. The model share ({tv('F2', 'Workers', 1):.1f}\\%) lies between them.")
if mt is not None:
    doc.para(f"Mode to work. The model has too many car passengers on the way to work ({tv('F2', 'Mode to work: car, passenger', 1):.1f}\\% against {tv('F2', 'Mode to work: car, passenger', 3):.1f}\\% in the ACS) "
             f"and too few car drivers ({tv('F2', 'Mode to work: car, driver', 1):.1f}\\% against {tv('F2', 'Mode to work: car, driver', 3):.1f}\\%). On work tours the car passenger share is {mtour('car passenger', 'model_mean'):.1f}\\% "
             f"against {mtour('car passenger', 'rts'):.1f}\\% in the 2017/18 survey, and car driver {mtour('car driver', 'model_mean'):.1f}\\% against {mtour('car driver', 'rts'):.1f}\\%. The excess is model error, not a change since the base period: "
             "the household car allocation gives each car to the member with the highest utility and sends the others to their next-best mode, and with no ride-sharing between household members "
             "this next-best mode is often car passenger. Bus and rail to work are also too high (by 1.5 and 1.8 points).")
doc.para(f"Travel time. The mean travel time to work is close ({tv('F2', 'Mean travel time', 1):.1f} against {tv('F2', 'Mean travel time', 3):.1f} min), but the median is {tv('F2', 'Median travel time', 1):.0f} "
         f"against {tv('F2', 'Median travel time', 3):.0f} min. The model has too many commutes under 15 minutes and too few of 30 to 34 and 45 to 89 minutes (Figure 15). "
         "ACS answers bunch at round values, mostly 30 minutes, which sets the observed median; model times come from the zone-to-zone skim, which has no such bunching and gives short "
         "times inside and between neighbouring zones.")
doc.figure(f"{FIG}/fig_fin24_commute.pdf", "Commute of Maryland workers, model and ACS 2024: departure hour, travel time to work and mode to work.")
md_table("F3", "Share of workers employed in their home area, model against the ACS 2024 one-year PUMS and LODES 2022.",
         "Share of the workers of each home area who work in the same area. Areas are counties or groups of counties that match the ACS place-of-work areas. ACS 2024: one-year PUMS, home and place-of-work area of the workers who travelled to work. "
         "LODES 2022: origin--destination jobs of all types. Model: workers with a work activity on the model day. The last rows give the share of Maryland residents working outside Maryland.")
doc.para(f"The two observed sources differ by about 15 points in every area (Maryland {tv('F3', 'Maryland, all', 2):.1f}\\% in the ACS against {tv('F3', 'Maryland, all', 3):.1f}\\% in LODES). "
         "LODES counts jobs, not workers: a worker with two jobs counts twice, and the employer reports the job at one address, often the head office of a firm with several sites. "
         "The ACS asks the worker where he or she worked. The model follows the ACS, which is the benchmark of choice for the workplaces of persons; the land-use validation shows the same workplaces against LODES.")
doc.para(f"Maryland residents working outside Maryland are {tv('F3', 'Maryland residents working', 1):.1f}\\% of the workers with a work activity in the model, against about 17\\% of all employed persons in the land-use model. "
         "The two use the same workplaces. The difference is the universe: the share here counts only workers with a work activity on the model day, so workers with an "
         "out-of-state workplace have a work activity less often than other workers.")
doc.figure(f"{FIG}/fig_fin24_ownshare.pdf", "Share of workers employed in their home area by area of residence: model, ACS 2024 one-year PUMS and LODES 2022.")
doc.section("Trip length and trip mode shares")
def add_one_trip(hdr, rows):
    k = [i for i, r in enumerate(rows) if r[0].startswith("Chains with")]
    if not k: return rows
    one = ["Chains with 1 trip (%)"]
    for c in range(1, len(hdr)):
        vals = [rows[i][c] for i in k]
        if all(v.strip() == "" for v in vals): one.append(""); continue
        tot = sum(float(v.replace("−", "-")) for v in vals); one.append(f"{max(0.0, 100 - tot):.1f}")
    return rows[:k[0]] + [one] + rows[k[0]:]
md_table("F5", "Activities per person, distance by purpose and trips per chain, Baltimore area, model against the 2017/18 travel survey and the 2017 national survey.",
         "Residents of the Baltimore metropolitan area aged 5 and over, weekdays. No travel diary of 2024 exists for the area; the surveys are of the base period. "
         "Distance: model zone-to-zone car distance; surveys: reported trip distance. Chains with 1 trip: chains that leave home and do not return the same day (100 minus the other rows).",
         small="\\scriptsize", fix_rows=add_one_trip)
doc.para(f"The model makes no one-trip chains: every person who leaves home returns home by the end of the simulated day, while {100 - sum(tv('F5', f'Chains with {k} trips', 4) for k in ['2', '3', '4', '5', '6+']):.1f}\\% "
         "of the survey chains end away from home (night work, overnight stays). Three-trip chains are too frequent "
         f"({tv('F5', 'Chains with 3', 1):.1f}\\% against {tv('F5', 'Chains with 3', 4):.1f}\\% and {tv('F5', 'Chains with 3', 5):.1f}\\%), the same as with the survey households "
         f"({tv('F5', 'Chains with 3', 3):.1f}\\%), so this is a property of the stop models and not of the 2024 population. "
         f"The school distance of 2024 is {tv('F5', 'School: average', 1):.1f} km against {tv('F5', 'School: average', 4):.1f} km in the 2017/18 survey and {tv('F5', 'School: average', 3):.1f} km for the "
         "survey households; it rose with the 2024 school assignment of the land-use model, which places students in schools farther from home than in 2016 (Table 16).")
doc.figure(f"{FIG}/fig_fin24_chains_distance.pdf", "Trips per home-based chain and average distance by purpose, model for 2024 and the two surveys.")
md_table("F6", "Trip mode shares, all weekday trips of Maryland residents aged 5 and over, model against the 2017/18 travel survey.",
         "Survey: trips of the Maryland survey households with person weights.")
md_table("F7", "Activities per person and distance by type: survey households, synthetic 2016 population and 2024 population.",
         "Persons aged 5 and over in the counties of the survey households, weekday. The first three model columns are the survey-based settings of the previous sections. "
         "The 2024 column differs from the chain test by the population and the land use. Distance: zone-to-zone car distance for the model and the survey.", small="\\scriptsize")

# ------------------------------------------------------------------ replications
doc.section("Spread across replications")
x = TOT[TOT.form == ("fin24" if a.single_form else "fin24_tw")].copy(); mT, mK = x.trips.mean(), x.person_km.mean()
CH = f"{fr.RUN}/matsim_input_choice.csv"
if os.path.exists(CH) and "ssq_rel_dev" in pd.read_csv(CH, nrows=1).columns:
    ch = pd.read_csv(CH).set_index("run"); x["ssq"] = x.source.map(ch.ssq_rel_dev)
    chosen = a.chosen or ch.ssq_rel_dev.idxmin()
    rule = ("The replication given to the assignment stage is the one closest to the mean of the replications: the smallest sum of squared relative deviations from the mean in trips per person, "
            "person-km per person and the trip mode shares, for Maryland residents aged 5 and over (last column).")
else:
    x["ssq"] = ((x.trips - mT) / mT) ** 2 + ((x.person_km - mK) / mK) ** 2; chosen = a.chosen or x.loc[x.ssq.idxmin(), "source"]
    rule = "The replication given to the assignment stage is the one with the smallest sum of squared relative deviations from the mean in trips and person-km (last column)."
rows = []
for r in x.itertuples():
    mark = " (given to the assignment stage)" if r.source == chosen else ""
    rows.append([f"Replication {r.seed}{mark}", thousands(r.trips), thousands(r.person_km), num((r.trips / mT - 1) * 100, 3, sign=True), num((r.person_km / mK - 1) * 100, 3, sign=True), num(1e5 * r.ssq, 1)])
y = TOT[TOT.form == "fin24"]
doc.table(["Replication", "Trips", "Person-km", hd("Trips vs", "mean (\\%)"), hd("Person-km vs", "mean (\\%)"), hd("Squared deviation", "from the mean", "($\\times 10^{-5}$)")], rows, "lrrrrr",
          "Weekday trips and person-kilometres of each replication, population of 2024" + ("." if a.single_form else " with the telework input."),
          note=f"Trips and person-km: all persons of the 10\\% sample, one weekday. Mean {thousands(x.trips.mean())} trips with standard deviation {thousands(x.trips.std())} (coefficient of variation {100 * x.trips.std() / x.trips.mean():.2f}\\%); "
               f"person-km {thousands(x.person_km.mean())}, standard deviation {thousands(x.person_km.std())} ({100 * x.person_km.std() / x.person_km.mean():.2f}\\%). "
               + ("" if a.single_form else f"Base-year attendance form: {thousands(y.trips.mean())} trips, standard deviation {thousands(y.trips.std())}. ")
               + (a.chosen_rule or rule) + " The land-use run that gives the 2024 population is chosen in the same way, as the run closest to the mean of the land-use runs.")
pages, errs, over = doc.build(a.out)
