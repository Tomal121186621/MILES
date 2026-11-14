#!/usr/bin/env python3
"""Rows of the article's activity-model tables (tab_s3_verification.tex, tab_s3_validation.tex) from data/abit_roorda_tables.csv
(variant 'base'), for the model runs named by the setting suffix.  Only the numeric rows are rewritten; layout and notes stay.

    ABIT_SUFFIX=_respec python3 reports/article/s3_tables.py      # default suffix _sched; edits WORKSPACE/5_reports/article/sections
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, re
import pandas as pd
V = f"{WORKSPACE}"; ART = f"{V}/5_reports/article"   # article sources (workspace)
SUF = os.environ.get("ABIT_SUFFIX", "_sched")
T = pd.read_csv(f"{V}/data/abit_roorda_tables.csv"); T = T[T.variant == "base"]
ROWS = [("Work", "WORK"), ("School", "SCHOOL"), ("Shopping", "SHOPPING"), ("Other", "OTHER"), (r"\quad recreation", "RECREATION"),
        (r"\quad accompanying", "ACCOMPANY"), (r"\quad other errands", "OTHER_OTHER"), ("Return home", "HOME"), ("Total", "ALL")]
sg = lambda x, d: f"{x:+.{d}f}".replace("+-", "-") if round(x, d) != 0 else f"{0:.{d}f}"


def row(lab, r):
    return (f"    {lab} & {r.model_total:.0f} & {r.model_total_sd:.0f} & {r.observed_total:.0f} & {sg(r.model_total - r.observed_total, 0)} & {sg(r.diff_pct, 1)} & "
            f"{r.model_km:.2f} & {r.model_km_sd:.2f} & {r.observed_km_zone_skim:.2f} & {sg(r.model_km - r.observed_km_zone_skim, 2)} & {sg(r.diff_km_pct, 1)} & "
            f"{r.observed_km_reported:.2f} & {sg(r.diff_km_pct_reported, 1)} \\\\")


for half in ["verification", "validation"]:
    d = T[T.setting == f"{half}{SUF}"].set_index("type"); assert len(d), f"{half}{SUF}"
    f = f"{ART}/sections/tab_s3_{half}.tex"; s = open(f).read().split("\n")
    for lab, ty in ROWS:
        i = [k for k, l in enumerate(s) if l.strip().startswith(lab + " &")]; assert len(i) == 1, (f, lab)
        s[i[0]] = row(lab, d.loc[ty])
    open(f, "w").write("\n".join(s)); print(f, "rows from", f"{half}{SUF}")
