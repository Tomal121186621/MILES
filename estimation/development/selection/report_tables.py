#!/usr/bin/env python3
"""Summary tables (markdown) of the MAST re-specification for REPORT.md, from the final_*.pkl files.

    python3 estimation/development/selection/report_tables.py   -> report_tables.md (pasted into REPORT.md) and summary_*.csv
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, pickle
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/side_experiments/respec_2026-11/abit"   # results of the selection (data); CODE = this folder
DISC = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
DEST = [f"{p}_{k}" for k in ["primary", "stop"] for p in DISC]
OTHER = ["WORK_wbwork", "WORK_wbhome", "WORK_wahb", "EDUCATION_nonstud", "EDUCATION_daycare", "OTHER_wbs"]
NAME = {**{f"{p}_primary": f"{p.lower()} main" for p in DISC}, **{f"{p}_stop": f"{p.lower()} stop" for p in DISC},
        "WORK_wbwork": "work business, usual workplace", "WORK_wbhome": "work business, from home", "WORK_wahb": "work trips, home workers",
        "EDUCATION_nonstud": "school without a record", "EDUCATION_daycare": "daycare", "OTHER_wbs": "outing first stop"}


def md(df, fl=3):
    cols = list(df.columns); out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" if df[c].dtype == object else "---:" for c in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join((f"{v:,.{fl}f}" if isinstance(v, (float, np.floating)) and np.isfinite(v) else "–" if isinstance(v, (float, np.floating)) else str(v)) for v in r.values) + " |")
    return "\n".join(out)


def loc_rows(segs, folder):
    fit, rob, log = [], [], []
    for s in segs:
        f = f"{HERE}/{folder}/work/final_{s}.pkl"
        if not os.path.exists(f): continue
        o = pickle.load(open(f, "rb")); h, c, ce = o["holdout"], o["current_holdout"], o["current_est"]
        Kc = len(o["current_spec"].params()) if o["current_spec"] else np.nan
        fit.append(dict(model=NAME[s], N=o["N"], K=o["K"], K_current=Kc, LL=o["LL"], LL_current=ce["LL_sum"] if ce else np.nan,
                        BIC=np.log(o["N"]) * o["K"] - 2 * o["LL"], BIC_current=np.log(o["N"]) * Kc - 2 * ce["LL_sum"] if ce else np.nan,
                        sel_holdout_LL_obs=h["LL_obs"], current_LL_obs=c["LL_obs"] if c else np.nan, KS=h["KS"], KS_current=c["KS"] if c else np.nan,
                        km_pred=h["km_pred"], km_current=c["km_pred"] if c else np.nan, km_obs=h["km_obs"]))
        t = o["table"]; sw = o["swap"]
        Rw = o["within_corr"]; A = np.abs(Rw.values - np.eye(len(Rw))); i, j = np.unravel_index(A.argmax(), A.shape)
        vif = o["within_vif"]
        rob.append(dict(model=NAME[s], swap_LR=sw["LR"], df=sw["df"], p=sw["p"], n_z_gt_1_96=sw["n_z_gt_196"], swap_LL_obs_on_est=sw["swap_holdout_on_est"],
                        current_LL_obs_on_est=ce["LL_obs"] if ce else np.nan,
                        boot_over_robust_max=float(np.nanmax(t.boot_se / t.rob_se)), cluster_over_robust_max=float(np.nanmax(t.cluster_se / t.rob_se)),
                        est_pairs_r_gt_0_9=len(o["corr_flags"]), cond_H=o["cond"], LOS_max_r=f"{Rw.index[i]}~{Rw.columns[j]} {Rw.values[i, j]:.2f}",
                        VIF_cgt=float(vif.get("cgt", np.nan)), nan_se=",".join(o.get("nan_se", [])) or "none"))
        for r in o["log"]: log.append(dict(model=NAME[s], **{k: r.get(k) for k in ["round", "block", "candidate", "estimate", "rob_t", "decision"]}))
    return pd.DataFrame(fit), pd.DataFrame(rob), pd.DataFrame(log)


def main():
    out = []
    for fam, segs, folder in [("Destinations", DEST, "destinations"), ("Other locations", OTHER, "other_locations")]:
        F, R, L = loc_rows(segs, folder)
        if not len(F): continue
        F.to_csv(f"{HERE}/{folder}/summary_fit.csv", index=False); R.to_csv(f"{HERE}/{folder}/summary_robustness.csv", index=False); L.to_csv(f"{HERE}/{folder}/summary_log.csv", index=False)
        out += [f"### {fam}: fit against the current models", "", md(F), "", f"### {fam}: robustness", "", md(R), ""]
        dec = L[L["round"].isin([1, 2]) & L.candidate.ne("base")].copy()
        dec["d"] = np.where(dec.decision.astype(str).str.startswith("kept"), "K", np.where(dec.decision.astype(str).str.startswith("not applicable"), "n/a",
                   np.where(dec.decision.astype(str).str.startswith("irrelevant"), "0", "–")))
        piv = dec.drop_duplicates(["model", "candidate"], keep="last").pivot(index="candidate", columns="model", values="d").fillna("")
        out += [f"### {fam}: candidate decisions (K kept, – rejected, 0 weight 0, n/a constant in the segment; last test shown)", "", md(piv.reset_index()), ""]
        bd = L[L.decision.astype(str).str.startswith(("base term", "base size", "size component", "weight diverged", "removed"))][["model", "candidate", "rob_t", "decision"]]
        out += [f"### {fam}: base terms removed and backward-check removals", "", md(bd) if len(bd) else "none", ""]
    open(f"{HERE}/report_tables.md", "w").write("\n".join(out)); print("\n".join(out)[:3000])


if __name__ == "__main__":
    main()
