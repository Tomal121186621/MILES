#!/usr/bin/env python3
"""Collects the per-model results of c_silo_*.py into silo_summary.csv: one row per flag (variable pair |r| >= 0.7, VIF >= 10,
estimate pair |r| >= 0.8) and one row per refit (estimation half; LR test against the final model).
    python3 estimation/development/collinearity/c_silo_summary.py   ->  silo_summary.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, glob, json
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"   # results of this step (data); CODE = this folder
ORDER = ["county", "zone", "dwelling", "cars", "workplace", "school_k8", "school_hs", "school_college"]
COLS = ["model", "row", "source", "pair", "p1", "p2", "type", "why", "var_r", "var_r_centred", "est_r", "est_r_centred", "centring_removes",
        "VIF", "VIF_p1", "VIF_p2", "refit", "LL", "K", "BIC", "dBIC", "LR", "df", "p", "member", "b_final", "se_final", "b_refit", "se_refit",
        "se_ratio", "sign_changes", "est_r_after"]


def main():
    out = []
    for m in ORDER:
        f = f"{HERE}/{m}_pairs.csv"
        if not os.path.exists(f): print("missing", m); continue
        d = pd.read_csv(f); d["row"] = np.where(d.get("refit", pd.Series(index=d.index, dtype=object)).notna(), "refit", "flag")
        fx = json.load(open(f"{HERE}/{m}_facts.json")); print(m, "LL", round(fx["LL"], 2), "max VIF", round(fx["max_vif"], 2), len(d), "rows")
        out.append(d)
    S = pd.concat(out, ignore_index=True).reindex(columns=COLS)
    S.to_csv(f"{HERE}/silo_summary.csv", index=False)
    print(S[S.row == "flag"][["model", "source", "pair", "type", "var_r", "var_r_centred", "est_r", "est_r_centred", "VIF"]].round(3).to_string())


if __name__ == "__main__":
    main()
