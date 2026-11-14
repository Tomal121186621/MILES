#!/usr/bin/env python3
"""Collinearity of the final school location models (other_locations/l07_school.py, bands K-8, high school, college; SCHOOL_LOGSUM =
locations/school_logsum_new.npy as in the final runs), estimation half, full choice set (all zones with enrolment of the band).
Choice situation = (student, possible home zone) row of the location mixture, weighted by its home-zone weight (the rows of one
student sum to 1), as in the estimator.  The size term ln S at the final size weights is shown with the variables (coefficient mu).
    python3 estimation/development/collinearity/c_silo_school.py [k8 hs col]   ->  school_<band>_var_corr.png, school_<band>_est_corr.png, school_<band>_pairs.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, ast
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; LOC = os.path.join(os.path.dirname(HERE), "locations")
os.environ.setdefault("SCHOOL_LOGSUM", f"{LOC}/school_logsum_new.npy")
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.path.insert(0, os.path.join(DEV, "other_locations")); sys.path.insert(0, CODE)
import c_silo_common as CC   # noqa: E402
import l07_school as L7   # noqa: E402  (imports the schoolchoice engine with SCHOOL_LOGSUM)
G, S = L7.G, L7.S

BAND = {"k8": "k8", "hs": "hs", "col": "college"}; TITLE = {"k8": "School location K–8", "hs": "School location, high school", "col": "College location"}
PLAB = {"mu_size": "size coefficient μ", "g_pub_in": "in-boundary public enrolment, log weight", "g_priv": "private enrolment, log weight",
        "g_priv4": "private 4-year enrolment, log weight", "g_cc": "2-year enrolment, log weight", "b_t": "car time (min)", "b_lt": "ln(1+time)",
        "b_intra": "same zone", "b_ccpub": "other county × public share", "b_cc": "other county", "b_cs": "other state",
        "b_tXg1": "time × income <$40k", "b_tXg4": "time × income $125k+", "b_tXcar0": "time × no car", "b_tXcarlow": "time × fewer cars than drivers",
        "lnS": "ln size S (final weights)"}


def one(seg):
    name = f"l07_school_{BAND[seg]}"; fr = pd.read_csv(f"{LOC}/{name}_fit.csv"); fin = fr[fr.step == "final"].iloc[0]
    line = [l for l in open(f"{LOC}/{name}.log") if l.startswith("final:")][-1]; spec = ast.literal_eval(line[len("final: "):line.index("]") + 1])
    co = pd.read_csv(f"{LOC}/{name}_coef.csv"); co = co[co.step == "final"].set_index("param").coef.to_dict()
    tex = CC.tex_labels(f"{os.path.dirname(HERE)}/tables_new/est_school_new.tex")
    for v in PLAB.values(): assert v in tex or v.startswith("ln size"), v       # labels are the table's row labels
    D = G.Design(seg, "estimation", "full"); t0, si, sabs = S.split(spec); assert not si

    def run(drop=(), replace=None):
        sp = [k for k in spec if S.pname(k) not in drop]; t, si_, sb = S.split(sp); saved = {}
        for pn, v in (replace or {}).items():
            k = next(k for k in spec if S.pname(k) == pn); saved[k] = D.cache.get(k); D.cache[k] = v.astype(np.float32)
        M = G.Model(D, t, si_, sb, None); M = S.Search.converge(None, M, M.at(co)); M.robust()
        for k, v in saved.items():
            if v is None: D.cache.pop(k, None)
            else: D.cache[k] = v
        return dict(LL=M.ll, K=len(M.th), N=D.N, names=list(M.names), b=M.th, se=M.se, cov=M.V, M=M)

    base = run(); print(seg, "LL", base["LL"], "reported", fin.LL, flush=True); assert abs(base["LL"] - fin.LL) < 0.1
    M = base["M"]; terms = M.terms; vn = [S.pname(k) for k in terms]
    X = np.moveaxis(M.Xs, 0, 2).astype(float); av = D.av; w = np.exp(D.lw)
    lw = np.zeros((len(D.comps), D.R))
    for j, k in enumerate(M.gidx): lw[k] += base["b"][1 + j]
    lnS = np.log((np.exp(lw)[:, :, None] * D.NK).sum(0) + 1e-12)
    inter = {}
    for k in terms:
        if "*" in k and k.split("*")[0] in terms:
            q = k.split("*")[1]; band = "income" if q in ("g1", "g3", "g4") else "car availability" if q in ("car0", "carlow") else None
            inter[S.pname(k)] = (S.pname(k.split("*")[0]), CC.zratio(X, vn.index(S.pname(k)), vn.index(S.pname(k.split("*")[0])), av), band)
    for k, (m, z, _) in inter.items():
        assert np.allclose(X[:, :, vn.index(k)] * av, X[:, :, vn.index(m)] * z[:, None] * av, atol=1e-4), k
    sets = [({"b_t", "b_lt"}, "functional form of one variable (time and ln(1 + time))")]
    protect = [n for n in base["names"] if n.startswith(("mu_", "g_"))]
    base.pop("M")
    CC.run_alt_model(f"school_{BAND[seg]}", f"{TITLE[seg]}, final model", X, vn, av, w, PLAB, inter, sets, base,
                     lambda drop, replace: {k: v for k, v in run(drop, replace).items() if k != "M"}, protect=protect, extra_vars=[("lnS", lnS[:, :, None])])


if __name__ == "__main__":
    for s in sys.argv[1:] or ["k8", "hs", "col"]: one(s)
