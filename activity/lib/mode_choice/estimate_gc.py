#!/usr/bin/env python3
"""Biogeme estimation of the tour mode choice in the specification of Chayan & Cirillo (2024), re-estimated as a tour model on the
estimation half of the 2017/18 RTS (work/gc_bio_<segment>_s<share>.parquet from `python3 prep_tours.py biodata2`).

    ~/.venvs/biogeme/bin/python activity/lib/mode_choice/estimate_gc.py [segments] [--steps base,dest,sens,pooled]

Utility of mode m (reference car driver CD; modes CD, WK, BK, CP, BUS, TRAIN):
    V_m = ASC_m + b_age,m age + b_male,m male + b_lic,m licence + b_hhsize,m hhsize + b_autos,m autos
          + b_core,m core_o + b_rural,m rural_o [+ b_core_d,m core_d + b_rural_d,m rural_d] + b_gc,m GC_m + b_km,m km
  with the socio-demographic, area-type and km terms on the five non-reference modes and b_gc,m on CD, CP, BUS and TRAIN (walk and
  bike have no GC, as in the published model).  GC_m = T_m + 60 C_m / VOT_h, VOT_h = s x household income / 2,080 (mc_common).
Structures: MNL (the published structure) and NL (nests auto = CD + CP, transit = BUS + TRAIN, non-motorised = WK + BK; Biogeme's
nest parameter mu >= 1).  No survey weights (exogenous sampling); robust (sandwich) standard errors.
Steps:
  base    constants only, MNL and NL with the area type at the home end (s = 0.50)
  dest    MNL and NL with the area type at both ends; LR test against base
  sens    the chosen structure with s = 0.35 and 0.70
  pooled  one model for all segments (every coefficient common) against the segmented models (LR test)
Outputs (results/): gc_<seg>_<model>.html / .yaml / .csv / _cov.csv, gc_summary.csv, gc_tests.csv
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/mode_choice"; WORK = f"{HERE}/work"; RES = f"{HERE}/results"; BIO = f"{WORK}/biogeme"
ALTS = ["CD", "WK", "BK", "CP", "BUS", "TRAIN"]; NUM = {a: i + 1 for i, a in enumerate(ALTS)}
SOCIO = ["age", "male", "lic", "hhsize", "autos", "core_o", "rural_o"]
DEST = ["core_d", "rural_d"]
GC_ALTS = ["CD", "CP", "BUS", "TRAIN"]
NESTS = {"auto": ["CD", "CP"], "transit": ["BUS", "TRAIN"], "nonmot": ["WK", "BK"]}
SEGMENTS = ["work", "school", "shopping", "other"]
# model of record per segment (results/gc_summary.csv, gc_tests.csv): the lowest AIC among the models whose GC coefficients are not
# significantly positive and whose nest parameters are interior; school keeps mode-specific GC (generic GC is positive), shopping
# the MNL (its NL puts mu_transit on the upper bound)
CHOSEN = {"work": "nl_dest_gen", "school": "mnl", "shopping": "mnl_gen", "other": "nl_dest_gen"}


def load(seg, s=50):
    return pd.read_parquet(f"{WORK}/gc_bio_{seg}_s{s}.parquet")


def model(tag, df, nested=False, asc_only=False, dest=False, generic=False, name="m", weight=None):
    """weight: column of df with observation weights (WESML, estimate_wesml.py); None = unweighted"""
    import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
    from biogeme.expressions import Beta, Variable as X
    from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit
    alts = [a for a in ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
    V = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in alts}
    if not asc_only:
        vars_ = SOCIO + (DEST if dest else [])
        for a in alts:
            if a == "CD": continue
            for v in vars_:
                if df.loc[df[f"av_{a}"] > 0, v].std() > 0: V[a] = V[a] + Beta(f"{v}_{a}", 0, None, None, 0) * X(v)
            V[a] = V[a] + Beta(f"km_{a}", 0, None, None, 0) * X("km")
        bg = Beta("gc", 0, None, None, 0)
        for a in GC_ALTS:
            if a in alts: V[a] = V[a] + (bg if generic else Beta(f"gc_{a}", 0, None, None, 0)) * X(f"gc_{a}")
    U = {NUM[a]: V[a] for a in alts}; AV = {NUM[a]: X(f"av_{a}") for a in alts}
    if nested:
        ns = []
        for k, v in NESTS.items():
            mem = [NUM[a] for a in v if a in alts]
            ns.append(OneNestForNestedLogit(Beta(f"mu_{k}", 1.2, 1.0, 10.0, 0) if len(mem) >= 2 else 1.0, mem, name=k))
        ll = models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(n for n in ns if n.list_of_alternatives)), X("y"))
    else:
        ll = models.loglogit(U, AV, X("y"))
    d = db.Database(f"{tag}_{name}", df.select_dtypes(include=[np.number, bool]).astype(float))
    os.makedirs(BIO, exist_ok=True); cwd = os.getcwd(); os.chdir(BIO)
    try:
        m = bio.BIOGEME(d, ll if weight is None else {"loglike": ll, "weight": X(weight)}, save_iterations=False, generate_html=True, generate_yaml=True); m.model_name = f"gc_{tag}_{name}"
        r = m.estimate()
    finally:
        os.chdir(cwd)
    return r, alts


def table(r):
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))
    return t.set_index("Name")


def save(tag, name, r, df, alts, llc):
    t = table(r); t.to_csv(f"{RES}/gc_{tag}_{name}.csv")
    cov = np.asarray(r.robust_variance_covariance_matrix); pd.DataFrame(cov, index=t.index, columns=t.index).to_csv(f"{RES}/gc_{tag}_{name}_cov.csv")
    for ext in ["html", "yaml"]:
        src = f"{BIO}/gc_{tag}_{name}.{ext}"
        if os.path.exists(src): os.replace(src, f"{RES}/gc_{tag}_{name}.{ext}")
    nav = df[[f"av_{a}" for a in alts]].sum(1).clip(lower=1); L0 = float(-np.log(nav).sum())
    LL = float(r.final_loglikelihood); K = int(r.number_of_free_parameters); N = len(df)
    return dict(segment=tag, model=name, N=N, K=K, LL0=L0, LLc=llc, LL=LL, rho2_0=1 - LL / L0, rho2bar_0=1 - (LL - K) / L0,
                rho2_c=(1 - LL / llc) if llc else np.nan, rho2bar_c=(1 - (LL - K) / llc) if llc else np.nan, AIC=2 * K - 2 * LL, BIC=K * np.log(N) - 2 * LL,
                converged=bool(r.algorithm_has_converged), gradient_norm=float(r.gradient_norm))


def lr(a, b):
    """LR test of the restricted model a against b"""
    from scipy.stats import chi2
    x = 2 * (b["LL"] - a["LL"]); k = b["K"] - a["K"]
    return dict(LR=x, df=k, p=float(chi2.sf(x, k)) if k > 0 else np.nan)


def upd(rows, f):
    new = pd.DataFrame(rows)
    if os.path.exists(f):
        old = pd.read_csv(f); key = ["segment", "model"] if "model" in new else ["segment", "test"]
        old = old[~old.set_index(key).index.isin(new.set_index(key).index)]; new = pd.concat([old, new])
    new.to_csv(f, index=False)


def run(seg, steps):
    rows, tests = [], []
    df = load(seg)
    rc, alts = model(seg, df, asc_only=True, name="constants"); llc = float(rc.final_loglikelihood)
    st = {"constants": save(seg, "constants", rc, df, alts, llc)}; rows.append(st["constants"])
    if "base" in steps:
        for name, kw in [("mnl", {}), ("nl", {"nested": True})]:
            r, alts = model(seg, df, name=name, **kw); st[name] = save(seg, name, r, df, alts, llc); rows.append(st[name])
            print(f"{seg} {name}: LL {st[name]['LL']:.1f} K {st[name]['K']} rho2_c {st[name]['rho2_c']:.3f}", flush=True)
        tests.append(dict(segment=seg, test="NL vs MNL", **lr(st["mnl"], st["nl"])))
    if "dest" in steps:
        for name, kw in [("mnl_dest", {"dest": True}), ("nl_dest", {"nested": True, "dest": True})]:
            r, alts = model(seg, df, name=name, **kw); st[name] = save(seg, name, r, df, alts, llc); rows.append(st[name])
        if "mnl" in st: tests.append(dict(segment=seg, test="area type at both ends vs home end (MNL)", **lr(st["mnl"], st["mnl_dest"])))
        if "nl" in st: tests.append(dict(segment=seg, test="area type at both ends vs home end (NL)", **lr(st["nl"], st["nl_dest"])))
    if "generic" in steps:
        for name, kw in [("mnl_gen", {"generic": True}), ("nl_gen", {"nested": True, "generic": True}), ("mnl_dest_gen", {"dest": True, "generic": True}), ("nl_dest_gen", {"nested": True, "dest": True, "generic": True})]:
            r, alts = model(seg, df, name=name, **kw); st[name] = save(seg, name, r, df, alts, llc); rows.append(st[name])
            print(f"{seg} {name}: LL {st[name]['LL']:.1f} K {st[name]['K']}", flush=True)
            base = name.replace("_gen", "")
            if base in st: tests.append(dict(segment=seg, test=f"mode-specific vs generic GC ({base})", **lr(st[name], st[base])))
            if name == "nl_gen": tests.append(dict(segment=seg, test="NL vs MNL (generic GC)", **lr(st["mnl_gen"], st["nl_gen"])))
            if name == "nl_dest_gen": tests.append(dict(segment=seg, test="NL vs MNL (generic GC, both ends)", **lr(st["mnl_dest_gen"], st["nl_dest_gen"])))
            if name == "mnl_dest_gen": tests.append(dict(segment=seg, test="area type at both ends vs home end (MNL, generic GC)", **lr(st["mnl_gen"], st["mnl_dest_gen"])))
    if "sens" in steps:
        best = os.environ.get("GC_STRUCTURE", CHOSEN[seg])
        for s in [35, 70]:
            d2 = load(seg, s); r, alts = model(seg, d2, nested=best.startswith("nl"), dest="_dest" in best, generic=best.endswith("_gen"), name=f"{best}_s{s}")
            x = save(seg, f"{best}_s{s}", r, d2, alts, llc); rows.append(x)
    upd(rows, f"{RES}/gc_summary_{seg}.csv"); upd(tests, f"{RES}/gc_tests_{seg}.csv")


def merge():
    """results/gc_summary.csv and gc_tests.csv from the per-segment files (segments run in parallel)"""
    for k in ["summary", "tests"]:
        fs = [f"{RES}/gc_{k}_{s}.csv" for s in SEGMENTS + ["pooled"] if os.path.exists(f"{RES}/gc_{k}_{s}.csv")]
        pd.concat([pd.read_csv(f) for f in fs]).to_csv(f"{RES}/gc_{k}.csv", index=False)


def pooled(structure):
    """every coefficient common to the four segments against the segmented models"""
    df = pd.concat([load(s) for s in SEGMENTS], ignore_index=True)
    rc, alts = model("pooled", df, asc_only=True, name="constants"); llc = float(rc.final_loglikelihood)
    r, alts = model("pooled", df, nested=structure.startswith("nl"), dest="_dest" in structure, generic=structure.endswith("_gen"), name=structure)
    st = save("pooled", structure, r, df, alts, llc)
    merge(); S = pd.read_csv(f"{RES}/gc_summary.csv"); seg = S[S.model.eq(structure) & S.segment.isin(SEGMENTS)]
    t = lr(st, dict(LL=seg.LL.sum(), K=int(seg.K.sum())))
    upd([st], f"{RES}/gc_summary_pooled.csv"); upd([dict(segment="all", test=f"segmented vs pooled ({structure})", **t)], f"{RES}/gc_tests_pooled.csv"); merge()
    print("pooled", structure, st["LL"], t, flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    segs = args[0].split(",") if args else SEGMENTS
    steps = sys.argv[sys.argv.index("--steps") + 1].split(",") if "--steps" in sys.argv else ["base", "dest"]
    if steps == ["pooled"]: pooled(os.environ.get("GC_STRUCTURE", "nl")); sys.exit()
    for s in segs: run(s, steps)
    merge()
