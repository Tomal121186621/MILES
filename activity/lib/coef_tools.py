#!/usr/bin/env python3
"""Stage 3: the calibrated ABIT coefficient set (3_abit/coef_calibrated) - how it is initialised from the pristine reference
(ABIT/input/maryland/coef, never written) and the estimation-half targets, and the parameter update rules of calibrate_abit.py.

Calibration parameters (file -> what it controls -> target of targets_estimation.csv):
  rt_freq_rates.csv          purpose,rate,segment,factor: weekly Poisson mean = rate x factor per discretionary purpose and
                             person segment (worker, student, nonworker, retiree); EDUCATION factor scales the school-day
                             probability of targets_education.csv                 -> tours per traveller-day by purpose x segment
  run_params.csv             wfh.attendance.dayfactor (daily stay-home probability = dayfactor x county usual-WFH share,
                             capped at 0.6)                                       -> work tours per worker traveller-day
                             workplace.silo = true (SILO job zones, stage-1 assignment; not calibrated)
  dest_friction_power.csv    b_time, b2 (exponential decay of both friction terms) per discretionary purpose
                                                                                   -> mean trip length by purpose
  stopfreq_offsets.csv       offset per spec x half (HBW/HBE/HBS/HBO, out/in)      -> stops per tour out / in by purpose
  rt_mode_by_purpose.csv     tour-mode shares by purpose = the ASC re-anchor targets of MarylandFullModeChoice (the model's own
                             calibration: ASCs are re-anchored against the generated tours at every start)   -> mode shares
  tod_rts.csv, duration.distributions.csv   sampled directly (15-min bins of the estimation half)  -> departure-time profiles
  targets_education.csv      school-day probability by band (estimation half)      -> EDUCATION tours per student
  rt_dist_by_purpose.csv     exp-mean distance per purpose used by the ASC pre-anchor sample (estimation-half medians)
Second pass (2026-10-22, upgrade_pass2; representative day = Monday, representative_day.REP_DAY):
  stop_purpose.csv           stop purpose by tour purpose x position (survey estimation half; not calibrated)
  dest_attraction.csv        attraction weights by purpose (hh.total, jj.total, jj.retail, jj.office, jj.other, students; fixed)
  dest_distance_bands.csv    purpose, lo_km, constant: distance-band constants of the discretionary destination choice
                                                                                   -> trip-length distribution by purpose (CR >= 0.80)
  rt_freq_rates.csv          + segment toddler (under-5s travel at the survey rates); EDUCATION factor fixed at the survey
                             traveller share of students (weekly school-day probability of ALL students = share of travelling
                             students with a school tour x share of students that travel), not calibrated
  stopfreq_offsets.csv       HBO offsets by tour purpose (HBO_RECREATION_out, ...)   -> stops per tour by purpose
  run_params.csv             disc.monday.weight (M, fixed 4), disc.freeday.weight (K: weight of a weekday without a mandatory
                             tour in the discretionary day assignment)             -> EDUCATION tours per travelling student
                             disc.sameday.penalty (C: a person's second discretionary tour avoids a day that already has one)
                                                                                   -> traveller share of the non-worker, non-student members
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import json, os, shutil
import numpy as np
import pandas as pd

ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; A3 = f"{V}/3_abit"
PRISTINE = f"{ABIT_HOME}/input/maryland/coef"; CALIB = f"{A3}/coef_calibrated"
PURPOSES = ["WORK", "EDUCATION", "SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
DISC = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
SEGS = ["worker", "student", "student_elementary", "student_middle", "student_high", "student_postsec", "nonworker", "retiree", "toddler"]   # student = fallback of the bands
MODES_FILE = ["CAR_DRIVER", "CAR_PASSENGER", "TRAIN", "TRAM_METRO", "BUS", "BIKE", "WALK"]
BANDS_LO = [0, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 50]       # the DIST_BINS of rts_common (lower edges, km)
HBO_PURPOSES = ["RECREATION", "ACCOMPANY", "OTHER"]
# attraction weights by purpose (second pass): attraction = 1 + sum(w x); hh.total is scaled to the full-count basis in the model
ATTR0 = {"WORK": {"jj.total": 1.0}, "EDUCATION": {"students": 1.0}, "SHOPPING": {"hh.total": 0.1, "jj.retail": 1.0},
         "RECREATION": {"hh.total": 1.0, "jj.retail": 0.5, "jj.total": 0.25}, "ACCOMPANY": {"hh.total": 1.0, "students": 1.0}, "OTHER": {"hh.total": 1.0, "jj.total": 1.0}}
ATTR_KEYS = ["hh.total", "jj.total", "jj.retail", "jj.office", "jj.other", "students"]


def targets(path=f"{A3}/targets_estimation.csv"):
    return pd.read_csv(path, dtype={"county": str})


def tget(tg, section, metric, purpose="all", segment="all", county="all"):
    m = tg[(tg.section == section) & (tg.metric == metric) & (tg.purpose == purpose) & (tg.segment == segment) & (tg.county == county)]
    return float(m.value.iloc[0]) if len(m) else float("nan")


def init_coef(dst=CALIB, tg=None, factor0=3.0, dayfactor0=1.0):
    """Pristine copy + the estimation-half files; calibration parameters at their starting values."""
    tg = targets() if tg is None else tg
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(PRISTINE, dst, ignore=shutil.ignore_patterns("*.bak*", "*_v1?.csv", "*backup*", "__pycache__"))
    # survey distribution files of the estimation half
    for f in ["tod_rts.csv", "duration.distributions.csv"]:
        shutil.copy(f"{A3}/estimation_distributions/{f}", f"{dst}/{f}")
    shutil.copy(f"{A3}/targets_education.csv", f"{dst}/targets_education.csv")
    # tour-mode re-anchor targets (tour main mode by purpose, estimation half)
    rows = []
    for p in PURPOSES:
        for m in MODES_FILE:
            v = 0.0 if m == "TRAM_METRO" else tget(tg, "modes", f"tour_share_{m}", purpose=p)
            rows.append(dict(purpose=p, mode=m, share=round(v, 6)))
    pd.DataFrame(rows).to_csv(f"{dst}/rt_mode_by_purpose.csv", index=False)
    # exp-mean distance per purpose (median / ln 2) for the ASC pre-anchor sample
    pd.DataFrame([dict(purpose=p, mean_km=round(tget(tg, "triplength", "median_km", purpose=p) / np.log(2), 3)) for p in PURPOSES]).to_csv(f"{dst}/rt_dist_by_purpose.csv", index=False)
    # frequency rates by purpose x segment (survey tours per traveller-day) with the starting weekly factor
    rows = []
    for p in DISC:
        rows.append(dict(purpose=p, rate=round(tget(tg, "tours", "tours_per_traveller_day", purpose=p), 4), segment="all", factor=factor0))
        for s in SEGS:
            rows.append(dict(purpose=p, rate=round(tget(tg, "tours", "tours_per_traveller_day", purpose=p, segment=s), 4), segment=s, factor=factor0))
    rows.append(dict(purpose="WORK", rate=0.0, segment="all", factor=1.0))
    for b in ["elementary", "middle", "high", "postsec"]: rows.append(dict(purpose="EDUCATION", rate=1.0, segment=f"student_{b}", factor=1.0))
    rows.append(dict(purpose="EDUCATION", rate=1.0, segment="student", factor=1.0))
    pd.DataFrame(rows).to_csv(f"{dst}/rt_freq_rates.csv", index=False)
    pd.DataFrame([dict(key="wfh.attendance.dayfactor", value=dayfactor0), dict(key="workplace.silo", value="true")]).to_csv(f"{dst}/run_params.csv", index=False)
    json.dump({"iteration": 0, "source": "init_coef", "pristine": PRISTINE}, open(f"{dst}/CALIBRATION_STATE.json", "w"), indent=1)
    return dst


# ------------------------------------------------------------------------------------------------ parameter access
def read_params(d):
    fr = pd.read_csv(f"{d}/rt_freq_rates.csv"); fr["segment"] = fr.segment.fillna("all")
    rp = pd.read_csv(f"{d}/run_params.csv", dtype=str).set_index("key").value.astype(object)
    fp = pd.read_csv(f"{d}/dest_friction_power.csv")
    so = pd.read_csv(f"{d}/stopfreq_offsets.csv")
    return fr, rp, fp, so


def write_params(d, fr, rp, fp, so):
    fr.to_csv(f"{d}/rt_freq_rates.csv", index=False)
    rp.rename("value").reset_index().to_csv(f"{d}/run_params.csv", index=False)
    fp.to_csv(f"{d}/dest_friction_power.csv", index=False)
    so.to_csv(f"{d}/stopfreq_offsets.csv", index=False)


def read_bands(d):
    f = f"{d}/dest_distance_bands.csv"
    return pd.read_csv(f) if os.path.exists(f) else None


def param_snapshot(d):
    fr, rp, fp, so = read_params(d)
    out = {f"factor_{r.purpose}_{r.segment}": float(r.factor) for r in fr.itertuples()}
    out["wfh_dayfactor"] = float(rp["wfh.attendance.dayfactor"])
    for k in ["disc.monday.weight", "disc.freeday.weight", "disc.sameday.penalty"]:
        if k in rp.index: out[k.replace(".", "_")] = float(rp[k])
    out |= {f"b_time_{r.purpose}": float(r.b_time) for r in fp.itertuples()} | {f"b2_{r.purpose}": float(r.b2) for r in fp.itertuples()}
    out |= {f"stop_offset_{r.key}": float(r.offset) for r in so.itertuples()}
    bd = read_bands(d)
    if bd is not None: out |= {f"band_{r.purpose}_{r.lo_km:g}": float(r.constant) for r in bd.itertuples()}
    return out


def upgrade_pass2(d=CALIB, tg=None):
    """Second pass of the calibration (2026-10-22): adds to an existing calibrated set the files and parameters of the three
    structural changes (stop purposes by tour purpose x position, purpose-specific attraction + distance-band constants,
    representative day = Monday with the free-day weight of the discretionary day assignment and the under-5 segment).
    The first-pass values of every other parameter are kept."""
    tg = targets() if tg is None else tg
    shutil.copy(f"{A3}/estimation_distributions/stop_purpose.csv", f"{d}/stop_purpose.csv")
    pd.DataFrame([dict(purpose=p, **{k: ATTR0[p].get(k, 0.0) for k in ATTR_KEYS}) for p in PURPOSES]).to_csv(f"{d}/dest_attraction.csv", index=False)
    if not os.path.exists(f"{d}/dest_distance_bands.csv"):
        pd.DataFrame([dict(purpose=p, lo_km=lo, constant=0.0) for p in DISC for lo in BANDS_LO]).to_csv(f"{d}/dest_distance_bands.csv", index=False)
    fr, rp, fp, so = read_params(d)
    # under-5s: survey rates per travelling under-5, starting factor = the non-worker factor of the purpose
    rows = []
    for p in DISC:
        if ((fr.purpose == p) & (fr.segment == "toddler")).any(): continue
        f0 = float(fr[(fr.purpose == p) & (fr.segment == "nonworker")].factor.iloc[0])
        rows.append(dict(purpose=p, rate=round(tget(tg, "tours", "tours_per_traveller_day", purpose=p, segment="toddler"), 4), segment="toddler", factor=f0))
    if rows: fr = pd.concat([fr, pd.DataFrame(rows)], ignore_index=True)
    # EDUCATION: weekly school-day probability of all students = p_band (travelling students) x share of students that travel
    s_stu = tget(tg, "travellers", "traveller_share_group", segment="student")
    fr.loc[fr.purpose == "EDUCATION", "factor"] = round(float(s_stu), 4)
    # HBO stop offsets by tour purpose, starting from the pooled HBO row
    for half in ["out", "in"]:
        base = so[so.key == f"HBO_{half}"]
        if len(base) == 0: continue
        for p in HBO_PURPOSES:
            if (so.key == f"HBO_{p}_{half}").any(): continue
            so = pd.concat([so, pd.DataFrame([dict(key=f"HBO_{p}_{half}", offset=float(base.offset.iloc[0]), spread=float(base.spread.iloc[0]))])], ignore_index=True)
    if "disc.monday.weight" not in rp.index: rp["disc.monday.weight"] = "4.0"
    if "disc.freeday.weight" not in rp.index: rp["disc.freeday.weight"] = "4.0"
    if "disc.sameday.penalty" not in rp.index: rp["disc.sameday.penalty"] = "1.0"
    write_params(d, fr, rp, fp, so)
    st = json.load(open(f"{d}/CALIBRATION_STATE.json")) if os.path.exists(f"{d}/CALIBRATION_STATE.json") else {}
    st |= {"pass2_from_iteration": st.get("iteration"), "pass": 2}; json.dump(st, open(f"{d}/CALIBRATION_STATE.json", "w"), indent=1)
    return d


def add_student_bands(d=CALIB, tg=None):
    """Band rows (student_elementary .. student_postsec) for every discretionary purpose and EDUCATION, starting from the pooled
    student factor of the file (2026-10-22, after iteration 2: the pooled student segment cannot reproduce the by-band rates)."""
    tg = targets() if tg is None else tg
    fr = pd.read_csv(f"{d}/rt_freq_rates.csv"); fr["segment"] = fr.segment.fillna("all"); rows = []
    for p in DISC + ["EDUCATION"]:
        pooled = fr[(fr.purpose == p) & (fr.segment == "student")]
        f0 = float(pooled.factor.iloc[0]) if len(pooled) else 1.0
        for b in ["elementary", "middle", "high", "postsec"]:
            if ((fr.purpose == p) & (fr.segment == f"student_{b}")).any(): continue
            rate = 1.0 if p == "EDUCATION" else round(tget(tg, "tours", "tours_per_traveller_day", purpose=p, segment=f"student_{b}"), 4)
            rows.append(dict(purpose=p, rate=rate, segment=f"student_{b}", factor=f0))
    fr = pd.concat([fr, pd.DataFrame(rows)], ignore_index=True); fr.to_csv(f"{d}/rt_freq_rates.csv", index=False); return fr


# ------------------------------------------------------------------------------------------------ TASHA-style sets (2026-10-22)
TASHA = f"{A3}/coef_tasha"; TASHA_CAL = f"{A3}/coef_tasha_cal"
TASHA_DIST = f"{A3}/estimation_distributions/tasha"


def init_tasha(dst=TASHA, src=CALIB, tg=None):
    """Behavioural TASHA set (Roorda et al. 2008: built from the base-year survey, no calibration adjustments): a copy of the
    calibrated set with every calibrated quantity that the TASHA path could use replaced by its estimated or pristine value:
      tasha/                     the joint frequency / start-time / duration distributions (build_distributions.py, estimation half)
      run_params.csv             tasha.generation = true, dest.choice.model = mnl (the MNL estimated on the estimation half,
                                 destination_choice/), workplace.silo = true; the calibrated day / weekly-assignment parameters
                                 (wfh.attendance.dayfactor, disc.*) are removed (the TASHA path does not use them)
      rt_mode_by_purpose.csv     the survey tour main-mode shares of the estimation half (the ASC anchor of MarylandFullModeChoice,
                                 i.e. the estimated alternative-specific constants; no trip-level correction)
      dest_friction_power.csv    pristine (the gravity form is not used for any purpose with an MNL)
      dest_distance_bands.csv, stopfreq_offsets.csv calibration files removed / pristine (not used by the TASHA path)"""
    tg = targets() if tg is None else tg
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "CALIBRATION_STATE.json"))
    shutil.copytree(TASHA_DIST, f"{dst}/tasha")
    for f in ["dest_distance_bands.csv", "tasha_freq_factors.csv"]:
        if os.path.exists(f"{dst}/{f}"): os.remove(f"{dst}/{f}")
    for f in ["dest_friction_power.csv", "stopfreq_offsets.csv"]: shutil.copy(f"{PRISTINE}/{f}", f"{dst}/{f}")
    rows = []
    for p in PURPOSES:
        for m in MODES_FILE:
            v = 0.0 if m == "TRAM_METRO" else tget(tg, "modes", f"tour_share_{m}", purpose=p)
            rows.append(dict(purpose=p, mode=m, share=round(v, 6)))
    pd.DataFrame(rows).to_csv(f"{dst}/rt_mode_by_purpose.csv", index=False)
    pd.DataFrame([dict(key="workplace.silo", value="true"), dict(key="tasha.generation", value="true"), dict(key="dest.choice.model", value="mnl")]).to_csv(f"{dst}/run_params.csv", index=False)
    json.dump({"set": "tasha behavioural", "source": src, "distributions": TASHA_DIST, "calibrated": False}, open(f"{dst}/TASHA_STATE.json", "w"), indent=1)
    finalize_tasha(dst)
    return dst


TASHA_EST = f"{A3}/tasha_estimation/results"
FINAL_PARAMS = {"home.return.file": "tasha_return_home.csv", "home.return.min.slack": "5", "regen.conditional": "true", "regen.band.first": "true",
                "relocate.joint": "true", "relocate.joint.mode": "anystop", "chain.slack.to.next": "1.0"}


def _sha(p):
    import hashlib
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def finalize_tasha(dst):
    """Model of record (2026-10-23, ROORDA_VALIDATION.md section 10): the estimated components of tasha_estimation/ added to a
    TASHA set, no calibration factor:
      dest_choice_mnl.csv        + the segments of results/dest_choice_loc.csv (estimate_locations.py, estimation half):
                                 + results/dest_choice_primary_cx.csv: <PURPOSE>_primary of the four discretionary purposes
                                 re-estimated with ln(distance) x tour with stops (estimate_complexity.py)
                                 + results/dest_choice_stop_seq.csv: <PURPOSE>_seq_stop, the four stop MNLs re-estimated with
                                 sequential anchors (from the previous location to the next anchor; estimate_stops_seq.py)
                                 WORK_wbwork_stop (work business of a worker with a usual workplace, anchors home and workplace),
                                 WORK_wbhome, WORK_wahb, EDUCATION_nonstud, EDUCATION_daycare (from home); replace the band model
      tasha/tasha_return_home.csv  the binary logit of a return home between consecutive out-of-home episodes
                                 (estimate_return_home.py, estimation half); replaces the 'home stay fits' rule
      tasha/tasha_params.csv     home.return.file, home.return.min.slack (5 min), regen.conditional = true and regen.band.first =
                                 true (regeneration from the episode's start-time distribution conditional on the free windows, first
                                 within the start band of the original draw), relocate.joint = true with mode anystop (a joint episode
                                 that is a stop in a participant's chain is located on the stop MNL), chain.slack.to.next = 1.0 (on a
                                 direct link the episode of lower precedence moves by the whole gap; no dwell time is added),
                                 attendance.file / .k / .q0 / .cap (work attendance of usual-workplace workers with the ACS
                                 work-at-home share of the home county and year; base year = tasha_wfh_2017_19.csv)"""
    loc = pd.read_csv(f"{TASHA_EST}/dest_choice_loc.csv"); rh = f"{TASHA_EST}/tasha_return_home.csv"
    # the four primary discretionary MNLs re-estimated with ln(distance) x tour with stops (estimate_complexity.py)
    loc = pd.concat([loc, pd.read_csv(f"{TASHA_EST}/dest_choice_primary_cx.csv"), pd.read_csv(f"{TASHA_EST}/dest_choice_stop_seq.csv")], ignore_index=True)
    mnl = pd.read_csv(f"{dst}/dest_choice_mnl.csv")
    mnl = pd.concat([mnl[~mnl.segment.isin(loc.segment.unique())], loc], ignore_index=True); mnl.to_csv(f"{dst}/dest_choice_mnl.csv", index=False)
    shutil.copy(rh, f"{dst}/tasha/tasha_return_home.csv")
    # work attendance with the year-specific telework input: the base-year table (ACS 2017-19, the survey's interview years) and
    # the estimated day factor k and other absence q0 (estimate_attendance.py); a run of another year sets tasha.attendance.file
    shutil.copy(f"{A3}/temporal_2024/telework/wfh_attendance_2017_19.csv", f"{dst}/tasha/tasha_wfh_2017_19.csv")
    att = pd.read_csv(f"{TASHA_EST}/tasha_attendance.csv", dtype=str).set_index("key").value
    pf = f"{dst}/tasha/tasha_params.csv"; p = pd.read_csv(pf, dtype=str)
    for k, v in list(FINAL_PARAMS.items()) + [("attendance.file", "tasha_wfh_2017_19.csv")] + list(att.items()):
        if (p.key == k).any(): p.loc[p.key == k, "value"] = v
        else: p = pd.concat([p, pd.DataFrame([dict(key=k, value=v)])], ignore_index=True)
    p.to_csv(pf, index=False)
    st = json.load(open(f"{dst}/TASHA_STATE.json")) if os.path.exists(f"{dst}/TASHA_STATE.json") else {}
    st["final_components"] = {"dest_choice_loc.csv": _sha(f"{TASHA_EST}/dest_choice_loc.csv"), "tasha_return_home.csv": _sha(rh), "params": FINAL_PARAMS,
                              "tasha_attendance.csv": _sha(f"{TASHA_EST}/tasha_attendance.csv"), "dest_choice_primary_cx.csv": _sha(f"{TASHA_EST}/dest_choice_primary_cx.csv"), "dest_choice_stop_seq.csv": _sha(f"{TASHA_EST}/dest_choice_stop_seq.csv"), "attendance": att.to_dict(),
                              "tasha_wfh_2017_19.csv": _sha(f"{dst}/tasha/tasha_wfh_2017_19.csv"),
                              "segments": sorted(loc.segment.unique().tolist())}
    json.dump(st, open(f"{dst}/TASHA_STATE.json", "w"), indent=1)
    return dst
