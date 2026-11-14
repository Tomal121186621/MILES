#!/usr/bin/env python3
"""Zone accessibilities from the RE-ESTIMATED primary-destination models (respec 2026-11), with a mode-choice-logsum variant
built on the RE-ESTIMATED tour mode-choice models (mode_logsum_new.py).

    python3 estimation/development/accessibility/accessibility_new.py [--purposes d_shop,d_rec,d_acc,d_oth] [--skip-est]

Segments, representative traveller, hansen, nonwork pooling and output contract as pipeline/accessibility.py (imported):
  A      ln sum_j exp(V_ij) of the final model of ../dest_primary/d_<p> (final rows of d_<p>_coef.csv; specification from the
         'final specification' line of d_<p>.log), its own impedance (car generalised time cgt; an old ABIT logsum term 'ls'
         would be evaluated with mode_logsum_new); work: the home -> workplace model of pipeline/accessibility.py (unchanged)
  A_ls   the final specification with cgt (or ls) replaced by lambda x LS_new, LS_new = mode_logsum_new for the purpose
         (shopping -> shopping model, recreation / accompany / other -> other model with rec / acc flags), lambda and every other
         coefficient re-estimated on the same estimation records with the same full-set mixture estimator (d_primary.Run.estimate);
         work: the logsum specification S9 of pipeline/accessibility.py (old ABIT logsum; the workplace model is not re-estimated)
LS_new of an estimation record: home zone of each location configuration -> every zone; outbound period = the record's arrival
period (tod), return period = that of the survey tour containing the record's trip when its outbound period agrees, else the
most frequent return period for that outbound period (tours of the purpose, estimation half); joint = the tour's flag (else the
purpose mean); stops = the record's tour-with-stops flag.  Representative traveller (accessibility): MD out / MD return
(tod = MD as in pipeline records()), joint and stops at the means of the purpose's mode-choice estimation tours.
Outputs (ESTIMATION_RESULTS/accessibility_new): accessibility_2016_new.csv (zone, segment, purpose = work / nonwork, A = car-based, hansen),
accessibility_2016_new_detail.csv (+ single purposes, A_usd, A_ls, beta_cost), accessibility_2016_new_multimodal.csv (contract
columns, A = A_ls), ls_lambda.csv, ls_coef.csv, accessibility_new_checks.csv, accessibility_new.log."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, ast, json, argparse, time
sys.dont_write_bytecode = True
import numpy as np, pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))                       # this folder (code)
HERE = f"{ESTIMATION_RESULTS}/accessibility_new"; SBS = ESTIMATION_RESULTS; DPD = f"{SBS}/dest_primary"   # results (data)
V26 = f"{WORKSPACE}"
sys.path.insert(0, CODE); sys.path.insert(0, f"{ORIOLE_HOME}/estimation/development/primary_destination")
import d_primary as DP          # noqa: E402  (full-set estimator; patches dc_model.features with lnd_male / lnd_hh1)
FS, M, C = DP.FS, DP.M, DP.C
import mode_logsum_new as L     # noqa: E402
sys.path.insert(0, f"{ORIOLE_HOME}/pipeline")
import accessibility as PA      # noqa: E402  (pipeline: zone_table, segments, records, model, accessibility)
import torch                    # noqa: E402

NAMES = {"d_shop": ("shopping", "SHOPPING"), "d_rec": ("recreation", "RECREATION"), "d_acc": ("accompany", "ACCOMPANY"), "d_oth": ("other", "OTHER")}
LOGF = open(f"{HERE}/accessibility_new.log", "a")


def log(s):
    print(s, flush=True); LOGF.write(s + "\n"); LOGF.flush()


# ------------------------------------------------------------------------------------------------ LS_new as a destination variable
def lsn(rec, alts, purpose):
    N, J = alts.shape; o = np.repeat(rec.home_idx.values.astype(np.int64), J); d = alts.ravel().astype(np.int64)
    rp = lambda c: np.repeat(rec[c].values.astype(float), J)
    person = dict(age=rp("age"), male=rp("male"), lic=rp("lic"), hhsize=rp("hhsize"), autos=rp("autos"), drivers=rp("drivers"),
                  children=rp("children"), inc_year=12.0 * rp("inc_month"), joint=rp("ls_joint"), stops=rp("ls_stops"))
    v = L.los(o, d, np.repeat(rec.ls_pout.values, J), np.repeat(rec.ls_pret.values, J))
    f = L.features(v, person, purpose); Vm, AV = L.utilities(L.MODEL_OF[purpose], f)
    ls, _ = L.logsum_and_logp(L.MODEL_OF[purpose], Vm, AV)
    return ls.reshape(N, J)


_prev = M.features


def features_n(rec, alts, names, sk, purpose):
    rest = [n for n in names if n != "lsn"]
    out = dict(_prev(rec, alts, rest, sk, purpose)) if rest else {}
    if "lsn" in names: out["lsn"] = lsn(rec, alts, purpose)
    return {k: out[k] for k in names}


M.features = features_n


# ------------------------------------------------------------------------------------------------ data
_tours = {}


def tours():
    if "t" not in _tours:
        t = pd.concat([pd.read_parquet(f"{L.M.WORK}/tours_{h}.parquet").assign(half=h) for h in ["estimation", "validation"]], ignore_index=True)
        _tours["t"] = t
        e = t[["tripids", "pout", "pret", "joint", "stops", "purpose"]].explode("tripids"); e["tripids"] = e.tripids.astype("int64")
        _tours["e"] = e.drop_duplicates("tripids").set_index("tripids")
    return _tours["t"], _tours["e"]


def mode_means(PUR):
    t, _ = tours(); g = t[(t.half == "estimation") & (t.purpose == PUR)]
    modal = g.groupby("pout").pret.agg(lambda x: x.value_counts().idxmax()).to_dict()
    return dict(joint=float(g.joint.astype(float).mean()), stops=float(g.stops.mean()), modal=modal, n=len(g))


def add_ls_cols(rec, PUR):
    _, e = tours(); mm = mode_means(PUR); m = e.reindex(rec.tripid.values)
    tod = rec.tod.values.astype(int); same = m.pout.notna().values & (m.pout.values == tod)
    rec = rec.copy(); rec["ls_pout"] = tod
    rec["ls_pret"] = np.where(same, m.pret.fillna(-1).values, [mm["modal"].get(k, k) for k in tod]).astype(int)
    rec["ls_joint"] = np.where(m.joint.notna().values, m.joint.astype(float).fillna(0).values, mm["joint"])
    rec["ls_stops"] = rec.multi.values.astype(float)
    return rec, float(same.mean())


class Data:
    """stand-in for d_primary.Run (estimate() needs data(), pur, sk) without opening the d_primary log files"""
    def __init__(self, name):
        self.name = name; self.pur = NAMES[name][1]; self.seg = f"{self.pur}_primary"; self.sk = C.skims(); self._d = {}

    def data(self, half):
        if half not in self._d:
            rec, cand, cfg = FS.load(self.seg, half); rec, share = add_ls_cols(rec, self.pur); self._d[half] = (rec, cand, cfg)
            log(f"  {self.name} {half}: N {len(rec)}, return period from the survey tour for {share:.1%}")
        return self._d[half]


def final_model(name):
    """(Spec, {param: value}, final LL, validation LL) of the final model of d_<p>"""
    line = [l for l in open(f"{DPD}/{name}.log") if l.startswith("final specification:")][-1]
    lin = ast.literal_eval(line.split("final specification:")[1].split(", size base")[0].strip())
    base = line.split("size base ")[1].split(",")[0].strip(); comps = ast.literal_eval(line.split("components ")[1].split(";")[0].strip())
    spec = M.Spec("final", lin, base, comps)
    c = pd.read_csv(f"{DPD}/{name}_coef.csv"); c = c[c.step == "final"]; x = dict(zip(c.param, c.coef))
    assert set(spec.params()) == set(x), (name, spec.params(), list(x))
    F = pd.read_csv(f"{DPD}/{name}_fit.csv"); F = F[F.step == "final"].iloc[-1]
    return spec, x, float(F.LL), float(F.validation_LL)


def ls_spec(spec):
    lin = [("lsn" if p in ("cgt", "ls") else p) for p in spec.linear]
    if "lsn" not in lin: lin.append("lsn")
    return M.Spec("LS", list(dict.fromkeys(lin)), spec.size_base, spec.size_comps)


def estimate_ls(name):
    D = Data(name); spec, x, LLf, VLf = final_model(name); s2 = ls_spec(spec)
    x0 = [x.get(p, 0.5 if p == "lsn" else 0.0) for p in s2.params()]
    t0 = time.time(); tab, LL, conv, mg, ab, N = DP.Run.estimate(D, s2, x0)
    rv, cv, gv = D.data("validation"); xv = tab.value.values
    vll = float(DP.X.heldout(rv, cv, gv, s2, xv, D.pur, D.sk, obs="mix")["LL"].sum())
    t = tab.set_index("param")
    r = dict(model=name, purpose=NAMES[name][0], replaced=",".join(p for p in spec.linear if p in ("cgt", "ls")) or "(none: added)",
             N=N, K=len(tab), LL_final=LLf, LL_ls=LL, val_LL_final=VLf, val_LL_ls=vll, lam=float(t.value["lsn"]), lam_se=float(t.rob_se["lsn"]),
             lam_t=float(t.rob_t["lsn"]), converged=conv, maxgrad=mg, at_bound=" ".join(ab), seconds=time.time() - t0)
    log(f"  {name} A_ls model: lambda {r['lam']:.4f} (robust t {r['lam_t']:.2f}); LL {LL:.2f} vs final {LLf:.2f}; validation LL {vll:.2f} vs {VLf:.2f}; "
        f"converged {conv}, maxgrad {mg:.1e} {('at bound ' + r['at_bound']) if ab else ''}")
    return r, tab.assign(model=name)


# ------------------------------------------------------------------------------------------------ accessibility
def flag_means(name):
    rec, _, _ = FS.load(f"{NAMES[name][1]}_primary", "estimation"); ch = M.chooser(rec)
    fm = {k: float(np.mean(ch[k])) for k in ["child", "kid", "senior", "worker", "am", "pm", "ev", "multi"]}
    fm["hh1"] = float((rec.hhsize.values == 1).mean()); return fm, float(rec.w.sum())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--purposes", default=",".join(NAMES)); ap.add_argument("--skip-est", action="store_true"); ap.add_argument("--est-only", action="store_true")
    a = ap.parse_args(); names = a.purposes.split(","); y = 2016
    log(f"==== accessibility_new {time.strftime('%Y-%m-%d %H:%M')} purposes {names}")
    # 1) A_ls models (estimation on the base-year zones of the estimation)
    lf = f"{HERE}/ls_lambda.csv"; cf = f"{HERE}/ls_coef.csv"
    if not a.skip_est:
        R, T = [], []
        for n in names: r, t = estimate_ls(n); R.append(r); T.append(t)
        R = pd.DataFrame(R); T = pd.concat(T)
        if os.path.exists(lf):
            R0 = pd.read_csv(lf); R = pd.concat([R0[~R0.model.isin(R.model)], R]); T0 = pd.read_csv(cf); T = pd.concat([T0[~T0.model.isin(T.model)], T])
        R.to_csv(lf, index=False); T.to_csv(cf, index=False)
    if a.est_only: return
    R = pd.read_csv(lf).set_index("model"); T = pd.read_csv(cf)
    # 2) accessibility (pipeline zone table of the year, as pipeline/accessibility.py)
    micro = f"{V26}/2_silo/input/microData"; schools = f"{V26}/2_silo/input/schools_{y}.csv"
    z = PA.zone_table(micro, schools, y); C._cache["z"] = z; sk = C.skims(); nz = len(z)
    hj = json.load(open(f"{PA.DCD}/results/hansen_work.json"))
    hansen = (np.power(z.jobs.values, hj["alpha"])[None, :] * np.exp(hj["beta"] * sk["t"].astype(float))).sum(1)
    est_old = pd.read_parquet(f"{C.WORK}/dc_records_estimation.parquet")
    fm_work = {k: float(v.mean()) for k, v in M.chooser(est_old[est_old.kind == "primary"]).items() if k in ["child", "kid", "senior", "worker", "am", "pm", "ev"]}
    models, fms, wsum, mm = {}, {}, {}, {}
    for n in NAMES:
        spec, x, _, _ = final_model(n)
        if "ls" in spec.linear: spec = M.Spec("final", [("lsn" if p == "ls" else p) for p in spec.linear], spec.size_base, spec.size_comps); x["lsn"] = x.pop("ls")
        s2 = ls_spec(final_model(n)[0]); t2 = T[T.model == n].set_index("param").value
        models[n] = ((spec, np.array([x[p] for p in spec.params()])), (s2, t2[s2.params()].values))
        fms[n], wsum[n] = flag_means(n); mm[n] = mode_means(NAMES[n][1])
        log(f"  {n}: final {spec.linear}; LS-model lambda {R.lam[n]:.4f}; flag means {({k: round(v, 3) for k, v in fms[n].items()})}; "
            f"LS joint {mm[n]['joint']:.3f} stops {mm[n]['stops']:.3f}")
    pi = pd.Series({NAMES[n][0]: wsum[n] for n in NAMES}); pi = (pi / pi.sum()).to_dict()
    rows = []
    for s in PA.segments(micro, y):
        segname = f"{PA.INC_NAMES[s['inc_group']]}_{PA.CAR_NAMES[s['car_avail']]}"
        vf = np.clip((max(1.0, s["inc_year"] / 12.0) / C.VOT_REF) ** C.VOT_ELAST, C.VOT_MIN, C.VOT_MAX)
        base_fl = dict(inc0=None, car0=float(s["car_avail"] == 0), car1=float(s["car_avail"] == 1))
        Ap = {}; bcs = {}
        # work: unchanged pipeline models
        rec = PA.records(s, fm_work, nz); fl = dict(fm_work)
        fl.update(inc0=float(rec.inc_cls.iloc[0] == 0), inc2=float(rec.inc_cls.iloc[0] == 2), **{k: base_fl[k] for k in ("car0", "car1")})
        spec, x = PA.model("WORK_primary", "F"); A = PA.accessibility(spec, x, "WORK", rec, sk, fl)
        g = "cgt" if "cgt" in spec.linear else "ctime" if "ctime" in spec.linear else None
        bc = x[spec.params().index(g)] * 60.0 / (C.MC_VOT[0] * vf) if g else np.nan
        spec9, x9 = PA.model("WORK_primary", "S9"); A9 = PA.accessibility(spec9, x9, "WORK", rec, sk, fl)
        Ap["work"] = (A, A9); bcs["work"] = bc
        for n, (pname, PUR) in NAMES.items():
            rec = PA.records(s, fms[n], nz)
            rec["ls_pout"] = 1; rec["ls_pret"] = 1; rec["ls_joint"] = mm[n]["joint"]; rec["ls_stops"] = mm[n]["stops"]; rec["multi"] = fms[n]["multi"]
            fl = dict(fms[n]); fl.update(inc0=float(rec.inc_cls.iloc[0] == 0), inc2=float(rec.inc_cls.iloc[0] == 2), **{k: base_fl[k] for k in ("car0", "car1")})
            (spec, x), (s2, x2) = models[n]
            A = PA.accessibility(spec, x, PUR, rec, sk, fl); A2 = PA.accessibility(s2, x2, PUR, rec, sk, fl)
            bcs[pname] = x[spec.params().index("cgt")] * 60.0 / (C.MC_VOT[0] * vf) if "cgt" in spec.linear else np.nan
            Ap[pname] = (A, A2)
        nw = [NAMES[n][0] for n in NAMES]; w = np.array([pi[p] for p in nw]); w = w / w.sum()
        for k in (0, 1):
            Mx = np.stack([Ap[p][k] for p in nw]); mx = Mx.max(0); Ap.setdefault("nonwork", [None, None])
            Ap["nonwork"][k] = mx + np.log((w[:, None] * np.exp(Mx - mx)).sum(0))
        bcs["nonwork"] = bcs["shopping"]
        for p in ["work"] + nw + ["nonwork"]:
            A, A2 = Ap[p]; bc = bcs[p]
            rows.append(pd.DataFrame(dict(zone=z.id.values.astype(int), year=y, inc_group=s["inc_group"], car_avail=s["car_avail"], segment=segname, purpose=p,
                                          A=A, A_usd=A / abs(bc) if np.isfinite(bc) else np.nan, A_ls=A2, beta_cost=bc, hansen=hansen)))
        log(f"  segment {segname} done")
    out = pd.concat(rows, ignore_index=True)
    f = f"{HERE}/accessibility_{y}_new.csv"
    out.to_csv(f.replace(".csv", "_detail.csv"), index=False, float_format="%.6g")
    c = out[out.purpose.isin(["work", "nonwork"])]
    c[["zone", "segment", "purpose", "A", "hansen"]].to_csv(f, index=False, float_format="%.6g")
    c.assign(A=c.A_ls)[["zone", "segment", "purpose", "A", "hansen"]].to_csv(f.replace(".csv", "_multimodal.csv"), index=False, float_format="%.6g")
    log(f"wrote {f}, _detail, _multimodal: {len(out)} detail rows; nonwork weights {({k: round(v, 3) for k, v in pi.items()})}")
    checks(out)


def checks(out):
    cur = pd.read_csv(f"{V26}/data/accessibility_2016_detail.csv")
    m = out.merge(cur[["zone", "segment", "purpose", "A", "A_ls"]], on=["zone", "segment", "purpose"], suffixes=("", "_cur"))
    rows = []
    for p, g in m.groupby("purpose"):
        x = out[out.purpose == p]; pv = x.pivot_table(index=["zone", "inc_group"], columns="car_avail", values="A")
        rows.append(dict(purpose=p, n=len(g), r_A=g.A.corr(g.A_cur), r_A_ls=g.A_ls.corr(g.A_ls_cur), r_A_new_vs_A_ls_new=g.A.corr(g.A_ls),
                         nan_A=int(x.A.isna().sum()), nan_A_ls=int(x.A_ls.isna().sum()), inf=int((~np.isfinite(x[["A", "A_ls"]].values)).sum()),
                         share_nocar_lt_carge_A=float((pv[0] < pv[2]).mean()), mean_carge_minus_nocar_A=float((pv[2] - pv[0]).mean()),
                         share_nocar_lt_carge_A_ls=float((x.pivot_table(index=["zone", "inc_group"], columns="car_avail", values="A_ls").pipe(lambda q: (q[0] < q[2]).mean())))))
    r = pd.DataFrame(rows); r.to_csv(f"{HERE}/accessibility_new_checks.csv", index=False); log(r.round(4).to_string())


if __name__ == "__main__":
    main()
