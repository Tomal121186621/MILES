#!/usr/bin/env python3
"""Compare your Biogeme estimates (../output/<model>_estimates.csv, written by the estimate_*.py script) with the article
(reference_estimates.csv). Prints both and the differences; writes ../output/comparison_with_article.csv.
    python compare_with_reference.py"""
import glob, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.abspath(f"{HERE}/../output")
f = [x for x in glob.glob(f"{OUT}/*_estimates.csv") if "check" not in x]
assert f, "no ../output/*_estimates.csv: run the estimate_*.py script first"
est = pd.read_csv(f[0]).set_index("Name")
val = est[[c for c in est.columns if c.lower().startswith("value")][0]]
rse = est[[c for c in est.columns if "robust" in c.lower() and "err" in c.lower()][0]]
ref = pd.read_csv(f"{HERE}/reference_estimates.csv")
fit = ref[ref.note == "model statistic"]; ref = ref[ref.note.isna() & ref.parameter.notna()].set_index("parameter")
c = pd.DataFrame({"article": ref.coefficient, "biogeme": val.reindex(ref.index), "article_robust_se": ref.robust_se, "biogeme_robust_se": rse.reindex(ref.index)})
c["difference"] = c.biogeme - c.article; c["se_difference"] = c.biogeme_robust_se - c.article_robust_se
pd.set_option("display.width", 200); print(c.round(5).to_string())
print(f"\nlargest |difference| of a coefficient: {c.difference.abs().max():.5f}; of a robust s.e.: {c.se_difference.abs().max():.5f}")
print("(the article reports 4 decimals: differences up to 0.00005 are rounding)")
print("article fit statistics:"); print(fit[["parameter", "coefficient"]].to_string(index=False))
c.to_csv(f"{OUT}/comparison_with_article.csv")
