#!/usr/bin/env python3
"""Coefficient set activity/parameters (formerly 3_abit/coef_respec): a copy of the model of record <workspace>/3_abit/coef_tasha
with the re-specified MAST models of the estimation results (ESTIMATION_RESULTS, adopted 2026-11-09) written into the engine's
files.  coef_tasha is never written.  Paths in run_params.csv are written with the placeholders {PARAMETERS} (the coefficient
directory of the run) and {WORKSPACE}; activity/write_properties.py substitutes them.  build_state.json and TASHA_STATE.json
record workspace paths as <workspace>/...

Sources (the files the estimation tables read: estimation/development/reports/make_pdf.py NEW map, tables/t_new_tables.py,
primary_destination_pooled/t_pooled.py; folder names below are the result folders under ESTIMATION_RESULTS):
  tour_mode_choice.csv          mode_choice/m08_coef.csv step final (work, shopping, other), m09_coef.csv step final (school);
                                school's person / household terms common to bus and train (<v>_PT) written to both <v>_BUS and <v>_TRAIN
  parking_paid_share.csv        3_abit/mode_choice/results/parking_paid_share.csv (park_area,share), the paid-parking variable
  dest_choice_mnl.csv           <P>_primary      dest_pooled/dp_final.pkl (pooled model, purpose scales folded in: every linear
                                                 coefficient and mu_size times the purpose's scale; size weights exp(theta),
                                                 not scaled; d_50_inf held at 0 = absent)
                                <P>_seq_stop     dest_stop/s_<p>_coef.csv final (sequential anchors); the mode-choice logsum 'ls'
                                <P>_stop         of these models is the logsum of the re-specified tour models -> variable
                                                 'lstour'; the same coefficients for the two-anchor form (_stop) used for joint
                                                 stops; mu_size absent in the final = held at 1
                                EDUCATION_daycare, EDUCATION_nonstud   locations/lp_edu_final.pkl (pooled; daycare's linear terms
                                                 times its scale; mu held at 1 in both and not scaled, as estimated)
                                WORK_wahb l03, WORK_wbhome l04, WORK_wbwork_stop l05, OTHER_wbs l06 (locations/<name>_coef.csv final)
  tasha/tasha_return_home.csv   activity/a03_return_coef.csv final
  tasha/tasha_subtour.csv       gen.* = activity/a01_outing_coef.csv final, mode.* = a02_outing_mode_coef.csv final; the outing
                                distributions (n.outings, n.stops, leave, purpose, dur) are kept from coef_tasha
  run_params.csv                mc.coef.file -> this set; + mc.park.share.file, mc.apply.short = false, mc.apply.joint = true,
                                mc.cd.availability = estimation, mc.car.allocation = tasha
  build_state.json             sha256 of every source and written file
  TERM_MAP.csv                  every estimated term: engine file, segment, engine variable, status (supported = the engine applied
                                the term before; coefficient file = written by this script in another form; Java = new engine code
                                of 2026-11-09, switched on by the term's key)
    python3 activity/build_parameters.py [--force]
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import hashlib, json, os, pickle, re, shutil, sys, time
import numpy as np, pandas as pd

V = WORKSPACE; A3 = f"{V}/3_abit"                        # data: coef_tasha, mode_choice/results, estimation_distributions
SRC, OUT = f"{A3}/coef_tasha", f"{MILES_HOME}/activity/parameters"


def ws_text(p):
    """a path as provenance text: <workspace>/... inside the workspace, else <estimation_results>/... inside the estimation results"""
    p = os.path.abspath(p)
    for root, tag in ((V, "<workspace>"), (ESTIMATION_RESULTS, "<estimation_results>")):
        if p == root or p.startswith(root + os.sep):
            return tag + p[len(root):]
    return p
SBS = f"{ESTIMATION_RESULTS}"
MC, DP, DS, LO, AC = f"{SBS}/mode_choice", f"{SBS}/dest_pooled", f"{SBS}/dest_stop", f"{SBS}/locations", f"{SBS}/activity"
PARK = f"{A3}/mode_choice/results/parking_paid_share.csv"
LICF = f"{A3}/estimation_distributions/tasha_respec/tasha_frequency.csv"; STARTF = f"{A3}/estimation_distributions/tasha_respec/tasha_start.csv"
PROPF = f"{A3}/estimation_distributions/tasha_respec/tasha_joint_propensity_mand.csv"
ALTS = ["CD", "WK", "BK", "CP", "BUS", "TRAIN"]
SOCIO = ["age", "male", "lic", "hhsize", "autos", "core_o", "rural_o", "core_d", "rural_d", "joint", "short", "acc", "rec", "kids", "park", "stops"]
ABBR = {"SHOPPING": "S", "RECREATION": "R", "ACCOMPANY": "A", "OTHER": "O"}
LIN_OK = re.compile(r"^(d_\d+_(\d+|inf)|dt_\d+_(\d+|inf)|d|dt|lnd|lndt|lnd_\w+|lndt_\w+|ctime|cgt|ls|lstour|intra|intra_a|intra_b|bc|dcz|va|othst|cbd|lnretden|mix|xcounty|xstate|ptav|ptav_car0)$")
FLAGS = {"inc0", "inc2", "car0", "car1", "child", "kid", "senior", "worker", "am", "pm", "ev", "nonauto", "worktour", "inbound", "multi", "male", "hh1", "hhsize"}
RH_VARS = {"const", "sl_0_05", "sl_05_1", "sl_1_2", "sl_2_4", "sl_4_inf", "lnslack", "detour_km", "lndetour", "dhome_km", "a_work", "a_school", "a_acc", "a_shop",
           "a_joint", "e_work", "e_school", "e_acc", "e_shop", "e_joint", "worker", "stud_k12", "stud_ps", "retiree", "toddler", "nep3", "nep4", "nep5", "am", "pm",
           "ev", "jj", "jmand", "female", "lic", "hhsize", "kids", "car0", "carshort", "inc_low", "inc_high", "nep"}
GEN_VARS = {"const", "sp_0_4", "sp_4_7", "sp_7_inf", "arr_early", "arr_late", "sw", "age_u30", "age_55p", "female", "inc_low", "inc_high", "car0", "carshort",
            "kids", "cbd_w", "lnretden_w", "lncomm", "lnacc2"}
MODE_VARS = {"const", "lnkm", "km", "cbd_w", "lnretden_w", "tm_cd", "tm_cp", "multi", "car0", "carshort", "age_u30", "age_55p", "female", "inc_low", "inc_high", "kids"}


def sha(p):
    h = hashlib.sha256(); h.update(open(p, "rb").read()); return h.hexdigest()


def final(path, step="final"):
    c = pd.read_csv(path); c = c[c.step == step]; assert len(c), f"no {step} rows in {path}"
    return dict(zip(c.param, c.coef.astype(float)))


# ------------------------------------------------------------------------------------------------ tour mode choice
def mode_choice():
    rows = []
    for seg, f in [("work", "m08"), ("shopping", "m08"), ("other", "m08"), ("school", "m09"), ("shopping_joint", "m11_joint"), ("other_joint", "m11_joint")]:
        c = pd.read_csv(f"{MC}/{f}_coef.csv"); c = c[(c.step == "final") & (c.segment == seg)]
        assert len(c), seg
        for p, v in zip(c.param, c.coef.astype(float)):
            if p.endswith("_PT"):
                for a in ("BUS", "TRAIN"): rows.append((seg, p[:-3] + "_" + a, v))
            else: rows.append((seg, p, v))
    for seg, p, v in rows:   # every term must be one the engine applies
        ok = p in ("gc", "time", "cost", "mu_auto", "mu_transit", "mu_nonmot") or re.match(r"^(ASC|km|gc)_(%s)$" % "|".join(ALTS), p) \
             or (p.rsplit("_", 1)[0] in SOCIO and p.rsplit("_", 1)[1] in ALTS)
        assert ok, f"tour mode choice: term {seg} {p} not in the engine"
        assert not p.startswith("ovt"), p
    return pd.DataFrame(rows, columns=["segment", "parameter", "value"])


# ------------------------------------------------------------------------------------------------ location models
def seg_rows(seg, lin, base, comps, mu):
    """engine rows: mu_size, size_<base> = 1, size_<c> = exp(theta_c), linear terms"""
    out = [(seg, "mu_size", float(mu)), (seg, f"size_{base}", 1.0)] + [(seg, f"size_{c}", float(np.exp(t))) for c, t in comps.items()]
    for k, v in lin.items():
        assert LIN_OK.match(k), f"{seg}: term {k} not in the engine"
        if k.startswith(("lnd_", "lndt_")): assert k.split("_", 1)[1] in FLAGS, f"{seg}: flag of {k}"
        if v != 0.0: out.append((seg, k, float(v)))
    return out


def log_spec(path):
    """size base and the 'mu fixed at 1' note of the final specification line of an estimation log"""
    l = [x for x in open(path).read().splitlines() if x.startswith("final specification")][-1]
    return l.split("size base ")[1].split(",")[0].strip(), "mu fixed at 1" in l


def separate(name, seg, d=LO, rename=None):
    b = final(f"{d}/{name}_coef.csv"); base, mu1 = log_spec(f"{d}/{name}.log")
    comps = {k[6:]: v for k, v in b.items() if k.startswith("theta_")}
    mu = b.get("mu_size", 1.0); assert ("mu_size" in b) != mu1, f"{name}: mu_size and log disagree"
    lin = {(rename or {}).get(k, k): v for k, v in b.items() if not k.startswith("theta_") and k != "mu_size"}
    return seg_rows(seg, lin, base, comps, mu)


def pooled_primary():
    d = pickle.load(open(f"{DP}/dp_final.pkl", "rb")); x, S, specs, fixed = d["x"], d["S"], d["specs"], d["fixed"]
    P = list(specs); rows = []
    def key(p, q):
        for g in S.get(q, []):
            if p in g:
                hold = [r for r in P if r in g and q in specs[r][0] + [f"theta_{c}" for c in specs[r][2]] + ["mu_size"]]
                allh = [r for r in P if q in specs[r][0] + [f"theta_{c}" for c in specs[r][2]] + ["mu_size"]]
                return ("shared" if hold == allh and len(hold) > 2 else "+".join(ABBR[r] for r in hold)) + "|" + q
        return f"{p}|{q}"
    for p in P:
        lin_names, base, comps = specs[p]; sc = float(x.get(f"scale|{p}", 1.0))
        lin = {}
        for q in lin_names:
            k = key(p, q)
            if fixed.get(k) == 0.0: continue
            lin[q] = sc * float(x[k])
        th = {c: float(x[key(p, f"theta_{c}")]) for c in comps}
        mu = sc * float(x[key(p, "mu_size")])
        rows += seg_rows(f"{p}_primary", lin, base, th, mu)
    # the coefficient table rows (V units, before the scale) must be the pickle's values
    c = pd.read_csv(f"{DP}/dp_coef.csv"); c = c[c.step == "final"]
    for r in c.itertuples():
        k = ("scale|" + r.purpose) if r.param == "scale" else f"{r.purpose}|{r.param}"
        assert abs(x[k] - r.coef) < 1e-9, (k, x[k], r.coef)
    return rows


def pooled_edu():
    d = pickle.load(open(f"{LO}/lp_edu_final.pkl", "rb")); x, S, specs, fixed = d["x"], d["S"], d["specs"], d["fixed"]
    seg = {"l01_daycare": "EDUCATION_daycare", "l02_nonstud": "EDUCATION_nonstud"}; rows = []
    for p, (lin_names, base, comps, mu_fixed) in specs.items():
        sc = float(x.get(f"scale|{p}", 1.0)); lin = {}
        for q in lin_names:
            k = f"N+D|{q}" if q in S else f"{p}|{q}"
            if fixed.get(k) == 0.0: continue
            lin[q] = sc * float(x[k])
        assert mu_fixed == 1.0   # held at 1, not a parameter: the scale does not multiply it (dc_model.utility, mu_fixed)
        rows += seg_rows(seg[p], lin, base, {c: float(x[f"{p}|theta_{c}"]) for c in comps}, 1.0)
    c = pd.read_csv(f"{LO}/lp_edu_coef.csv"); c = c[c.step == "final"]
    for r in c.itertuples():
        k = ("scale|" + r.purpose) if r.param == "scale" else f"{r.purpose}|{r.param}"
        assert abs(x[k] - r.coef) < 1e-9, (k, x[k], r.coef)
    return rows


def dest_mnl():
    rows = pooled_primary()
    for nm, p in [("shop", "SHOPPING"), ("rec", "RECREATION"), ("acc", "ACCOMPANY"), ("oth", "OTHER")]:
        for seg in (f"{p}_seq_stop", f"{p}_stop"): rows += separate(f"s_{nm}", seg, DS, rename={"ls": "lstour"})
    rows += pooled_edu()
    for nm, seg in [("l03_wahb", "WORK_wahb"), ("l04_wbhome", "WORK_wbhome"), ("l05_wbwork", "WORK_wbwork_stop"), ("l06_outing_dest", "OTHER_wbs")]:
        rows += separate(nm, seg)
    df = pd.DataFrame(rows, columns=["segment", "variable", "value"])
    old = set(pd.read_csv(f"{SRC}/dest_choice_mnl.csv").segment)
    assert set(df.segment) == old, f"segments differ from coef_tasha: {set(df.segment) ^ old}"
    return df


# ------------------------------------------------------------------------------------------------ activity models
def activity(out_dir):
    rh = final(f"{AC}/a03_return_coef.csv"); assert set(rh) <= RH_VARS, set(rh) - RH_VARS
    pd.DataFrame({"variable": list(rh), "value": list(rh.values())}).to_csv(f"{out_dir}/tasha/tasha_return_home.csv", index=False)
    gen, mo = final(f"{AC}/a01_outing_coef.csv"), final(f"{AC}/a02_outing_mode_coef.csv")
    assert set(gen) <= GEN_VARS, set(gen) - GEN_VARS; assert set(mo) <= MODE_VARS, set(mo) - MODE_VARS
    lines = open(f"{SRC}/tasha/tasha_subtour.csv").read().splitlines()
    keep = [l for l in lines[1:] if not l.startswith(("gen.", "mode."))]
    new = [lines[0]] + [f"gen.{k},{v!r}" for k, v in gen.items()] + [f"mode.{k},{v!r}" for k, v in mo.items()] + keep
    open(f"{out_dir}/tasha/tasha_subtour.csv", "w").write("\n".join(new) + "\n")


JAVA_MC = {"time": "generic minutes of CD, CP, BUS, TRAIN", "cost": "generic $ of CD, CP, BUS, TRAIN", "kids": "household member under 18",
           "park": "paid-parking share of the main-activity zone's area", "stops": "tour with a stop besides the main activity"}


def term_map():
    rows = []
    mc = mode_choice(); m9 = set(pd.read_csv(f"{MC}/m09_coef.csv").query("step == 'final'").param)
    for r in mc.itertuples():
        p = r.parameter; base = p.rsplit("_", 1)[0] if p.rsplit("_", 1)[-1] in ALTS else p
        src = p if not (r.segment == "school" and base + "_PT" in m9) else base + "_PT"
        if base in JAVA_MC: st, note = "Java", JAVA_MC[base]
        elif src.endswith("_PT"): st, note = "coefficient file", "bus and train share the term: written to both"
        elif base == "short": st, note = "Java", "not in the re-estimated models (TASHA car allocation instead)"
        elif base == "joint": st, note = "Java", "applied as estimated to tours whose main activity is a joint household episode, at the household stage (mc.apply.joint; coef_tasha: 0); 0 in the stop logsum"
        else: st, note = "supported", ""
        rows.append(("tour mode choice", r.segment, src, "tour_mode_choice.csv", p, st, note))
    dm = dest_mnl()
    scale = {"SHOPPING": 1.0}; d = pickle.load(open(f"{DP}/dp_final.pkl", "rb"))["x"]
    for p in ("RECREATION", "ACCOMPANY", "OTHER"): scale[p] = d[f"scale|{p}"]
    for r in dm.itertuples():
        v, seg = r.variable, r.segment; fam = "primary destination (pooled)" if seg.endswith("_primary") else "stop" if "stop" in seg and not seg.startswith("WORK") else "location"
        if v.startswith("size_") or v == "mu_size":
            st, note = "coefficient file", "size weight exp(theta), base 1" if v.startswith("size_") else ("mu held at 1" if r.value == 1.0 else "")
            if seg.endswith("_primary") and v == "mu_size" and scale[seg.split("_")[0]] != 1.0: note = f"mu_size x scale {scale[seg.split('_')[0]]:.4f}"
        elif v == "lstour": st, note = "Java", "logsum of the re-specified tour models (estimation: 'ls' of s_stops_newls)"
        elif v.split("_", 1)[-1] in ("male", "hh1", "hhsize") and v.startswith(("lnd_", "lndt_")): st, note = "Java", "new chooser flag"
        else: st, note = "supported", ""
        if seg.endswith("_primary") and v not in ("mu_size",) and not v.startswith("size_") and scale[seg.split("_")[0]] != 1.0:
            note = (note + "; " if note else "") + f"x purpose scale {scale[seg.split('_')[0]]:.4f}"; st = "coefficient file" if st == "supported" else st
        if seg == "EDUCATION_daycare" and not v.startswith("size_") and v != "mu_size": note = (note + "; " if note else "") + "x scale 1.2279 (pooled with non-student school)"; st = "coefficient file" if st == "supported" else st
        if seg.endswith("_stop") and not seg.endswith("seq_stop") and not seg.startswith("WORK"): note = (note + "; " if note else "") + "same coefficients as the sequential stop model (two-anchor form, joint stops)"
        rows.append((fam, seg, v, "dest_choice_mnl.csv", v, st, note))
    for fn, mdl, keys, java in [("tasha/tasha_return_home.csv", "return home", final(f"{AC}/a03_return_coef.csv"), {"female", "lic", "hhsize", "kids", "car0", "carshort", "inc_low", "inc_high", "nep"}),
                                ("tasha/tasha_subtour.csv", "outing occurrence", final(f"{AC}/a01_outing_coef.csv"), set()),
                                ("tasha/tasha_subtour.csv", "outing mode", final(f"{AC}/a02_outing_mode_coef.csv"), {"car0", "carshort", "multi"})]:
        pre = "" if mdl == "return home" else ("gen." if mdl == "outing occurrence" else "mode.")
        for k in keys: rows.append((mdl, "", k, fn, pre + k, "Java" if k in java else "supported", ""))
    pd.DataFrame(rows, columns=["model", "segment", "estimated_term", "engine_file", "engine_variable", "status", "note"]).to_csv(f"{OUT}/TERM_MAP.csv", index=False)


def main():
    force = "--force" in sys.argv
    if os.path.exists(OUT):
        if not force: raise SystemExit(f"{OUT} exists (--force rebuilds it from coef_tasha)")
        shutil.rmtree(OUT)
    mc, dm = mode_choice(), dest_mnl()          # build (and check) before anything is written
    shutil.copytree(SRC, OUT)
    if os.path.exists(f"{OUT}/TASHA_STATE.json"):   # provenance of the copied set: workspace paths as <workspace>/...
        t = open(f"{OUT}/TASHA_STATE.json").read(); open(f"{OUT}/TASHA_STATE.json", "w").write(t.replace(V, "<workspace>"))
    mc.to_csv(f"{OUT}/tour_mode_choice.csv", index=False)
    shutil.copy(PARK, f"{OUT}/parking_paid_share.csv")
    dm.to_csv(f"{OUT}/dest_choice_mnl.csv", index=False)
    activity(OUT)
    # 2026-11-10: individual discretionary frequencies (IS, IO_REC, IO_OTH) with licence cells, as IO_ACC (build_distributions.py with
    # TASHA_LIC_TYPES=IO_ACC,IS,IO_REC,IO_OTH TASHA_DIST_OUT=estimation_distributions/tasha_respec; every other row identical)
    shutil.copy(LICF, f"{OUT}/tasha/tasha_frequency.csv")
    # joint start conditional on the participants' work / school that day, drawn after the mandatory episodes (TASHA_JOINT_PB=1:
    # start rows JM / JN, levels 20-22; every other row identical)
    shutil.copy(STARTF, f"{OUT}/tasha/tasha_start.csv")
    shutil.copy(PROPF, f"{OUT}/tasha/tasha_joint_propensity_mand.csv")
    open(f"{OUT}/tasha/tasha_params.csv", "a").write("freq.licence.types,IO_ACC;IS;IO_REC;IO_OTH\njoint.start.conditional,true\n"
                                                    "joint.members.mandatory,true\njoint.propensity.mand.file,tasha_joint_propensity_mand.csv\njoint.freq.mandatory,true\n")
    rp = pd.read_csv(f"{OUT}/run_params.csv", dtype=str)
    # paths as placeholders: {PARAMETERS} = the run's coefficient directory, {WORKSPACE} = the workspace (write_properties.py)
    rp["value"] = rp.value.str.replace(f"{SRC}/", "{PARAMETERS}/", regex=False).str.replace(f"{V}/", "{WORKSPACE}/", regex=False)
    rp.loc[rp.key == "mc.coef.file", "value"] = "{PARAMETERS}/tour_mode_choice.csv"
    # author's choice (2026-11-09): short and joint as estimated, car-driver availability by the estimation rule, no car allocation
    # author's choices (2026-11-09): joint as estimated; 'fewer cars than drivers' is not in the re-estimated models (car availability
    # follows the household car allocation): TASHA allocation of the household's cars (mc.car.allocation = tasha)
    rp = pd.concat([rp, pd.DataFrame({"key": ["mc.park.share.file", "mc.apply.short", "mc.apply.joint", "mc.cd.availability", "mc.car.allocation"],
                                      "value": ["{PARAMETERS}/parking_paid_share.csv", "false", "true", "estimation", "tasha"]}),
                    pd.DataFrame({"key": ["mc.joint.rule", "mc.joint.model"], "value": ["representative", "group"]})])   # 2026-11-10: TASHA joint-tour representative, group-level model (m11_joint_group.py)
    rp.to_csv(f"{OUT}/run_params.csv", index=False)
    srcs = [f"{MC}/m08_coef.csv", f"{MC}/m09_coef.csv", f"{DP}/dp_final.pkl", f"{DP}/dp_coef.csv", f"{LO}/lp_edu_final.pkl", f"{LO}/lp_edu_coef.csv", PARK] + \
           [f"{DS}/s_{n}_coef.csv" for n in ("shop", "rec", "acc", "oth")] + [f"{LO}/{n}_coef.csv" for n in ("l03_wahb", "l04_wbhome", "l05_wbwork", "l06_outing_dest")] + \
           [f"{AC}/{n}_coef.csv" for n in ("a01_outing", "a02_outing_mode", "a03_return")]
    srcs += [LICF, STARTF, PROPF, f"{MC}/m11_joint_coef.csv"]
    outs = ["tasha/tasha_start.csv", "tasha/tasha_frequency.csv", "tasha/tasha_params.csv", "tour_mode_choice.csv", "parking_paid_share.csv", "dest_choice_mnl.csv", "run_params.csv", "tasha/tasha_return_home.csv", "tasha/tasha_subtour.csv"]
    json.dump({"built": time.ctime(), "from": ws_text(SRC), "sources": {ws_text(p): sha(p) for p in srcs},
               "written": {f: sha(f"{OUT}/{f}") for f in outs}}, open(f"{OUT}/build_state.json", "w"), indent=1)
    term_map()
    print(f"{OUT}: tour_mode_choice {len(mc)} rows ({mc.segment.value_counts().to_dict()}), dest_choice_mnl {len(dm)} rows, "
          f"{dm.segment.nunique()} segments; return home, outings, run_params written")


if __name__ == "__main__":
    main()
