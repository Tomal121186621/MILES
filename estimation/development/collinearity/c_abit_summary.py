#!/usr/bin/env python3
"""Collects the per-model results of c_abit_*.py into abit_summary.csv (as c_silo_summary.py): one row per flag (variable pair
|r| >= 0.7, VIF >= 10, estimate pair |r| >= 0.8), one row per refit and one row per explicit check (pair "CHECK: ...").
    python3 estimation/development/collinearity/c_abit_summary.py   ->  abit_summary.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, json
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"   # results of this step (data); CODE = this folder
ORDER = (["mc_work", "mc_shopping", "mc_other", "mc_school", "mj_shopping", "mj_other", "dp_pooled"]
         + [f"st_{p}" for p in ("shop", "rec", "acc", "oth")]
         + ["lp_edu", "l03_wahb", "l04_wbhome", "l05_wbwork", "l06_outing_dest", "a01_outing", "a02_outing_mode", "a03_return",
            "l01_daycare", "l02_nonstud"])
# 2026-11-11: mj_shopping / mj_other (group-level mode models of the joint tours, c_abit_mode_joint.py) added
# 2026-11-09: dp_pooled (pooled primary destinations) replaces dp_shop/rec/acc/oth; lp_edu (pooled) replaces l01 / l02, whose
# 2026-11-08 rows are kept at the end, marked superseded
STATUS = {"l01_daycare": "superseded by lp_edu (rows of the 2026-11-08 separate model)", "l02_nonstud": "superseded by lp_edu (rows of the 2026-11-08 separate model)"}
COLS = ["model", "status", "purpose", "row", "source", "pair", "p1", "p2", "type", "why", "var_r", "var_r_centred", "est_r", "est_r_centred", "centring_removes",
        "VIF", "VIF_p1", "VIF_p2", "refit", "LL", "K", "BIC", "dBIC", "LR", "df", "p", "member", "b_final", "se_final", "b_refit", "se_refit",
        "se_ratio", "sign_changes", "est_r_after"]


def main():
    out = []
    for m in ORDER:
        f = f"{HERE}/{m}_pairs.csv"
        if not os.path.exists(f): print("missing", m); continue
        try: d = pd.read_csv(f)
        except pd.errors.EmptyDataError: d = pd.DataFrame(columns=["model", "pair"])
        ref = d["refit"].notna() if "refit" in d else pd.Series(False, index=d.index)
        chk = d["pair"].astype(str).str.startswith("CHECK")
        d["row"] = np.where(chk, "check", np.where(ref, "refit", "flag")); d["status"] = STATUS.get(m, "final")
        fx = json.load(open(f"{HERE}/{m}_facts.json")); print(m, "LL", round(fx["LL"], 2), "max VIF", round(fx["max_vif"], 2), len(d), "rows")
        out.append(d)
    S = pd.concat(out, ignore_index=True)
    S = S.reindex(columns=COLS + [c for c in S.columns if c not in COLS])
    S.to_csv(f"{HERE}/abit_summary.csv", index=False)
    print(S[S.row == "flag"][["model", "source", "pair", "type", "var_r", "est_r", "est_r_centred", "VIF"]].round(3).to_string())


if __name__ == "__main__":
    main()
