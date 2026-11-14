"""convergence of the other-tour TC model (m04) and the cost of fixing the school time coefficient at the other-tour value"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
import m03_time_cost as T3, m04_refine as R4
G = T3.G
import biogeme.database as db, biogeme.biogeme as bio
os.chdir(f"{HERE}/bio"); num = lambda x: x.select_dtypes(include=[np.number, bool]).astype(float)
seg = "other"; df = T3.data("estimation", seg); alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
st = R4.RUNS[0][3]
m = bio.BIOGEME(db.Database("o", num(df)), R4.loglike(df, alts, T3.EXTRA[seg], "TC", **st), save_iterations=False, generate_html=False, generate_yaml=False)
m.model_name = "m04b"; r = m.estimate()
print("messages", r.optimization_messages); print("gradient norm", r.gradient_norm, "LL", r.final_loglikelihood)
t = G.table(r); print(t[["Value", "Robust t-stat."]].round(4).to_string())
