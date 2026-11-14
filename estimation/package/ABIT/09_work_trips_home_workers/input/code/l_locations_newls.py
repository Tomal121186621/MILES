#!/usr/bin/env python3
"""l_locations.py with the mode-choice logsum (block 14b, variable `ls`) of the RE-ESTIMATED tour mode models
(../accessibility_new/mode_logsum_new.py) in place of the old ABIT mode model (dc_common.mode_logsum, 3_abit/coef_calibrated,
called by dc_model.features; nothing cached, the variable is computed when the data of a model are built).  Everything else is
l_locations.py, imported unchanged (same records, block order, rule, guards, final check, validation half).

Same construction as the old variable: primary form ls = LS(anchor, j); detour form ls = LS(home, j) + LS(j, work) - LS(home, work).
Mode model by segment: WORK_* -> work; EDUCATION_* -> school (the old code used OTHER for EDUCATION); OTHER_wbs -> other (as before).
Record attributes as in the mode-model estimation (3_abit/mode_choice/prep_tours.py): age, male, licence, household size, cars,
drivers (-> fewer cars than drivers), children (-> kids), household income (inc_year = 12 x inc_month); outbound period = period
of the arrival at the activity (= tod), return period = period of the departure of the next trip (episodes; = pout if none);
joint = the episode's joint-travel group (jgid >= 0); stops = the home-based chain of the episode (prep_tours.chains) has more
than one episode (0 if the episode is in no closed chain).

    TAZ_THREADS=6 python3 l_locations_newls.py check                 # plumbing check (old function reproduced) + old / new summary
    TAZ_THREADS=6 python3 l_locations_newls.py l01_daycare [...]     # sequences -> <name>_fit.csv, _coef.csv, .log
    TAZ_THREADS=6 python3 l_locations_newls.py revise l01_daycare [...]   # final stage of 2026-11-09 only (l_locations.Run.revise)"""
# COPY of Validation_2026/side_experiments/respec_2026-11/step_by_step/locations/l_locations_newls.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import os, sys
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "6")
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import l_locations as LL                   # noqa: E402
M, C = LL.M, LL.C
sys.path.insert(0, f"{HERE}/../accessibility_new")
import mode_logsum_new as MN               # noqa: E402
A3 = _PKG_HERE  # PATH
sys.path.insert(0, f"{A3}/mode_choice")
import prep_tours as PT                    # noqa: E402
import te_common as T                      # noqa: E402

NEW_MODEL = {"WORK": "work", "EDUCATION": "school", "OTHER": "other"}
WHICH = {"ls": "new"}                      # "new" | "old" (plumbing check)
_prev = M.features                         # dc_taz_engine.features_x -> dc_model.features


# ------------------------------------------------------------------------------------------------ record attributes
_ext = {}


def extra(half):
    """per tripid: ls_pret (period of the next departure), ls_joint, ls_stops"""
    if half in _ext: return _ext[half]
    e = T.episodes(half).sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    nxt = e.groupby("person_id").dep_min.shift(-1)
    out = pd.DataFrame({"tripid": e.tripid.values, "ls_pret": np.where(nxt.notna(), PT.M.period(nxt.fillna(0).values), -1),
                        "ls_joint": (e.jgid.values >= 0).astype(float), "ls_stops": 0.0})
    st = {}
    for _, c in PT.chains(e):
        eps = c[:-1]
        for r in eps: st[r["tripid"]] = float(len(eps) > 1)
    out["ls_stops"] = out.tripid.map(st).fillna(0.0).values; out["in_chain"] = out.tripid.isin(st.keys())
    _ext[half] = out.set_index("tripid"); return _ext[half]


def add_cols(rec, half):
    x = extra(half).reindex(rec.tripid.values)
    rec = rec.copy(); rec["ls_pout"] = np.asarray(rec.tod.values, int)
    pr = x.ls_pret.values; rec["ls_pret"] = np.where(np.isfinite(pr) & (pr >= 0), pr, rec.ls_pout.values).astype(int)
    rec["ls_joint"] = np.nan_to_num(x.ls_joint.values.astype(float)); rec["ls_stops"] = np.nan_to_num(x.ls_stops.values.astype(float))
    return rec


_load0 = LL.Run.load


def load(self, half, form):
    rec, cand = _load0(self, half, form); return add_cols(rec, half), cand


LL.Run.load = load


