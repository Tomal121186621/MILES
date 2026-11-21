#!/usr/bin/env python3
"""Workplace choice for SILO (2026-11-20): export of the 24-term model (w13_drop_off_g4.py step D) to the engine's coefficient file,
in the naming and form of w11_export_silo.py (centred time interactions folded into b_t).  The row b_off_shXg4 is left out: the engine
(JobDataManagerImpl, job.choice.model = respec) sums whatever b_<base>[X<var>] rows the file has, so a missing row is a zero term.
No engine change.

Check (no SILO run): the utilities of the 300 verification workers of w11_verify (workers.csv, all zones with jobs) are computed
(a) as in the estimation (wdc.feat, centred terms, step D coefficients) and (b) from the exported file the way the engine reads it
(per base variable: sum of coefficient x product of the uncentred person variables, then base x zone value), and compared.
    python3 w13_export_silo.py   ->  2_silo/input/workplace_choice_coefficients.csv, w13_export_check.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import wdc   # noqa: E402
S = f"{WORKSPACE}/2_silo"
OUT = f"{S}/input/workplace_choice_coefficients.csv"
BASE = {"t": "t", "lt": "lt", "intra": "intra", "cc": "cc", "cs": "cs", "dcw": "dc", "z_hiearn": "hiearn", "z_off_sh": "off_sh", "z_ret_sh": "ret_sh", "z_ind_sh": "ind_sh"}
ENGINE_BASE = {v: k for k, v in BASE.items()}
c = pd.read_csv(f"{HERE}/w13_coef.csv"); c = c[c.step == "D"].set_index("param").coef
assert "z_off_sh*g4" not in c.index and len(c) == 24


def engine_coefficients():
    rows = {}; bt = c["t"]
    for p, v in c.items():
        if p == "mu": rows["mu_size"] = v; continue
        parts = p.split("*"); base = BASE[parts[0]]; xs = parts[1:]
        if any(x.endswith("_c") for x in xs):
            assert base == "t" and len(xs) == 1, p
            x = xs[0][:-2]; rows[f"b_tX{x}"] = v; bt -= v * wdc.MEAN[x]
        elif p != "t":
            rows["b_" + base + "".join("X" + x for x in xs)] = v
    rows["b_t"] = bt
    return rows


def main():
    rows = engine_coefficients(); assert len(rows) == 24 and "b_off_shXg4" not in rows, len(rows)
    with open(OUT, "w") as f:
        f.write("parameter,estimate\n")
        for k in ["b_t"] + [k for k in rows if k != "b_t"]: f.write(f"{k},{float(rows[k])!r}\n")
    print(f"{OUT}: {len(rows)} terms; b_t {rows['b_t']:.6f} (estimated {c['t']:.6f}, centring folded in)")
    # ---- check: estimation utilities against the engine reading of the file, 300 verification workers x all zones with jobs
    W = pd.read_csv(f"{HERE}/w11_verify/workers.csv"); idx = W.test_id.values
    P = wdc.persons(True); Q = {k: v[idx] for k, v in P.items()}
    A = np.broadcast_to(wdc.AZ, (len(idx), len(wdc.AZ)))
    lnS = np.log(wdc.JOBS[wdc.AZ].sum(1))[None, :]
    U_est = sum(v * wdc.feat(p, Q["hidx"], A, Q) for p, v in c.items() if p != "mu") + c["mu"] * lnS
    f = pd.read_csv(OUT).set_index("parameter").estimate; eff = {}
    for k, v in f.items():
        if not k.startswith("b_"): continue
        parts = k[2:].split("X"); x = np.full(len(idx), v)
        for q in parts[1:]: x = x * wdc.pvar(q, Q)
        eff[parts[0]] = eff.get(parts[0], 0) + x
    U_eng = f["mu_size"] * lnS + sum(e[:, None] * wdc.base(ENGINE_BASE[b], Q["hidx"], A, Q) for b, e in eff.items())
    d = np.abs(U_eng - U_est)
    pd.DataFrame({"test_id": np.repeat(idx, len(wdc.AZ)), "V_estimation": U_est.ravel(), "V_engine_form": U_eng.ravel()}).to_csv(f"{HERE}/w13_export_check.csv", index=False)
    print(f"check: {d.size} worker x zone utilities; max abs diff {d.max():.3g}")
    assert d.max() < 1e-9


if __name__ == "__main__":
    main()
