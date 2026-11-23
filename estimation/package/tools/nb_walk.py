"""Cells of the data walk-through (sections 1-4) of the model notebooks, by model family; used by build_notebooks.py.

Each function returns a list of notebook cells. The code of the cells reads the shipped files, mirrors the filters of the
preparation scripts of the folder (input/code, ../00_shared_prep/code) and, when RUN_DATA_PREP = True, runs those scripts in a
scratch copy and compares the rebuilt tables with the shipped ones.
"""
import nbformat as nbf


def md(s):
    return nbf.v4.new_markdown_cell(s.strip("\n"))


def code(s):
    return nbf.v4.new_code_cell(s.strip("\n"))


# =====================================================================================================================
# DAYMAP: survey files and split (all DAYMAP models)
# =====================================================================================================================
def rts_cells(intro=True):
    C = []
    if intro:
        C.append(md("""
### 1.1 The 2017/18 Regional Travel Survey

All DAYMAP models are estimated on the 2017/18 RTS of the Baltimore and Washington regions (weekday travel day). Three files
are shipped in `../00_shared_data/rts_2017_18/raw`:

- `RTS_raw_flat_data.csv.gz`: the survey as received, one row per trip with its household, person and vehicle fields;
- `rts_trips_clean.csv.gz`: the trips after the survey cleaning (one row per trip, departure / arrival in minutes);
- `rts_tours.csv.gz`: home-based tours, work-based subtours and open tours built from the clean trips.

The cleaning script of the last two files is not shipped; the cleaned files are the starting point of the preparation here.
Race and ethnicity fields are not read.
"""))
    C.append(code("""
flat, trips, tours = nt.rts_raw()
split = pd.read_csv(os.path.join(nt.ABIT_SHARED, "rts_2017_18", "split", "rts_split.csv"))
display(nt.rts_counts(flat, trips, tours, split))
show = ["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "dep_min", "arr_min", "travel_mode",
        "distance", "hhsize", "numvehicle", "hh_income_broad", "age", "employment_status", "student_status", "wttrdfin"]
trips[[c for c in show if c in trips]].head()
"""))
    C.append(md("""
### 1.2 Estimation and hold-out halves

The households are split in two halves (`make_rts_split.py`): strata of home county x household size (1 to 5+), a seeded
shuffle inside each stratum (seed 2026), then alternate assignment. Every model is estimated on the estimation half; the
hold-out (validation) half is the other half of the same survey and is not read by the estimation. With `RUN_DATA_PREP` the
split is rebuilt into a scratch folder and compared with the shipped `rts_split.csv`.
"""))
    C.append(code("""
REBUILD = os.path.join(OUT, "rebuild_check")            # scratch folder: provided files are never overwritten
if RUN_DATA_PREP:
    rc = nt.run_quiet(f"{sys.executable} make_rts_split.py", cwd=nt.ABIT_PREP, env={"ABIT_REBUILT": REBUILD})
    display(nt.compare_frames(pd.read_csv(os.path.join(REBUILD, "rts_2017_18", "split", "rts_split.csv")), split,
                              key=["household_id"], name="rts_split.csv"))
else:
    print("skipped (RUN_DATA_PREP = False)")
hh = flat.drop_duplicates("household_id").set_index("household_id")
hh["half"] = split.set_index("household_id")["half"]
t = pd.crosstab(hh["hhsize"].clip(upper=5).rename("household size (5 = 5+)"), hh["half"])
t.loc["all"] = t.sum()
t
"""))
    return C


