#!/usr/bin/env python3
"""Roorda-style verification / validation of the TAZ coefficient sets (2026-10-28), with validate_survey.run_setting unchanged.

    python3 activity/lib/tasha_estimation/roorda_taz.py   -> data/abit_roorda_tables_taz.csv, abit_roorda_ks_taz.csv, abit_roorda_extra_taz.csv,
                               5_reports/estimation_manual/abit/tables/tab_roorda_taz.tex

Settings (survey population, seeds 1-10): verification_* (estimation half) and validation_* (validation half) for
  behavtaz / caltaz   coef_tasha_taz / coef_tasha_cal_taz (TAZ re-specified destination rows)
  behavnow / calnow   coef_tasha / coef_tasha_cal as they are now (control: the tour-mode files changed on 2026-10-27, after the
                      runs of record svy_*_behav / svy_*_cal of 2026-10-26, which are read from data/abit_roorda_tables.csv)
The shared outputs of validate_survey.py (data/abit_roorda_*.csv, roorda_tables.md, figures) are not written."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
A3 = f"{WORKSPACE}/3_abit"
sys.path.insert(0, f"{TERP_HOME}/activity/validation"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_survey as RV                     # noqa: E402
from compare_dc_taz import num, table, TAB         # noqa: E402
V = RV.V; TAGS = ["behavnow", "behavtaz", "calnow", "caltaz", "behavtaz2", "rec1029"]
RUN = sys.argv[1].split(",") if len(sys.argv) > 1 else TAGS     # tags to (re)compute; the others are kept from the _taz files
for t in TAGS:
    RV.SETTINGS[f"verification_{t}"] = ("survey", "estimation", [f"svy_est_{t}_s{s:02d}" for s in range(1, 11)], RV.RUNROOT)
    RV.SETTINGS[f"validation_{t}"] = ("survey", "validation", [f"svy_val_{t}_s{s:02d}" for s in range(1, 11)], RV.RUNROOT)


def main():
    res = [RV.run_setting(f"{k}_{t}") for t in RUN for k in ["verification", "validation"]]
    T, K, E, _ = (pd.concat([r[i] for r in res], ignore_index=True) for i in range(4))
    new = set(T.setting)
    fs = [f"{V}/data/abit_roorda_{x}_taz.csv" for x in ["tables", "ks", "extra"]]
    if all(os.path.exists(f) for f in fs):
        T, K, E = (pd.concat([o[~o.setting.isin(new)], n], ignore_index=True) for o, n in zip([pd.read_csv(f) for f in fs], [T, K, E]))
    T.to_csv(f"{V}/data/abit_roorda_tables_taz.csv", index=False); K.to_csv(f"{V}/data/abit_roorda_ks_taz.csv", index=False); E.to_csv(f"{V}/data/abit_roorda_extra_taz.csv", index=False)
    O = pd.read_csv(f"{V}/data/abit_roorda_tables.csv"); A = pd.concat([O[O.setting.str.endswith(("_behav", "_cal")) & ~O.setting.str.startswith("chain")], T], ignore_index=True)
    A = A[A.variant == "base"]
    lab = {"rec1029": "behavioural, of record (TAZ, 10-29)", "behavtaz2": "behavioural, TAZ (specification of record)", "behav": "behavioural, of record (10-26)", "behavnow": "behavioural, current (10-27)", "behavtaz": "behavioural, TAZ",
           "cal": "calibrated, of record (10-26)", "calnow": "calibrated, current (10-27)", "caltaz": "calibrated, TAZ"}
    types = ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME", "ALL"]; rows, out = [], []
    for k in ["verification", "validation"]:
        for t in ["behav", "behavnow", "behavtaz2", "rec1029", "behavtaz", "cal", "calnow", "caltaz"]:
            g = A[A.setting == f"{k}_{t}"].set_index("type")
            if not len(g): continue
            act = [g.diff_pct.get(x, np.nan) for x in types]; km = [g.diff_km_pct.get(x, np.nan) for x in types]
            out.append(dict(setting=k, set=t, **{f"act_{x}": a for x, a in zip(types, act)}, **{f"km_{x}": b for x, b in zip(types, km)}))
            rows.append(" & ".join([k, lab[t]] + [num(v, 1) for v in act] + [num(v, 1) for v in km]))
    pd.DataFrame(out).to_csv(f"{V}/data/abit_roorda_compare_taz.csv", index=False)
    head = ["Setting", "Set"] + [f"\\makecell[b]{{{x.title()}\\\\act.}}" for x in ["work", "school", "shop", "other", "home", "all"]] + [f"\\makecell[b]{{{x.title()}\\\\km}}" for x in ["work", "school", "shop", "other", "home", "all"]]
    table(f"{TAB}/tab_roorda_taz.tex", "Roorda-style verification and validation (survey population, mean of 10 replications): deviation from the survey (\\%) in activities and average distance, model of record and TAZ sets.",
          "tab:roordataz", head, rows,
          "Sources: \\texttt{data/abit\\_roorda\\_tables.csv} (of record, runs of 2026-10-26), \\texttt{data/abit\\_roorda\\_tables\\_taz.csv} (\\texttt{tasha\\_estimation/roorda\\_taz.py}), "
          "\\texttt{abit\\_roorda\\_compare\\_taz.csv}. Current: the record sets as they are after the tour-mode changes of 2026-10-27 (control for the TAZ sets, which are copies of them). "
          "TAZ: \\path{coef_tasha_taz}, \\path{coef_tasha_cal_taz} (re-specified, without the LOS terms); TAZ (specification of record): \\path{coef_tasha_taz2}. Distance: zone skim on both sides, survey trip ends at the tract internal point (as for the runs of record); exclusion rule base.",
          "@{}ll" + "r" * 12 + "@{}", size="\\scriptsize")
    print(pd.DataFrame(out).round(1).to_string())


if __name__ == "__main__":
    main()
