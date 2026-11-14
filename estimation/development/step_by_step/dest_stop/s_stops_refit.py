#!/usr/bin/env python3
"""Stop-location models re-estimated with the mode-choice logsum of the tour mode models re-estimated without 'fewer cars than
drivers' (2026-11-09, ../mode_choice m08_sequence.py / m09_school.py, M3 = household size, cars, members under 18): the FINAL
specification of each model (s_<p>_fit/_coef_{TAG}.csv, <name>_{TAG}.log) and the current specification ('record') are
re-estimated on the estimation half with the new 'ls' (s_stops_newls: LS of the re-estimated tour models; no reselection); the
validation-half LL of both.  The rows 'final' and 'record' of <name>_fit.csv / _coef.csv are replaced; the previous final is kept
as step 'final_{TAG}'; the selection rows (steps before the final) are those of the previous run (previous logsum).
    TAZ_THREADS=6 python3 s_stops_refit.py [s_shop s_rec ...]
"""
import os, sys, time, hashlib
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "6")
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import s_stops_newls   # noqa: F401  (patches 'ls')
import s_stops as S
TAG = os.environ.get("REFIT_FROM", "pre1109z")   # the previous run whose final specification is refitted
M, F_, X = S.M, S.F_, S.X


def refit(name):
    t0 = time.time(); B = f"{HERE}/{name}"
    fit0 = pd.read_csv(f"{B}_fit_{TAG}.csv", dtype={"step": str}); c0 = pd.read_csv(f"{B}_coef_{TAG}.csv", dtype={"step": str})
    line = [l for l in open(f"{B}_{TAG}.log").read().splitlines() if l.startswith("final specification")][-1]
    base = line.split("size base ")[1].split(",")[0].strip(); mu1 = "mu fixed at 1" in line
    xf = c0[c0.step == "final"].drop_duplicates("param", keep="last").set_index("param").coef.to_dict()
    xr = c0[c0.step == "record"].drop_duplicates("param", keep="last").set_index("param").coef.to_dict()
    lin = [q for q in xf if not q.startswith("theta_") and q != "mu_size"]; comps = [q[6:] for q in xf if q.startswith("theta_")]
    run = S.Run(name)
    mc = os.path.join(os.path.dirname(HERE), "mode_choice", "m08_coef.csv")
    run.log(f"{name}: REFIT 2026-11-09 with the logsum of the current tour mode models (no 'fewer cars than drivers'; car-driver availability consistent with the TASHA allocation) (m08_coef.csv md5 "
            f"{hashlib.md5(open(mc, 'rb').read()).hexdigest()[:10]}); final specification of the previous run, no reselection")
    spec = M.Spec("final", lin, base, comps, mu_fixed=1.0 if mu1 else None)
    r = run.fit("final", "final model (refit, new logsum)", spec, xf)
    s0 = F_.spec_of(run.seg); rr = run.fit("record", "current specification (refit, new logsum)", M.Spec("record", s0.linear, s0.size_base, s0.size_comps), xr)
    rv, cv, gv = F_.load(run.seg, "validation")
    v = {}
    for k, q in (("final", r), ("record", rr)):
        h = X.heldout(rv, cv, gv, q["spec"], np.array([q["x"][p] for p in q["spec"].params()]), run.pur, run.sk, obs="mix"); v[k] = float(h["LL"].sum())
    old = fit0[fit0.step == "final"].iloc[0]
    rows = fit0[~fit0.step.isin(["final", "record"])].to_dict("records") + [dict(old, step=f"final_{TAG}", label="final model, previous logsum")]
    rows.append(dict(step="final", label="final model", K=r["K"], LL=r["LL"], BIC=r["BIC"], decision="final", validation_LL=v["final"]))
    ro = fit0[fit0.step == "record"]
    rows.append(dict(ro.iloc[0].to_dict() if len(ro) else {}, step="record", label="current specification", K=rr["K"], LL=rr["LL"], BIC=rr["BIC"], validation_LL=v["record"]))
    coefs = c0[~c0.step.isin(["final", "record"])].to_dict("records") + [dict(x, step=f"final_{TAG}") for x in c0[c0.step == "final"].to_dict("records")] + \
            [x for x in run.coefs if x["step"] in ("final", "record")]
    cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL"]
    pd.DataFrame(rows).reindex(columns=cols).to_csv(f"{B}_fit.csv", index=False); pd.DataFrame(coefs).to_csv(f"{B}_coef.csv", index=False)
    run.log(f"final: K {r['K']} LL {r['LL']:.2f} (previous {old.LL:.2f}) validation LL {v['final']:.2f} (previous {old.validation_LL:.2f}); "
            f"ls {r['x'].get('ls', float('nan')):.4f} (previous {xf.get('ls', float('nan')):.4f})")
    run.log(f"current specification: K {rr['K']} LL {rr['LL']:.2f} validation LL {v['record']:.2f}")
    run.log(f"final specification: {lin}, size base {base}, components {comps}" + ("; mu fixed at 1 (bound)" if mu1 else "") + f"; {time.time() - t0:.0f} s")


if __name__ == "__main__":
    for n in sys.argv[1:] or list(S.MODELS): refit(n)