# =====================================================================================================================
# DAYMAP location models 01-10
# =====================================================================================================================
# kind: dc = tour primaries / stops (prep_dc_taz.py), loc = WB / WAHB / SCH episodes (estimate_locations.records),
# wbs = first stop of a work-based outing (estimate_subtour_dest.records)
LOCATION = {
    "01_primary_destination_pooled": dict(kind="dc", rkind="primary", purposes=["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]),
    "02_stop_shopping": dict(kind="dc", rkind="stop", purposes=["SHOPPING"]),
    "03_stop_recreation": dict(kind="dc", rkind="stop", purposes=["RECREATION"]),
    "04_stop_accompanying": dict(kind="dc", rkind="stop", purposes=["ACCOMPANY"]),
    "05_stop_other": dict(kind="dc", rkind="stop", purposes=["OTHER"]),
    "06_outing_first_stop_destination": dict(kind="wbs", segments=["OTHER_wbs"]),
    "07_work_business_usual_workplace": dict(kind="loc", segments=["WORK_wbwork"]),
    "08_work_business_other_persons": dict(kind="loc", segments=["WORK_wbhome"]),
    "09_work_trips_home_workers": dict(kind="loc", segments=["WORK_wahb"]),
    "10_school_daycare_without_record_pooled": dict(kind="loc", segments=["EDUCATION_nonstud", "EDUCATION_daycare"]),
}

ANCHOR_TEXT = {
    "01_primary_destination_pooled": "home",
    "02_stop_shopping": "origin of the trip to the stop (anchor a)",
    "03_stop_recreation": "origin of the trip to the stop (anchor a)",
    "04_stop_accompanying": "origin of the trip to the stop (anchor a)",
    "05_stop_other": "origin of the trip to the stop (anchor a)",
    "06_outing_first_stop_destination": "usual workplace",
    "07_work_business_usual_workplace": "home (the second anchor is the usual workplace)",
    "08_work_business_other_persons": "home",
    "09_work_trips_home_workers": "home",
    "10_school_daycare_without_record_pooled": "home",
}


def location_cells(folder):
    cfg = LOCATION[folder]
    kind = cfg["kind"]
    C = [md("## 1. Raw data")]
    C += rts_cells()
    raw_name = {"dc": ("dc_rec_{h}_taz", "dc_cand_{h}_taz", "dc_cfg_{h}_taz"), "loc": ("loc_records_{h}", "loc_cand_{h}", None),
                "wbs": ("wbs_dest_records_{h}", "wbs_dest_cand_{h}", None)}[kind]
    what = {"dc": """one record per trip to a discretionary activity (shopping, recreation, accompanying, other) of a home-based tour:
either the primary activity of the tour (`kind = primary`, model 01) or an intermediate stop on a tour of any purpose
(`kind = stop`, models 02-05). Each record keeps its possible destination zones (`dc_cand`, tract or traffic zone of the
survey spread over model zones) and its possible anchor zones (`dc_cfg`).""",
            "loc": """one record per work trip outside the usual workplace (WB), work trip of a person working at home (WAHB), or school
trip of a person without a school record (non-students and children in daycare); the column `segment` separates the models
(07 WORK_wbwork, 08 WORK_wbhome, 09 WORK_wahb, 10 EDUCATION_nonstud and EDUCATION_daycare).""",
            "wbs": """one record per work-based outing: the first stop of an outing from the usual workplace that returns to it."""}[kind]
    C.append(md(f"""
### 1.3 Records of this model

The preparation turns the survey into the record files of `input/data/raw` ({', '.join('`' + r.format(h='<half>') + '.parquet`' for r in raw_name if r)}):
{what}
"""))
    C.append(code(f"""
CODE = os.path.join(FOLDER, "input", "code"); RAW = os.path.join(FOLDER, "input", "data", "raw")
HALVES = ["estimation", "validation"]
raw_rec = {{h: pd.read_parquet(os.path.join(RAW, f"{raw_name[0]}.parquet")) for h in HALVES}}
raw_cand = {{h: pd.read_parquet(os.path.join(RAW, f"{raw_name[1]}.parquet")) for h in HALVES}}
by = ["kind", "purpose"] if "kind" in raw_rec["estimation"] else ["segment"]
t = pd.concat({{h: raw_rec[h].groupby(by).size() for h in HALVES}}, axis=1).fillna(0).astype(int)
t.loc[("all",) * len(by) if len(by) > 1 else "all", :] = t.sum()
display(t)
cols = ["tripid", "person_id", "kind", "purpose", "segment", "type", "tour_purpose", "position", "geoid", "km_rep", "tod",
        "age", "occ", "hhsize", "autos", "inc_cls", "home_idx", "home_zone_idx", "work_idx", "n_dz", "n_cfg"]
raw_rec["estimation"][[c for c in cols if c in raw_rec["estimation"]]].head()
"""))

    # ---------------------------------------------------------------- 2. preparation
    C.append(md("## 2. Data preparation\n\n### 2.1 From survey trips to the records\n"))
    if kind == "dc":
        sel = "the primary activities of tours with purpose " + ", ".join(cfg["purposes"]) if cfg["rkind"] == "primary" \
            else f"the stops with purpose {cfg['purposes'][0]} (on tours of any purpose)"
        C.append(md(f"""
`input/code/prep_dc_taz.py` (function `build`) works on the home-based tours of `rts_tours.csv.gz` and the trips of
`rts_trips_clean.csv.gz` of one half. The filters are mirrored below in pandas with the script's own helpers (survey loading,
split, survey population). This model keeps {sel}.
The last step, locating every trip end in the model zones (survey traffic zone or tract spread over zones), needs the TAZ
crosswalks and runs only in the rebuild of section 2.2; its result is the shipped record file.
"""))
        stop_step = "" if cfg["rkind"] == "primary" else 's[-1] = ("discretionary stops before / after the primary activity of these tours", len(st))'
        sel_code = (f"rec = pr[pr.purpose_abit.isin({cfg['purposes']!r})].rename(columns={{'purpose_abit': 'purpose'}})" if cfg["rkind"] == "primary"
                    else f"rec = st[st.d_purpose.isin({cfg['purposes']!r})]")
        C.append(code(f"""
sys.path.insert(0, CODE)
import rts_common as RC, prep_dc_data as PD, dc_common as DC
S = RC.load_split()
tc = pd.read_csv(os.path.join(RC.RTS, "rts_trips_clean.csv.gz"), low_memory=False,
                 usecols=["tripid", "household_id", "person_id", "d_activity", "dep_min", "arr_min"])
tours_closed = RC.load_tours()            # anchor home or work (open tours dropped), purpose_abit of the primary activity
steps, N_RAW = {{}}, {{}}
KIND_STEP = lambda pr: ("tours with a shopping, recreation, accompany or other primary activity", len(pr))
for h in HALVES:
    P = PD.people(h)
    t = tc[tc.household_id.map(S).eq(h)].copy(); t["d_purpose"] = t.d_activity.map(RC.ACT_PURPOSE)
    s = [("tours in rts_tours.csv.gz (both halves)", len(tours))]
    tr = tours[tours.household_id.map(S).eq(h)]; s.append(("tours of the half", len(tr)))
    tr = tours_closed[tours_closed.household_id.map(S).eq(h) & tours_closed.anchor.eq("home")]; s.append(("home-based closed tours", len(tr)))
    tr = tr[~tr.primary_act.isin([1, -9])]; s.append(("primary activity known and not home", len(tr)))
    key = t.drop_duplicates(["person_id", "arr_min"]).set_index(["person_id", "arr_min"])
    hit = key.reindex(pd.MultiIndex.from_arrays([tr.person_id.values, tr.primary_arr.values]))
    tr = tr.assign(p_tripid=hit.tripid.values); tr = tr[tr.p_tripid.notna()]; s.append(("trip to the primary activity found", len(tr)))
    pr = tr[tr.purpose_abit.isin(DC.DISC)]
    s.append(KIND_STEP(pr))
    mm = t.merge(tr[["person_id", "start_min", "end_min", "primary_arr", "primary_dep", "purpose_abit", "p_tripid"]], on="person_id")
    mm = mm[(mm.dep_min >= mm.start_min) & (mm.arr_min <= mm.end_min) & (mm.d_purpose != "HOME") & (mm.tripid != mm.p_tripid)]
    pos = np.where(mm.arr_min < mm.primary_arr, "out", np.where(mm.dep_min >= mm.primary_dep, "in", ""))
    st = mm[(pos != "") & mm.d_purpose.isin(DC.DISC)].drop_duplicates("tripid")
    {stop_step}
    {sel_code}
    s.append(("records of this model (purpose, primary / stop)", len(rec)))
    rec = rec[rec.person_id.isin(P.index)]; s.append(("person in the survey population", len(rec)))
    sel = raw_rec[h][(raw_rec[h].kind == {cfg['rkind']!r}) & raw_rec[h].purpose.isin({cfg['purposes']!r})]
    s.append(("every trip end located in the model zones (shipped records)", len(sel)))
    steps[h] = s; N_RAW[h] = len(sel)
reasons = {{"tours of the half": "households of the other half",
           "home-based closed tours": "open tours and work-based subtours",
           "primary activity known and not home": "primary activity home or missing",
           "trip to the primary activity found": "no trip arrives at the primary activity time",
           "tours with a shopping, recreation, accompany or other primary activity": "work, school or home primary activity",
           "discretionary stops before / after the primary activity of these tours": "one row per stop (trips to work, school or home are not stops)",
           "records of this model (purpose, primary / stop)": "other purposes",
           "person in the survey population": "person not in the survey population (imputed members)",
           "every trip end located in the model zones (shipped records)": "destination, origin or home not located in a model zone"}}
nt.funnel2(steps, reasons)
"""))
    elif kind == "loc":
        segs = cfg["segments"]
        C.append(md(f"""
`input/code/estimate_locations.py` (function `records`) starts from the typed survey episodes of `../00_shared_data/rts_2017_18/episodes`
(one row per trip destination with its activity type, see `00_tasha_distributions`). The filters are mirrored below with
the script's helpers; the mirrored records are then compared with the shipped `loc_records_<half>.parquet` (same trip ids).
This model uses segment{'s' if len(segs) > 1 else ''} {', '.join(segs)}.
"""))
        C.append(code(f"""
sys.path.insert(0, CODE)
import te_common as TE, prep_dc_data as PD, dc_common as DC
SEGS = {segs!r}
steps, mirrored = {{}}, {{}}
for h in HALVES:
    e = TE.episodes(h); P = PD.people(h); ovg = set(PD.overlay().geoid)
    s = [("trips of the half", int((trips.household_id.map(split.set_index("household_id")["half"]) == h).sum())),
         ("episodes of persons in the survey population", len(e))]
    x = e[e.type.isin(["WB", "WAHB", "SCH"])]; s.append(("work outside the usual workplace, work at home, school", len(x)))
    x = x[~(x.type.eq("SCH") & x.seg.str.startswith("student"))]; s.append(("school trips of students removed", len(x)))
    seg = np.select([x.type.eq("WB") & x.seg.eq("worker_usual") & (x.wz > 0), x.type.eq("WB"), x.type.eq("WAHB"), x.seg.eq("toddler")],
                    ["WORK_wbwork", "WORK_wbhome", "WORK_wahb", "EDUCATION_daycare"], "EDUCATION_nonstud")
    x = x[np.isin(seg, SEGS)]; s.append(("segment of this model", len(x)))
    x = x[x.person_id.isin(P.index) & (x.hz > 0)]; s.append(("home zone known", len(x)))
    x = x[x.d_geoid.isin(ovg)]; s.append(("destination tract in the tract-to-zone overlay", len(x)))
    steps[h] = s; mirrored[h] = x
reasons = {{"episodes of persons in the survey population": "home episodes kept; trips of persons without a segment removed",
           "work outside the usual workplace, work at home, school": "other activity types",
           "school trips of students removed": "students keep their school record (school location of SILO)",
           "segment of this model": "other segments",
           "destination tract in the tract-to-zone overlay": "destination tract unknown or outside the zone system"}}
display(nt.funnel2(steps, reasons))
for h in HALVES:
    shipped = raw_rec[h][raw_rec[h].segment.isin(SEGS)]
    same = np.array_equal(np.sort(mirrored[h].tripid.to_numpy()), np.sort(shipped.tripid.to_numpy()))
    print(f"{{h}}: mirrored {{len(mirrored[h]):,}} records, shipped {{len(shipped):,}}; same trip ids: {{same}}")
"""))
    else:
        C.append(md("""
`input/code/estimate_subtour_dest.py` (function `records`) finds the work-based outings in the typed survey episodes
(`tasha_distributions.subtours`: a work episode at the usual workplace, one or more discretionary episodes, again a work
episode at the usual workplace) and keeps the first stop of each outing. Mirrored below and compared with the shipped
`wbs_dest_records_<half>.parquet`.
"""))
        C.append(code("""
sys.path.insert(0, CODE)
import te_common as TE, prep_dc_data as PD, dc_common as DC, tasha_distributions as TD
steps, mirrored = {}, {}
for h in HALVES:
    e = TE.episodes(h).sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    P = PD.people(h); ovg = set(PD.overlay().geoid)
    s = [("episodes of persons in the survey population", len(e))]
    e = TD.subtours(e)
    s.append(("stops of work-based outings", int(e.wbs.sum())))
    prev = e.groupby("person_id").wbs.shift(1, fill_value=False)
    x = e[e.wbs & ~prev.values].copy(); s.append(("first stop of each outing", len(x)))
    x["wz"] = e.loc[x.wbs_root.values].wz.values
    x = x[x.person_id.isin(P.index) & (x.wz > 0)]; s.append(("workplace zone known", len(x)))
    x = x[x.d_geoid.isin(ovg)]; s.append(("destination tract in the tract-to-zone overlay", len(x)))
    steps[h] = s; mirrored[h] = x
reasons = {"stops of work-based outings": "episodes that are not stops of an outing from the usual workplace",
           "first stop of each outing": "second and later stops (they belong to the stop model of the outing)",
           "destination tract in the tract-to-zone overlay": "destination tract unknown or outside the zone system"}
display(nt.funnel2(steps, reasons))
for h in HALVES:
    same = np.array_equal(np.sort(mirrored[h].tripid.to_numpy()), np.sort(raw_rec[h].tripid.to_numpy()))
    print(f"{h}: mirrored {len(mirrored[h]):,} records, shipped {len(raw_rec[h]):,}; same trip ids: {same}")
"""))

    # rebuild
    if kind == "dc":
        rebuild_txt = """`prep_dc_taz.py` (locating the trip ends, writing `dc_rec`, `dc_cand`, `dc_cfg` of both halves), then
`build_estimation_tables.py` and `build_biogeme_data.py` are run in a scratch copy of `input/code` next to this folder
(the scripts write into their own `input/data`; the shipped files are not touched), and every rebuilt table is compared
with the shipped one. About 5-8 min. The script's own final comparison with an older record file is not run (that file is
not shipped)."""
        driver = "import prep_dc_taz as T; LOC = T.Locator(); [T.build(h, LOC) for h in ('estimation', 'validation')]"
        raw_files = "[]"
    elif kind == "loc":
        rebuild_txt = """`estimate_locations.records` (record files of both halves), `build_estimation_tables.py` and
`build_biogeme_data.py` are run in a scratch copy of `input/code` next to this folder (the scripts write into their own
`input/data`; the shipped files are not touched), and every rebuilt table is compared with the shipped one. About 2-3 min."""
        driver = "import estimate_locations as L; L.records('estimation'); L.records('validation')"
        raw_files = "[]"
    else:
        rebuild_txt = """`estimate_subtour_dest.records` (record files of both halves), `build_estimation_tables.py` and
`build_biogeme_data.py` are run in a scratch copy of `input/code` next to this folder (the scripts write into their own
`input/data`; the shipped files are not touched), and every rebuilt table is compared with the shipped one. About 2-3 min."""
        driver = "import estimate_subtour_dest as L; L.records('estimation'); L.records('validation')"
        raw_files = "[]"
    C.append(md(f"### 2.2 Rebuild check\n\n{rebuild_txt}"))
    C.append(code(f"""
if RUN_DATA_PREP:
    t0 = time.time()
    SCR = nt.scratch_tree(FOLDER, raw_files={raw_files})
    SCODE = os.path.join(SCR, "input", "code")
    nt.run({('python3 -c "' + driver + '"')!r}, cwd=SCODE)
    nt.run("python3 build_estimation_tables.py", cwd=SCODE)
    nt.run("python3 build_biogeme_data.py", cwd=SCODE)
    res = pd.concat([nt.compare_trees(os.path.join(SCR, "input", "data", "raw"), RAW, only=r"{raw_name[0].split('_{h}')[0]}|{raw_name[1].split('_{h}')[0]}"{'+ "|dc_cfg"' if kind == 'dc' else ''}),
                     nt.compare_trees(os.path.join(SCR, "input", "data", "estimation"), os.path.join(FOLDER, "input", "data", "estimation")).assign(half="estimation"),
                     nt.compare_trees(os.path.join(SCR, "input", "data", "holdout"), os.path.join(FOLDER, "input", "data", "holdout")).assign(half="hold-out")],
                    ignore_index=True)
    nt.drop_scratch(SCR)
    print(f"rebuild and comparison: {{(time.time() - t0) / 60:.1f}} min")
    display(res)
    nt.rebuild_verdict(res, glob.glob(os.path.join(FOLDER, "model", "estimate_*.py"))[0])
else:
    print("skipped (RUN_DATA_PREP = False): the shipped tables are used")
"""))

    # ---------------------------------------------------------------- 3. estimation data
    C.append(md(f"""
## 3. Choice set and estimation data

The alternatives are all 1,588 model zones (no sampling). The observed location of a record is not one zone: its survey
tract (or traffic zone) is spread over the zones it overlaps, with weights `b` (candidates), and the anchor of the record
({ANCHOR_TEXT[folder]}) can also be spread over several zones with weights `w` (configurations). The likelihood of record n is

  L_n = Σ_c w_c Σ_k b_k exp(V_c(z_k)) / Σ_j exp(V_c(j)),  j = 1 … 1,588.
"""))
    C.append(code("""
ZONES = pd.read_csv(os.path.join(nt.ABIT_SHARED, "zones", "zones_model_attributes.csv")).sort_values("idx").reset_index(drop=True)
ZONES["area_group"] = nt.area_group_of_county(ZONES.countyfips)

def read_tables(sub):
    base = os.path.join(FOLDER, "input", "data", sub)
    segs = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))) or [""]
    out = {}
    for k in ["records", "candidates", "configurations"]:
        out[k] = pd.concat([pd.read_parquet(os.path.join(base, s, f"{k}.parquet")).assign(**({"group": s or "all"} if k == "records" else {})) for s in segs], ignore_index=True)
    return out

EST, HOLD = read_tables("estimation"), read_tables("holdout")
display(pd.DataFrame({h: {k: f"{len(v):,}" for k, v in T.items()} for h, T in [("estimation", EST), ("hold-out", HOLD)]}))
rec, cand, cfg = EST["records"], EST["candidates"], EST["configurations"]
print("records by group:", rec.group.value_counts().to_dict())
fig, ax = nt.panels(3, ncol=3, w=4.2, h=2.8)
nt.bar(cand.groupby("rec").size().value_counts().sort_index(), "candidate zones of the observed location", "records", ax=ax[0])
nt.hist(cand.b, "weight b of a candidate zone", "candidate rows", bins=40, ax=ax[1])
nt.bar(cfg.groupby("rec").size().value_counts().sort_index(), "anchor configurations", "records", ax=ax[2])
plt.tight_layout(); plt.show()
ex = rec.rec[rec.rec.isin(cand.groupby("rec").size().pipe(lambda s: s[s > 1].index))].iloc[0]
print(f"example record {ex}: candidate zones and anchor configurations (zone index 0..1587 -> zone id)")
display(cand[cand.rec == ex].assign(zone_id=lambda d: ZONES.id.values[d.zidx]))
display(cfg[cfg.rec == ex].assign(anchor_zone_id=lambda d: ZONES.id.values[d.home_idx]))
"""))
    C.append(md("""
The Biogeme table is wide: one row per record, with the chooser flags `f_*`, the candidates (`cz_k`, `b_k`, zone attributes
`cand_*_k`), the configurations (`w_c`, `za_c`, `zb_c`) and, for every configuration c and zone j, the zone variables
`imp_c_j` (car km or detour km), `cgt_c_j` (car generalised time) and `ls_c_j` (mode-choice logsum) where the model uses them.
It is stored in parts of at most 1,000 records.
"""))
    C.append(code("""
est = os.path.join(FOLDER, "input", "data", "estimation")
meta = json.load(open(os.path.join(est, "biogeme_meta.json")))
print({k: v for k, v in meta.items() if k != "parts"})
parts = sorted(glob.glob(os.path.join(est, "biogeme_part*.parquet")))
p0 = pd.read_parquet(parts[0])
stem = pd.Series([re.sub(r"(_\\d+)+$", "", c) for c in p0.columns])
groups = stem.groupby(stem, sort=False).size().rename("columns").to_frame()
print(f"{len(parts)} parts; part 0: {p0.shape[0]:,} records x {p0.shape[1]:,} columns")
display(groups.T)
dd = os.path.join(est, "data_dictionary.csv")
pd.read_csv(dd) if os.path.exists(dd) else None
"""))

    # ---------------------------------------------------------------- 4. descriptives
    C.append(md(f"""
## 4. Descriptive statistics

All shares below are over records (the estimation is unweighted); a record with several candidate zones or configurations
counts with the weights b (normalised per record) and w. Distances are car distances (skim of the 2016 base, km) from the
{ANCHOR_TEXT[folder]} to the zones of the observed location.
"""))
    C.append(code("""
SK = DC.skims()["d"]                                   # car km, zone index x zone index

def chosen(T):
    c = T["candidates"].copy(); c["bn"] = c.b / c.groupby("rec").b.transform("sum")
    g = c.merge(T["configurations"][["rec", "home_idx", "w"]], on="rec")
    g["p"] = g.bn * g.w                                # weight of (candidate zone, configuration)
    g["km"] = SK[g.home_idx.to_numpy(), g.zidx.to_numpy()]
    g["area_group"] = pd.Categorical(ZONES.area_group.astype(str).to_numpy()[g.zidx.to_numpy()], categories=nt.AREA_GROUPS, ordered=True)
    return g.merge(T["records"][["rec", "group"]], on="rec")

CH, CHH = chosen(EST), chosen(HOLD)
area = (CH.groupby(["group", "area_group"], observed=False).p.sum().unstack(0))
area = 100 * area / area.sum()
display(area.round(2).rename_axis("area group of the chosen zone"))
fig, ax = plt.subplots(figsize=(7.5, 3.2))
(area.mean(axis=1) if area.shape[1] == 1 else area).plot.barh(ax=ax, color=[nt.OBS, nt.LIGHT, "#6b6b6b", "#c4c4c4"][:area.shape[1]], width=0.8, legend=area.shape[1] > 1)
ax.invert_yaxis(); ax.set_xlabel("share of records (%)"); ax.set_ylabel("")
plt.tight_layout(); plt.show()
"""))
    C.append(md("Share of the chosen zones by area of the study region (the survey covers the Baltimore and Washington regions)."))
    C.append(code("""
edges = [0, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 50, 301]
labels = ["0-1", "1-2", "2-3", "3-5", "5-7.5", "7.5-10", "10-15", "15-20", "20-30", "30-50", "50+"]
groups_ = sorted(CH.group.unique())
fig, ax = nt.panels(len(groups_) + 1, ncol=min(3, len(groups_) + 1), w=4.3, h=2.9)
for a, g in zip(ax, groups_):
    x = CH[CH.group == g]
    a.hist(x.km.clip(upper=80), bins=np.arange(0, 81, 2), weights=x.p, color=nt.OBS)
    a.set_xlabel(f"car km to the chosen zone, 80 = 80+{'' if g == 'all' else ' (' + g + ')'}"); a.set_ylabel("records")
r = rec.km_rep.clip(upper=80)
ax[-1].hist(r.dropna(), bins=np.arange(0, 81, 2), color=nt.LIGHT); ax[-1].set_xlabel("reported trip distance, km, 80 = 80+ (all)"); ax[-1].set_ylabel("records")
plt.tight_layout(); plt.show()
band = pd.DataFrame({g: nt.binned(CH[CH.group == g].km, edges, labels, CH[CH.group == g].p) for g in groups_}).round(2)
band.index.name = "car km (band)"
med = np.interp(0.5, (CH.sort_values("km").p.cumsum() / CH.p.sum()).to_numpy(), CH.sort_values("km").km.to_numpy())
print(f"median car distance to the chosen zone {med:.1f} km; {band.iloc[:6].sum().mean():.0f} % of the records within 10 km")
band.T
"""))
    C.append(md("Car distance from the anchor to the chosen zone (b- and w-weighted) and the reported trip distance; the table gives the shares by distance band."))
    C.append(code("""
inc_lab = {0: "<50k", 1: "50-100k", 2: "100k+"}; tod_lab = {0: "AM 6-9", 1: "midday 9-15", 2: "PM 15-19", 3: "evening"}
items = [("hhsize", "household size (6 = 6+)", lambda s: s.clip(upper=6)), ("autos", "cars (4 = 4+)", lambda s: s.clip(upper=4)),
         ("inc_cls", "household income ($/year)", lambda s: s.map(inc_lab)), ("occ", "occupation (1 worker, 2 unemployed, 3 student, 4 retired)", lambda s: s),
         ("tod", "arrival time", lambda s: s.map(tod_lab)), ("position", "stop position (out / in)", lambda s: s.replace("", np.nan)),
         ("tour_purpose", "purpose of the tour", lambda s: s.replace("", np.nan)), ("multi", "tour with stops (1)", lambda s: s)]
items = [i for i in items if i[0] in rec and rec[i[0]].astype(str).replace("", np.nan).nunique() > 1]
fig, ax = nt.panels(len(items) + 1, ncol=3, w=4.3, h=2.8)
for a, (c, lab, f) in zip(ax, items):
    v = f(rec[c]).value_counts()
    v = v.reindex([x for x in (list(inc_lab.values()) if c == "inc_cls" else list(tod_lab.values()) if c == "tod" else sorted(v.index)) if x in v.index])
    nt.bar(100 * v / v.sum(), lab, "share of records (%)", ax=a, rot=30 if c in ("tod", "tour_purpose", "inc_cls") else 0)
nt.hist(rec.age, "age (years)", "records", bins=range(0, 96, 5), ax=ax[-1])
plt.tight_layout(); plt.show()
"""))
    C.append(md("Explanatory variables of the choosers (the model uses them as flags `f_*` interacted with the impedance)."))
    C.append(code("""
REF = pd.read_csv(os.path.join(FOLDER, "model", "reference_estimates.csv"))
attr = sorted(set(REF["project_name"].astype(str).str.extract(r"lnx_([a-z]+)")[0].dropna()))
print("attraction variable(s) of this model, ln(1 + x):", attr)
zc = {"ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school enrolment", "pop": "persons"}
fig, ax = nt.panels(6, ncol=3, w=4.3, h=2.8)
for a, (c, lab) in zip(ax, list(zc.items())):
    a.hist(np.log1p(ZONES[c]), bins=40, color=nt.OBS)
    a.set_xlabel(f"ln(1 + {lab}) of a zone" + ("  [attraction of this model]" if c in attr else "")); a.set_ylabel("zones")
ax[5].hist(np.log(ZONES.area_km2.clip(lower=0.05)), bins=40, color=nt.OBS); ax[5].set_xlabel("ln(zone area, km²)"); ax[5].set_ylabel("zones")
plt.tight_layout(); plt.show()
zch = CH.groupby("zidx").p.sum()
comp = pd.DataFrame({"all zones (mean)": ZONES[list(zc) + ["area_km2"]].mean(),
                     "chosen zones (record-weighted mean)": ZONES[list(zc) + ["area_km2"]].iloc[zch.index].mul(zch.values, axis=0).sum() / zch.sum()}).round(1)
comp.index = [zc.get(i, "zone area (km²)") for i in comp.index]
comp
"""))
    C.append(md("Zone attractions over the 1,588 zones (the attraction variable of this model is marked), and the mean attraction and area of the chosen zones against all zones."))
    C.append(code("""
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
nt.zone_map(pd.Series(zch.values, index=ZONES.id.values[zch.index]), "records (chosen zone, b-weighted)", ax=ax[0], log=True)
home = EST["configurations"].groupby("home_idx").w.sum()
nt.zone_map(pd.Series(home.values, index=ZONES.id.values[home.index]), "records (anchor zone, w-weighted)", ax=ax[1], log=True)
ax[0].set_title("chosen zones", fontsize=10); ax[1].set_title("anchor zones", fontsize=10)
plt.tight_layout(); plt.show()
"""))
    C.append(md("""
Chosen and anchor zones of the estimation half (Baltimore-Washington area; white: no record). The survey trip weight `w`
of the records is not used by the estimation:
"""))
    C.append(code("""
print(f"survey trip weight w of the records: mean {rec.w.mean():.1f}, min {rec.w.min():.1f}, max {rec.w.max():.1f} (not used by the likelihood)")
a = CH.groupby("area_group", observed=False).p.sum(); b = CHH.groupby("area_group", observed=False).p.sum()
t = pd.DataFrame({"estimation half %": 100 * a / a.sum(), "hold-out half %": 100 * b / b.sum()})
db = pd.DataFrame({"estimation half %": nt.binned(CH.km, edges, labels, CH.p), "hold-out half %": nt.binned(CHH.km, edges, labels, CHH.p)})
t = pd.concat({"area group": t, "car km": db}).round(2)
t["difference (points)"] = (t.iloc[:, 0] - t.iloc[:, 1]).round(2)
print(f"records: estimation {EST['records'].shape[0]:,}, hold-out {HOLD['records'].shape[0]:,}; largest difference of a share: {t['difference (points)'].abs().max():.1f} points")
t
"""))
    C.append(md("Shares of the chosen areas and distance bands in the two halves; the largest difference is printed above the table."))
    return C


# =====================================================================================================================
# DAYMAP tour mode 14-19
# =====================================================================================================================
MODE = {
    "14_tour_mode_work": dict(seg="work", joint=False),
    "15_tour_mode_school": dict(seg="school", joint=False),
    "16_tour_mode_shopping": dict(seg="shopping", joint=False),
    "17_tour_mode_other": dict(seg="other", joint=False),
    "18_tour_mode_joint_shopping": dict(seg="shopping", joint=True),
    "19_tour_mode_joint_other": dict(seg="other", joint=True),
}
MODE_LAB = '{1: "car driver", 2: "walk", 3: "bike", 4: "car passenger", 5: "bus", 6: "train"}'


def episode_rebuild_cells():
    """Shared episodes rebuild check (build_episodes.py / te_common in the shared chain)."""
    return code("""
if RUN_DATA_PREP:
    nt.run(f"{sys.executable} build_episodes.py", cwd=nt.ABIT_PREP, env={"ABIT_REBUILT": REBUILD}, quiet=True)
    display(nt.compare_trees(os.path.join(REBUILD, "rts_2017_18", "episodes"), os.path.join(nt.ABIT_SHARED, "rts_2017_18", "episodes")))
else:
    print("skipped (RUN_DATA_PREP = False)")
""")


def mode_cells(folder):
    cfg = MODE[folder]; seg = cfg["seg"]; joint = cfg["joint"]
    C = [md("## 1. Raw data")]
    C += rts_cells()
    C.append(md(f"""
### 1.3 Records of this model

`input/data/raw/tours_<half>.parquet` holds the home-based tours of both halves (one row per tour: purpose, main activity,
home and main zone, chosen mode, level of service of every mode); `gc_bio_<segment>_s50` / `gc_hold_<segment>_s50` are the
tours of one segment whose chosen mode is available{', `wesml_est` / `wesml_hold` the WESML weights of the work tours' if seg == 'work' else ''}.
This model uses the {'joint ' if joint else ''}{seg} tours{' (one record per joint household group)' if joint else ''}.
"""))
    C.append(code(f"""
CODE = os.path.join(FOLDER, "input", "code"); RAW = os.path.join(FOLDER, "input", "data", "raw")
HALVES = ["estimation", "validation"]; GC = {{"estimation": "gc_bio_{seg}_s50", "validation": "gc_hold_{seg}_s50"}}
TOURS = {{h: pd.read_parquet(os.path.join(RAW, f"tours_{{h}}.parquet")) for h in HALVES}}
GCT = {{h: pd.read_parquet(os.path.join(RAW, GC[h] + ".parquet")) for h in HALVES}}
display(pd.concat({{h: TOURS[h].groupby("segment").size() for h in HALVES}}, axis=1).rename_axis("tours by segment"))
display(pd.crosstab(TOURS["estimation"].segment, TOURS["estimation"].choice2, margins=True).rename_axis(index="segment (estimation half)", columns="chosen mode"))
cols = ["person_id", "purpose", "type", "segment", "hz", "mz", "start", "end", "choice", "choice2", "joint", "km", "car_min",
        "bus_ok", "train_ok", "age", "lic", "hhsize", "autos", "inc_year", "w"]
TOURS["estimation"][cols].head()
"""))
    C.append(md("""
## 2. Data preparation

### 2.1 From survey episodes to tours

`../00_shared_prep/code/prep_tours.py` cuts the typed episodes of each person-day into home-based chains (a chain runs
from a departure from home to the next arrival at home), keeps chains that start and end at home, drops tours with an
air, water or other trip, keeps persons of the survey population and tours whose home and main zone are in the zone
system. The main activity is the work episode, else school, else the longest episode; the tour mode is the highest mode
used on any trip (transit > car driver > car passenger > bike > walk). With `RUN_DATA_PREP` the shared chain (episodes,
tours, segment tables{', WESML weights' if True else ''}) is rebuilt into a scratch folder; its step counts and the comparison
with the shipped files follow.
"""))
    C.append(code("""
REBUILD = os.path.join(OUT, "rebuild_check")
if RUN_DATA_PREP:
    t0 = time.time()
    ENV = {"ABIT_REBUILT": REBUILD, "WESML_TOURS": os.path.join(REBUILD, "mode_choice_work")}
    nt.run(f"{sys.executable} prep_tours.py", cwd=nt.ABIT_PREP, env=ENV, quiet=True)
    nt.run(f"{sys.executable} prep_tours.py biodata2", cwd=nt.ABIT_PREP, env=ENV, quiet=True)
    nt.run(f"{sys.executable} wesml_targets.py", cwd=nt.ABIT_PREP, env=ENV, quiet=True)
    st = {h: pd.read_csv(os.path.join(REBUILD, "mode_choice_inputs", f"tour_build_{h}.csv")) for h in HALVES}
    def kept(d):
        out, n = [], None
        for step, k in zip(d.step, d.n):
            n = n - k if step.startswith("dropped") else k
            out.append((step.replace("dropped: ", "without "), n))
        return out
    display(nt.funnel2({h: kept(st[h]) for h in HALVES},
                       {"without air / water / other mode": "tour with an air, water or other trip",
                        "persons of the survey-population input": "person not in the survey population",
                        "home and main zone in the zone system": "home or main-activity tract outside the zone system"}))
    W_ = os.path.join(REBUILD, "mode_choice_work")
    pairs = [(os.path.join(REBUILD, "rts_2017_18", "episodes", f"episodes_{h}.parquet"), os.path.join(nt.ABIT_SHARED, "rts_2017_18", "episodes", f"episodes_{h}.parquet")) for h in HALVES]
    pairs += [(os.path.join(W_, f"tours_{h}.parquet"), os.path.join(RAW, f"tours_{h}.parquet")) for h in HALVES]
    pairs += [(os.path.join(W_, GC[h] + ".parquet"), os.path.join(RAW, GC[h] + ".parquet")) for h in HALVES]
    pairs += [(os.path.join(REBUILD, "mode_choice_inputs", "parking_paid_share.csv"), os.path.join(nt.ABIT_SHARED, "mode_choice_inputs", "parking_paid_share.csv"))]
    pairs += [(os.path.join(REBUILD, "mode_choice_inputs", "wesml", f), os.path.join(RAW, f)) for f in ["wesml_est.parquet", "wesml_hold.parquet"] if os.path.exists(os.path.join(RAW, f))]
    res_shared = pd.concat([nt.compare_frames(nt.read_table(a), nt.read_table(b), name=os.path.basename(b)) for a, b in pairs], ignore_index=True)
    print(f"shared chain rebuilt in {(time.time() - t0) / 60:.1f} min")
    display(res_shared)
else:
    print("skipped (RUN_DATA_PREP = False)")
"""))
    if not joint:
        C.append(md(f"""
### 2.2 From tours to the estimation table

The model keeps the tours of segment *{seg}* whose chosen mode is available (availability rules in section 3); the shipped
segment table `{'gc_bio_' + seg + '_s50'}` is that selection, and `build_estimation_tables.py` keeps its numeric columns
{'and adds the WESML weight ' if seg == 'work' else ''}(`input/data/estimation/tours.parquet`). Tours dropped because the
chosen mode was not available, by mode:
"""))
        C.append(code("""
steps = {}
for h in HALVES:
    t = TOURS[h]
    steps[h] = [("home-based tours", len(t)), ("tours of the segment", int((t.segment == SEGMENT).sum())),
                ("chosen mode available (estimation table)", len(GCT[h]))]
display(nt.funnel2(steps, {"tours of the segment": "other segments", "chosen mode available (estimation table)": "chosen mode not available"}))
drop = pd.concat({h: TOURS[h][TOURS[h].segment == SEGMENT].choice2.value_counts() - GCT[h].choice.value_counts().reindex(TOURS[h][TOURS[h].segment == SEGMENT].choice2.value_counts().index).fillna(0) for h in HALVES}, axis=1)
drop.astype(int).rename_axis("chosen mode").rename(columns=lambda c: f"{c}: dropped")
""".replace("SEGMENT", repr(seg))))
    else:
        C.append(md(f"""
### 2.2 From tours to joint household groups

`m11_joint_group.groups` keeps the {seg} tours with the chosen mode available that belong to a joint household episode
(the same activity with other household members) and makes one record per group of two or more member tours: the
representative is the oldest member who can drive (else the oldest member), the group mode is car driver when any member
drove. Modes that no estimation group chose are not offered, and hold-out groups that chose them are dropped
(`build_estimation_tables.py`).
"""))
        C.append(code(f"""
sys.path.insert(0, CODE)
import m11_joint_group as M11
here = os.getcwd()
G_ = {{h: M11.groups(h, {seg!r}) for h in HALVES}}
os.chdir(here)
EST_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "estimation", "tours.parquet"))
HOLD_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "tours.parquet"))
NT = {{"estimation": len(EST_T), "validation": len(HOLD_T)}}
steps = {{}}
for h in HALVES:
    t = TOURS[h]
    steps[h] = [("home-based tours", len(t)), ("tours of the segment", int((t.segment == {seg!r}).sum())),
                ("chosen mode available", len(GCT[h])), ("member tours of joint groups (2+ members)", int(G_[h].n_members.sum())),
                ("one record per group", len(G_[h])), ("group mode offered (estimation table)", NT[h])]
nt.funnel2(steps, {{"tours of the segment": "other segments", "chosen mode available": "chosen mode not available",
                   "member tours of joint groups (2+ members)": "individual tours, or a joint episode with one tour in the data",
                   "one record per group": "one representative member per group",
                   "group mode offered (estimation table)": "mode chosen by no estimation group"}})
"""))
    C.append(md("""
### 2.3 Rebuild check of the estimation table

`build_estimation_tables.py` is run in a scratch copy of `input/code` whose `input/data/raw` holds the rebuilt tours and
segment tables of 2.1; the rebuilt `tours.parquet` of both halves is compared with the shipped one.
"""))
    C.append(code("""
if RUN_DATA_PREP:
    import shutil
    SCR = nt.scratch_tree(FOLDER)
    W_ = os.path.join(REBUILD, "mode_choice_work")
    for f in os.listdir(RAW):
        src = os.path.join(W_, f) if os.path.exists(os.path.join(W_, f)) else os.path.join(REBUILD, "mode_choice_inputs", "wesml", f)
        if f.endswith(".parquet") and os.path.exists(src):
            shutil.copy2(src, os.path.join(SCR, "input", "data", "raw", f))
    print("raw files of the scratch copy (rebuilt):", sorted(os.listdir(os.path.join(SCR, "input", "data", "raw"))))
    nt.run(f"{sys.executable} build_estimation_tables.py", cwd=os.path.join(SCR, "input", "code"))
    res = pd.concat([nt.compare_trees(os.path.join(SCR, "input", "data", h), os.path.join(FOLDER, "input", "data", h)).assign(half=h) for h in ["estimation", "holdout"]], ignore_index=True)
    nt.drop_scratch(SCR)
    display(res)
    nt.rebuild_verdict(pd.concat([res_shared, res], ignore_index=True), glob.glob(os.path.join(FOLDER, "model", "estimate_*.py"))[0])
else:
    print("skipped (RUN_DATA_PREP = False)")
"""))
    # ---------------------------------------------------------------- 3
    C.append(md(f"""
## 3. Choice set and estimation table

Six alternatives (code `y`): 1 car driver, 2 walk, 3 bike, 4 car passenger, 5 bus, 6 train. Availability: car driver if the
person is 16+, has a licence and the household has a car (and the household's cars are not all used by other members'
overlapping car-driver tours); car passenger always; walk if the round trip is at most 12 km, bike at most 50 km; bus and
train if a transit path exists (walk access; drive access at the home end for train) and home and destination differ.
Level of service: car time and cost from the period skims, transit time and fare, generalised cost `gc_*` (minutes, value
of time 50 % of the wage rate){'; for a joint group the representative member carries the variables, car driver is available if any member can drive' if joint else ''}.
"""))
    C.append(code(f"""
LAB = {MODE_LAB}
EST_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "estimation", "tours.parquet"))
HOLD_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "tours.parquet"))
print(f"estimation table: {{EST_T.shape[0]:,}} rows x {{EST_T.shape[1]}} columns; hold-out {{HOLD_T.shape[0]:,}} rows")
av = [c for c in EST_T.columns if c.startswith("av_")]
t = pd.DataFrame({{"available (% of records)": (100 * (EST_T[av] > 0).mean()).round(1)}})
t.index = [c[3:] for c in av]
display(t.T)
display(EST_T.head())
dd = os.path.join(FOLDER, "input", "data", "estimation", "data_dictionary.csv")
pd.read_csv(dd) if os.path.exists(dd) else None
"""))
    # ---------------------------------------------------------------- 4
    C.append(md("## 4. Descriptive statistics\n\n### Observed mode shares" + (" (unweighted, survey-weighted and WESML-weighted)" if seg == "work" else " (unweighted and survey-weighted)" if not joint else "")))
    wcode = ""
    if not joint:
        wcode = """
assert len(GCT["estimation"]) == len(EST_T) and (GCT["estimation"].y.to_numpy() == EST_T.y.to_numpy()).all()   # row-aligned
"""
    C.append(code(wcode + f"""
sh = nt.shares_table(EST_T.y.map(LAB), None if {joint} else GCT["estimation"].w)
if "wesml" in EST_T:
    ws = EST_T.groupby(EST_T.y.map(LAB)).wesml.sum(); sh["WESML-weighted share %"] = (100 * ws / ws.sum()).round(2)
sh = sh.reindex([v for v in LAB.values() if v in sh.index])
display(sh)
cols_ = [c for c in sh.columns if "share" in c]
nt.grouped_bars(sh[cols_].rename(columns={{"share %": "unweighted", "weighted share %": "survey weight", "WESML-weighted share %": "WESML weight"}}), "chosen mode", "share of {'groups' if joint else 'tours'} (%)", colors=[nt.OBS, nt.LIGHT, "#8a8a8a"], rot=0)
plt.tight_layout(); plt.show()
"""))
    C.append(md("Observed mode shares of the estimation half; the survey weight (and the WESML weight for work tours) re-weights them to the population."))
    C.append(code("""
fig, ax = nt.panels(2, ncol=2, w=6, h=3)
labs = [lab for m, lab in LAB.items() if (EST_T.y == m).any()]
data = [EST_T.km[EST_T.y == m].clip(lower=0.5) for m, lab in LAB.items() if (EST_T.y == m).any()]
bp = ax[0].boxplot(data, vert=False, tick_labels=[f"{l} ({len(d)})" for l, d in zip(labs, data)], showfliers=False, patch_artist=True,
                   medianprops=dict(color="white"), boxprops=dict(facecolor=nt.OBS, color=nt.OBS), whiskerprops=dict(color=nt.OBS), capprops=dict(color=nt.OBS))
ax[0].set_xscale("log"); ax[0].set_xlabel("round-trip car distance (km, log scale)"); ax[0].invert_yaxis()
b = nt.binned(EST_T.km, [0, 5, 10, 20, 40, 80, 1e9], ["0-5", "5-10", "10-20", "20-40", "40-80", "80+"])
nt.bar(b, "round-trip car distance (km)", "share of records (%)", ax=ax[1])
plt.tight_layout(); plt.show()
print(f"median round-trip distance {EST_T.km.median():.1f} km; by mode:", EST_T.groupby(EST_T.y.map(LAB)).km.median().round(1).to_dict())
"""))
    C.append(md("Round-trip car distance by chosen mode (box: quartiles, line: median, whiskers: 1.5 interquartile range); walk and bike tours are the shortest."))
    C.append(code("""
inc = pd.cut(EST_T.inc_year, [-1, 50000, 100000, 150000, 1e12], labels=["<50k", "50-100k", "100-150k", "150k+"])
items = [(EST_T.hhsize.clip(upper=6), "household size (6 = 6+)"), (EST_T.autos.clip(upper=4), "cars (4 = 4+)"),
         (inc, "household income ($/year)"), (EST_T.lic, "driving licence (1 yes)"), (EST_T.kids, "member under 18 (1 yes)"),
         (EST_T.stops.clip(upper=4), "stops on the tour (4 = 4+)")]
fig, ax = nt.panels(len(items) + 2, ncol=4, w=3.4, h=2.7)
for a, (v, lab) in zip(ax, items):
    c = v.value_counts().sort_index(); nt.bar(100 * c / c.sum(), lab, "share (%)", ax=a, rot=30 if "income" in lab else 0)
nt.hist(EST_T.age, "age (years)", "records", bins=range(0, 96, 5), ax=ax[-2])
nt.hist(EST_T.t_CD.clip(upper=180), "car time of the tour (min)", "records", bins=40, ax=ax[-1])
plt.tight_layout(); plt.show()
"""))
    C.append(md("Explanatory variables of the records: household, person and tour (the representative member for joint groups)."))
    if not joint:
        C.append(code("""
g = GCT["estimation"]
per = g.pout.map({0: "AM 6-9", 1: "midday 9-15", 2: "PM 15-19", 3: "night"}).value_counts().reindex(["AM 6-9", "midday 9-15", "PM 15-19", "night"])
ZA = pd.read_csv(os.path.join(nt.ABIT_SHARED, "zones", "zones_model_attributes.csv")).sort_values("idx").reset_index(drop=True)
nt.bar(100 * per / per.sum(), "period of the main activity", "share of tours (%)", rot=0, figsize=(5.5, 2.8)); plt.tight_layout(); plt.show()
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
nt.zone_map(pd.Series(g.groupby("h").size().pipe(lambda s: pd.Series(s.values, index=ZA.id.values[s.index]))), "tours (home zone)", ax=ax[0], log=True)
nt.zone_map(pd.Series(g.groupby("m").size().pipe(lambda s: pd.Series(s.values, index=ZA.id.values[s.index]))), "tours (main-activity zone)", ax=ax[1], log=True)
ax[0].set_title("home zones", fontsize=10); ax[1].set_title("main-activity zones", fontsize=10)
plt.tight_layout(); plt.show()
tr = g.groupby(g.m.map(lambda i: ZA.countyfips.iat[i]).pipe(nt.area_group_of_county), observed=False).y.apply(lambda y: 100 * (y >= 5).mean())
print("transit share (%) by area group of the main-activity zone:", tr.round(1).to_dict())
"""))
        C.append(md("Period of the main activity, and home and main-activity zones of the tours (Baltimore-Washington area)."))
    else:
        C.append(md("The group table keeps no zones; the zones of the member tours are in `tours_<half>.parquet`."))
    if seg == "work":
        C.append(md("""
### WESML weights

Work tours are re-weighted to the ACS 2017-19 commute-mode shares of 23 county strata: w = Q(mode | stratum) / H(mode | stratum),
Q from the ACS, H the unweighted share of the survey tours. The weights enter the log-likelihood (w · ln P).
"""))
        C.append(code("""
WE = pd.read_parquet(os.path.join(RAW, "wesml_est.parquet"))
print(f"WESML weight: mean {EST_T.wesml.mean():.3f}, min {EST_T.wesml.min():.3f}, max {EST_T.wesml.max():.3f}, {WE.stratum.nunique()} strata")
display(EST_T.groupby(EST_T.y.map(LAB)).wesml.agg(["mean", "min", "max"]).round(3).rename_axis("mode"))
tg = pd.read_csv(os.path.join(nt.ABIT_SHARED, "mode_choice_inputs", "wesml", "wesml_targets.csv"))
tg = tg[tg.half.eq("est")]
tot = tg.drop_duplicates("stratum").n_tours.sum(); q = tg.assign(x=tg.acs * tg.n_tours).groupby("mode").x.sum() / tot
hh_ = tg.assign(x=tg.survey_unweighted * tg.n_tours).groupby("mode").x.sum() / tot
fig, ax = plt.subplots(1, 2, figsize=(11, 3.2))
nt.hist(EST_T.wesml, "WESML weight", "work tours", bins=50, ax=ax[0])
nt.grouped_bars(pd.DataFrame({"ACS commute share": 100 * q, "survey tours (unweighted)": 100 * hh_}), "mode", "share (%)", ax=ax[1], colors=[nt.LIGHT, nt.OBS])
plt.tight_layout(); plt.show()
"""))
        C.append(md("The survey over-represents train commuters against the ACS: their weights are below 1, those of bus and car passenger above 1."))
    C.append(md("### Estimation half vs hold-out half"))
    C.append(code("""
t = nt.half_comparison(EST_T.y.map(LAB), HOLD_T.y.map(LAB), "chosen mode")
print(f"records: estimation {len(EST_T):,}, hold-out {len(HOLD_T):,}; largest difference of a share: {t['difference (points)'].abs().max():.1f} points")
t
"""))
    C.append(md("Unweighted mode shares of the two halves."))
    return C




# =====================================================================================================================
# DAYMAP 11-13: work-based outings and return home (binary logit), 20: transit leg mode
# =====================================================================================================================
def _scratch_rebuild(raw_keep, driver=None, shared_tours=False):
    """Rebuild cell: build_estimation_tables.py in a scratch copy whose raw folder holds only raw_keep (the other raw files are
    rebuilt by the scripts); compare raw files and estimation tables with the shipped ones."""
    pre = ""
    if shared_tours:
        pre = """
    nt.run(f"{sys.executable} prep_tours.py", cwd=nt.ABIT_PREP, env={"ABIT_REBUILT": REBUILD}, quiet=True)
    import shutil
    for h in HALVES:
        shutil.copy2(os.path.join(REBUILD, "mode_choice_work", f"tours_{h}.parquet"), os.path.join(SCR, "input", "data", "raw"))
"""
    return code(f"""
if RUN_DATA_PREP:
    t0 = time.time()
    SCR = nt.scratch_tree(FOLDER, raw_files={list(raw_keep)!r})
    SCODE = os.path.join(SCR, "input", "code")
{pre}
{'    nt.run(' + repr('python3 -c "' + driver + '"') + ', cwd=SCODE)' if driver else ''}
    nt.run("python3 build_estimation_tables.py", cwd=SCODE)
    res = pd.concat([nt.compare_trees(os.path.join(SCR, "input", "data", "raw"), RAW),
                     nt.compare_trees(os.path.join(SCR, "input", "data", "estimation"), os.path.join(FOLDER, "input", "data", "estimation")).assign(half="estimation"),
                     nt.compare_trees(os.path.join(SCR, "input", "data", "holdout"), os.path.join(FOLDER, "input", "data", "holdout")).assign(half="hold-out")],
                    ignore_index=True)
    nt.drop_scratch(SCR)
    print(f"rebuild and comparison: {{(time.time() - t0) / 60:.1f}} min")
    display(res)
    nt.rebuild_verdict(res, glob.glob(os.path.join(FOLDER, "model", "estimate_*.py"))[0])
else:
    print("skipped (RUN_DATA_PREP = False): the shipped tables are used")
""")


def outing_cells(folder):
    m12 = folder.startswith("12")
    C = [md("## 1. Raw data")]
    C += rts_cells()
    C.append(md("""
### 1.3 Records of this model

`input/code/estimate_subtours.py` (function `data`) writes three files per half into `input/data/raw`: `wbs_<half>` (one
row per work episode at the usual workplace of a worker, with the outing flag `y` and the model variables), `wbs_w_<half>`
(the same episodes with their survey fields) and `wbs_out_<half>` (one row per work-based outing: stops, zones, modes).
""" + ("Model 12 uses the outings (`wbs_out`)." if m12 else "Model 11 uses the work episodes (`wbs`).")))
    C.append(code("""
CODE = os.path.join(FOLDER, "input", "code"); RAW = os.path.join(FOLDER, "input", "data", "raw")
HALVES = ["estimation", "validation"]
WBS = {h: pd.read_parquet(os.path.join(RAW, f"wbs_{h}.parquet")) for h in HALVES}
WW = {h: pd.read_parquet(os.path.join(RAW, f"wbs_w_{h}.parquet")) for h in HALVES}
WO = {h: pd.read_parquet(os.path.join(RAW, f"wbs_out_{h}.parquet")) for h in HALVES}
display(pd.DataFrame({h: {"work episodes (wbs)": len(WBS[h]), "with an outing (y = 1)": int(WBS[h].y.sum()), "outings (wbs_out)": len(WO[h])} for h in HALVES}))
WO["estimation"][["person_id", "n_stops", "leave", "ret", "purposes", "zones", "wz", "hz", "mode", "tour_mode", "w"]].head()
"""))
    C.append(md("""
## 2. Data preparation

### 2.1 From survey episodes to work episodes and outings

`estimate_subtours.data` takes the typed episodes of the half, finds the work-based outings (`tasha_distributions.subtours`:
work at the usual workplace, one or more discretionary episodes, again work at the usual workplace; the work episode and its
continuations are merged) and keeps the work episodes below. The filters are mirrored with the script's helpers.
"""))
    C.append(code("""
sys.path.insert(0, CODE)
import te_common as TE, tasha_distributions as TD
steps = {}
for h in HALVES:
    e = TE.episodes(h).sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    e = TD.subtours(e)
    s = [("episodes of persons in the survey population", len(e))]
    w = e[e.type.isin(["PW", "SW"])]; s.append(("work episodes at the usual workplace", len(w)))
    w = w[~w.wbs_cont]; s.append(("not a return to the workplace after an outing", len(w)))
    w = w[w.seg.eq("worker_usual")]; s.append(("worker with a usual workplace", len(w)))
    span = np.where(w.wbs_n > 0, w.merged_dur, w.dur)
    w = w[pd.notna(span) & (span > 0)]; s.append(("duration known", len(w)))
    w = w[(w.wz > 0) & (w.hz > 0)]; s.append(("home and workplace zone known", len(w)))
    steps[h] = s; print(f"{h}: {int((w.wbs_n > 0).sum()):,} of the {len(w):,} work episodes have an outing")
nt.funnel2(steps, {"work episodes at the usual workplace": "other episode types",
                   "not a return to the workplace after an outing": "continuation merged into the work episode",
                   "worker with a usual workplace": "segment other than worker_usual",
                   "duration known": "last episode of the day (no departure)",
                   "home and workplace zone known": "home or workplace tract outside the zone system"})
"""))
    if m12:
        C.append(md("""
### 2.2 From outings to the estimation table

`a02_outing_mode.load` keeps the outings with a known mode of the outing and of the work tour, and a known zone of the
first stop and of the workplace. The choice is `y = 1` when the outing is walked, 0 when it keeps the mode of the work tour.
"""))
        C.append(code("""
steps = {}
for h in HALVES:
    o = WO[h]; s = [("outings", len(o))]
    o = o[o.tour_mode.notna() & o["mode"].notna()]; s.append(("mode of the outing and of the work tour known", len(o)))
    z1 = o.zones.str.split(";").str[0].astype(int)
    o = o[((z1 > 0) & (o.wz > 0)).values]; s.append(("first-stop and workplace zone known", len(o)))
    steps[h] = s
nt.funnel2(steps)
"""))
    else:
        C.append(md("### 2.2 From work episodes to the estimation table\n\n`a01_outing.load` adds person attributes (age, licence) of the survey population; no record is dropped. The choice `y = 1` when the work episode has at least one outing."))
    C.append(md("""
### 2.3 Rebuild check

In a scratch copy of `input/code` without the raw files, `estimate_subtours.data` rebuilds them from the episodes, then
`build_estimation_tables.py` runs, and every rebuilt table is compared with the shipped one. The shipped
`estimate_subtours.py` reads the survey population from `00_shared_data/survey_pop`; the files are in
`00_shared_data/rts_2017_18/survey_pop`, so the rebuild sets that folder (`ES.A3 = te_common.A3`) before calling `data`.
"""))
    C.append(_scratch_rebuild([], driver="import te_common as T, estimate_subtours as ES; ES.A3 = T.A3; ES.data('estimation'); ES.data('validation')"))
    C.append(md("## 3. Estimation table\n\nBinary logit: " + ("1 = the outing is walked, 0 = it keeps the work-tour mode." if m12 else "1 = the work episode has at least one outing, 0 = none.")))
    C.append(code("""
EST_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "estimation", "estimation_table.parquet"))
HOLD_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "estimation_table.parquet"))
print(f"estimation table: {EST_T.shape[0]:,} rows x {EST_T.shape[1]} columns; hold-out {HOLD_T.shape[0]:,} rows")
display(EST_T.head())
pd.read_csv(os.path.join(FOLDER, "input", "data", "estimation", "data_dictionary.csv"))
"""))
    C.append(md("## 4. Descriptive statistics\n\n### Observed choice (unweighted and with the survey trip weight `w`, which the estimation does not use)"))
    lab = '{0: "keeps the work-tour mode", 1: "walks"}' if m12 else '{0: "no outing", 1: "at least one outing"}'
    C.append(code(f"""
LAB = {lab}
display(nt.shares_table(EST_T.y.astype(int).map(LAB), EST_T.w))
"""))
    if m12:
        C.append(code("""
ZA = pd.read_csv(os.path.join(nt.ABIT_SHARED, "zones", "zones_model_attributes.csv")).sort_values("idx").reset_index(drop=True)
o = WO["estimation"]; o = o[o.tour_mode.notna() & o["mode"].notna()]
z1 = o.zones.str.split(";").str[0].astype(int); o = o[((z1 > 0) & (o.wz > 0)).values]; z1 = z1[((z1 > 0)).values].loc[o.index]
assert len(o) == len(EST_T)
fig, ax = nt.panels(4, ncol=4, w=3.5, h=2.8)
for y_, lab in LAB.items():
    ax[0].hist(EST_T.km[EST_T.y == y_].clip(upper=20), bins=np.arange(0, 20.5, 0.5), histtype="step", lw=1.6, color=nt.OBS if y_ else nt.LIGHT, label=lab)
ax[0].set_xlabel("car km workplace - first stop"); ax[0].set_ylabel("outings"); ax[0].legend(fontsize=7, frameon=False)
tm = np.select([EST_T.tm_cd == 1, EST_T.tm_cp == 1], ["car driver", "car passenger"], "other")
c = pd.Series(tm).value_counts(); nt.bar(100 * c / c.sum(), "mode of the work tour", "share (%)", ax=ax[1], rot=20)
c = EST_T.multi.map({0: "one stop", 1: "2+ stops"}).value_counts(); nt.bar(100 * c / c.sum(), "stops of the outing", "share (%)", ax=ax[2])
c = (o.leave % 1440 // 60).value_counts().sort_index(); nt.bar(c, "departure hour of the outing", "outings", ax=ax[3])
plt.tight_layout(); plt.show()
print("walk share (%) by work-tour mode:", (100 * EST_T.groupby(tm).y.mean()).round(1).to_dict())
"""))
        C.append(md("Distance to the first stop by choice, work-tour mode, stops and departure hour of the outings."))
        C.append(code("""
items = [("age_u30", "age under 30"), ("age_55p", "age 55+"), ("female", "female"), ("lic", "driving licence"), ("car0", "no car"),
         ("carshort", "fewer cars than drivers"), ("inc_low", "income < $50k"), ("inc_high", "income $100k+"), ("cbd_w", "workplace in a CBD zone"), ("midday", "leaves 11:00-14:00")]
t = pd.DataFrame({"share of outings (%)": [100 * EST_T[c].mean() for c, _ in items],
                  "walk share if 1 (%)": [100 * EST_T.y[EST_T[c] == 1].mean() for c, _ in items]}, index=[l for _, l in items]).round(1)
display(t)
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
cnt = pd.Series(z1.values).value_counts(); nt.zone_map(cnt, "outings (first-stop zone)", ax=ax[0], log=True)
cw = o.wz.value_counts(); nt.zone_map(cw, "outings (workplace zone)", ax=ax[1], log=True)
ax[0].set_title("first stops", fontsize=10); ax[1].set_title("workplaces", fontsize=10)
plt.tight_layout(); plt.show()
"""))
        C.append(md("Person and outing variables (share of outings with the flag, and the walk share among them); zones of the first stops and workplaces."))
    else:
        C.append(code("""
fig, ax = nt.panels(4, ncol=4, w=3.5, h=2.8)
for y_, lab in LAB.items():
    ax[0].hist(EST_T.dur_h[EST_T.y == y_].clip(upper=14), bins=np.arange(0, 14.25, 0.5), histtype="step", lw=1.6, color=nt.OBS if y_ else nt.LIGHT, label=lab)
ax[0].set_xlabel("work-episode span (h)"); ax[0].set_ylabel("work episodes"); ax[0].legend(fontsize=7, frameon=False)
ax[1].hist(EST_T.arr / 60, bins=np.arange(0, 24.5, 0.5), color=nt.OBS); ax[1].set_xlabel("arrival at work (hour)"); ax[1].set_ylabel("work episodes")
ax[2].hist(EST_T.km_comm.clip(upper=100), bins=50, color=nt.OBS); ax[2].set_xlabel("home - workplace car km"); ax[2].set_ylabel("work episodes")
c = EST_T.nsub.clip(upper=3).value_counts().sort_index(); nt.bar(c, "outings per work episode (3 = 3+)", "work episodes", ax=ax[3])
plt.tight_layout(); plt.show()
band = pd.cut(EST_T.dur_h, [0, 4, 7, 9, 24], labels=["<4 h", "4-7 h", "7-9 h", "9+ h"])
print("outing share (%) by span:", (100 * EST_T.groupby(band, observed=False).y.mean()).round(1).to_dict())
"""))
        C.append(md("Span of the work episode by outcome, arrival time, commute distance and number of outings; work episodes of 7 h or more have the most outings."))
        C.append(code("""
items = [("age_u30", "age under 30"), ("age_55p", "age 55+"), ("female", "female"), ("lic", "driving licence"), ("car0", "no car"),
         ("carshort", "fewer cars than drivers"), ("kids", "child under 16"), ("inc_low", "income < $50k"), ("inc_high", "income $100k+"),
         ("cbd_w", "workplace in a CBD zone"), ("sw", "arrives after 15:00")]
t = pd.DataFrame({"share of work episodes (%)": [100 * EST_T[c].mean() for c, _ in items],
                  "outing share if 1 (%)": [100 * EST_T.y[EST_T[c] == 1].mean() for c, _ in items]}, index=[l for _, l in items]).round(1)
display(t)
ww = WW["estimation"].loc[EST_T.row_index.values]
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
nt.zone_map(ww.wz.value_counts(), "work episodes (workplace zone)", ax=ax[0], log=True)
r = ww.assign(y=EST_T.y.values).groupby("wz").y.agg(["mean", "size"]); r = r[r["size"] >= 5]
nt.zone_map(100 * r["mean"], "outing share (%), zones with 5+ episodes", ax=ax[1])
ax[0].set_title("workplaces", fontsize=10); ax[1].set_title("outing share", fontsize=10)
plt.tight_layout(); plt.show()
"""))
        C.append(md("Person and workplace variables (share of work episodes with the flag, and the outing share among them); workplace zones and the outing share by zone."))
    C.append(md("### Estimation half vs hold-out half"))
    C.append(code("""
t = nt.half_comparison(EST_T.y.astype(int).map(LAB), HOLD_T.y.astype(int).map(LAB), "choice")
print(f"records: estimation {len(EST_T):,}, hold-out {len(HOLD_T):,}; largest difference of a share: {t['difference (points)'].abs().max():.1f} points")
t
"""))
    return C


def return_cells(folder):
    C = [md("## 1. Raw data")]
    C += rts_cells()
    C.append(md("""
### 1.3 Records of this model

`input/code/estimate_return_home.py` (function `pairs`) writes `rh_pairs_wbs_<half>.parquet`: one row per pair of consecutive
out-of-home episodes of a person-day, with `y = 1` when the person went home between them, the slack time (time between the
two episodes minus the travel time via home), the detour via home and the purposes of both episodes.
"""))
    C.append(code("""
CODE = os.path.join(FOLDER, "input", "code"); RAW = os.path.join(FOLDER, "input", "data", "raw")
HALVES = ["estimation", "validation"]
PR = {h: pd.read_parquet(os.path.join(RAW, f"rh_pairs_wbs_{h}.parquet")) for h in HALVES}
display(pd.DataFrame({h: {"pairs": len(PR[h]), "home in between (y = 1)": int(PR[h].y.sum()), "both work episodes": int(PR[h].workwork.sum())} for h in HALVES}))
PR["estimation"].head()
"""))
    C.append(md("""
## 2. Data preparation

### 2.1 From survey episodes to pairs of episodes

Mirrored from `pairs`: the stops of work-based outings and the returns to the workplace leave the sequence (the outing model
generates them), each out-of-home episode is paired with the next out-of-home episode of the same person-day, and pairs with
an unknown zone, end time or type are dropped; `a03_return.load` then drops the pairs of two work episodes.
"""))
    C.append(code("""
sys.path.insert(0, CODE)
import te_common as TE, tasha_distributions as TD
steps = {}
for h in HALVES:
    e = TE.episodes(h).sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    s = [("episodes of persons in the survey population", len(e))]
    e = TD.subtours(e); e = e[~(e.wbs | e.wbs_cont)].reset_index(drop=True); s.append(("without work-based outings", len(e)))
    e["end"] = e.groupby("person_id").dep_min.shift(-1)
    out = e[~e.is_home]; s.append(("out-of-home episodes", len(out)))
    same = np.r_[out.person_id.values[1:] == out.person_id.values[:-1], False]
    a = out[same]; b = out.iloc[np.where(same)[0] + 1]
    s.append(("pairs of consecutive out-of-home episodes", len(a)))
    ok = (a.dz.values > 0) & (b.dz.values > 0) & (a.hz.values > 0) & a.end.notna().values & a.type.notna().values & b.type.notna().values
    s.append(("zones, end time and types known", int(ok.sum())))
    ww = a.type.isin(["WB", "WAHB", "PW", "SW"]).values & b.type.isin(["WB", "WAHB", "PW", "SW"]).values
    s.append(("not two work episodes (estimation table)", int((ok & ~ww).sum())))
    steps[h] = s
nt.funnel2(steps, {"without work-based outings": "stops of work-based outings and returns to the workplace",
                   "out-of-home episodes": "home episodes", "pairs of consecutive out-of-home episodes": "last out-of-home episode of the day",
                   "zones, end time and types known": "zone outside the zone system, last trip without departure, or untyped episode",
                   "not two work episodes (estimation table)": "work followed by work (a return home is a separate decision)"})
"""))
    C.append(md("### 2.2 Rebuild check\n\nThe raw pair files are deleted in a scratch copy of `input/code`, so `pairs` rebuilds them; then `build_estimation_tables.py` runs and the tables are compared with the shipped ones."))
    C.append(_scratch_rebuild([]))
    C.append(md("## 3. Estimation table\n\nBinary logit: 1 = the person goes home between the two episodes."))
    C.append(code("""
EST_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "estimation", "estimation_table.parquet"))
HOLD_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "estimation_table.parquet"))
print(f"estimation table: {EST_T.shape[0]:,} rows x {EST_T.shape[1]} columns; hold-out {HOLD_T.shape[0]:,} rows")
display(EST_T.head())
pd.read_csv(os.path.join(FOLDER, "input", "data", "estimation", "data_dictionary.csv"))
"""))
    C.append(md("## 4. Descriptive statistics\n\n### Observed choice (unweighted and with the survey trip weight `w`, not used by the estimation)"))
    C.append(code("""
LAB = {0: "goes on directly", 1: "returns home"}
P = PR["estimation"].loc[EST_T.row_index.values]
display(nt.shares_table(EST_T.y.astype(int).map(LAB), P.w))
fig, ax = nt.panels(4, ncol=4, w=3.5, h=2.8)
for y_, lab in LAB.items():
    ax[0].hist((P.slack[EST_T.y.values == y_] / 60).clip(-1, 8), bins=np.arange(-1, 8.25, 0.25), histtype="step", lw=1.6, color=nt.OBS if y_ else nt.LIGHT, label=lab)
ax[0].set_xlabel("slack time (h)"); ax[0].set_ylabel("pairs"); ax[0].legend(fontsize=7, frameon=False)
ax[1].hist(EST_T.detour_km.clip(upper=40), bins=40, color=nt.OBS); ax[1].set_xlabel("detour via home (car km)"); ax[1].set_ylabel("pairs")
ax[2].hist(EST_T.dhome_km.clip(upper=60), bins=40, color=nt.OBS); ax[2].set_xlabel("first episode - home (car km)"); ax[2].set_ylabel("pairs")
c = EST_T.nep.clip(upper=8).value_counts().sort_index(); nt.bar(c, "out-of-home episodes of the day (8 = 8+)", "pairs", ax=ax[3])
plt.tight_layout(); plt.show()
band = pd.cut(P.slack / 60, [-1e9, 0.5, 1, 2, 4, 1e9], labels=["<0.5 h", "0.5-1 h", "1-2 h", "2-4 h", "4+ h"])
print("return-home share (%) by slack:", (100 * EST_T.groupby(band.values, observed=False).y.mean()).round(1).to_dict())
"""))
    C.append(md("Slack time between the two episodes by outcome, detour via home, distance from home and episodes per day; the return-home share rises with the slack."))
    C.append(code("""
t = pd.crosstab(P.a_purpose.values, P.e_purpose.values, values=EST_T.y.values, aggfunc="mean").mul(100).round(1)
t.index.name = "first episode"; t.columns.name = "next episode"
print("return-home share (%) by purpose of the two episodes"); display(t)
items = [("worker", "worker"), ("stud_k12", "K-12 student"), ("stud_ps", "post-secondary student"), ("retiree", "retiree"), ("toddler", "under 5"),
         ("female", "female"), ("lic", "driving licence"), ("kids", "child under 16"), ("car0", "no car"), ("inc_low", "income < $50k"),
         ("inc_high", "income $100k+"), ("am", "first ends before 9:00"), ("pm", "first ends 15-19"), ("ev", "first ends from 19:00"), ("jj", "both joint")]
display(pd.DataFrame({"share of pairs (%)": [100 * EST_T[c].mean() for c, _ in items],
                      "return-home share if 1 (%)": [100 * EST_T.y[EST_T[c] == 1].mean() for c, _ in items]}, index=[l for _, l in items]).round(1))
c = EST_T.hhsize.clip(upper=6).astype(int).value_counts().sort_index()
nt.bar(100 * c / c.sum(), "household size (6 = 6+)", "share of pairs (%)", figsize=(5, 2.8)); plt.tight_layout(); plt.show()
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
nt.zone_map(P.hz.value_counts(), "pairs (home zone)", ax=ax[0], log=True)
r = P.assign(y=EST_T.y.values).groupby("hz").y.agg(["mean", "size"]); r = r[r["size"] >= 10]
nt.zone_map(100 * r["mean"], "return-home share (%), zones with 10+ pairs", ax=ax[1])
ax[0].set_title("home zones", fontsize=10); ax[1].set_title("return-home share", fontsize=10)
plt.tight_layout(); plt.show()
"""))
    C.append(md("Return-home share by purpose, person type and time of day; home zones of the pairs and the return-home share by home zone."))
    C.append(md("### Estimation half vs hold-out half"))
    C.append(code("""
PH = PR["validation"].loc[HOLD_T.row_index.values]
t = pd.concat({"choice": nt.half_comparison(EST_T.y.astype(int).map(LAB), HOLD_T.y.astype(int).map(LAB), "x"),
               "purpose of the first episode": nt.half_comparison(P.a_purpose, PH.a_purpose, "x")})
print(f"records: estimation {len(EST_T):,}, hold-out {len(HOLD_T):,}; largest difference of a share: {t['difference (points)'].abs().max():.1f} points")
t
"""))
    return C


def leg_cells(folder):
    C = [md("## 1. Raw data")]
    C += rts_cells()
    C.append(md("""
### 1.3 Records of this model

`input/code/estimate_transit_legs.py` (function `legs`) cuts every transit tour of `tours_<half>.parquet` (tour mode transit
with walk or drive access) into its linked trips (legs): consecutive survey trips joined at a change-of-mode activity become
one leg with the highest mode used. `tlegs_<half>.parquet` holds one row per leg.
"""))
    C.append(code("""
CODE = os.path.join(FOLDER, "input", "code"); RAW = os.path.join(FOLDER, "input", "data", "raw")
HALVES = ["estimation", "validation"]
TOURS = {h: pd.read_parquet(os.path.join(RAW, f"tours_{h}.parquet")) for h in HALVES}
LEGS = {h: pd.read_parquet(os.path.join(RAW, f"tlegs_{h}.parquet")) for h in HALVES}
display(pd.DataFrame({h: {"tours": len(TOURS[h]), "transit tours": int(TOURS[h].choice.isin(["TW", "TD"]).sum()),
                          "legs of transit tours": len(LEGS[h])} for h in HALVES}))
LEGS["estimation"][["tour", "person_id", "q", "n", "first", "last", "main", "mode", "merged", "outing", "oz", "dz", "dep", "tour_choice", "purpose", "w"]].head(8)
"""))
    C.append(md("""
## 2. Data preparation

### 2.1 From transit tours to the estimation table

`features` drops the legs of work-based outings (generated by the outing model), legs with an unknown zone or mode, and
legs whose chosen mode is not available (walk up to 8 km, bike up to 30 km, car driver for licence holders 16+ with a car).
`free_car.py` then applies DAYMAP's free-car rule: car driver needs a household car that is free over the whole tour window
(the household's car-driver tours overlapping the window are fewer than its cars at every instant); legs whose observed mode
becomes unavailable are dropped.
"""))
    C.append(code("""
sys.path.insert(0, CODE)
import estimate_transit_legs as E
import free_car as FC
steps, X_ = {}, {}
for h in HALVES:
    L = LEGS[h]
    s = [("transit tours", int(TOURS[h].choice.isin(["TW", "TD"]).sum())), ("legs of the transit tours", len(L))]
    s.append(("not a leg of a work-based outing", int((~L.outing).sum())))
    l2 = L[~L.outing]; s.append(("zones and mode known", int(((l2.o >= 0) & (l2.d >= 0) & l2["mode"].notna()).sum())))
    X0 = E.features(L); s.append(("chosen mode available (licence, age, household car)", int(X0.chosen_av.sum())))
    X = FC.apply(X0, h); X_[h] = X
    s.append(("chosen mode available with a free household car (estimation table)", int(X.chosen_av.sum())))
    steps[h] = s
display(nt.funnel2(steps, {"not a leg of a work-based outing": "legs of outings from the workplace",
                           "zones and mode known": "zone outside the zone system or unknown mode",
                           "chosen mode available (licence, age, household car)": "chosen mode not available",
                           "chosen mode available with a free household car (estimation table)": "car driver chosen but no household car free over the tour window"}))
pd.concat({h: X_[h][~X_[h].chosen_av]["mode"].value_counts() for h in HALVES}, axis=1).rename_axis("chosen mode of the dropped legs")
"""))
    C.append(md("### 2.2 Rebuild check\n\nThe shared `prep_tours.py` rebuilds the tours into a scratch folder; a scratch copy of `input/code` gets these tours only, so `legs` rebuilds the leg files, and `build_estimation_tables.py` the estimation tables; all are compared with the shipped files."))
    C.append(code("""
REBUILD = os.path.join(OUT, "rebuild_check")
"""))
    C.append(_scratch_rebuild([], shared_tours=True))
    C.append(md("""
## 3. Choice set and estimation table

Five alternatives (code `y`): 1 transit, 2 walk, 3 car passenger, 4 car driver, 5 bike. Transit and car passenger are always
available, walk up to 8 km, bike up to 30 km, car driver for licence holders aged 16+ in a household with a car that is free
over the tour window.
"""))
    C.append(code("""
LAB = {1: "transit", 2: "walk", 3: "car passenger", 4: "car driver", 5: "bike"}
EST_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "estimation", "estimation_table.parquet"))
HOLD_T = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "estimation_table.parquet"))
print(f"estimation table: {EST_T.shape[0]:,} rows x {EST_T.shape[1]} columns; hold-out {HOLD_T.shape[0]:,} rows")
av = [c for c in EST_T.columns if c.startswith("av_")]
t = pd.DataFrame({"available (% of legs)": (100 * (EST_T[av] > 0).mean()).round(1)}); t.index = [c[3:] for c in av]
display(t.T); display(EST_T.head())
pd.read_csv(os.path.join(FOLDER, "input", "data", "estimation", "data_dictionary.csv"))
"""))
    C.append(md("## 4. Descriptive statistics\n\n### Observed leg modes (unweighted and with the survey trip weight `w`)"))
    C.append(code("""
sh = nt.shares_table(EST_T.y.map(LAB), EST_T.w).reindex([v for v in LAB.values()])
display(sh)
nt.grouped_bars(sh[["share %", "weighted share %"]].rename(columns={"share %": "unweighted", "weighted share %": "survey weight"}), "leg mode", "share of legs (%)", colors=[nt.OBS, nt.LIGHT])
plt.tight_layout(); plt.show()
pos = np.select([EST_T["first"] == 1, EST_T["last"] == 1], ["first leg", "last leg"], "middle leg")
display((100 * pd.crosstab(pos, EST_T.y.map(LAB), normalize="index")).round(1).rename_axis(index="position", columns="leg mode"))
"""))
    C.append(md("Leg modes overall and by position in the tour: access and egress legs (first, last) carry the walk and car legs."))
    C.append(code("""
fig, ax = nt.panels(3, ncol=3, w=4.4, h=2.9)
labs = [l for m, l in LAB.items() if (EST_T.y == m).any()]
data = [EST_T.km[EST_T.y == m].clip(lower=0.2) for m, l in LAB.items() if (EST_T.y == m).any()]
ax[0].boxplot(data, vert=False, tick_labels=labs, showfliers=False, patch_artist=True, medianprops=dict(color="white"),
              boxprops=dict(facecolor=nt.OBS, color=nt.OBS), whiskerprops=dict(color=nt.OBS), capprops=dict(color=nt.OBS))
ax[0].set_xscale("log"); ax[0].set_xlabel("car km of the leg (log scale)"); ax[0].invert_yaxis()
c = EST_T.segment.value_counts(); nt.bar(100 * c / c.sum(), "tour segment", "share of legs (%)", ax=ax[1])
c = EST_T.n.clip(upper=6).value_counts().sort_index(); nt.bar(c, "legs of the tour (6 = 6+)", "legs", ax=ax[2])
plt.tight_layout(); plt.show()
items = [("cars0", "no car"), ("carshort", "fewer cars than drivers"), ("lic", "driving licence"), ("age_u18", "under 18"), ("age_65p", "65+"),
         ("peak", "peak period"), ("wash", "home in the WMATA area"), ("rail", "rail tour"), ("stops", "tour with stops"), ("nopath", "no transit path for the leg")]
pd.DataFrame({"share of legs (%)": [100 * EST_T[c].mean() for c, _ in items],
              "transit share if 1 (%)": [100 * (EST_T.y[EST_T[c] == 1] == 1).mean() for c, _ in items]}, index=[l for _, l in items]).round(1)
"""))
    C.append(md("Leg distance by mode, tour segment, legs per tour, and the person and leg variables with the transit share among the legs that have them."))
    C.append(code("""
L = LEGS["estimation"]; X = X_["estimation"]; Lk = L.loc[X.index[X.chosen_av]]
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
nt.zone_map(Lk.oz.value_counts(), "legs (origin zone)", ax=ax[0], log=True)
nt.zone_map(Lk.hz.value_counts(), "legs (home zone of the tour)", ax=ax[1], log=True)
ax[0].set_title("leg origins", fontsize=10); ax[1].set_title("home zones", fontsize=10)
plt.tight_layout(); plt.show()
"""))
    C.append(md("Origin zones of the legs and home zones of the transit tours."))
    C.append(md("### Estimation half vs hold-out half"))
    C.append(code("""
t = nt.half_comparison(EST_T.y.map(LAB), HOLD_T.y.map(LAB), "leg mode")
print(f"records: estimation {len(EST_T):,}, hold-out {len(HOLD_T):,}; largest difference of a share: {t['difference (points)'].abs().max():.1f} points")
t
"""))
    return C


FAMILY = {**{f: mode_cells for f in MODE}, "11_outing_generation": outing_cells, "12_outing_mode": outing_cells,
          "13_return_home": return_cells, "20_transit_leg_mode": leg_cells}


# =====================================================================================================================
# SILO 01-08
# =====================================================================================================================
SILO_SETUP = """
SH = os.path.abspath(os.path.join(FOLDER, "..", "00_shared_data")); CODE = os.path.join(FOLDER, "input", "code")
RAW = os.path.join(FOLDER, "input", "data", "raw"); REBUILD = os.path.join(OUT, "rebuild_check")
ZS = pd.read_csv(os.path.join(SH, "zone_system", "zoneSystem.csv"))[["ZoneId", "COUNTYFIPS", "JUR_NAME", "PUMA_10"]].rename(columns={"ZoneId": "zone"})
ZS["area_group"] = nt.area_group_of_county(ZS.COUNTYFIPS)
"""

SILO_BUILD = """
def rebuild_tables(python=sys.executable, pre=""):
    \"\"\"build_estimation_data.main() of input/code with its output folder set to a scratch folder; returns the comparison with the
    shipped estimation and hold-out tables.\"\"\"
    out = os.path.join(REBUILD, "data"); [os.makedirs(os.path.join(out, h), exist_ok=True) for h in ("estimation", "holdout")]
    nt.run(f'{python} -c "import build_estimation_data as B; {pre}B.OUT = {out!r}; B.main()"', cwd=CODE)
    return pd.concat([nt.compare_trees(os.path.join(out, h), os.path.join(FOLDER, "input", "data", h)).assign(half=h) for h in ("estimation", "holdout")],
                     ignore_index=True)
"""

PUMS_FUNNEL = """
# ACS PUMS 2014-2018 of DC, DE, MD, PA, VA, WV: the reading and filters of s03_pums.main('est'), mirrored
sys.path.insert(0, CODE)
import s03_pums as S3
P, H = S3.load("est")
f = nt.Funnel("PUMS household records (6 states)", len(H))
H = H[(H.TYPE == 1) & (H.NP > 0)].copy(); f.add("households (not group quarters, not vacant)", len(H), "group quarters and vacant units")
rel = P.RELP; hd = P[rel == 0].drop_duplicates("SERIALNO").set_index("SERIALNO")
H = H.set_index("SERIALNO"); H["mig"] = hd.MIG.reindex(H.index)
H["mig7"] = (hd.MIGSP.reindex(H.index).fillna(0) * 100000 + hd.MIGPUMA.reindex(H.index).fillna(0)).astype(int)
H["puma7"] = H.ST * 100000 + H.PUMA; H["dtype"] = S3.bld_type(H.BLD)
cov = pd.read_csv(os.path.join(SH, "resloc_work", "geo_puma_region.csv")).groupby("puma7").coverage.first()
mcov = pd.read_csv(os.path.join(SH, "resloc_work", "geo_mig_zone.csv")).groupby("mig7").coverage.first()
H["dest_cov"] = H.puma7.map(cov).fillna(0); H["orig_cov"] = H.mig7.map(mcov).fillna(0)
x = H[H.MV == 1]; f.add("moved in within the last 12 months", len(x), "not a recent mover")
x = x[x.mig == 3]; f.add("householder lived in another U.S. house a year ago", len(x), "same house, or abroad")
x = x[x.dest_cov > 0]; f.add("destination PUMA in the zone system", len(x), "PUMA outside the study area")
x = x[x.orig_cov > 0]; f.add("origin MIGPUMA in the zone system", len(x), "moved in from outside the study area")
x = x[x.dtype != "NA"]; f.add("known structure type (mover households)", len(x), "boat, RV, van")
MOV = pd.read_parquet(os.path.join(SH, "resloc_work", "pums_movers_est.parquet"))
f.add("estimation half (80 %, hash of SERIALNO)", int((MOV.half == "estimation").sum()), "hold-out half (20 %)")
display(f.table()); nt.funnel_plot(f, "households")
print("mirrored mover households equal the shipped pums_movers_est.parquet:", sorted(x.index) == sorted(MOV.SERIALNO))
"""

PUMS_REBUILD = """
if RUN_DATA_PREP:
    import shutil
    W3 = os.path.join(REBUILD, "resloc_work"); os.makedirs(W3, exist_ok=True)
    for f_ in ["geo_puma_region.csv", "geo_mig_zone.csv"]:
        shutil.copy2(os.path.join(SH, "resloc_work", f_), W3)
    nt.run(f'{sys.executable} -c "import s03_pums as S; S.WORK = {W3!r}; S.main(\\\\"est\\\\")"', cwd=CODE, quiet=True)
    res_p = pd.concat([nt.compare_frames(pd.read_parquet(os.path.join(W3, f_)), pd.read_parquet(os.path.join(SH, "resloc_work", f_)), name=f_)
                       for f_ in ["pums_movers_est.parquet", "pums_pool_est.parquet"]], ignore_index=True)
    display(res_p)
else:
    print("skipped (RUN_DATA_PREP = False)")
"""


RES2 = {"01_residential_puma", "02_residential_dwelling"}   # two-level residential model (ACS PUMS movers)


def silo_cells(folder):
    k = "res" if folder in RES2 else folder[:2]
    C = [md("## 1. Raw data"), code(SILO_SETUP + SILO_BUILD)]
    if k in ("01", "03", "res"):
        C.append(md("""
### 1.1 ACS PUMS 2014-2018 (5-year), six states

The residential models are estimated on households of the ACS Public Use Microdata Sample (household and person files of
DC, DE, MD, PA, VA, WV; `../00_shared_data/acs_pums_2014_2018_5yr`) that moved into their dwelling within the last
12 months. Origin (migration PUMA of the householder) and destination (PUMA of the dwelling) are PUMAs, mapped to the
SILO counties and zones by the geography tables of `../00_shared_data/resloc_work` (zones without a 2010 tract internal point
by their centroid: `geo_puma_zone_all.csv`, `geo_mig_zone_all.csv`). The householder's race (PUMS `RAC1P`, `HISP`) enters
only the own-race share of the PUMA level.
"""))
        C.append(code("""
display(nt.files_table(os.path.join(SH, "acs_pums_2014_2018_5yr")))
MOV = pd.read_parquet(os.path.join(SH, "resloc_work", "pums_movers_est.parquet"))
POOL = pd.read_parquet(os.path.join(SH, "resloc_work", "pums_pool_est.parquet"))
print(f"mover households: {len(MOV):,} (estimation {int((MOV.half == 'estimation').sum()):,}, hold-out {int((MOV.half == 'validation').sum()):,}); "
      f"dwellings occupied by recent movers (pool of alternatives): {len(POOL):,}")
nt.no_race(MOV).head()
"""))
        C.append(md("""
## 2. Data preparation

### 2.1 From PUMS records to mover households

`input/code/s03_pums.py` reads the 12 PUMS files and keeps the mover households below. The split into an estimation
(80 %) and a hold-out half (20 %) is fixed by a hash of the household serial number (`md5(SERIALNO) mod 5 = 0` = hold-out).
The reading and the filters are run here with the script's own functions.
"""))
        C.append(code(PUMS_FUNNEL))
        if folder == "01_residential_puma":
            C.append(md("All 97 PUMAs are available and no mover is dropped at the PUMA level (every zone has a PUMA, zones without a tract point by their centroid). The counts below check this."))
            C.append(code("""
IDX = pd.read_csv(os.path.join(FOLDER, "input", "data", "estimation", "puma_index.csv"))
EST_IDS = pd.read_parquet(os.path.join(FOLDER, "input", "data", "estimation", "puma_estimation.parquet"), columns=["household"]).household
HOLD_IDS = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "puma_holdout.parquet"), columns=["household"]).household
for h_, ids in (("estimation", EST_IDS), ("validation", HOLD_IDS)):
    m_ = MOV[MOV.half == h_]; out = m_[~m_.SERIALNO.isin(ids)]
    print(f"{h_} half: {len(m_):,} movers, {len(ids):,} in the PUMA table; not in it: {len(out):,}")
"""))
        C.append(md("### 2.2 Rebuild check\n\n`s03_pums.main('est')` is run with its output folder set to a scratch folder (movers and pool files compared with the shipped ones); then `build_estimation_data.py` writes the estimation tables into a scratch folder and they are compared with the shipped ones (the script also asserts the log-likelihood of the original run)."
                    + (" The PUMA build replays the dwelling draws of the same generator and computes the inclusive values (about 2.5 min, 4 GB; geopandas is needed, so it runs with `python3` of the base environment)." if folder == "01_residential_puma" else "")
                    + (" The county table takes the county data with the inclusive values of the lower levels (`input/data/raw/county_data_*.pkl`) as shipped: the upstream geography and inclusive-value steps need files that are not in the package (a 2016 job file and an out-of-time PUMS sample)." if k == "01" else "")))
        C.append(code(PUMS_REBUILD + f"""
if RUN_DATA_PREP:
    t0 = time.time()
    res = rebuild_tables({'"python3"' if k == "01" or folder == "01_residential_puma" else 'sys.executable'})
    print(f"build: {{(time.time() - t0) / 60:.1f}} min"); display(res)
    nt.rebuild_verdict(pd.concat([res_p, res], ignore_index=True), glob.glob(os.path.join(FOLDER, "model", "estimate_*.py"))[0])
"""))
    elif k == "02":
        C.append(md("""
### 1.1 The 2017/18 Regional Travel Survey (households)

The zone and structure-type level of the residential model uses the households of the 2017/18 RTS
(`../00_shared_data/rts_2017_18/RTS_raw_flat_data.csv`; one row per trip with household and person fields). A record is a
household: its home zone (tract internal point) and structure type (single-family detached, attached, multi-family, mobile
home) are the observed choice. Race and ethnicity fields are not read.
"""))
        C.append(code("""
flat = pd.read_csv(os.path.join(SH, "rts_2017_18", "RTS_raw_flat_data.csv"), low_memory=False, usecols=lambda c: not nt.RACE.search(c))
print(f"flat file: {len(flat):,} rows, {flat.household_id.nunique():,} households, {flat.person_id.nunique():,} persons")
flat.drop_duplicates("household_id")[["household_id", "home_state_county_fips", "home_tract_fips", "home_type", "hhsize", "numvehicle", "numdrivers", "hh_income_detailed", "wthhfin"]].head()
"""))
        C.append(md("""
## 2. Data preparation

### 2.1 From survey households to choosers

`s05_zone.load_rts` (run here as shipped) keeps households with a home zone in the zone system, a known income and a
structure type 1-4; `build_estimation_data.py` keeps households with a known age of the oldest member, and the sampling of
the alternatives drops households whose observed (zone, structure type) cell has no dwelling in the 2016 stock. The split
is the household split of the survey (`rts_split.csv`, seed 2026, stratified by county and household size).
"""))
        C.append(code("""
sys.path.insert(0, CODE)
import s05_zone as Z
h, log = Z.load_rts()
steps = {}
EST_N = len(pd.read_parquet(os.path.join(FOLDER, "input", "data", "estimation", "zone_estimation.parquet"), columns=["household"]))
HOLD_N = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "zone_holdout_fullset.parquet"), columns=["household"]).household.nunique()
h2 = h[h.age_max.notna() & (h.age_max >= 0)]
f = nt.Funnel("households of the survey", log["households_rts"])
f.add("home zone, income and structure type known", log["kept"], f"home zone outside the system {log['households_rts'] - log['home_zone_in_system']}, income unknown {log['households_rts'] - log['income_known']}, type 5+ {log['households_rts'] - log['type_1_4']} (overlapping)")
f.add("age of the oldest member known", len(h2), "no age recorded")
f.add("estimation half", int((h2.half == "estimation").sum()), "hold-out half")
f.add("observed cell in the dwelling stock (estimation table)", EST_N, "observed zone x type without a 2016 dwelling, or region with < 2 cells")
display(f.table())
print(f"hold-out half: {int((h2.half == 'validation').sum()):,} households, {HOLD_N:,} in the hold-out table")
"""))
        C.append(md("### 2.2 Rebuild check\n\n`build_estimation_data.py` (same random draw of the alternatives, seed of the original run) writes the estimation table and the full-choice-set hold-out table into a scratch folder; both are compared with the shipped tables (the script asserts the log-likelihoods of the original run)."))
        C.append(code("""
if RUN_DATA_PREP:
    t0 = time.time(); res = rebuild_tables(); print(f"build: {(time.time() - t0) / 60:.1f} min"); display(res)
    nt.rebuild_verdict(res, glob.glob(os.path.join(FOLDER, "model", "estimate_*.py"))[0])
else:
    print("skipped (RUN_DATA_PREP = False)")
"""))
    elif k == "04":
        C.append(md("""
### 1.1 ACS PUMS 2014-2018, Maryland

The car ownership model uses the Maryland households of the ACS PUMS 2014-2018 (`csv_hmd.zip`, `csv_pmd.zip`). A record is a
household with its number of vehicles (0, 1, 2, 3+), persons, workers, income, dwelling and the accessibility of its PUMA.
"""))
        C.append(code("""
import zipfile
def pums(kind, cols):
    with zipfile.ZipFile(os.path.join(SH, "acs_pums_2014_2018_5yr", f"csv_{kind}md.zip")) as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        return pd.read_csv(zf.open(n), usecols=cols, low_memory=False, dtype={"SERIALNO": str})
H = pums("h", ["SERIALNO", "PUMA", "NP", "VEH", "HINCP", "WGTP", "TYPE", "ADJINC", "BLD", "BDSP"])
print(f"Maryland PUMS household records: {len(H):,}")
H.head()
"""))
        C.append(md("""
## 2. Data preparation

### 2.1 From PUMS records to households

`input/code/s01_data.py` keeps households (TYPE 1) with persons, a known vehicle count and a positive weight, adds persons,
workers, income (2016 $), dwelling type and the PUMA accessibility, drops records with a missing value, and splits by a hash
of the serial number (`md5 mod 5 = 0` = hold-out, 20 %). Mirrored below.
"""))
        C.append(code("""
HH = pd.read_parquet(os.path.join(RAW, "hh.parquet"))
f = nt.Funnel("Maryland PUMS household records", len(H))
x = H[H.TYPE == 1]; f.add("households (TYPE 1)", len(x), "group quarters")
x = x[x.NP > 0]; f.add("with persons", len(x), "vacant units")
x = x[x.VEH.notna() & (x.WGTP > 0)]; f.add("vehicles known, positive weight", len(x), "")
f.add("no missing value (hh.parquet)", len(HH), "missing accessibility or density")
f.add("estimation half (80 %)", int((HH.half == "estimation").sum()), "hold-out half (20 %)")
display(f.table()); nt.funnel_plot(f, "households")
"""))
        C.append(md("### 2.2 Rebuild check\n\n`s01_data.main()` and `build_estimation_data.main()` run with their output folders set to a scratch folder; the household file and the estimation and hold-out tables are compared with the shipped ones."))
        C.append(code("""
if RUN_DATA_PREP:
    t0 = time.time(); R1 = os.path.join(REBUILD, "raw"); os.makedirs(R1, exist_ok=True)
    nt.run(f'{sys.executable} -c "import s01_data as S; S.RAWD = {R1!r}; S.main()"', cwd=CODE, quiet=True)
    res_h = nt.compare_frames(pd.read_parquet(os.path.join(R1, "hh.parquet")), HH, name="hh.parquet")
    res = rebuild_tables(pre=f"B.RAWD = {R1!r}; ")
    res = pd.concat([res_h, res], ignore_index=True); print(f"rebuild: {(time.time() - t0) / 60:.1f} min"); display(res)
    nt.rebuild_verdict(res, glob.glob(os.path.join(FOLDER, "model", "estimate_*.py"))[0])
else:
    print("skipped (RUN_DATA_PREP = False)")
"""))
    elif k == "05":
        C.append(md("""
### 1.1 The 2017/18 Regional Travel Survey (workers)

The workplace model uses the workers of the 2017/18 RTS with a fixed usual workplace. Their home and workplace locations
are the survey traffic zones (BMC, TPB) or tracts, spread over the model zones with housing-unit (home) and job (workplace)
weights; the worker file of `input/data/raw` holds one row per worker with the modal home zone `hz` and workplace zone `wz`.
"""))
        C.append(code("""
flat = pd.read_csv(os.path.join(SH, "rts_2017_18", "RTS_raw_flat_data.csv"), low_memory=False, usecols=lambda c: not nt.RACE.search(c))
per = flat.drop_duplicates("person_id")
WK = pd.read_parquet(os.path.join(RAW, "workers_v2.parquet"))
print(f"persons of the survey: {len(per):,}; workers in workers_v2.parquet: {len(WK):,} (estimation {int((WK.half == 'estimation').sum()):,})")
WK.head()
"""))
        C.append(md("""
## 2. Data preparation

### 2.1 From survey persons to workers

The worker script of the shared DAYMAP preparation (`../../ABIT/00_shared_prep/code`, step S15) keeps the persons with a fixed usual workplace and a work tract, locates
home and workplace in the zone system (traffic-zone crosswalks, else tract splits) and drops the records below. With
`RUN_DATA_PREP` it is run into a scratch folder (with the shipped crosswalks and tract splits) and its record log is shown.
"""))
        C.append(code("""
n_fixed = int(((per.j1_workplace_loc == 1) & (per.work_tract_fips > 0)).sum())
print(f"persons with a fixed usual workplace and a work tract code (mirrored): {n_fixed:,}")
if RUN_DATA_PREP:
    import shutil
    RW = os.path.join(REBUILD, "abit_shared"); os.makedirs(os.path.join(RW, "taz_crosswalks"), exist_ok=True)
    for f_ in os.listdir(os.path.join(nt.ABIT_SHARED, "taz_crosswalks")):
        shutil.copy2(os.path.join(nt.ABIT_SHARED, "taz_crosswalks", f_), os.path.join(RW, "taz_crosswalks"))
    nt.run("python3 rts_11_data_v2.py", cwd=nt.ABIT_PREP, env={"ABIT_REBUILT": RW}, quiet=True)
    lg = pd.read_csv(os.path.join(RW, "taz_crosswalks", "tables_rts", "drop_log_v2.csv"))
    st = []; n = None
    for step, v in zip(lg.step, lg.n):
        n = n + v if step.startswith("dropped") else v
        st.append((step.replace("dropped: ", "without: "), n))
    display(nt.funnel2({"both halves": st[:-2]}))
    print(dict(st[-2:]))
    res_w = nt.compare_frames(pd.read_parquet(os.path.join(RW, "taz_crosswalks", "workers_v2.parquet")), WK, name="workers_v2.parquet")
    display(res_w)
else:
    print("skipped (RUN_DATA_PREP = False)")
"""))
        C.append(md("### 2.2 Rebuild check of the model data\n\n`w01_data.py` (zone data, car skim, workers: `data.npz`) runs with its output redirected (`W01_OUT`), then `build_estimation_data.main()` (the 99 sampled alternatives of each worker, seed of the original run) with a scratch output folder; both are compared with the shipped files."))
        C.append(code("""
if RUN_DATA_PREP:
    t0 = time.time(); npz = os.path.join(REBUILD, "data.npz")
    nt.run(f"{sys.executable} w01_data.py", cwd=CODE, env={"W01_OUT": npz}, quiet=True)
    a, b = np.load(npz, allow_pickle=True), np.load(os.path.join(RAW, "data.npz"), allow_pickle=True)
    eq = lambda u, v: u.shape == v.shape and (np.array_equal(u, v, equal_nan=True) if u.dtype.kind in "fc" else np.array_equal(u, v))
    same = {k_: k_ in a.files and eq(a[k_], b[k_]) for k_ in b.files}
    bad = [k_ for k_, v in same.items() if not v]
    res_n = pd.DataFrame([{"table": f"data.npz ({len(same)} arrays)", "result": "identical" if not bad else "DIFFERENT", "differing columns": ", ".join(bad)}])
    res = rebuild_tables(); print(f"rebuild: {(time.time() - t0) / 60:.1f} min")
    res = pd.concat([res_w, res_n, res], ignore_index=True); display(res)
    nt.rebuild_verdict(res, glob.glob(os.path.join(FOLDER, "model", "estimate_*.py"))[0])
else:
    print("skipped (RUN_DATA_PREP = False)")
"""))
    else:   # 06-08 schools
        seg = {"06": "k8", "07": "hs", "08": "col"}[k]
        rng = {"k8": "5-14", "hs": "13-19", "col": "16+"}[seg]
        C.append(md(f"""
### 1.1 The 2017/18 Regional Travel Survey (students)

The school location models use the students of the 2017/18 RTS with their home and school locations (survey traffic zone or
tract). `../00_shared_data/school_choice_work/students.parquet` holds one row per student of the three segments (K-8,
high school, college) with the modal home zone `hz`, school zone `sz` and the half of the household split.
"""))
        C.append(code("""
flat = pd.read_csv(os.path.join(SH, "rts_2017_18", "RTS_raw_flat_data.csv"), low_memory=False, usecols=lambda c: not nt.RACE.search(c))
per = flat.drop_duplicates("person_id")
STU = pd.read_parquet(os.path.join(SH, "school_choice_work", "students.parquet"))
print(f"persons of the survey: {len(per):,}; students in students.parquet: {len(STU):,}")
display(STU.groupby(["seg", "half"]).size().unstack())
STU[STU.seg == SEG].head()
""".replace("SEG", repr(seg))))
        C.append(md(f"""
## 2. Data preparation

### 2.1 From survey persons to students

`sc_01_data.py` keeps students (`student_status` 1) of a school type with an inventory of schools: K-8 (type 2), 9th-12th
(type 3), college (2-year, 4-year, graduate: types 6-8); daycare, home school, vocational and other schools are left out.
It drops online-only students, ages outside the segment range ({seg}: {rng}), students whose home or school is not located
in a zone with enrolment of their band, and households without income. The first filters are mirrored below; the last
ones need the location step of `sc_01_data.py`, which is not run here (it reads the survey through the original project
folders and writes there), so the result is taken from the shipped `students.parquet`.
"""))
        C.append(code(f"""
SEGMAP = {{2: "k8", 3: "hs", 6: "col", 7: "col", 8: "col"}}
f = nt.Funnel("persons of the survey", len(per))
x = per[per.student_status == 1]; f.add("students", len(x), "not a student")
x = x[x.school_type.isin(SEGMAP)]; f.add("school type with a school inventory", len(x), "daycare, home school, vocational, other")
x = x[x.school_type.map(SEGMAP) == {seg!r}]; f.add("segment {seg}", len(x), "other segments")
x = x[x.school_freq != 8]; f.add("not online only", len(x), "online classes only")
lo, hi = {{"k8": (5, 14), "hs": (13, 19), "col": (16, 200)}}[{seg!r}]
x = x[x.age.between(lo, hi)]; f.add("age in the segment range", len(x), "age missing or outside the range")
s_ = STU[STU.seg == {seg!r}]
f.add("home and school located, income known (students.parquet)", len(s_), "home or school not in a zone with enrolment of the band; income missing")
f.add("estimation half", int((s_.half == "estimation").sum()), "hold-out half")
display(f.table()); nt.funnel_plot(f, "persons")
print("students of students.parquet among the mirrored records:", bool(set(s_.person_id) <= set(x.person_id)))
"""))
        C.append(md("### 2.2 Rebuild check\n\n`build_estimation_data.main()` (full choice set of the zones with enrolment of the band, location weights of home and school) runs with a scratch output folder; the student, alternative and candidate tables of both halves are compared with the shipped ones."))
        C.append(code("""
if RUN_DATA_PREP:
    t0 = time.time(); res = rebuild_tables(); print(f"build: {(time.time() - t0) / 60:.1f} min"); display(res)
    nt.rebuild_verdict(res, glob.glob(os.path.join(FOLDER, "model", "estimate_*.py"))[0])
else:
    print("skipped (RUN_DATA_PREP = False)")
"""))
    return C



def silo_desc(folder):
    k = {"01_residential_puma": "puma", "02_residential_dwelling": "03"}.get(folder, folder[:2])
    C = [md("## 4. Descriptive statistics")]
    if k == "puma":
        C.append(code("""
J_ = len(IDX)
cty = ZS.groupby("PUMA_10").COUNTYFIPS.agg(lambda c: c.mode().iloc[0]); name = ZS.drop_duplicates("COUNTYFIPS").set_index("COUNTYFIPS").JUR_NAME
IDX["county"] = IDX.puma7.map(cty).map(name); IDX["area_group"] = nt.area_group_of_county(IDX.puma7.map(cty).fillna(0).astype(int))
HO = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "puma_holdout.parquet"))
ch, chh = IDX.iloc[df.choice.values], IDX.iloc[HO.choice.values]
t = pd.DataFrame({"movers": ch.puma7.value_counts()}).join(IDX.set_index("puma7")[["county"]]); t["share %"] = (100 * t.movers / t.movers.sum()).round(2)
display(t.head(15))
ag = nt.half_comparison(ch.area_group.astype(str).values, chh.area_group.astype(str).values, "area group of the destination PUMA")
nt.bar(ag["estimation half %"], "area group of the destination PUMA", "share of movers (%)", horizontal=True, figsize=(7, 3)); plt.tight_layout(); plt.show()
print("unavailable PUMAs:", ", ".join(f"{p} ({c})" for p, c in zip(IDX.puma7[df[[f'av_{j}' for j in range(J_)]].sum().values == 0], IDX.county[df[[f'av_{j}' for j in range(J_)]].sum().values == 0])))
"""))
        C.append(md("Destination PUMAs of the movers (the 15 largest) and the area-group shares of the two halves."))
        C.append(code("""
M_ = MOV[MOV.half == "estimation"].set_index("SERIALNO").reindex(df.household.values)
fig, ax = nt.panels(6, ncol=3, w=4.3, h=2.8)
nt.bar((100 * M_.size4.value_counts(normalize=True)).sort_index(), "household size (4 = 4+)", "share (%)", ax=ax[0])
nt.bar((100 * M_.inc_group.value_counts(normalize=True)).reindex(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]), "income group (2016 $)", "share (%)", ax=ax[1], rot=20)
nt.hist(M_.age_max, "age of the oldest member (years)", "households", bins=range(15, 96, 5), ax=ax[2])
nt.bar((100 * (M_.n_child > 0).value_counts(normalize=True)).sort_index(), "children (True: any member under 18)", "share (%)", ax=ax[3])
nt.bar((100 * M_.n_workers.clip(upper=3).value_counts(normalize=True)).sort_index(), "workers (3 = 3+)", "share (%)", ax=ax[4])
nt.hist(df.weight, "weight (coverage of origin x destination / mean)", "households", bins=40, ax=ax[5])
plt.tight_layout(); plt.show()
"""))
        C.append(md("Mover households of the PUMA table: size, income, age, children, workers, weight."))
        C.append(code("""
A_ = df[[f"av_{j}" for j in range(J_)]].to_numpy(bool); r_ = np.arange(len(df))
rows = []
for v in ["IV", "lnM", "d2", "d3", "same", "adjacent", "same_state", "commute_log", "crime_x_child", "lnddens", "own_race"]:
    X_ = df[[f"{v}_{j}" for j in range(J_)]].to_numpy()
    rows.append({"variable": v, "chosen PUMA (mean)": X_[r_, df.choice.values].mean(), "available PUMAs (mean)": X_[A_].mean()})
display(pd.DataFrame(rows).set_index("variable").round(3))
same_c = df[[f"same_{j}" for j in range(J_)]].to_numpy()[r_, df.choice.values]
print(f"destination inside the previous migration area (same > 0): {100 * (same_c > 0).mean():.1f} % of the movers")
pz = pd.read_csv(os.path.join(SH, "resloc_work", "geo_puma_zone_all.csv")); dest = ch.puma7.value_counts()
z = pz.assign(n=pz.puma7.map(dest).fillna(0) * pz.hu / pz.groupby("puma7").hu.transform("sum")).groupby("zone").n.sum()
fig, ax = plt.subplots(figsize=(7.5, 6)); nt.zone_map(z[z > 0], "movers (destination PUMA spread over its zones by housing units)", ax=ax, log=True, zoom="md"); plt.tight_layout(); plt.show()
ag
"""))
        C.append(md("Explanatory variables at the chosen PUMA against their mean over the available PUMAs, the share of moves inside the previous migration area, the destinations on the map, and the area-group shares of the two halves."))
        C.append(code("""
# chosen against available PUMAs for three explanatory variables
pick = lambda v: df[[f"{v}_{j}" for j in range(J_)]].to_numpy()
nt.chosen_vs_available([("Commute, sum of ln(1 + min)", pick("commute_log")[r_, df.choice.values], pick("commute_log")[A_]),
                        ("ln dwelling density", pick("lnddens")[r_, df.choice.values], pick("lnddens")[A_]),
                        ("ln market size", pick("lnM")[r_, df.choice.values], pick("lnM")[A_])], "Chosen PUMA against all available PUMAs, estimation movers")
nt.market_plot(os.path.join(FOLDER, "input", "data", "estimation", "market.csv"))
"""))
        C.append(md("How to read it: line = chosen PUMAs, grey = all available PUMAs; the further apart the two, the more the variable separates the choices. Market size M is the dwelling stock times a fixed turnover rate of the PUMA."))
    elif k == "01":
        C.append(code("""
IDX = pd.read_csv(os.path.join(FOLDER, "input", "data", "estimation", "county_index.csv"))
IDX["fips"] = IDX.county_fips.astype(str).str.split(";").str[0].astype(int)
IDX["area_group"] = nt.area_group_of_county(IDX.fips)
name = ZS.drop_duplicates("COUNTYFIPS").set_index("COUNTYFIPS").JUR_NAME
IDX["county"] = [";".join(name.get(int(c), c) for c in str(v).split(";")) for v in IDX.county_fips]
def chosen_shares(d, w=None):
    cs = d[[f"chosen_set_{j}" for j in range(len(IDX))]].to_numpy(float)
    cs = cs / cs.sum(axis=1, keepdims=True)                 # a destination PUMA spanning n counties: 1/n to each
    if w is not None: cs = cs * np.asarray(w)[:, None]
    return pd.Series(cs.sum(axis=0), index=IDX.county)
HO = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "county_holdout.parquet"))
s_ = chosen_shares(df); sw = chosen_shares(df, df.weight)
t = pd.DataFrame({"movers": s_.round(1), "share %": (100 * s_ / s_.sum()).round(2), "weighted share %": (100 * sw / sw.sum()).round(2)})
display(t.sort_values("movers", ascending=False).head(15))
ag = pd.DataFrame({"estimation half %": chosen_shares(df).groupby(IDX.area_group.values, observed=False).sum(),
                   "hold-out half %": chosen_shares(HO).groupby(IDX.area_group.values, observed=False).sum()})
ag = (100 * ag / ag.sum()).round(2)
nt.bar(ag["estimation half %"], "area group of the destination county", "share of movers (%)", horizontal=True, figsize=(7, 3)); plt.tight_layout(); plt.show()
"""))
        C.append(md("Destination counties of the movers (the 15 largest; a PUMA that spans several counties counts 1/n for each) and the shares by area group. The weight is the expected in-area share of origin and destination."))
        C.append(code("""
M_ = MOV[MOV.half == "estimation"].set_index("SERIALNO").reindex(df.household.values)
fig, ax = nt.panels(6, ncol=3, w=4.3, h=2.8)
nt.bar((100 * M_.size4.value_counts(normalize=True)).sort_index(), "household size (4 = 4+)", "share (%)", ax=ax[0])
nt.bar((100 * M_.inc_group.value_counts(normalize=True)).reindex(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]), "income group (2016 $)", "share (%)", ax=ax[1], rot=20)
nt.hist(df.age_oldest, "age of the oldest member (years)", "households", bins=range(15, 96, 5), ax=ax[2])
nt.bar((100 * M_.dtype.value_counts(normalize=True)).reindex(["SFD", "SFA", "MF234", "MF5plus", "MH"]), "structure type", "share (%)", ax=ax[3])
nt.bar((100 * M_.owner.map({0: "renter", 1: "owner"}).value_counts(normalize=True)), "tenure", "share (%)", ax=ax[4])
nt.bar((100 * M_.n_workers.clip(upper=3).value_counts(normalize=True)).sort_index(), "workers (3 = 3+)", "share (%)", ax=ax[5])
plt.tight_layout(); plt.show()
c = df[[f"commute_log_{j}" for j in range(len(IDX))]].to_numpy(); cs = df[[f"chosen_set_{j}" for j in range(len(IDX))]].to_numpy(float)
same = (df[[f"same_region_{j}" for j in range(len(IDX))]].to_numpy() * cs).sum(axis=1) > 0
print(f"movers within their origin county: {100 * same.mean():.1f} %; weight: mean {df.weight.mean():.3f}, min {df.weight.min():.3f}, max {df.weight.max():.3f}")
"""))
        C.append(md("Mover households: size, income, age of the oldest member, structure type and tenure of the new dwelling, workers."))
        C.append(code("""
pz = pd.read_csv(os.path.join(SH, "resloc_work", "geo_puma_zone_all.csv"))
dest = M_.puma7.value_counts()
z = pz.assign(n=pz.puma7.map(dest).fillna(0) * pz.hu / pz.groupby("puma7").hu.transform("sum")).groupby("zone").n.sum()
fig, ax = plt.subplots(figsize=(7.5, 6)); nt.zone_map(z[z > 0], "movers (destination PUMA spread over its zones by housing units)", ax=ax, log=True, zoom="md"); plt.tight_layout(); plt.show()
ag
"""))
        C.append(md("Destinations of the movers (Maryland and DC; a PUMA is spread over its zones by housing units) and the area-group shares of the two halves."))
    elif k == "02":
        C.append(code("""
CT = ["SFD", "SFA", "MF", "MH"]
ch = pd.DataFrame({"zone": df.zone_0, "stype": df.stype_0})
ch["area_group"] = nt.area_group_of_zone(ch.zone)
HF = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "zone_holdout_fullset.parquet"), columns=["household", "chosen", "zone", "stype"])
hc = HF[HF.chosen == 1]
t = pd.concat({"structure type": nt.half_comparison(ch.stype, hc.stype, "x"),
               "area group": nt.half_comparison(ch.area_group.astype(str), nt.area_group_of_zone(hc.zone).astype(str), "x")})
sh = nt.shares_table(ch.stype, df.weight_rts_wthhfin).reindex(CT)
fig, ax = nt.panels(2, ncol=2, w=5.5, h=3)
nt.grouped_bars(sh[["share %", "weighted share %"]].rename(columns={"share %": "unweighted", "weighted share %": "survey weight"}), "structure type of the home", "share of households (%)", ax=ax[0], colors=[nt.OBS, nt.LIGHT])
a = ch.area_group.value_counts().reindex(nt.AREA_GROUPS); nt.bar(100 * a / a.sum(), "area group of the home zone", "share (%)", ax=ax[1], horizontal=True)
plt.tight_layout(); plt.show()
print("alternatives per household:", df[[f"av_{j}" for j in range(30)]].sum(axis=1).value_counts().sort_index().to_dict())
"""))
        C.append(md("Observed structure type (unweighted and with the survey household weight) and area of the home zone."))
        C.append(code("""
fig, ax = nt.panels(6, ncol=3, w=4.3, h=2.8)
nt.bar((100 * df.hhsize.clip(upper=6).value_counts(normalize=True)).sort_index(), "household size (6 = 6+)", "share (%)", ax=ax[0])
nt.bar((100 * df.inc_group.value_counts(normalize=True)).reindex(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]), "income group", "share (%)", ax=ax[1], rot=20)
nt.bar((100 * df.car.value_counts(normalize=True)).reindex(["nocar", "carlt", "carge"]), "cars (none / fewer than 16+ / enough)", "share (%)", ax=ax[2])
nt.bar((100 * df.children.value_counts(normalize=True)).sort_index(), "children (1 yes)", "share (%)", ax=ax[3])
nt.hist(df.age_oldest, "age of the oldest member (years)", "households", bins=range(15, 96, 5), ax=ax[4])
nt.hist(df.weight, "estimation weight (household weight / mean)", "households", bins=50, ax=ax[5])
plt.tight_layout(); plt.show()
fig, ax = plt.subplots(figsize=(7.5, 6)); nt.zone_map(ch.zone.value_counts(), "households (home zone)", ax=ax, log=True); plt.tight_layout(); plt.show()
t
"""))
        C.append(md("Households of the estimation half: size, income, cars, children, age, weight; home zones; shares of the two halves."))
    elif k == "03":
        C.append(code("""
TY = ["SFD", "SFA", "MF234", "MF5plus", "MH"]
HO = pd.read_parquet(os.path.join(FOLDER, "input", "data", "holdout", "dwelling_holdout.parquet"), columns=["type_0", "cost_0", "bedrooms_0"])
fig, ax = nt.panels(3, ncol=3, w=4.3, h=2.9)
c = df.type_0.value_counts().reindex(TY); nt.bar(100 * c / c.sum(), "structure type of the chosen dwelling", "share (%)", ax=ax[0])
nt.hist(df.cost_0.clip(upper=4000), "monthly housing cost of the chosen dwelling (2016 $)", "households", bins=50, ax=ax[1])
c = df.bedrooms_0.clip(upper=5).value_counts().sort_index(); nt.bar(100 * c / c.sum(), "bedrooms (5 = 5+)", "share (%)", ax=ax[2])
plt.tight_layout(); plt.show()
alt = pd.DataFrame({"chosen dwelling": [df.cost_0.median(), df.bedrooms_0.mean()],
                    "sampled alternatives": [np.nanmedian(df[[f"cost_{j}" for j in range(1, 30)]].to_numpy()), np.nanmean(df[[f"bedrooms_{j}" for j in range(1, 30)]].to_numpy())]},
                   index=["median monthly cost ($)", "mean bedrooms"]).round(1)
alt
"""))
        C.append(md("Chosen dwellings: structure type, monthly housing cost and bedrooms; the 29 sampled alternatives come from the same PUMA's pool of recently occupied dwellings."))
        C.append(code("""
# chosen against sampled dwellings: cost share of income and bedrooms minus household size
cs = lambda j: 12 * df[f"cost_{j}"] / np.maximum(df.income_2016usd, 5000)
alts_cs = np.concatenate([cs(j).to_numpy() for j in range(1, 30)]); alts_bd = np.concatenate([(df[f"bedrooms_{j}"] - df.persons.clip(upper=5)).to_numpy() for j in range(1, 30)])
nt.chosen_vs_available([("Housing cost / income", cs(0).clip(upper=1.5), np.clip(alts_cs, None, 1.5)),
                        ("Bedrooms minus household size", df.bedrooms_0 - df.persons.clip(upper=5), alts_bd)], "Chosen against the 29 sampled dwellings, estimation movers")
"""))
        C.append(md("How to read it: line = chosen dwellings, grey = the 29 sampled dwellings; the further apart the two, the more the variable separates the choices."))
        C.append(code("""
fig, ax = nt.panels(4, ncol=4, w=3.4, h=2.8)
nt.bar((100 * df.persons.clip(upper=6).value_counts(normalize=True)).sort_index(), "persons (6 = 6+)", "share (%)", ax=ax[0])
nt.hist(df.income_2016usd.clip(upper=300000) / 1000, "household income (2016 k$)", "households", bins=50, ax=ax[1])
nt.bar((100 * df.children_any.value_counts(normalize=True)).sort_index(), "children (1 yes)", "share (%)", ax=ax[2])
nt.hist(df.age_oldest, "age of the oldest member (years)", "households", bins=range(15, 96, 5), ax=ax[3])
plt.tight_layout(); plt.show()
pz = pd.read_csv(os.path.join(SH, "resloc_work", "geo_puma_zone_all.csv")); dest = df.puma7.value_counts()
z = pz.assign(n=pz.puma7.map(dest).fillna(0) * pz.hu / pz.groupby("puma7").hu.transform("sum")).groupby("zone").n.sum()
fig, ax = plt.subplots(figsize=(7.5, 6)); nt.zone_map(z[z > 0], "movers (PUMA of the dwelling spread over its zones)", ax=ax, log=True, zoom="md"); plt.tight_layout(); plt.show()
t = pd.concat({"structure type": nt.half_comparison(df.type_0, HO.type_0, "x"),
               "bedrooms": nt.half_comparison(df.bedrooms_0.clip(upper=5), HO.bedrooms_0.clip(upper=5), "x")})
t
"""))
        C.append(md("Mover households (persons, income, children, age), their PUMAs, and the shares of the two halves (estimation 80 %, hold-out 20 %)."))
    elif k == "04":
        C.append(code("""
HO = pd.read_csv(os.path.join(FOLDER, "input", "data", "holdout", "car_ownership_holdout.csv"))
W_ = HH[HH.half == "estimation"].set_index("serial").reindex(df.serial.astype(str).values)
assert W_.w.notna().all()
sh = nt.shares_table(df.cars.map({0: "0", 1: "1", 2: "2", 3: "3+"}), W_.w.values)
display(sh)
nt.grouped_bars(sh[["share %", "weighted share %"]].rename(columns={"share %": "unweighted", "weighted share %": "household weight (WGTP)"}), "cars of the household", "share of households (%)", colors=[nt.OBS, nt.LIGHT])
plt.tight_layout(); plt.show()
"""))
        C.append(md("Observed cars per household, unweighted and with the PUMS household weight (the estimation is unweighted)."))
        C.append(code("""
fig, ax = nt.panels(8, ncol=4, w=3.4, h=2.8)
nt.bar((100 * W_.hhsize.clip(upper=6).value_counts(normalize=True)).sort_index(), "persons (6 = 6+)", "share (%)", ax=ax[0])
nt.bar((100 * df.workers.clip(upper=4).value_counts(normalize=True)).sort_index(), "workers (4 = 4+)", "share (%)", ax=ax[1])
nt.bar((100 * df.children.clip(upper=4).value_counts(normalize=True)).sort_index(), "children under 16 (4 = 4+)", "share (%)", ax=ax[2])
nt.hist(W_.income_k.clip(upper=400), "household income (2016 k$)", "households", bins=50, ax=ax[3])
nt.hist(df.age10 * 10 + 45, "age of the oldest member (years)", "households", bins=range(15, 96, 5), ax=ax[4])
dw = pd.Series(np.select([df.sfd == 1, df.multifamily == 1], ["single-family detached", "multi-family"], "other")).value_counts()
nt.bar(100 * dw / dw.sum(), "dwelling", "share (%)", ax=ax[5], rot=20)
nt.hist(df.ln_density, "ln density of the PUMA", "households", bins=40, ax=ax[6])
nt.hist(df.acc_gain, "accessibility gain of a car", "households", bins=40, ax=ax[7])
plt.tight_layout(); plt.show()
print("share without a car (%) by workers:", (100 * df.groupby(df.workers.clip(upper=3)).cars.apply(lambda c: (c == 0).mean())).round(1).to_dict())
"""))
        C.append(md("Households of the estimation half: persons, workers, children, income, age, dwelling, density and the accessibility gain of owning a car."))
        C.append(code("""
r = df.groupby("puma7").cars.apply(lambda c: 100 * (c == 0).mean())
z = ZS.set_index("zone").PUMA_10.map(r).dropna()
fig, ax = plt.subplots(figsize=(7.5, 6)); nt.zone_map(z, "households without a car (%), by PUMA", ax=ax, zoom="md"); plt.tight_layout(); plt.show()
nt.half_comparison(df.cars, HO.cars, "cars")
"""))
        C.append(md("Share of households without a car by PUMA (Maryland), and the car shares of the two halves."))
    elif k == "05":
        C.append(code("""
HO = pd.read_csv(os.path.join(FOLDER, "input", "data", "holdout", "workplace_holdout_workers.csv"))
ag = pd.concat({"home": nt.half_comparison(nt.area_group_of_zone(df.home_zone).astype(str), nt.area_group_of_zone(HO.home_zone).astype(str), "x"),
                "workplace": nt.half_comparison(nt.area_group_of_zone(df.work_zone).astype(str), nt.area_group_of_zone(HO.work_zone).astype(str), "x")})
od = pd.crosstab(nt.area_group_of_zone(df.home_zone), nt.area_group_of_zone(df.work_zone), normalize="index").mul(100).round(1)
od.index.name = "home area"; od.columns.name = "workplace area"
display(od)
fig, ax = nt.panels(3, ncol=3, w=4.4, h=2.9)
nt.hist(df.t_0.clip(upper=120), "car time home - workplace (min, AM peak)", "workers", bins=48, ax=ax[0])
b = nt.binned(df.t_0, [0, 10, 20, 30, 45, 60, 90, 1e9], ["<10", "10-20", "20-30", "30-45", "45-60", "60-90", "90+"]); nt.bar(b, "car time to work (min)", "share of workers (%)", ax=ax[1])
nt.hist(df[[f"t_{j}" for j in range(1, 100)]].to_numpy().ravel().clip(max=240), "car time to the sampled alternatives (min)", "alternatives", bins=48, ax=ax[2], color=nt.LIGHT)
plt.tight_layout(); plt.show()
print(f"median car time to work {df.t_0.median():.1f} min (sampled alternatives {np.nanmedian(df[[f't_{j}' for j in range(1, 100)]].to_numpy()):.1f} min); same zone: {100 * (df.home_zone == df.work_zone).mean():.1f} %")
"""))
        C.append(md("Workplace area by home area (row %), car time to the chosen workplace against the 99 sampled zones (uniform over the zones with jobs)."))
        C.append(code("""
fig, ax = nt.panels(6, ncol=3, w=4.3, h=2.8)
nt.bar((100 * df.income_group.value_counts(normalize=True)).sort_index(), "income group (1 < 40k ... 4 125k+)", "share (%)", ax=ax[0])
nt.bar((100 * df.car_seg.map({0: "no car", 1: "cars < workers", 2: "cars >= workers"}).value_counts(normalize=True)), "cars", "share (%)", ax=ax[1], rot=20)
nt.hist(df.age, "age (years)", "workers", bins=range(15, 86, 5), ax=ax[2])
nt.bar((100 * df.female.value_counts(normalize=True)).sort_index(), "female (1 yes)", "share (%)", ax=ax[3])
nt.bar((100 * df.lic.value_counts(normalize=True)).sort_index(), "driving licence (1 yes)", "share (%)", ax=ax[4])
nt.bar((100 * df.hhs.value_counts(normalize=True)).sort_index(), "household size variable hhs", "share (%)", ax=ax[5])
plt.tight_layout(); plt.show()
jz = pd.read_csv(os.path.join(FOLDER, "input", "data", "holdout", "zones_with_jobs.csv"))
fig, ax = nt.panels(3, ncol=3, w=4.4, h=2.9)
jz["jobs"] = jz[["jobs_RET", "jobs_OFF", "jobs_IND", "jobs_OTH"]].sum(axis=1)
nt.hist(np.log1p(jz.jobs), "ln(1 + jobs) of a zone", "zones", bins=40, ax=ax[0])
nt.hist(100 * jz.z_off_sh, "office share of the jobs of a zone (%)", "zones", bins=40, ax=ax[1])
nt.hist(np.log1p(df.jobs_OFF_0 + df.jobs_RET_0 + df.jobs_IND_0 + df.jobs_OTH_0), "ln(1 + jobs) of the chosen zone", "workers", bins=40, ax=ax[2])
plt.tight_layout(); plt.show()
"""))
        C.append(md("Workers (income group, cars, age, sex, licence, household size) and the job attraction of the zones."))
        C.append(code("""
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
nt.zone_map(df.home_zone.value_counts(), "workers (home zone)", ax=ax[0], log=True)
nt.zone_map(df.work_zone.value_counts(), "workers (workplace zone)", ax=ax[1], log=True)
ax[0].set_title("homes", fontsize=10); ax[1].set_title("workplaces", fontsize=10)
plt.tight_layout(); plt.show()
ag
"""))
        C.append(md("Home and workplace zones of the workers, and the area shares of the two halves (the hold-out is evaluated on all 1,587 zones with jobs)."))
    else:
        C.append(code("""
CAND = cand.merge(st[["student"]], on="student")
w = st.set_index("student")
c = CAND.copy()
c["wh"] = [w.at[s_, f"w_home_{h}"] for s_, h in zip(c.student, c.home_slot)]
c["ws"] = [w.at[s_, f"w_school_{k}"] for s_, k in zip(c.student, c.school_slot)]
c["p"] = c.wh * c.ws; c["p"] = c.p / c.groupby("student").p.transform("sum")
tb = pd.DataFrame({"chosen school": [np.average(c.t, weights=c.p)], "all available zones": [np.average(alt.t, weights=alt.av > 0)]}, index=["mean car time (min)"]).round(1)
fig, ax = nt.panels(3, ncol=3, w=4.4, h=2.9)
ax[0].hist(c.t.clip(upper=90), bins=45, weights=c.p, color=nt.OBS); ax[0].set_xlabel("car time home - school (min)"); ax[0].set_ylabel("students")
b = (c.zone.map(dict(zip(ZS.zone, ZS.area_group.astype(str)))))
a = c.groupby(b).p.sum().reindex(nt.AREA_GROUPS).fillna(0); nt.bar(100 * a / a.sum(), "area group of the school zone", "share (%)", ax=ax[1], horizontal=True)
nt.bar(st.band.value_counts(), "enrolment band", "students", ax=ax[2])
plt.tight_layout(); plt.show()
print(f"possible home zones per student: {st.filter(like='w_home_').gt(0).sum(axis=1).value_counts().sort_index().to_dict()}; "
      f"possible school zones: {st.filter(like='w_school_').gt(0).sum(axis=1).value_counts().sort_index().to_dict()}")
tb
"""))
        C.append(md("Car time from home to the chosen school (weighted over the possible home and school zones), area of the school zone and enrolment band."))
        C.append(code("""
# car time to the chosen school zone against all available zones (chosen weighted by the location weights)
nt.chosen_vs_available([("Car time home - school (min)", np.repeat(c.t.values, np.maximum(1, (c.p * 20).round().astype(int).values)).clip(max=90),
                         alt.t[alt.av > 0].clip(upper=90).values)], "Chosen school zone against the available zones, estimation students")
"""))
        C.append(md("How to read it: line = chosen school zones, grey = all available zones; the further apart the two, the more car time separates the choices."))
        C.append(code("""
fig, ax = nt.panels(5, ncol=5, w=3, h=2.7)
nt.hist(st.age, "age (years)", "students", bins=range(0, 60, 1), ax=ax[0])
nt.bar((100 * st.female.value_counts(normalize=True)).sort_index(), "female (1 yes)", "share (%)", ax=ax[1])
nt.bar((100 * st.income_group.value_counts(normalize=True)).sort_index(), "income group", "share (%)", ax=ax[2])
car = pd.Series(np.select([st.car0 == 1, st.carlow == 1], ["no car", "cars < drivers"], "enough cars")).value_counts()
nt.bar(100 * car / car.sum(), "cars", "share (%)", ax=ax[3], rot=20)
z = alt[alt.av > 0].drop_duplicates("zone").zone.nunique(); ax[4].axis("off"); ax[4].text(0, 0.5, f"{z:,} zones with enrolment\\nof the segment's bands", fontsize=10)
plt.tight_layout(); plt.show()
SZ = pd.read_parquet(os.path.join(SH, "school_choice_work", "zone_size.parquet"))
fig, ax = plt.subplots(1, 2, figsize=(13, 5.6))
nt.zone_map(c.groupby("zone").p.sum(), "students (school zone)", ax=ax[0], log=True)
hz_ = st.melt(id_vars="student", value_vars=[x for x in st.columns if x.startswith("home_zone_")], value_name="zone")
nt.zone_map(hz_[hz_.zone > 0].zone.value_counts(), "students (possible home zones)", ax=ax[1], log=True)
ax[0].set_title("schools", fontsize=10); ax[1].set_title("homes", fontsize=10)
plt.tight_layout(); plt.show()
"""))
        C.append(md("Students (age, sex, income group, cars) and their school and home zones."))
        C.append(code("""
sth = pd.read_parquet(os.path.join(os.path.dirname(M.DATA).replace(os.sep + "estimation", os.sep + "holdout"), os.path.basename(M.DATA).replace("_estimation", "_holdout") + "_students.parquet"))
pd.concat({"enrolment band": nt.half_comparison(st.band, sth.band, "x"), "income group": nt.half_comparison(st.income_group, sth.income_group, "x")})
"""))
        C.append(md("Bands and income groups of the two halves."))
    return C


SILO_FAMILY = {f: silo_cells for f in ["01_residential_puma", "02_residential_dwelling", "04_car_ownership",
                                       "05_workplace_choice", "06_school_location_K8", "07_school_location_high_school", "08_school_location_college"]}
