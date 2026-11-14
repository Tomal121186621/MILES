#!/usr/bin/env python3
"""Impedance elasticities of the destination models of record (TAZ, 2026-10-29), as destination_choice/export_dc.elasticities:
probability-weighted point elasticity of all distance and time variables (+1 %), full choice set, 3,000 records of the estimation
half, each at its most likely anchor configuration.  -> results/elasticities_taz.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
import torch
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import estimate_dc_taz as Z, dc_model as M, dc_common as C   # noqa: E402
from estimate_complexity import final_spec, multi_flag       # noqa: E402
sk = C.skims(); sk_d = dict(sk); sk_d["d"] = sk["d"] * 1.01; sk_d["draw"] = sk["draw"] * 1.01; sk_d["t"] = sk["t"] * 1.01
rows = []
for kind, f in [("primary", "cx_estimates_taz.csv"), ("stop", "seq_estimates_taz.csv")]:
    E = pd.read_csv(f"{Z.RES}/{f}")
    for p in C.DISC:
        seg = f"{p}_{kind}"; spec, _ = final_spec(seg)
        if kind == "primary": spec = M.Spec("FX", spec.linear + ["lnd_multi"], spec.size_base, spec.size_comps)
        x = E[E.segment == seg].set_index("param").value[spec.params()].values; th = torch.tensor(x)
        rec, cand, _ = Z.load_taz("estimation", seg)
        if kind == "primary": rec["multi"] = multi_flag(rec, "estimation")
        rec = rec.sample(min(len(rec), 3000), random_state=3).reset_index(drop=True); e = 0.0
        for i0 in range(0, len(rec), 500):
            sub = rec.iloc[i0:i0 + 500]; cs = cand[cand.rec.isin(sub.rec)]; a, l, b = M.full_sets(sub, cs)
            V0 = M.utility(th, spec, M.Data(sub, a, l, b, spec, p, sk)).numpy(); Vd = M.utility(th, spec, M.Data(sub, a, l, b, spec, p, sk_d)).numpy()
            P = np.exp(V0 - V0.max(1, keepdims=True)); P /= P.sum(1, keepdims=True); e += float((P * (Vd - V0) / 0.01 * (1 - P)).sum())
        rows.append(dict(segment=seg, elasticity_impedance=e / len(rec))); print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv(f"{Z.RES}/elasticities_taz.csv", index=False)
