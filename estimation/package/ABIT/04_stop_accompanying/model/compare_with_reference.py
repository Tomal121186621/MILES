#!/usr/bin/env python3
"""Compare a Biogeme run (estimated_parameters.csv, estimated_fit.csv written by the estimate script) with reference_estimates.csv.

    ~/.venvs/biogeme/bin/python compare_with_reference.py [--outdir ../output]
Prints, per parameter: reference coefficient and robust s.e. (project output, full precision), Biogeme value and robust s.e.,
difference and difference / reference s.e.; then LL, N, K of the run against the article.  Writes comparison.csv in outdir.
"""
import argparse, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument("--outdir", default=os.path.join(HERE, "..", "output")); a = ap.parse_args()
ref = pd.read_csv(os.path.join(HERE, "reference_estimates.csv"))
fit_ref = ref[ref.parameter.isin(["LL0", "LL_beta", "N", "K"])].set_index("parameter")
ref = ref[~ref.parameter.isin(["LL0", "LL_beta", "N", "K"])].set_index("parameter")
est = pd.read_csv(os.path.join(a.outdir, "estimated_parameters.csv"))
name = "Name" if "Name" in est else est.columns[0]
est = est.set_index(name)
se_col = next((c for c in est.columns if c.lower().startswith("robust") and "err" in c.lower()), None)
out = pd.DataFrame({"reference": ref.coefficient, "reference_robust_se": ref.robust_se, "article": ref.article_coefficient,
                    "biogeme": est.Value.reindex(ref.index), "biogeme_robust_se": est[se_col].reindex(ref.index) if se_col else float("nan")})
out["difference"] = out.biogeme - out.reference
out["difference_over_se"] = out.difference / out.reference_robust_se
pd.set_option("display.width", 200); print(out.round(5).to_string())
extra = sorted(set(est.index) - set(ref.index))
if extra: print("parameters in the run but not in the reference:", extra)
f = os.path.join(a.outdir, "estimated_fit.csv")
if os.path.exists(f):
    r = pd.read_csv(f).iloc[0]
    print(f"LL run {r.LL:.3f}  article {fit_ref.article_coefficient['LL_beta']}  (project {fit_ref.coefficient['LL_beta']:.3f});  "
          f"N run {int(r.N)} article {int(fit_ref.article_coefficient['N'])};  K run {int(r.K)} article {int(fit_ref.article_coefficient['K'])}")
out.to_csv(os.path.join(a.outdir, "comparison.csv"))
print("max |difference / s.e.|:", float(out.difference_over_se.abs().max()))