# ------------------------------------------------------------------------------------------------ the logsum variable
def person_new(rec):
    f = lambda k: rec[k].values.astype(float)
    return dict(age=f("age"), male=f("male"), lic=f("lic"), hhsize=f("hhsize"), autos=f("autos"), drivers=f("drivers"),
                children=f("children"), inc_year=f("inc_year"), joint=f("ls_joint"), stops=f("ls_stops"),
                pout=rec.ls_pout.values.astype(int), pret=rec.ls_pret.values.astype(int))


def ls_old(rec, alts, purpose, sk):
    """dc_model.features 'ls' (old ABIT mode model), written out with the same legs"""
    mp = purpose if purpose in C.DISC + ["WORK"] else "OTHER"; p = M.person(rec); o = rec.home_idx.values
    f = lambda oo, dd, pp: C.mode_logsum(mp, oo, dd, pp, sk)
    if (rec.kind.values == "stop").all():
        b = rec.anchor_b.values; N, J = alts.shape
        rep = {k: np.repeat(v, J) for k, v in p.items()}
        l2 = f(alts.ravel(), np.repeat(b, J)[:, None], rep)[:, 0].reshape(N, J)
        return f(o, alts, p) + l2 - f(o, b[:, None], p)
    return f(o, alts, p)


def ls_new(rec, alts, purpose, sk):
    md = NEW_MODEL[purpose]; p = person_new(rec); o = rec.home_idx.values
    if (rec.kind.values == "stop").all():
        b = rec.anchor_b.values; N, J = alts.shape
        rep = {k: np.repeat(v, J) for k, v in p.items()}
        l2 = MN.mode_logsum_new(md, alts.ravel(), np.repeat(b, J), rep).reshape(N, J)
        return MN.mode_logsum_new(md, o, alts, p) + l2 - MN.mode_logsum_new(md, o, b, p)[:, None]
    return MN.mode_logsum_new(md, o, alts, p)


def features(rec, alts, names, sk, purpose):
    if "ls" not in names: return _prev(rec, alts, names, sk, purpose)
    rest = [n for n in names if n != "ls"]; out = dict(_prev(rec, alts, rest, sk, purpose)) if rest else {}
    out["ls"] = (ls_new if WHICH["ls"] == "new" else ls_old)(rec, alts, purpose, sk)
    return {k: out[k] for k in names}


M.features = features


# ------------------------------------------------------------------------------------------------ plumbing check
def check():
    sk = C.skims(); rows = []
    for name, form in [("l01_daycare", "primary"), ("l02_nonstud", "primary"), ("l03_wahb", "primary"), ("l04_wbhome", "primary"),
                       ("l05_wbwork", "primary"), ("l05_wbwork", "stop"), ("l06_outing_dest", "primary")]:
        r = LL.Run.__new__(LL.Run); r.seg, r.pur = LL.MODELS[name]
        rec, _ = r.load("estimation", form); rec = rec.iloc[:60].reset_index(drop=True)
        alts = np.broadcast_to(np.arange(len(C.zones())), (len(rec), len(C.zones()))).copy()
        ref = _prev(rec, alts, ["ls"], sk, r.pur)["ls"]                       # the old code path (dc_model.features)
        WHICH["ls"] = "old"; old = features(rec, alts, ["d", "ls"], sk, r.pur)["ls"]
        WHICH["ls"] = "new"; new = features(rec, alts, ["d", "ls"], sk, r.pur)["ls"]
        ok = np.isfinite(new)
        rows.append(dict(model=name, form=form, n=len(rec), max_abs_diff_old=float(np.abs(old - ref).max()),
                         old_mean=float(ref.mean()), old_sd=float(ref.std()), new_mean=float(new[ok].mean()), new_sd=float(new[ok].std()),
                         new_nonfinite=int((~ok).sum()), corr=float(np.corrcoef(ref[ok], new[ok])[0, 1]),
                         joint=float(rec.ls_joint.mean()), stops=float(rec.ls_stops.mean()), pret_ne_pout=float((rec.ls_pret != rec.ls_pout).mean())))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/l_newls_check.csv", index=False)


if __name__ == "__main__":
    if sys.argv[1:] == ["check"]: check()
    else:
        rev = sys.argv[1:2] == ["revise"]; args = sys.argv[2:] if rev else sys.argv[1:]
        for n in args or list(LL.MODELS):
            r = LL.Run(n); r.log("mode-choice logsum (block 14b): RE-ESTIMATED tour mode models (mode_logsum_new; WORK -> work, "
                                 "EDUCATION -> school, OTHER -> other), l_locations_newls.py")
            r.revise() if rev else r.go()
