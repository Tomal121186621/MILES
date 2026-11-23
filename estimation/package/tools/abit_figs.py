"""DAYMAP models of the manual-estimation package: coefficient rows from model/reference_estimates.csv and hold-out
predictions (probabilities of every alternative, by Biogeme simulation of the model's own log-likelihood with the choice set to
each alternative in turn).  Shared by the estimation PDF (5_reports/estimation_pdfs/make_abit_figures.py) and the notebooks."""
import importlib, os, re, sys, tempfile
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODES6 = {1: "Car driver", 2: "Walk", 3: "Bike", 4: "Car passenger", 5: "Bus", 6: "Train"}
ALTS = {**{f: MODES6 for f in ("14_tour_mode_work", "15_tour_mode_school", "16_tour_mode_shopping", "17_tour_mode_other", "18_tour_mode_joint_shopping",
                                "19_tour_mode_joint_other")},
        "20_transit_leg_mode": {1: "Transit", 2: "Walk", 3: "Car passenger", 4: "Car driver", 5: "Bike"},
        "11_outing_generation": {0: "No outing", 1: "Outing"}, "12_outing_mode": {0: "Mode of the work tour", 1: "Walk"},
        "13_return_home": {0: "Goes on directly", 1: "Returns home"}}
SUFFIX = {"WALK": "Walk", "BIKE": "Bike", "CAR_PASSENGER": "Car passenger", "BUS": "Bus", "TRAIN": "Train", "CAR_DRIVER": "Car driver",
          "walk": "Walk", "bike": "Bike", "car_passenger": "Car passenger", "car_driver": "Car driver", "transit": "Transit",
          "SHOPPING": "Shopping", "RECREATION": "Recreation", "ACCOMPANY": "Accompanying", "OTHER": "Other", "SO": "Shopping, other"}


def tex2txt(s):
    s = str(s)
    for a, b in [("\\,", " "), ("$\\times$", "x"), ("$<$", "<"), ("$>$", ">"), ("$^2$", "2"), ("\\$", "$"), ("\\%", "%"), ("--", "-"), ("$", ""), ("\\", "")]:
        s = s.replace(a, b)
    s = re.sub(r"\bln\b", "log", s)
    return re.sub(r"\s+", " ", s).strip()


def reference(folder):
    r = pd.read_csv(f"{ROOT}/ABIT/{folder}/model/reference_estimates.csv")
    r = r[~r.parameter.isin(["LL0", "LL_beta", "LL_holdout", "N", "K"]) & r.parameter.astype(str).str.match(r"^(B_|ASC_|MU_|G_|L_|S_|LAMBDA|THETA|SCALE)", na=False)].copy()
    c = "article_coefficient" if "article_coefficient" in r and r.article_coefficient.notna().all() else "coefficient"
    s = "article_robust_se" if "article_robust_se" in r and r.article_robust_se.notna().all() else "robust_se"
    r["coef"], r["se"] = r[c].astype(float), r[s].astype(float)
    return r


def coef_rows(folder):
    r = reference(folder); out = []
    for _, x in r.iterrows():
        p = x.parameter; lab = x.get("article_label") if "article_label" in r else None; grp = x.get("article_group") if "article_group" in r else None
        series = ""
        if isinstance(lab, str) and " | " in lab:                       # mode models: "Label | Mode"
            lab, m = lab.rsplit(" | ", 1); series = "" if m == "generic" else m
        else:
            for suf in sorted(SUFFIX, key=len, reverse=True):
                if p.endswith("_" + suf): series = SUFFIX[suf]; break
            if p.endswith("_shared"): series = ""
        if not isinstance(lab, str) or not lab.strip():
            lab = p.replace("ASC_", "Constant ").replace("B_", "")
            for suf in sorted(SUFFIX, key=len, reverse=True):
                if lab.endswith("_" + suf): lab = lab[: -len(suf) - 1]; break
            lab = lab.replace("_", " ").strip().capitalize()
        lab = tex2txt(lab)
        if lab.lower().startswith("constant"): lab = "Constant"
        if not isinstance(grp, str):
            grp = "Constants and scales" if (lab == "Constant" or p.startswith("MU_")) else ("Level of service" if series == "" else "Person, household and destination")
        out.append(dict(label=lab, group=tex2txt(grp), coef=x.coef, se=x.se, series=series))
    rows = pd.DataFrame(out)
    if rows.series.nunique() > 1 and (rows.series == "").any():
        rows.loc[rows.series == "", "series"] = "All" if folder.startswith(("1", "2")) else "All purposes"
    return rows


def module(folder):
    d = f"{ROOT}/ABIT/{folder}/model"
    name = next(f[:-3] for f in sorted(os.listdir(d)) if f.startswith("estimate_") and f.endswith(".py") and "_pre" not in f)
    sys.path.insert(0, d)
    try:
        if name in sys.modules: del sys.modules[name]
        return importlib.import_module(name)
    finally:
        sys.path.pop(0)


