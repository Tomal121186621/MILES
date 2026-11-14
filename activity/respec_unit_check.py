#!/usr/bin/env python3
"""Unit check of the re-specified ABIT models in the engine (coefficient set 3_abit/coef_respec, 2026-11-09): the utilities the Java
classes compute for choice situations of the survey population (estimation half; persons, households and zones of the estimation
records) against the utilities of the estimation code (the Python / Biogeme definitions of side_experiments/respec_2026-11).

    python3 respec_unit_check.py run      ABIT on the estimation-half survey population with a copy of coef_respec plus the debug
                                          switches (dest.mnl.debug.*, mc.tours.full, tasha debug.file), skims base_transit2024
                                          -> run_survey/svy_est_respecchk_s01
    python3 respec_unit_check.py check    -> respec_unit_check.csv (one row per model: situations, alternatives, max |dV|, max |dP|)

Checks (Python side):
  destinations / stops / locations  dc_model.utility (d_primary: ln distance x male / one-person household; s_stops: chooser
        flags; s_stops_newls: 'ls' = logsum of the re-specified tour models) with the coefficients of coef_respec/dest_choice_mnl.csv
        (lstour -> ls), every zone of each debug choice (dest.mnl.debug.file, first 40 choices of every segment)
  tour mode choice  accessibility_new/mode_logsum_new (features, utilities, Biogeme lognested probabilities) on the tours of
        output/mc_tours.csv (mc.tours.full: utilities and probabilities at full precision); 'fewer cars than drivers' and 'joint'
        (main activity a joint household episode: joint_id of mc_tours) applied as estimated (mc.apply.short / mc.apply.joint)
  return home   estimate_return_home.design + a03_return.load columns, from the episode zones, types, times and person of the
        debug line (tasha debug.file, tag RH)
  outings       a01 (estimate_subtours.data definitions: work span, arrival, secondary work, ln(1 + home-work km), workplace CBD)
        and a02 (ln(1 + km workplace-first stop), CBD, cars, more than one stop, mode of the work tour) from the debug lines
"""
import os, re, shutil, subprocess, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd

A3 = os.path.dirname(os.path.abspath(__file__)); V = os.path.dirname(A3)
SBS = f"{V}/side_experiments/respec_2026-11/step_by_step"; TE = f"{A3}/tasha_estimation"
COEF = f"{A3}/coef_respec"; SK = f"{A3}/skims/base_transit2024"
NAME = "svy_est_respecchk_s01"; RUN = f"{A3}/run_survey/{NAME}"
SCR = f"{RUN}_debug"   # coefficient copy with the debug switches and the debug files
OUT = f"{A3}/respec_unit_check.csv"


def run():
    sys.path.insert(0, A3); import survey_population as S
    os.makedirs(SCR, exist_ok=True); c = f"{SCR}/coef"; shutil.rmtree(c, ignore_errors=True); shutil.copytree(COEF, c)
    for f in ("dest_debug.csv", "tasha_debug.csv"):
        if os.path.exists(f"{SCR}/{f}"): os.remove(f"{SCR}/{f}")
    rp = open(f"{c}/run_params.csv").read()   # short and joint applied as estimated (mc.apply.short, mc.apply.joint of the set)
    rp += f"mc.tours.full,true\ndest.mnl.debug.file,{SCR}/dest_debug.csv\ndest.mnl.debug.per.segment,true\ndest.mnl.debug.n,40\n"
    open(f"{c}/run_params.csv", "w").write(rp)
    open(f"{c}/tasha/tasha_params.csv", "a").write(f"debug.file,{SCR}/tasha_debug.csv\ndebug.n,400\n")
    S.run("estimation", 1, coef=c, tag="respecchk", skims=SK, force=True)


