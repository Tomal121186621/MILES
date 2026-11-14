#!/usr/bin/env python3
"""Stage 3, TASHA-style activity generation (2026-10-22): the joint frequency / start-time / duration distributions of
Roorda, Miller & Habib (2008, TR-A 42, pp. 362-363; Miller & Roorda 2003), built from the ESTIMATION half of the 2017/18 RTS
only (data/rts_split.csv, seed 2026; person weight w of survey_pop/estimation/persons_map.csv = wtperfin for the travellers,
wthhfin for the imputed non-travelling members; trip weight wttrdfin).  Nothing of the validation half is read.

    python3 activity/distributions/build_distributions.py            -> 3_abit/estimation_distributions/tasha/*.csv  + build report (stdout)

Episodes.  One episode per trip destination of a person-day (rts_trips_clean.csv, sorted by tripno): start = arrival, duration =
departure of the next trip minus the arrival (unknown for the last trip of the day).  Activity types (TASHA's ten, as far as the
RTS identifies them; the 'other' categories are split by the ABIT purpose because location and mode choice are purpose-specific):
  WB    work business            work trip (d_activity 2) not at the usual work tract (incl. every work trip of persons
                                 without a usual work tract: workplace varies / drives for a living without a tract, non-workers)
  WAHB  work-at-home business    work trip of a person whose usual workplace is home (j1_workplace_loc 3)
  PW    primary work             work trip to the usual work tract (work_state_county_fips + work_tract_fips) arriving < 15:00
  SW    secondary work           the same, arriving >= 15:00
  RHW   return home from work    a home episode entered from a work episode and left for a work episode (lunch at home)
  SCH   school                   d_activity 4, any person (students, enrolled workers, non-workers; under-5s: daycare/preschool)
  JO_REC, JO_OTH  joint other    recreation / other activity done with other household members (below)
  JS    joint shopping
  IO_REC, IO_ACC, IO_OTH  individual other (drop-off / pick-up is always individual: the escort's episode)
  IS    individual shopping
  (precedence of the scheduling = this order, TASHA's.)
Joint episodes.  Trips of one household with the same ABIT purpose (SHOPPING, RECREATION, OTHER), the same destination tract and
arrival times within 15 min of each other (travelers_hh >= 2 on every trip) form one joint episode if at least two members
report it; a party trip reported by one member only stays individual.  Joint frequencies are household-level (households of 2+
persons); participants: P(k | type, household size) and a participation propensity by person segment.
Person segments (reproducible from the SILO person and household in ABIT):
  worker_usual / worker_home / worker_none  employed, by usual workplace (fixed / varying / driving with a work tract; at home;
                                            no tract).  The RTS and SILO carry no full/part-time flag; the workplace type is a
                                            person attribute drawn in ABIT from P(type | age band) of the survey workers.
  student_elementary / _middle / _high / _postsec, nonworker, retiree, toddler (under 5)
  groups for the fallback: worker, student (incl. toddler), other (nonworker, retiree)
  household class: single, multi_nochild, multi_child (a member under 16)
Distributions and fallback (minimum cell size MIN_* unweighted records; a cell below it is not written and the model falls back
to the next coarser cell, the order is in tasha_params.csv):
  frequency   P(n | type, segment, household class, prior band)  prior band = episodes of the types that precede the type
              in the precedence order on that person-day (0, 1, 2+; TASHA's 'schedule attributes'); n = 0..6.  First level
              (2026-11-02): mandatory band M/N (a work or school episode of a preceding type, or none) x the other preceding
              episodes (0, 1, 2+), e.g. 'M0', 'N2'
              fallback: (seg, hh, mband) -> (seg, *, mband) -> (group, *, mband) -> (seg, hh, prior) -> (seg, *, prior) ->
              (group, *, prior) -> (*, *, prior) -> (seg, *, *) -> (*, *, *)
  joint freq  P(n | type, household composition, workers 0/1+); fallback (comp, *) -> (*, *)
  start       P(15-min arrival bin | type, segment, frequency f (1, 2, 3+), episode index i (1, 2, 3+; chronological))
              fallback: (seg, f, i) -> (group, f, i) -> (*, f, i) -> (*, f, *) -> (*, *, *)
  duration    P(duration bin | type, segment, start band); bins of 5 min to 2 h, then 15 min to 24 h
              fallback: (seg, band) -> (group, band) -> (*, band) -> (*, *)
  location    WB, WAHB, SCH without a school record (incl. daycare): P(car-distance band | type, origin) of the episodes'
              distance from the usual work zone (WB of worker_usual) or from home, zone within the band by attraction
  params      minimum at-home slack between two out-of-home episodes (10th percentile of the observed at-home durations
              between two out-of-home episodes that are not RHW), workplace-type shares by age band, scheduling constants
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, f"{TERP_HOME}/activity/lib"); sys.path.insert(0, f"{TERP_HOME}/activity/survey")
from rts_common import V, RTS, ACT_PURPOSE, MI_KM, load_split, band_of, DIST_BINS
from activity_metrics import dist_matrix
from survey_population import tract_zone, geoid

A3 = f"{V}/3_abit"; OUT = os.environ.get("TASHA_DIST_OUT") or f"{A3}/estimation_distributions/tasha"
# types whose person frequency has driving-licence cells first (persons 16+); 2026-11-10 (coef_respec): IS, IO_REC, IO_OTH as well
LIC_TYPES = os.environ.get("TASHA_LIC_TYPES", "IO_ACC").split(",")
TYPES = ["WB", "WAHB", "PW", "SW", "RHW", "SCH", "JO_REC", "JO_OTH", "JS", "IO_REC", "IO_ACC", "IO_OTH", "IS"]
JOINT = ["JO_REC", "JO_OTH", "JS"]
PURPOSE_OF = {"WB": "WORK", "WAHB": "WORK", "PW": "WORK", "SW": "WORK", "RHW": "HOME", "SCH": "EDUCATION", "JO_REC": "RECREATION",
              "JO_OTH": "OTHER", "JS": "SHOPPING", "IO_REC": "RECREATION", "IO_ACC": "ACCOMPANY", "IO_OTH": "OTHER", "IS": "SHOPPING"}
SEGS = ["worker_usual", "worker_home", "worker_none", "student_elementary", "student_middle", "student_high", "student_postsec",
        "nonworker", "retiree", "toddler"]
GROUP = {s: ("worker" if s.startswith("worker") else "student" if s.startswith("student") or s == "toddler" else "other") for s in SEGS}
HHC = ["single", "multi_nochild", "multi_child"]
MIN_FREQ, MIN_START, MIN_DUR, MIN_LOC = 50, 40, 40, 40
NMAX = 6
START_STEP = 15; NSTART = 96
DUR_EDGES = list(range(0, 121, 5)) + list(range(135, 1441, 15))
START_BANDS = [0, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 24]        # hours (lower edges); band k = [edge_k, edge_k+1)
WAGE = [16, 25, 55, 65]                                            # workplace-type age bands: <25, 25-54, 55-64, 65+
JOINT_WINDOW = 15
LOC_BINS = list(DIST_BINS[:-1]) + [75, 100, 150, 1e9]   # location bands: the trip-length bins with the open 50+ band split


def sband(start_min):
    h = np.asarray(start_min, float) / 60.0
    return np.clip(np.searchsorted(START_BANDS, h, side="right") - 1, 0, len(START_BANDS) - 2)


def wage_band(age):
    return np.clip(np.searchsorted(WAGE, np.asarray(age), side="right") - 1, 0, len(WAGE) - 1)


def load():
    split = load_split(); est = set(split[split == "estimation"].index)
    pm = pd.read_csv(f"{A3}/survey_pop/estimation/persons_map.csv")
    pm = pm[pm.household_id.isin(est)].copy()
    flat = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", low_memory=False,
                       usecols=["person_id", "tripid", "j1_workplace_loc", "work_state_county_fips", "work_tract_fips", "d_state_county_fips",
                                "d_tract_fips", "o_state_county_fips", "o_tract_fips", "hh_member1", "hh_member2", "hh_member3", "hh_member4",
                                "hh_member5", "hh_member6", "hh_member7", "hh_member8", "school_type", "persno"])
    per = flat.drop_duplicates("person_id").set_index("person_id")
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv", low_memory=False,
                    usecols=["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "dep_min", "arr_min", "wttrdfin", "travelers_hh", "age"])
    t = t[t.household_id.isin(est)].merge(flat.drop_duplicates("tripid")[["tripid", "d_state_county_fips", "d_tract_fips", "o_state_county_fips", "o_tract_fips"]], on="tripid", how="left")
    t = t.sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    return pm, per, t


def segments(pm, per, hh_ages):
    """Segment per persons_map row; imputed workers are split fractionally over the workplace types (rows duplicated with weight
    shares of the travelling workers of the same age band), since the survey has no workplace record for them."""
    pm = pm.copy()
    j1 = pm.person_id.map(per.j1_workplace_loc); wt = geoid(pm.person_id.map(per.work_state_county_fips), pm.person_id.map(per.work_tract_fips))
    pm["work_geoid"] = wt.values
    wtype = np.where(j1.eq(3), "home", np.where(j1.isin([1, 2, 4]) & pm.work_geoid.ne(""), "usual", "none"))
    seg = np.select([pm.occ.eq(1), pm.occ.eq(3), pm.occ.eq(4), pm.occ.eq(0)],
                    [np.char.add("worker_", wtype.astype(str)), np.char.add("student_", band_of(pm.age.clip(lower=5)).astype(str)), "retiree", "toddler"], "nonworker")
    pm["seg"] = seg; pm["wage"] = wage_band(pm.age)
    trav_w = pm[pm.occ.eq(1) & ~pm.imputed]
    shares = trav_w.groupby(["wage", "seg"]).w.sum().unstack(fill_value=0.0); shares = shares.div(shares.sum(axis=1), axis=0)
    imp = pm[pm.occ.eq(1) & pm.imputed]; rows = []
    for s in ["worker_usual", "worker_home", "worker_none"]:
        x = imp.copy(); x["seg"] = s; x["w"] = x.w * x.wage.map(shares[s]).fillna(0.0); rows.append(x)
    pm = pd.concat([pm[~(pm.occ.eq(1) & pm.imputed)]] + rows, ignore_index=True)
    a = hh_ages.reindex(pm.household_id)
    pm["hhsize"] = pm.household_id.map(pm.drop_duplicates("id").groupby("household_id").size()).values
    pm["hhc"] = np.where(pm.hhsize.eq(1), "single", np.where(pm.household_id.map(hh_ages).values, "multi_child", "multi_nochild"))
    pm["group"] = pm.seg.map(GROUP)
    return pm, shares


def episodes(t, per):
    """One row per trip destination (episode) with its TASHA type (joint / individual decided later)."""
    e = t.copy()
    e["purpose"] = e.d_activity.map(ACT_PURPOSE).fillna("OTHER")
    nxt = e.groupby("person_id").dep_min.shift(-1); e["dur"] = nxt - e.arr_min
    e.loc[e.dur < 0, "dur"] = np.nan
    e["d_geoid"] = geoid(e.d_state_county_fips, e.d_tract_fips).values
    e["work_geoid"] = geoid(e.person_id.map(per.work_state_county_fips), e.person_id.map(per.work_tract_fips)).values
    j1 = e.person_id.map(per.j1_workplace_loc)
    work = e.purpose.eq("WORK"); at_usual = work & e.d_geoid.ne("") & e.d_geoid.eq(e.work_geoid)
    e["type"] = None
    e.loc[work & ~at_usual, "type"] = "WB"
    e.loc[work & j1.eq(3), "type"] = "WAHB"
    e.loc[at_usual & (e.arr_min < 900), "type"] = "PW"
    e.loc[at_usual & (e.arr_min >= 900), "type"] = "SW"
    e.loc[e.purpose.eq("EDUCATION"), "type"] = "SCH"
    # return home from work: home episode entered from work and left for work
    prev_o = e.o_activity.map(ACT_PURPOSE); nxt_d = e.groupby("person_id").d_activity.shift(-1).map(ACT_PURPOSE)
    e.loc[e.purpose.eq("HOME") & prev_o.eq("WORK") & nxt_d.eq("WORK"), "type"] = "RHW"
    e["is_home"] = e.purpose.eq("HOME")
    # joint detection (SHOPPING, RECREATION, OTHER)
    cand = e[e.purpose.isin(["SHOPPING", "RECREATION", "OTHER"]) & (e.travelers_hh >= 2) & e.d_geoid.ne("")].sort_values(["household_id", "purpose", "d_geoid", "arr_min"])
    gid = np.zeros(len(cand), dtype=np.int64); g = 0; prev = None
    for k, (hh, pu, dg, ar) in enumerate(zip(cand.household_id.values, cand.purpose.values, cand.d_geoid.values, cand.arr_min.values)):
        if prev is None or (hh, pu, dg) != prev[:3] or ar - prev[3] > JOINT_WINDOW: g += 1
        gid[k] = g; prev = (hh, pu, dg, ar)
    cand = cand.assign(jgid=gid)
    size = cand.groupby("jgid").person_id.nunique(); cand["jsize"] = cand.jgid.map(size)
    e["jgid"] = -1; e["jsize"] = 1
    e.loc[cand.index, "jgid"] = cand.jgid.values; e.loc[cand.index, "jsize"] = cand.jsize.values
    joint = e.jsize >= 2
    e.loc[joint & e.purpose.eq("SHOPPING"), "type"] = "JS"
    e.loc[joint & e.purpose.eq("RECREATION"), "type"] = "JO_REC"
    e.loc[joint & e.purpose.eq("OTHER"), "type"] = "JO_OTH"
    ind = e.type.isna() & ~e.is_home
    e.loc[ind & e.purpose.eq("SHOPPING"), "type"] = "IS"
    e.loc[ind & e.purpose.eq("RECREATION"), "type"] = "IO_REC"
    e.loc[ind & e.purpose.eq("ACCOMPANY"), "type"] = "IO_ACC"
    e.loc[ind & e.purpose.eq("OTHER"), "type"] = "IO_OTH"
    e.loc[~joint, "jgid"] = -1
    return e


SUB_ANCHOR = {"PW", "SW"}
SUB_STOP = {"JO_REC", "JO_OTH", "JS", "IO_REC", "IO_ACC", "IO_OTH", "IS"}


def subtours(e):
    """Work-based subtours (2026-11-03): an outing from the usual workplace that returns to it, i.e. a work episode at the usual
    workplace (PW / SW), one or more discretionary episodes (no home, no other work or school episode) and again a PW / SW
    episode.  e: episodes of one or more person-days sorted by person and trip number (TD.episodes).  Returns e with
      wbs        the episode is a stop of a subtour
      wbs_cont   the episode is the return to the workplace (continuation of the work episode)
      wbs_root   index (label of e) of the work episode the outing belongs to (-1 otherwise; also set on the root itself)
      wbs_n      on the root: number of subtours of the merged work episode
      merged_dur on the root: from its arrival to the end of its last continuation (NaN when that end is unknown)
    The scheduler generates the outing inside the work episode (MarylandTashaGenerator.subtours); the frequency, start-time and
    duration distributions therefore see the merged work episode and not the subtour stops nor the continuation."""
    e = e.copy()
    ty = np.where(e.is_home.values, "HOME", e.type.fillna("NA").astype(str).values)
    pid = e.person_id.values; arr = e.arr_min.values.astype(float); dur = e.dur.values.astype(float); lab = e.index.values
    n = len(e); wbs = np.zeros(n, bool); cont = np.zeros(n, bool); root = np.full(n, -1, dtype=np.int64); nsub = np.zeros(n, int); mdur = dur.copy()
    i = 0
    while i < n:
        if ty[i] in SUB_ANCHOR and not cont[i]:
            r = i; last = i; k = i
            while True:
                j = k + 1
                while j < n and pid[j] == pid[r] and ty[j] in SUB_STOP: j += 1
                if j < n and pid[j] == pid[r] and j > k + 1 and ty[j] in SUB_ANCHOR:
                    wbs[k + 1:j] = True; cont[j] = True; root[k + 1:j + 1] = lab[r]; nsub[r] += 1; last = j; k = j
                else: break
            if last > r:
                root[r] = lab[r]; mdur[r] = arr[last] + dur[last] - arr[r] if np.isfinite(dur[last]) else np.nan
            i = last + 1
        else: i += 1
    e["wbs"] = wbs; e["wbs_cont"] = cont; e["wbs_root"] = root; e["wbs_n"] = nsub; e["merged_dur"] = mdur
    return e


def pdf_rows(df, keys, valcol, wcol, edges, min_n, label):
    rows = []
    for k, g in df.groupby(keys, dropna=False):
        if len(g) < min_n: continue
        h, _ = np.histogram(g[valcol].values, bins=edges, weights=g[wcol].values)
        if h.sum() <= 0: continue
        rows.append(dict(zip(keys, k if isinstance(k, tuple) else (k,)), n=len(g), probs=";".join(f"{v:.6g}" for v in h / h.sum())))
    return rows


def with_wild(df, cols):
    """Copies of df with the given columns set to '*' (wildcard cells)."""
    d = df.copy()
    for c in cols: d[c] = "*"
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    pm, per, t = load()
    hh_child = pm.groupby("household_id").age.min().lt(16)
    pm, wshares = segments(pm, per, hh_child)
    e = episodes(t, per)
    pseg = pm[~pm.imputed].drop_duplicates("person_id").set_index("person_id")
    e = e[e.person_id.isin(pseg.index)].copy()
    # work-based subtours (2026-11-03): the outing and the return to the workplace are generated inside the work episode by the
    # scheduler (subtour model, tasha_estimation/estimate_subtours.py); here the work episode is merged (duration to the end of
    # its last continuation) and the subtour stops and continuations leave the frequency, start and duration distributions
    e = subtours(e)
    rt = e.wbs_n.gt(0); e.loc[rt, "dur"] = e.loc[rt, "merged_dur"]; e.loc[e.wbs | e.wbs_cont, "type"] = None
    print(f"work-based subtours: {int(e.wbs_n.sum()):,} outings from {int(rt.sum()):,} work episodes; {int(e.wbs.sum()):,} stops removed from the distributions")
    e["seg"] = e.person_id.map(pseg.seg); e["group"] = e.seg.map(GROUP); e["hhc"] = e.person_id.map(pseg.hhc)
    # survey workers of type 'usual' are a single segment row in pseg (travellers are not split)
    ev = e[e.type.notna()].copy()
    print(f"estimation half: {pm.id.nunique():,} persons ({pm.imputed.sum():,} imputed rows), {len(t):,} trips, {len(ev):,} typed episodes")
    print("episodes by type (unweighted):", ev.type.value_counts().reindex(TYPES).fillna(0).astype(int).to_dict())

    # ------------------------------------------------------------------ person-level frequencies with the prior band
    cnt = ev[~ev.type.isin([])].groupby(["person_id", "type"]).size().unstack(fill_value=0).reindex(columns=TYPES, fill_value=0)
    # joint types count at person level too (participation), but their FREQUENCY is generated per household
    P = pm[["id", "person_id", "household_id", "seg", "group", "hhc", "w", "imputed", "age", "occ", "hhsize"]].copy()
    # licence (2026-11-03): the accompany frequency of persons 16+ also by driving licence (survey_pop pp.csv of the half)
    lic = pd.read_csv(f"{A3}/survey_pop/estimation/pp.csv", usecols=["id", "driversLicense"]).set_index("id").driversLicense.astype(str).eq("True")
    P["lic"] = np.where(P.age.values >= 16, np.where(P.id.map(lic).fillna(False).values, "~L", "~N"), "")
    C = cnt.reindex(P.person_id.values).fillna(0).astype(int).to_numpy().copy()
    C[P.imputed.values] = 0
    prior = np.zeros_like(C)
    for k in range(1, len(TYPES)): prior[:, k] = prior[:, k - 1] + C[:, k - 1]
    # mandatory band (2026-11-02): the frequency of a type also depends on whether the person has a work or school episode
    # of a preceding type that day ('M') or not ('N'), with the count of the other preceding episodes (0, 1, 2+): band 'M1' etc.
    # Workers on a work day have fewer discretionary episodes than on a day without work (estimation half: shopping 0.26 against
    # 0.47 per worker); the total prior count alone mixes both.  The cells of the earlier band (0, 1, 2) stay as the fallback.
    MANDF = ["WB", "WAHB", "PW", "SW", "SCH"]
    priorMf = np.zeros_like(C)
    for k in range(1, len(TYPES)): priorMf[:, k] = priorMf[:, k - 1] + (C[:, k - 1] if TYPES[k - 1] in MANDF else 0)
    fr = []
    for k, ty in enumerate(TYPES):
        if ty in JOINT: continue
        mb = np.char.add(np.where(priorMf[:, k] > 0, "M", "N"), np.minimum(prior[:, k] - priorMf[:, k], 2).astype(str))
        d = pd.DataFrame({"type": ty, "seg": P.seg.values, "group": P.group.values, "hhc": P.hhc.values,
                          "prior": np.minimum(prior[:, k], 2).astype(str), "mband": mb, "n": np.minimum(C[:, k], NMAX), "w": P.w.values})
        cells = [d.assign(cseg=d.seg, chh=d.hhc, cpr=d.mband), d.assign(cseg=d.seg, chh="*", cpr=d.mband), d.assign(cseg=d.group, chh="*", cpr=d.mband),
                 d.assign(cseg=d.seg, chh=d.hhc, cpr=d.prior), d.assign(cseg=d.seg, chh="*", cpr=d.prior), d.assign(cseg=d.group, chh="*", cpr=d.prior),
                 d.assign(cseg="*", chh="*", cpr=d.prior), d.assign(cseg=d.seg, chh="*", cpr="*"), d.assign(cseg="*", chh="*", cpr="*")]
        if ty in LIC_TYPES:   # licence cells first (persons 16+): seg~L / seg~N, group~L / group~N; fallback to the cells below
            a = d[P.lic.values != ""].assign(segl=lambda x: x.seg + P.lic.values[P.lic.values != ""], grpl=lambda x: x.group + P.lic.values[P.lic.values != ""])
            for c in [a.assign(cseg=a.segl, chh=a.hhc, cpr=a.mband), a.assign(cseg=a.segl, chh="*", cpr=a.mband), a.assign(cseg=a.grpl, chh="*", cpr=a.mband),
                      a.assign(cseg=a.segl, chh="*", cpr=a.prior), a.assign(cseg=a.grpl, chh="*", cpr=a.prior), a.assign(cseg=a.segl, chh="*", cpr="*"), a.assign(cseg=a.grpl, chh="*", cpr="*")]:
                for key, g in c.groupby(["cseg", "chh", "cpr"]):
                    if len(g) < MIN_FREQ: continue
                    h = np.bincount(g.n.values, weights=g.w.values, minlength=NMAX + 1)
                    fr.append(dict(level="person", type=ty, seg=key[0], hh=key[1], prior=key[2], n=len(g), mean=float((np.arange(NMAX + 1) * h).sum() / h.sum()),
                                   probs=";".join(f"{v:.6g}" for v in h / h.sum())))
        for lev, c in enumerate(cells):
            for key, g in c.groupby(["cseg", "chh", "cpr"]):
                if len(g) < MIN_FREQ and lev < len(cells) - 1: continue
                h = np.bincount(g.n.values, weights=g.w.values, minlength=NMAX + 1)
                fr.append(dict(level="person", type=ty, seg=key[0], hh=key[1], prior=key[2], n=len(g), mean=float((np.arange(NMAX + 1) * h).sum() / h.sum()),
                               probs=";".join(f"{v:.6g}" for v in h / h.sum())))
    # household-level joint frequencies (households with 2+ persons)
    hh = pm.drop_duplicates("household_id")[["household_id", "hhsize", "hhc"]].set_index("household_id")
    hw = pm.drop_duplicates("household_id").set_index("household_id").wthhfin
    nwk = pm[pm.occ.eq(1)].drop_duplicates("id").groupby("household_id").size()
    hh["wk"] = np.where(nwk.reindex(hh.index).fillna(0) > 0, "1+", "0"); hh["w"] = hw
    hh["comp"] = np.where(hh.hhc.eq("multi_child"), "child", np.where(hh.hhsize.eq(2), "two_adult", "three_adult"))
    hh = hh[hh.hhsize >= 2]
    jt = ev[ev.type.isin(JOINT)].drop_duplicates("jgid")
    jc = jt.groupby(["household_id", "type"]).size().unstack(fill_value=0).reindex(columns=JOINT, fill_value=0).reindex(hh.index).fillna(0).astype(int)
    for ty in JOINT:
        d = hh.assign(n=np.minimum(jc[ty].values, NMAX))
        for lev, (a, b) in enumerate([("comp", "wk"), ("comp", None), (None, None)]):
            d2 = d.assign(ca=d[a] if a else "*", cb=d[b] if b else "*")
            for key, g in d2.groupby(["ca", "cb"]):
                if len(g) < MIN_FREQ and lev < 2: continue
                h = np.bincount(g.n.values, weights=g.w.values, minlength=NMAX + 1)
                fr.append(dict(level="household", type=ty, seg=key[0], hh=key[1], prior="*", n=len(g), mean=float((np.arange(NMAX + 1) * h).sum() / h.sum()),
                               probs=";".join(f"{v:.6g}" for v in h / h.sum())))
    if os.environ.get("TASHA_JOINT_PB"):
        # household joint frequency conditional on the members' work / school that day (2026-11-10, coef_respec; MarylandTashaGenerator
        # joint.freq.mandatory): band MN (no member with a WB, WAHB, PW, SW or SCH episode), MS (some), MA (all); cells (household type,
        # workers, band) -> (household type, band) -> (band), at least MIN_FREQ households (the engine then falls back to the cells
        # without the band)
        mand_p = set(ev[ev.type.isin(["WB", "WAHB", "PW", "SW", "SCH"])].person_id)
        pmu = pm[~pm.imputed].drop_duplicates("id"); nm = pmu.assign(m=pmu.person_id.isin(mand_p)).groupby("household_id").m.sum()
        hh["band"] = np.where(nm.reindex(hh.index).fillna(0) == 0, "MN", np.where(nm.reindex(hh.index).fillna(0) >= hh.hhsize, "MA", "MS"))
        for ty in JOINT:
            d = hh.assign(n=np.minimum(jc[ty].values, NMAX))
            for a, b in [("comp", "wk"), ("comp", None), (None, None)]:
                d2 = d.assign(ca=d[a] if a else "*", cb=d[b] if b else "*")
                for key, g in d2.groupby(["ca", "cb", "band"]):
                    if len(g) < MIN_FREQ: continue
                    h = np.bincount(g.n.values, weights=g.w.values, minlength=NMAX + 1)
                    fr.append(dict(level="household", type=ty, seg=key[0], hh=key[1], prior=key[2], n=len(g), mean=float((np.arange(NMAX + 1) * h).sum() / h.sum()),
                                   probs=";".join(f"{v:.6g}" for v in h / h.sum())))
        print("households by band:", hh.band.value_counts().to_dict(), "joint episodes per household by band:", d.assign(t=jc.sum(1).values).groupby("band").t.mean().round(3).to_dict())
    fr = pd.DataFrame(fr); fr.to_csv(f"{OUT}/tasha_frequency.csv", index=False)
    # prior band of each (person, type): '0' or '1+' episodes of the preceding types on the person-day (schedule attribute)
    MAND = ["WB", "WAHB", "PW", "SW", "SCH"]
    priorM = np.zeros_like(C)
    for k in range(1, len(TYPES)): priorM[:, k] = priorM[:, k - 1] + (C[:, k - 1] if TYPES[k - 1] in MAND else 0)
    pband = np.where(priorM > 0, 2, np.where(prior > 0, 1, 0))   # 0 none, 1 other episodes only, 2 work / school episodes
    pri = pd.DataFrame(pband, columns=TYPES); pri["person_id"] = P.person_id.values
    pri = pri[~P.imputed.values].drop_duplicates("person_id").set_index("person_id")

    # ------------------------------------------------------------------ start time | frequency, episode index
    ev["fn"] = ev.groupby(["person_id", "type"]).arr_min.transform("size").clip(upper=3).astype(int).astype(str)
    pv = pri.stack().rename("prior_n"); ev["pb"] = pd.Series(pd.MultiIndex.from_arrays([ev.person_id, ev.type]).map(pv).fillna(0).values).map({0: "0", 1: "O", 2: "M"}).values
    ev["fd"] = np.where(ev.fn.eq("1"), "1", "2+")
    ev["ix"] = (ev.groupby(["person_id", "type"]).cumcount() + 1).clip(upper=3).astype(str)
    # joint episodes: household level (one record per joint episode, frequency and index within the household)
    jt = ev[ev.type.isin(JOINT)].drop_duplicates("jgid").sort_values(["household_id", "type", "arr_min"]).copy()
    jt["fn"] = jt.groupby(["household_id", "type"]).arr_min.transform("size").clip(upper=3).astype(int).astype(str)
    jt["ix"] = (jt.groupby(["household_id", "type"]).cumcount() + 1).clip(upper=3).astype(str)
    jt["seg"] = jt.household_id.map(hh.comp).fillna("*"); jt["group"] = "*"; jt["pb"] = "*"; jt["fd"] = np.where(jt.fn.eq("1"), "1", "2+")
    sv = pd.concat([ev[~ev.type.isin(JOINT)], jt], ignore_index=True)
    sv["w"] = sv.wttrdfin
    st_rows = []
    edges = np.arange(0, 1441, START_STEP)
    # start | type, segment, frequency, episode index, prior band; fallback drops the prior band, then segment -> group -> all,
    # then the index, then the frequency
    for lev, (cs, cf, ci, cp) in enumerate([("seg", "fn", "ix", "pb"), ("seg", "fn", "ix", None), ("group", "fn", "ix", None), (None, "fn", "ix", None), (None, "fn", None, None), (None, None, None, None)]):
        d = sv.assign(cseg=sv[cs] if cs else "*", cf=sv[cf] if cf else "*", ci=sv[ci] if ci else "*", cpb=sv[cp] if cp else "*")
        st_rows += [dict(r, level=lev) for r in pdf_rows(d, ["type", "cseg", "cf", "ci", "cpb"], "arr_min", "w", edges, MIN_START if lev < 5 else 1, "start")]
    if os.environ.get("TASHA_JOINT_PB"):
        # joint start conditional on the participants' work / school that day (2026-11-10, coef_respec; MarylandTashaGenerator
        # joint.start.conditional): pb = JM when any participant of the joint episode has a WB, WAHB, PW, SW or SCH episode that day,
        # else JN; cells (household type, frequency, index, JM/JN) -> (all, frequency, index, JM/JN) -> (all, all, all, JM/JN), each
        # with at least MIN_START episodes; the engine falls back to the cells without the band below these (levels 20-22 here)
        mand_p = set(ev[ev.type.isin(MAND)].person_id)
        jm = ev[ev.type.isin(JOINT)].groupby("jgid").person_id.agg(lambda p: "JM" if any(q in mand_p for q in p) else "JN")
        jj = jt.assign(jpb=jt.jgid.map(jm).values, w=jt.wttrdfin)
        for lev, (cs, cf, ci) in enumerate([("seg", "fn", "ix"), (None, "fn", "ix"), (None, None, None)]):
            d = jj.assign(cseg=jj[cs] if cs else "*", cf=jj[cf] if cf else "*", ci=jj[ci] if ci else "*", cpb=jj.jpb)
            st_rows += [dict(r, level=20 + lev) for r in pdf_rows(d, ["type", "cseg", "cf", "ci", "cpb"], "arr_min", "w", edges, MIN_START, "start")]
        print("joint start bands (episodes):", jj.jpb.value_counts().to_dict())
    st = pd.DataFrame(st_rows).rename(columns={"cseg": "seg", "cf": "f", "ci": "i", "cpb": "pb"}); st = st[~((st.level == 0) & st.pb.eq("*"))]
    st.to_csv(f"{OUT}/tasha_start.csv", index=False)

    # ------------------------------------------------------------------ duration | start band
    # at-home episodes between two out-of-home episodes (not RHW): duration of the home stay by arrival band, type HOME; the
    # scheduler returns home between two episodes only when a home stay drawn from it fits into the slack
    hb = e[e.is_home & e.type.isna() & e.dur.notna() & e.o_activity.map(ACT_PURPOSE).ne("HOME") & e.person_id.isin(pseg.index)].copy()
    hb["type"] = "HOME"; hb["w"] = hb.wttrdfin; hb["group"] = "*"; hb["fd"] = "*"
    sv = pd.concat([sv, hb[["type", "seg", "group", "arr_min", "dur", "w", "wttrdfin", "fd"]]], ignore_index=True)
    dv = sv[sv.dur.notna() & (sv.dur >= 1)].copy(); dv["band"] = sband(dv.arr_min).astype(str)
    du_rows = []
    # duration | type, segment, start band, frequency (1 / 2+ episodes of the type); fallback drops the frequency, then
    # segment -> group -> all, then the band
    for lev, (cs, cb, cf) in enumerate([("seg", "band", "fd"), ("seg", "band", None), ("group", "band", None), (None, "band", None), (None, None, None)]):
        d = dv.assign(cseg=dv[cs] if cs else "*", cb=dv[cb] if cb else "*", cfd=dv[cf].fillna("*") if cf else "*")
        du_rows += [dict(r, level=lev) for r in pdf_rows(d, ["type", "cseg", "cb", "cfd"], "dur", "w", np.array(DUR_EDGES, float), MIN_DUR if lev < 4 else 1, "dur")]
    du = pd.DataFrame(du_rows).rename(columns={"cseg": "seg", "cb": "band", "cfd": "fd"}); du = du[~((du.level == 0) & du.fd.eq("*"))]
    du.to_csv(f"{OUT}/tasha_duration.csv", index=False)

    # ------------------------------------------------------------------ joint participants
    jp = ev[ev.type.isin(JOINT)].copy()
    k = jp.groupby("jgid").person_id.nunique(); first = jp.drop_duplicates("jgid").set_index("jgid")
    kk = pd.DataFrame({"type": first.type, "hhsize": first.household_id.map(hh.hhsize).clip(upper=5), "k": k.reindex(first.index), "w": first.wttrdfin})
    part = []
    for (ty, hs), g in kk.dropna().groupby(["type", "hhsize"]):
        h = np.bincount(g.k.astype(int).clip(upper=8).values, weights=g.w.values, minlength=9)[2:]
        part.append(dict(type=ty, hhsize=int(hs), n=len(g), probs=";".join(f"{v:.6g}" for v in h / h.sum())))
    # participation propensity by segment: participants of segment s / members of segment s in the households of the episodes
    members = pm.drop_duplicates("id").groupby(["household_id", "seg"]).size().unstack(fill_value=0)
    prop = []
    jx = first.reset_index()[["jgid", "household_id", "wttrdfin"]]
    par = jp.drop_duplicates(["jgid", "person_id"]).assign(seg=lambda x: x.person_id.map(pseg.seg)).groupby(["jgid", "seg"]).size().unstack(fill_value=0)
    for s in SEGS:
        if s not in members.columns: continue
        m = jx.household_id.map(members[s]).fillna(0).values
        p_ = par[s].reindex(jx.jgid).fillna(0).values if s in par.columns else np.zeros(len(jx))
        den = (m * jx.wttrdfin.values).sum()
        prop.append(dict(seg=s, members=float(m.sum()), participants=float(p_.sum()), propensity=float((p_ * jx.wttrdfin.values).sum() / den) if den > 0 else 0.0))
    if os.environ.get("TASHA_JOINT_PB"):
        # participation propensity by segment and work / school that day (2026-11-10, coef_respec; MarylandTashaGenerator
        # joint.members.mandatory): segment|M (the member has a WB, WAHB, PW, SW or SCH episode that day) or segment|N; participants
        # of the cell / members of the cell in the households of the episodes, weighted as above; a cell with fewer than 30 members
        # takes the segment's propensity (the engine falls back to the segment row)
        mand_p = set(ev[ev.type.isin(["WB", "WAHB", "PW", "SW", "SCH"])].person_id)
        mm = pm[~pm.imputed].drop_duplicates("person_id").copy(); mm["cell"] = mm.seg + "|" + np.where(mm.person_id.isin(mand_p), "M", "N")
        mem2 = mm.groupby(["household_id", "cell"]).size().unstack(fill_value=0)
        par2 = jp.drop_duplicates(["jgid", "person_id"]).assign(cell=lambda x: x.person_id.map(mm.set_index("person_id").cell)).groupby(["jgid", "cell"]).size().unstack(fill_value=0)
        pm2 = []
        for cell in sorted(mem2.columns):
            m = jx.household_id.map(mem2[cell]).fillna(0).values; p_ = par2[cell].reindex(jx.jgid).fillna(0).values if cell in par2.columns else np.zeros(len(jx))
            den = (m * jx.wttrdfin.values).sum()
            if m.sum() >= 30 and den > 0: pm2.append(dict(seg=cell, members=float(m.sum()), participants=float(p_.sum()), propensity=float((p_ * jx.wttrdfin.values).sum() / den)))
        pd.DataFrame(pm2).to_csv(f"{OUT}/tasha_joint_propensity_mand.csv", index=False)
        print("joint propensity by segment and work / school that day:", {r["seg"]: round(r["propensity"], 3) for r in pm2})
    pd.DataFrame(part).to_csv(f"{OUT}/tasha_joint_participants.csv", index=False)
    pd.DataFrame(prop).to_csv(f"{OUT}/tasha_joint_propensity.csv", index=False)

    # ------------------------------------------------------------------ location bands (WB, WAHB, SCH without a school record)
    tz = tract_zone().set_index("geoid").zone; dm = dist_matrix()
    lv = ev[ev.type.isin(["WB", "WAHB", "SCH"])].copy()
    lv["dz"] = lv.d_geoid.map(tz).fillna(-1).astype(int)
    lv["home_zone"] = lv.person_id.map(pm.drop_duplicates("person_id").set_index("person_id").home_zone).fillna(-1).astype(int)
    lv["work_zone"] = lv.work_geoid.map(tz).fillna(-1).astype(int)
    lv["origin"] = np.where(lv.type.eq("WB") & lv.seg.eq("worker_usual") & (lv.work_zone > 0), "work", "home")
    oz = np.where(lv.origin.eq("work"), lv.work_zone, lv.home_zone)
    ok = (oz > 0) & (lv.dz > 0); lv = lv[ok].copy(); oz = oz[ok]
    lv["km"] = dm[oz, lv.dz.values]
    # SCH: only the persons without a school record in the model (non-students and under-5s); students keep their school
    lv = lv[~(lv.type.eq("SCH") & lv.seg.str.startswith("student"))]
    lv["ltype"] = np.where(lv.type.eq("SCH") & lv.seg.eq("toddler"), "DAYCARE", lv.type)
    loc = []
    for (ty, o), g in lv.groupby(["ltype", "origin"]):
        h, _ = np.histogram(g.km.values, bins=LOC_BINS, weights=g.wttrdfin.values)
        loc.append(dict(type=ty, origin=o, n=len(g), probs=";".join(f"{v:.6g}" for v in h / h.sum())))
    pd.DataFrame(loc).to_csv(f"{OUT}/tasha_location_bands.csv", index=False)

    # ------------------------------------------------------------------ parameters
    hm = ev[ev.is_home & ev.type.isna()]
    first_trip = t.groupby("person_id").tripno.transform("min").eq(t.tripno)
    # at-home episodes between two out-of-home episodes: a home episode with a known duration that is followed by a trip
    hm = e[e.is_home & e.type.isna() & e.dur.notna() & e.o_activity.map(ACT_PURPOSE).ne("HOME")]
    from rts_common import wquantile
    hmin = wquantile(hm.dur.values, hm.wttrdfin.values, 0.10)
    params = [("home.min.slack", round(hmin, 1)), ("home.stay.factor", 1.0), ("max.shift.min", 30), ("chain.slack.to.next", 0.5), ("protect.precedence", "true"), ("relocate.stops", "true"), ("shorten.min.frac", 0.5), ("max.regenerate", 10), ("cleanup.work.max.min", 30),
              ("start.step", START_STEP), ("duration.edges", ";".join(map(str, DUR_EDGES))), ("start.bands", ";".join(map(str, START_BANDS))),
              ("worker.age.bands", ";".join(map(str, WAGE))), ("joint.window.min", JOINT_WINDOW), ("nmax", NMAX),
              ("dist.bins", ";".join(f"{b:g}" for b in LOC_BINS[:-1])), ("types", ";".join(TYPES)), ("purpose.of", ";".join(f"{k}:{v}" for k, v in PURPOSE_OF.items()))]
    for wa in range(len(WAGE)):
        r = wshares.loc[wa] if wa in wshares.index else pd.Series(dtype=float)
        params.append((f"worker.type.share.{wa}", ";".join(f"{r.get(s, 0.0):.6g}" for s in ["worker_usual", "worker_home", "worker_none"])))
    pd.DataFrame(params, columns=["key", "value"]).to_csv(f"{OUT}/tasha_params.csv", index=False)

    # ------------------------------------------------------------------ report
    def nd(df, lev_col=None): return len(df)
    print(f"\nfrequency distributions: {len(fr)} (person {int((fr.level == 'person').sum())}, household {int((fr.level == 'household').sum())})")
    print(f"start-time distributions: {len(st)}; duration distributions: {len(du)}; participants {len(part)}; location {len(loc)}")
    print("start cells by level:", st.level.value_counts().sort_index().to_dict(), " duration cells by level:", du.level.value_counts().sort_index().to_dict())
    print(f"minimum at-home slack (p10 of the at-home episodes between out-of-home episodes): {hmin:.1f} min ({len(hm):,} episodes)")
    print("workplace-type shares by age band:"); print(wshares.round(3).to_string())
    # weighted episodes per person by type (all persons 5+, for the Roorda comparison)
    wsum = pm[pm.age >= 5].w.sum()
    x = ev[ev.age >= 5].groupby("type").wttrdfin.sum() / wsum
    print("episodes per person 5+ by type:", x.reindex(TYPES).round(4).to_dict())
    print("joint propensity:", pd.DataFrame(prop).set_index("seg").propensity.round(3).to_dict())


if __name__ == "__main__":
    main()
