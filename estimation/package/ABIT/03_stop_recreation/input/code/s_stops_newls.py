#!/usr/bin/env python3
"""Stop-location sequences of s_stops.py re-run with the mode-choice logsum of the RE-ESTIMATED mode models (2026-11-08).

Where the old logsum came from: dc_model.features, variable "ls" (no cache: computed each time a chunk's utility variables are
built), = dc_common.mode_logsum (DAYMAP MarylandFullModeChoice, coefficients 3_abit/coef_calibrated/modechoice_full_<purpose>.csv,
one-way leg, car / bus / rail skims) of the stop's purpose, detour form
    ls = LS(a -> j) + LS(j -> b) - LS(a -> b)        a = previous location (home_idx of the configuration), b = next anchor.
Here only that variable changes: LS = ../accessibility_new/mode_logsum_new.mode_logsum_new of the stop's purpose (shopping ->
shopping; recreation / accompany / other -> other, rec / acc flags from the purpose), person from the record (age, male, lic,
hhsize, autos, children, drivers, inc_year), joint = 0 (not in the records), stops = 1, periods pout = pret = the record's time
of day (tod: 0 AM, 1 MD, 2 PM, 3 evening/night).  Same legs, same difference, no truncation (as before).
Everything else is s_stops.py (imported, unchanged): blocks, rule, guards, final check, validation, outputs (<name>_fit.csv,
_coef.csv, _n.csv, .log; the previous outputs are kept as *_oldls.*).
    TAZ_THREADS=4 python3 s_stops_newls.py check            # plumbing check (old function through the new code) + old vs new
    TAZ_THREADS=4 python3 s_stops_newls.py s_shop [s_rec ...]
    TAZ_THREADS=6 python3 s_stops_newls.py revise s_shop [s_rec ...]   # final stage of 2026-11-09 only (s_stops.Run.revise)
"""
# COPY of Validation_2026/side_experiments/respec_2026-11/step_by_step/dest_stop/s_stops_newls.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "accessibility_new"))
import s_stops as S                     # noqa: E402  (imports the estimator, patches dc_model.chooser)
import mode_logsum_new as LN            # noqa: E402
M, C = S.M, S.C

_features_prev = M.features             # dc_taz_engine.features_x -> dc_model.features (old "ls")


def person_old(rec):
    return M.person(rec)


def person_new(rec):
    r = rec
    tod = r.tod.values.astype(np.int64)
    return dict(age=r.age.values.astype(float), male=r.male.values.astype(float), lic=r.lic.values.astype(float),
                hhsize=r.hhsize.values.astype(float), autos=r.autos.values.astype(float), children=r.children.values.astype(float),
                drivers=r.drivers.values.astype(float), inc_year=r.inc_year.values.astype(float),
                joint=(r.joint.values.astype(float) if "joint" in r else np.zeros(len(r))), stops=np.ones(len(r)), pout=tod, pret=tod)


def fn_old(purpose, o, d, pers, sk):
    mp = purpose if purpose in C.DISC + ["WORK"] else "OTHER"
    return C.mode_logsum(mp, o, d[:, None], pers, sk)[:, 0]


def fn_new(purpose, o, d, pers, sk):
    return LN.mode_logsum_new(purpose, o, d, pers)


FN = {"old": (fn_old, person_old), "new": (fn_new, person_new)}
WHICH = "new"
_cache = {}


def ls_rows(rec, purpose, sk, which, block=150):
    """(n, 1588): LS(a -> j) + LS(j -> b) - LS(a -> b) for every zone j, rows of rec (a = home_idx, b = anchor_b)"""
    fn, pf = FN[which]; nz = len(C.zones()); out = np.empty((len(rec), nz))
    for i0 in range(0, len(rec), block):
        r = rec.iloc[i0:i0 + block]; n = len(r); P = pf(r)
        a = r.home_idx.values.astype(np.int64); b = r.anchor_b.values.astype(np.int64); jz = np.arange(nz)
        Pf = {k: np.repeat(v, nz) for k, v in P.items()}
        l1 = fn(purpose, np.repeat(a, nz), np.tile(jz, n), Pf, sk).reshape(n, nz)
        l2 = fn(purpose, np.tile(jz, n), np.repeat(b, nz), Pf, sk).reshape(n, nz)
        l0 = fn(purpose, a, b, P, sk)
        out[i0:i0 + n] = l1 + l2 - l0[:, None]
    return out


def ls_feature(rec, alts, purpose, sk, which=None):
    which = which or WHICH
    keys = list(zip(rec.rec.values.astype(np.int64), rec.home_idx.values.astype(np.int64), rec.anchor_b.values.astype(np.int64),
                    rec.tod.values.astype(np.int64), rec.age.values.astype(float), rec.inc_year.values.astype(float)))
    keys = [(which, purpose) + k for k in keys]
    miss = [i for i, k in enumerate(keys) if k not in _cache]
    if miss:
        v = ls_rows(rec.iloc[miss], purpose, sk, which)
        for i, row in zip(miss, v): _cache[keys[i]] = row
    V = np.stack([_cache[k] for k in keys])
    return np.take_along_axis(V, np.asarray(alts, np.int64), 1)


def features_ls(rec, alts, names, sk, purpose):
    if "ls" not in names or not (rec.kind.values == "stop").all(): return _features_prev(rec, alts, names, sk, purpose)
    rest = [n for n in names if n != "ls"]
    out = dict(_features_prev(rec, alts, rest, sk, purpose)) if rest else {}
    out["ls"] = ls_feature(rec, alts, purpose, sk)
    return {k: out[k] for k in names}


M.features = features_ls


def check(n=40, seed=7):
    """plumbing: the new code pointed at the old function reproduces dc_model's old "ls"; then old vs new"""
    import dc_model as DM
    import importlib.util
    spec = importlib.util.spec_from_file_location("dc_model_pristine", DM.__file__); P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)                                       # an untouched copy of dc_model (old "ls")
    sk = C.skims(); rows = []
    for name, seg in S.MODELS.items():
        pur = seg.split("_")[0]; rec, cand, cfg = S.F_.load(seg, "estimation")
        r = rec.sample(n, random_state=seed).reset_index(drop=True)
        rs = np.random.default_rng(seed); alts = np.stack([rs.choice(len(C.zones()), 60, replace=False) for _ in range(n)])
        ref = P.features(r, alts, ["ls"], sk, pur)["ls"]
        mine = ls_feature(r, alts, pur, sk, "old")
        new = ls_feature(r, alts, pur, sk, "new")
        rows.append(dict(model=name, rows=n, alts=alts.size, max_abs_diff_old=float(np.abs(ref - mine).max()), mean_old=float(ref.mean()),
                         sd_old=float(ref.std()), mean_new=float(new.mean()), sd_new=float(new.std()),
                         corr_old_new=float(np.corrcoef(ref.ravel(), new.ravel())[0, 1]), finite_new=float(np.isfinite(new).mean())))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/s_newls_check.csv", index=False)


class Run(S.Run):
    def head(self):
        self.log("mode-choice logsum (ls): re-estimated mode models (accessibility_new/mode_logsum_new), stops = 1, joint = 0, "
                 "periods = time of day of the record; previous run (ABIT mode model logsum): *_oldls.*")

    def go(self):
        self.head(); return super().go()

    def revise(self):
        self.head(); return super().revise()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["check"]: check()
    elif args[:1] == ["revise"]:
        for nm in args[1:] or list(S.MODELS): Run(nm).revise()
    else:
        for nm in args or list(S.MODELS): Run(nm).go()