# ------------------------------------------------------------------------------------------------ destinations
def check_dest(rows):
    sys.path.insert(0, TE); sys.path.insert(0, f"{V}/3_abit/destination_choice")
    sys.path.insert(0, f"{SBS}/dest_primary"); sys.path.insert(0, f"{SBS}/dest_stop"); sys.path.insert(0, f"{SBS}/accessibility_new")
    import d_primary   # noqa: F401  (ln distance x male / one-person household)
    import s_stops_newls   # noqa: F401  (chooser flags, 'ls' of the re-specified tour models)
    import torch, dc_model as M, dc_common as C, prep_dc_data as PD
    d = pd.read_csv(f"{SCR}/dest_debug.csv", header=None,
                    names=["seg", "pid", "za", "zb", "start", "mode", "inbound", "tp", "zj", "V", "nonauto", "worktour", "inb", "multi"])
    coef = pd.read_csv(f"{COEF}/dest_choice_mnl.csv"); sk = C.skims(); m = C.id2idx(); z = C.zones()
    pm = pd.read_csv(f"{A3}/survey_pop/estimation/persons_map.csv").set_index("id"); P = PD.people("estimation")
    res = {}
    for (seg, pid, za, zb, st, nonauto, wt, inb, mv), g in d.groupby(["seg", "pid", "za", "zb", "start", "nonauto", "worktour", "inb", "multi"], sort=False):
        sp = pm.person_id.get(pid)
        if pd.isna(sp) or sp not in P.index: continue
        c = coef[coef.segment == seg].set_index("variable").value; stop = seg.endswith("_stop")
        sizes = [k[5:] for k in c.index if k.startswith("size_")]; base = [k for k in sizes if c[f"size_{k}"] == 1.0][0]; comps = [k for k in sizes if k != base]
        lin = [("ls" if k == "lstour" else k) for k in c.index if k != "mu_size" and not k.startswith("size_")]
        rec = pd.DataFrame({"person_id": [sp], "kind": ["stop" if stop else "primary"], "tod": [PD.tod_cls(np.array([st]))[0]],
                            "mode_auto": [1.0 - nonauto], "tour_purpose": ["WORK" if wt > 0 else "OTHER"], "position": ["in" if inb > 0 else "out"],
                            "multi": [mv], "home_idx": [0], "anchor_b": [int(m[zb]) if zb >= 0 else -1]})
        rec = PD.chooser_cols(rec, P); rec["home_idx"] = int(m[za]); rec["rec"] = 0
        rec["joint"] = 0.0
        spec = M.Spec("F", lin, base, comps)
        theta = torch.tensor([c["lstour" if k == "ls" else k] for k in lin] + [np.log(c[f"size_{k}"]) for k in comps] + [c["mu_size"]])
        alts = np.arange(len(z))[None, :]
        s_stops_newls._cache.clear()
        D = M.Data(rec, alts, np.zeros((1, len(z))), np.zeros((1, len(z))), spec, seg.split("_")[0], sk)
        Vp = M.utility(theta, spec, D).detach().numpy()[0]
        j = m[g.zj.values]; dv = np.abs(Vp[j] - g.V.values)
        # probabilities over the zones of the line (the full choice set)
        pj = np.exp(g.V.values - g.V.max()); pj /= pj.sum(); pp = np.exp(Vp[j] - Vp[j].max()); pp /= pp.sum()
        r = res.setdefault(seg, dict(model=f"location: {seg}", situations=0, alternatives=0, max_abs_dV=0.0, max_abs_dP=0.0, max_abs_V=0.0))
        r["situations"] += 1; r["alternatives"] += len(g); r["max_abs_dV"] = max(r["max_abs_dV"], float(dv.max()))
        r["max_abs_dP"] = max(r["max_abs_dP"], float(np.abs(pj - pp).max())); r["max_abs_V"] = max(r["max_abs_V"], float(np.abs(g.V.values).max()))
    rows += list(res.values())