def holdout_probabilities(folder):
    """hold-out table (as read by the model script, plus the raw columns) and the probability of every alternative"""
    import biogeme.biogeme as bio, biogeme.database as bdb
    from biogeme.parameters import Parameters
    M = module(folder); df = M.read("holdout")
    ll = M.formulas() if hasattr(M, "formulas") else M.loglike() if callable(getattr(M, "loglike", None)) else M.LOGLIKE
    ll = ll["loglike"] if isinstance(ll, dict) else ll
    r = pd.read_csv(f"{ROOT}/ABIT/{folder}/model/reference_estimates.csv"); r = r[r.parameter.astype(str).str.match(r"^(B_|ASC_|MU_)")]
    betas = dict(zip(r.parameter, r.coefficient.astype(float)))
    alts = sorted(ALTS[folder]); P = pd.DataFrame(index=df.index)
    pr = Parameters(); pr.set_value("generate_html", False); pr.set_value("generate_yaml", False)
    here = os.getcwd(); os.chdir(tempfile.mkdtemp())
    try:
        for j in alts:
            d = df.copy(); d["y"] = float(j)
            av = d.get({20: None}.get(0)) if False else None
            m = bio.BIOGEME(bdb.Database(f"h{j}", d), {"lp": ll}, parameters=pr); m.model_name = f"p{j}"
            lp = m.simulate(betas)["lp"].values
            P[j] = np.where(np.isfinite(lp), np.exp(lp), 0.0)
    finally:
        os.chdir(here)
    P = P.div(P.sum(1), axis=0)
    raw = pd.read_parquet(next(f"{ROOT}/ABIT/{folder}/input/data/holdout/{f}" for f in ("tours.parquet", "estimation_table.parquet")
                               if os.path.exists(f"{ROOT}/ABIT/{folder}/input/data/holdout/{f}")))
    return raw.reset_index(drop=True), P.reset_index(drop=True)


def weights(raw):
    if "wesml" in raw: return raw["wesml"].astype(float).values      # work tours: choice-based sample weights (WESML); the other models are unweighted
    return np.ones(len(raw))


SEGMENT = {   # (column rule, panel title, x label) of the second hold-out panel
    "11_outing_generation": (lambda r: pd.cut(r.dur_h, [0, 4, 7, 99], labels=["< 4 h", "4-7 h", "7 h +"]), "Outing", "Work episode duration"),
    "12_outing_mode": (lambda r: pd.cut(r.km, [-1, 0.5, 1, 1e9], labels=["< 0.5 km", "0.5-1 km", "1 km +"]), "Walk", "Distance to the stop"),
    "13_return_home": (lambda r: r.nep.clip(upper=5).astype(int).astype(str).replace({"5": "5+"}), "Return home", "Episodes of the day"),
    "20_transit_leg_mode": (lambda r: np.select([r["first"] == 1, r["last"] == 1], ["First leg", "Last leg"], "Other leg"), "Transit", "Leg of the tour"),
}
for _f in ("14_tour_mode_work", "15_tour_mode_school", "16_tour_mode_shopping", "17_tour_mode_other", "18_tour_mode_joint_shopping", "19_tour_mode_joint_other"):
    SEGMENT[_f] = (lambda r: np.where(r.autos == 0, "No car", np.where(r.autos < r.drivers, "Cars < drivers", "Cars >= drivers")), "Car driver", "Household cars")


def holdout_tables(folder):
    """panel tables (observed / model shares, %) for the hold-out figure"""
    raw, P = holdout_probabilities(folder); w = weights(raw); A = ALTS[folder]
    y = raw.y.astype(int).values
    obs = pd.Series({A[j]: 100 * w[y == j].sum() / w.sum() for j in sorted(A)}); mod = pd.Series({A[j]: 100 * (w * P[j].values).sum() / w.sum() for j in sorted(A)})
    t1 = pd.DataFrame({"observed": obs, "model": mod})
    if len(A) == 2: t1 = t1.iloc[[1]]
    seg, title, xl = SEGMENT[folder]; g = np.asarray(seg(raw)).astype(str)
    focus = {**{f: 1 for f in ("14_tour_mode_work", "15_tour_mode_school", "16_tour_mode_shopping", "17_tour_mode_other", "18_tour_mode_joint_shopping", "19_tour_mode_joint_other")},
             "20_transit_leg_mode": 1}.get(folder, 1)
    rows = {}
    for k in pd.unique(g):
        m = g == k
        if w[m].sum() <= 0 or m.sum() < 20: continue
        rows[k] = (100 * w[m][y[m] == focus].sum() / w[m].sum(), 100 * (w[m] * P[focus].values[m]).sum() / w[m].sum())
    t2 = pd.DataFrame(rows, index=["observed", "model"]).T
    if isinstance(g[0], str) and folder in SEGMENT and folder.startswith(("11", "12")):
        t2 = t2.reindex([c for c in ["< 4 h", "4-7 h", "7 h +", "< 0.5 km", "0.5-1 km", "1 km +"] if c in t2.index])
    t2 = t2.sort_index() if folder in ("13_return_home",) else t2
    return t1, (title, t2, xl), len(raw)
