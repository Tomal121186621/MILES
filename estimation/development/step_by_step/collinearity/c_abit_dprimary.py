#!/usr/bin/env python3
"""Collinearity of the final primary-destination model: since 2026-11-09 the POOLED model of shopping, recreation, accompanying and
other tours (dest_pooled/dp_pooled.py, revised final: dp_final.pkl, row 'final' of dp_fit.csv; purpose scales, distance > 50 km
held at 0), estimation half, full choice set.  The separate models of dest_primary (checked by the 2026-11-08 version of this
script, c_abit_dprimary_pre1109r.py) are superseded.  Method: c_abit_pool.py (per-purpose variable correlations with the size
columns, per-purpose and pooled VIF, robust estimate correlations of the pooled model, flags, refits of the pooled model).
    POOL_THREADS=3 python3 c_abit_dprimary.py
    -> dp_shop|rec|acc|oth_var_corr.png/.csv (per purpose), dp_pooled_var_corr.png (the four side by side),
       dp_pooled_var_corr_pooled.csv, dp_pooled_est_corr.png/.csv, dp_pooled_pairs.csv, dp_pooled_facts.json, dp_pooled.log"""
import os, sys
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "4")
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); SB = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(SB, "dest_pooled")); sys.path.insert(0, os.path.join(SB, "dest_primary"))
sys.path.insert(0, os.path.join(SB, "tables_new"))
import c_abit_pool as CP   # noqa: E402
import dp_pooled as DPP    # noqa: E402  (imports d_primary: patched features, estimator modules)
import t_dest_primary as TD   # noqa: E402  (row labels of the destination tables)

P = DPP.PURP
PWORD = {"SHOPPING": "shopping", "RECREATION": "recreation", "ACCOMPANY": "accompanying", "OTHER": "other"}
TAGS = {p: f"dp_{DPP.SHORT[p]}" for p in P}
COMPL = {"pop": "population", "ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school enrolment"}
LAB = {v: CP.CC.plain(l) for _, t in TD.groups() for v, l in t if isinstance(v, str)}
LAB.update({k: v.replace("theta ", "θ ") for k, v in LAB.items() if k.startswith("theta_")})


def composite(files, out, title):
    """the per-purpose variable heatmaps, 2 x 2, as one image (page of the PDF)"""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(20, 20))
    for a, f in zip(ax.ravel(), files):
        a.imshow(plt.imread(f)); a.axis("off")
    fig.suptitle(title, fontsize=16); fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(out, dpi=220); plt.close(fig)


def main():
    lf = open(f"{HERE}/dp_pooled.log", "w")
    def log(s): print(s, flush=True); lf.write(str(s) + "\n"); lf.flush()
    fit = pd.read_csv(f"{DPP.HERE}/dp_fit.csv"); fin = fit[fit.step == "final"].iloc[0]
    ref = None
    if len(sys.argv) > 1 and sys.argv[1] == "from-log":   # refit rows of an earlier (interrupted) run: python3 c_abit_dprimary.py from-log <file>
        import numpy as np, ast
        ref = [eval(l, {"np": np}) for l in open(sys.argv[2]) if l.startswith("{'refit'")]
    CP.run("dp_pooled", "dp_pooled", DPP, P, f"{DPP.HERE}/dp_final.pkl", float(fin.LL), int(fin.K), lambda q: LAB[q], PWORD, TAGS,
           "Primary destination, pooled model (4 purposes)", COMPL, threads=int(os.environ.get("POOL_THREADS", "3")), log=log,
           refit_ok=ref is None, ref_rows=ref)
    composite([f"{HERE}/{TAGS[p]}_var_corr.png" for p in P], f"{HERE}/dp_pooled_var_corr.png",
              "Primary destination, pooled model: correlations of the explanatory variables, per purpose (within choice situation)")


if __name__ == "__main__":
    main()