# ------------------------------------------------------------------------------------------------ tour mode choice
def check_mode(rows):
    sys.path.insert(0, f"{SBS}/accessibility_new"); sys.path.insert(0, f"{V}/3_abit/destination_choice")
    import mode_logsum_new as LN, prep_dc_data as PD, dc_common as C
    t = pd.read_csv(f"{RUN}/output/mc_tours.csv"); m = C.id2idx()
    pm = pd.read_csv(f"{A3}/survey_pop/estimation/persons_map.csv").set_index("id"); P = PD.people("estimation")
    t["sp"] = t.person_id.map(pm.person_id); t = t[t.sp.isin(P.index) & t.V_CP.notna()].copy()
    p = P.reindex(t.sp.values)
    per = lambda x: np.select([(x % 1440 // 60 >= 6) & (x % 1440 // 60 < 9), (x % 1440 // 60 >= 9) & (x % 1440 // 60 < 15), (x % 1440 // 60 >= 15) & (x % 1440 // 60 < 19)], [0, 1, 2], 3)
    for seg, g in t.groupby("segment"):
        gp = p[t.segment.values == seg]
        h, mz = m[g.home_zone.values], m[g.main_zone.values]
        v = LN.los(h, mz, per(g.start.values), per(g.end.values))
        person = dict(age=gp.age.values.astype(float), male=(gp.gender.values == 1).astype(float), lic=gp.lic.values.astype(float), hhsize=gp.hhsize.values.astype(float),
                      autos=gp.autos.values.astype(float), children=gp.children.values.astype(float), drivers=gp.drivers.values.astype(float),
                      inc_year=12.0 * gp.inc_month.values, joint=(g.joint_id.values != 0).astype(float), stops=(g.n_act.values > 1).astype(float),
                      acc=(g.purpose.values == "ACCOMPANY").astype(float), rec=(g.purpose.values == "RECREATION").astype(float))
        f = LN.features(v, person, seg); Vd, AV = LN.utilities(seg, f); _, lp = LN.logsum_and_logp(seg, Vd, AV)
        dv = dp = 0.0; nav = 0
        for a in LN.ALTS:
            jav = g[f"V_{a}"].notna().values; assert (jav == AV[a]).all(), f"{seg} {a}: availability differs in {(jav != AV[a]).sum()} tours"
            if jav.any():
                dv = max(dv, float(np.abs(g[f"V_{a}"].values[jav] - Vd[a][jav]).max())); nav += int(jav.sum())
            pj = g[f"pf_{a}"].values; pp = np.where(AV[a], np.exp(lp[a]), 0.0); dp = max(dp, float(np.abs(pj - pp).max()))
        rows.append(dict(model=f"tour mode choice: {seg}", situations=len(g), alternatives=nav, max_abs_dV=dv, max_abs_dP=dp,
                         max_abs_V=float(np.nanmax(np.abs(g[[f"V_{a}" for a in LN.ALTS]].values)))))
        # group-level model of the joint tours (mc.joint.model = group): the representative's utilities VJ_*
        if "VJ_CP" in g and g.VJ_CP.notna().any():
            sj = f"{seg}_joint"; c = pd.read_csv(f"{SBS}/mode_choice/m11_joint_coef.csv"); c = c[c.segment == sj]
            LN._coef[sj] = dict(zip(c.param, c.coef.astype(float))); LN.FORM[sj] = LN.FORM[seg]
            if seg in LN.NESTS: LN.NESTS[sj] = LN.NESTS[seg]
            k = g.VJ_CP.notna().values; fj = {q: (np.asarray(x)[k] if np.ndim(x) else x) for q, x in f.items()}; fj["joint"] = np.ones(k.sum())
            Vj, _ = LN.utilities(sj, fj); dj = 0.0; nj = 0
            for a in LN.ALTS:
                mk = g[f"VJ_{a}"].notna().values[k]
                if mk.any(): dj = max(dj, float(np.abs(g[f"VJ_{a}"].values[k][mk] - Vj[a][mk]).max())); nj += int(mk.sum())
            rows.append(dict(model=f"joint group model: {sj}", situations=int(k.sum()), alternatives=nj, max_abs_dV=dj, max_abs_dP=np.nan,
                             max_abs_V=float(np.nanmax(np.abs(g.loc[k, [f"VJ_{a}" for a in LN.ALTS]].values)))))


# ------------------------------------------------------------------------------------------------ activity models
def check_activity(rows):
    sys.path.insert(0, TE); sys.path.insert(0, f"{SBS}/activity"); sys.path.insert(0, f"{V}/3_abit")
    import estimate_return_home as ER, dc_common as C
    from abit_metrics import dist_matrix
    dm = dist_matrix(); m = C.id2idx(); z = C.zones(); d = C.skims()["d"]
    pm = pd.read_csv(f"{A3}/survey_pop/estimation/persons_map.csv").set_index("id")
    import stepwise as S; pa = S.person_attrs("estimation")
    L = [l.rstrip("\n").split(",") for l in open(f"{SCR}/tasha_debug.csv")]
    # return home
    rh = pd.DataFrame([x[1:] for x in L if x[0] == "RH"], columns=["pid", "a_type", "a_purpose", "a_joint", "a_end", "az", "e_type", "e_purpose", "e_joint", "ez", "hz", "seg",
                                                                   "nep", "slack", "female", "lic", "hhsize", "kids", "cars", "drivers", "inc", "V"])
    for k in ["pid", "a_joint", "a_end", "az", "e_joint", "ez", "hz", "nep", "slack"]: rh[k] = rh[k].astype(int)
    for k in ["female", "lic", "hhsize", "kids", "cars", "drivers", "inc", "V"]: rh[k] = rh[k].astype(float)
    dah, dhe, dae = dm[rh.az.values, rh.hz.values], dm[rh.hz.values, rh.ez.values], dm[rh.az.values, rh.ez.values]
    rh["detour"] = np.maximum(0.0, dah + dhe - dae); rh["dah"] = dah
    X = ER.design(rh).copy()
    # person and household terms from the survey population (a03_return.load: stepwise.person_attrs)
    q = pa.reindex(rh.pid.map(pm.person_id).values)
    X["nep"] = rh.nep.values.astype(float); X["female"] = q.female.values; X["lic"] = q.lic.values; X["hhsize"] = q.hhsize.values.astype(float)
    X["kids"] = q.kids.values; X["car0"] = (q.autos.values <= 0).astype(float); X["carshort"] = ((q.autos.values > 0) & (q.autos.values < q.drivers.values)).astype(float)
    X["inc_low"] = (q.inc.values < 50000).astype(float); X["inc_high"] = (q.inc.values >= 100000).astype(float)
    b = pd.read_csv(f"{SBS}/activity/a03_return_coef.csv"); b = b[b.step == "final"].set_index("param").coef
    Vp = (X[b.index] * b.values).sum(1).values; ok = q.age.notna().values
    rows.append(dict(model="return home (a03)", situations=int(ok.sum()), alternatives=2, max_abs_dV=float(np.abs(Vp - rh.V.values)[ok].max()),
                     max_abs_dP=float(np.abs(1 / (1 + np.exp(-Vp)) - 1 / (1 + np.exp(-rh.V.values)))[ok].max()), max_abs_V=float(np.abs(rh.V.values).max())))
    # outing occurrence
    g = pd.DataFrame([x[1:] for x in L if x[0] == "WBSGEN"], columns=["pid", "type", "start", "dur", "hz", "wz", "age", "female", "inc", "cars", "drivers", "kids", "V"])
    for k in ["pid", "start", "dur", "hz", "wz", "age"]: g[k] = g[k].astype(int)
    g["V"] = g.V.astype(float); h = g.dur.values / 60.0
    X = pd.DataFrame({"const": 1.0, "sp_0_4": np.minimum(h, 4), "sp_4_7": np.clip(h - 4, 0, 3), "sp_7_inf": np.maximum(h - 7, 0),
                      "arr_early": (g.start.values < 420).astype(float), "arr_late": (g.start.values >= 600).astype(float), "sw": (g.type.values == "SW").astype(float),
                      "cbd_w": z.cbd.values[m[g.wz.values]], "lncomm": np.log1p(d[m[g.hz.values], m[g.wz.values]])})
    b = pd.read_csv(f"{SBS}/activity/a01_outing_coef.csv"); b = b[b.step == "final"].set_index("param").coef
    Vp = (X[b.index] * b.values).sum(1).values
    rows.append(dict(model="outing occurrence (a01)", situations=len(g), alternatives=2, max_abs_dV=float(np.abs(Vp - g.V.values).max()),
                     max_abs_dP=float(np.abs(1 / (1 + np.exp(-Vp)) - 1 / (1 + np.exp(-g.V.values))).max()), max_abs_V=float(np.abs(g.V.values).max())))
    # outing mode
    o = pd.DataFrame([x[1:] for x in L if x[0] == "WBSMODE"], columns=["pid", "wz", "z1", "ns", "tm", "V"])
    if len(o):
        for k in ["pid", "wz", "z1", "ns"]: o[k] = o[k].astype(int)
        o["V"] = o.V.astype(float); q = pa.reindex(o.pid.map(pm.person_id).values); km = d[m[o.wz.values], m[o.z1.values]]
        X = pd.DataFrame({"const": 1.0, "lnkm": np.log1p(km), "cbd_w": z.cbd.values[m[o.wz.values]], "car0": (q.autos.values <= 0).astype(float),
                          "carshort": ((q.autos.values > 0) & (q.autos.values < q.drivers.values)).astype(float),
                          "tm_cd": (o.tm.values == "CAR_DRIVER").astype(float), "tm_cp": (o.tm.values == "CAR_PASSENGER").astype(float), "multi": (o.ns.values > 1).astype(float)})
        b = pd.read_csv(f"{SBS}/activity/a02_outing_mode_coef.csv"); b = b[b.step == "final"].set_index("param").coef
        Vp = (X[b.index] * b.values).sum(1).values
        rows.append(dict(model="outing mode (a02)", situations=len(o), alternatives=2, max_abs_dV=float(np.abs(Vp - o.V.values).max()),
                         max_abs_dP=float(np.abs(1 / (1 + np.exp(-Vp)) - 1 / (1 + np.exp(-o.V.values))).max()), max_abs_V=float(np.abs(o.V.values).max())))


def check():
    rows = []
    for fn in (check_mode, check_activity, check_dest): fn(rows)
    r = pd.DataFrame(rows); r.to_csv(OUT, index=False)
    pd.set_option("display.width", 200); print(r.to_string(index=False))


if __name__ == "__main__":
    {"run": run, "check": check}[sys.argv[1]]()
