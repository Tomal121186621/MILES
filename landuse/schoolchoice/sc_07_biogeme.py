#!/usr/bin/env python3
"""Biogeme check of the final FULL-choice-set school-choice likelihood on a subsample (the role of jobchoice/rts_25b).
Subsample: the first SUB estimation-half students of the segment with one possible home zone and one possible school zone (for these
the location mixture is a plain logit).  Biogeme utility per alternative (all zones with enrolment of the segment's bands):
mu ln(sum_c exp(g_c + h' x) N_c) + sum_k b_k x_k (+ the logsum with coefficient 1 where fixed), availability = enrolment of the
student's band; models.loglogit.  Biogeme's simulate at the full-set estimates is compared with the engine's per-student LL.
Run under the watchdog of `sc_07_biogeme.py run` (kills a check whose resident memory exceeds 20 GB).
Output tables/biogeme_check_<seg>.csv.   Usage: sc_07_biogeme.py run [SUB=100]  |  sc_07_biogeme.py one <seg> <SUB>"""
import os, sys, json, time, subprocess, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import sc_common as C   # noqa: E402
LIMIT_KB = 20 * 1024 * 1024
if sys.argv[1] == "run":
    SUB = sys.argv[2] if len(sys.argv) > 2 else "100"
    for seg in C.SEG:
        p = subprocess.Popen([sys.executable, __file__, "one", seg, SUB]); peak = 0; t0 = time.time(); killed = ""
        while p.poll() is None:
            try:
                kids = subprocess.run(["pgrep", "-P", str(p.pid)], capture_output=True, text=True).stdout.split()
                rss = sum(int(x or 0) for x in subprocess.run(["ps", "-o", "rss=", "-p", ",".join([str(p.pid)] + kids)], capture_output=True, text=True).stdout.split())
            except Exception: rss = 0
            peak = max(peak, rss)
            if rss > LIMIT_KB: p.kill(); killed = f"stopped: resident memory {rss / 1e6:.1f} GB > 20 GB"; break
            time.sleep(2)
        f = f"{C.T}/biogeme_check_{seg}.csv"
        if killed: pd.DataFrame([dict(seg=seg, status=killed, seconds=time.time() - t0)]).to_csv(f, index=False)
        else:
            d = pd.read_csv(f); d["peak_rss_GB"] = peak / 1e6; d.to_csv(f, index=False)
        print(seg, killed or "done", f"peak {peak / 1e6:.2f} GB", flush=True)
    sys.exit()
import biogeme.biogeme as bio, biogeme.database as db   # noqa: E402
from biogeme.expressions import Beta, Variable, exp, log   # noqa: E402
from biogeme.models import loglogit   # noqa: E402
import sc_03_engine as G; import sc_04_stepwise as S   # noqa: E402
seg, SUB = sys.argv[2], int(sys.argv[3])
fj = json.load(open(f"{C.W}/final_{seg}.json")); spec, fixed = fj["spec"], fj.get("fixed", {}); e = fj["coef_fullset"]
D = G.Design(seg, "estimation", "full"); srch = S.Search.__new__(S.Search); srch.seg = seg; M = srch.model(D, spec, fixed)
LLn, _ = M.scores(M.at(e))
one = (np.bincount(D.rec, minlength=D.N) == 1) & (D.Sz[:, 1] < 0); recs = np.flatnonzero(one)[:SUB]; rows = np.array([np.flatnonzero(D.rec == r)[0] for r in recs])
J = D.A.shape[1]; cols = {"choice": D.cand[rows, 0].astype(float)}
for k in range(J):
    cols[f"av{k}"] = D.av[rows, k].astype(float)
    for c in range(len(D.comps)): cols[f"n{c}_{k}"] = D.NK[c][rows, k].astype(float)
    for ti, t in enumerate(M.terms): cols[f"x{ti}_{k}"] = M.Xs[ti][rows, k].astype(float)
    if fixed: cols[f"o{k}"] = np.asarray(M.off)[rows, k].astype(float)
for j, x in enumerate(M.size_inter): cols[f"sx{j}"] = M.SX[j][rows]
data = db.Database(f"sc_{seg}", pd.DataFrame(cols))
mu = Beta("mu_size", 1, None, None, 0); B = {t: Beta(f"b_{t.replace('*', 'X')}", 0, None, None, 0) for t in M.terms}
Gc = {c: Beta(f"g_{c}", 0, None, None, 0) for c in M.gfree}; H = {x: Beta(f"h_{x.replace(':', 'X')}", 0, None, None, 0) for x in M.size_inter}
def wgt(c):
    a = Gc[c] if c in Gc else None
    for j, x in enumerate(M.size_inter):
        if x.split(":")[0] == c: a = (a if a is not None else 0) + H[x] * Variable(f"sx{j}")
    return 1.0 if a is None else exp(a)
W_ = [wgt(c) for c in D.comps]
V, av = {}, {}
for k in range(J):
    s = sum(W_[c] * Variable(f"n{c}_{k}") for c in range(len(D.comps)))
    v = mu * log(s + 1e-12)
    for ti, t in enumerate(M.terms): v = v + B[t] * Variable(f"x{ti}_{k}")
    if fixed: v = v + Variable(f"o{k}")
    V[k] = v; av[k] = Variable(f"av{k}")
os.makedirs(f"{C.W}/biogeme", exist_ok=True); os.chdir(f"{C.W}/biogeme")
t0 = time.time(); b = bio.BIOGEME(data, {"ll": loglogit(V, av, Variable("choice"))}); b.model_name = f"sc_{seg}"
ll_b = b.simulate(the_beta_values=e)["ll"].values
out = pd.DataFrame([dict(seg=seg, status="done", students=len(recs), alternatives=J, LL_biogeme=float(ll_b.sum()), LL_engine=float(LLn[recs].sum()),
                         max_abs_diff_per_student=float(np.abs(ll_b - LLn[recs]).max()), seconds=time.time() - t0)])
out.to_csv(f"{C.T}/biogeme_check_{seg}.csv", index=False); print(out.to_string(index=False))
