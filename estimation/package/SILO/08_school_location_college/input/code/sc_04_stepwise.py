#!/usr/bin/env python3
# Copy of 2_silo/schoolchoice/sc_04_stepwise.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Stepwise specification search of the school location choice, by segment (the rule of jobchoice/rts_22_stepwise.py).

Estimation half, sampled choice sets (sc_03_engine.Design 'sampled', seed 20261029); held-out LL per student on the validation half
with the FULL choice set.  Base S0: size term (mu, component weights) + car time t.  Candidate groups in a theory order (STEPS); within
a step all candidates are estimated together, then terms are removed one at a time (weakest first) until every remaining term
  (a) has the expected sign ('+'/'-'; '?' = no prior) and |robust t| >= 1.96,
  (b) is not collinear (robust parameter correlation |r| > 0.8) with a stronger parameter unless itself |t| >= 4;
the step is kept only if it lowers BIC and raises the held-out LL, and its terms are stable across a second draw of alternatives
(seed 20261030; |change| / robust s.e. < 1).  Added after the steps (not in rts_22): a backward check of the
t / ln(1+t) / logsum / same-zone terms, repeated until none offends: a wrong sign is dropped (rule a); a non-significant term is
dropped if BIC improves and the held-out LL loses at most 0.001 per student.  A logsum coefficient above 1 is fixed at 1 (as V2c of
the workplace model; LR test reported) and the backward check is repeated.
Term names: utility 'base*var' (b_...), size component 'size:in' (g_pub_in, the SABS in-boundary weight), size interaction 'comp:var'
(h_compXvar).   Outputs tables/stepwise_<seg>.csv, stepwise_<seg>_decisions.csv, estimates_<seg>_<model>.csv, cov_<seg>_<model>.csv,
work/final_<seg>.json.   Usage: sc_04_stepwise.py [k8 hs col]"""
import os, sys, json, numpy as np, pandas as pd
from scipy.stats import chi2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sc_03_engine as G; import sc_common as C   # noqa: E402
K12 = {"lt": "-", "ls": "+", "intra": "+", "cc": "-", "ccpub": "-", "cs": "-", "size:in": "+", "t*agec": "+", "t*female": "?", "t*g1": "-", "t*g4": "+",
       "t*car0": "-", "t*carlow": "-", "priv:g1": "-", "priv:g3": "+", "priv:g4": "+", "t": "-"}
COL = {"lt": "-", "ls": "+", "intra": "+", "cc": "-", "cs": "-", "t*agec": "?", "t*female": "?", "t*g1": "-", "t*g4": "+", "t*car0": "-", "t*carlow": "-",
       "priv4:g1": "-", "priv4:g4": "+", "cc:a25": "+", "cc:g1": "+", "cc:g4": "-", "t": "-"}
WHY = {"lt": "concave distance decay", "ls": "school-tour mode-choice logsum: accessibility by all modes", "intra": "a school in the home zone (walk, neighbourhood)",
       "cc": "MD counties are school districts: public K-12 rarely crosses a county line", "ccpub": "the county effect applies to the public part of the zone's enrolment",
       "cs": "state line (districts, in-state tuition)", "size:in": "the attendance-zone school (SABS 2015-16): assigned school",
       "t*agec": "older students travel farther (K-12) / no prior (college)", "t*female": "no prior", "t*g1": "low-income households: less car access, closer schools",
       "t*g4": "high-income households travel farther (choice schools)", "t*car0": "no car: closer schools beyond the logsum", "t*carlow": "fewer cars than drivers",
       "priv:g1": "private schools cost tuition: low-income households less", "priv:g3": "income sorting into private schools", "priv:g4": "income sorting into private schools",
       "priv4:g1": "private 4-year tuition", "priv4:g4": "income sorting into private universities", "cc:a25": "older students attend community colleges more",
       "cc:g1": "low-income students attend community colleges more", "cc:g4": "high-income students attend community colleges less", "t": "distance decay"}
STEPS = {"k12": [("S1 ln(1+t)", ["lt"]), ("S2 logsum", ["ls"]), ("S3 same zone", ["intra"]), ("S4 county / state line", ["cc", "ccpub", "cs"]),
                 ("S5 SABS in-boundary", ["size:in"]), ("S6 distance x person", ["t*agec", "t*female", "t*g1", "t*g4", "t*car0", "t*carlow"]),
                 ("S7 private x income", ["priv:g1", "priv:g3", "priv:g4"])],
         "col": [("S1 ln(1+t)", ["lt"]), ("S2 logsum", ["ls"]), ("S3 same zone", ["intra"]), ("S4 county / state line", ["cc", "cs"]),
                 ("S6 distance x person", ["t*agec", "t*female", "t*g1", "t*g4", "t*car0", "t*carlow"]),
                 ("S7 institution type x person", ["priv4:g1", "priv4:g4", "cc:a25", "cc:g1", "cc:g4"])]}


def pname(k):
    if k == "size:in": return "g_pub_in"
    if ":" in k: return "h_" + k.replace(":", "X")
    return "b_" + k.replace("*", "X")


def split(spec):
    return [k for k in spec if ":" not in k], [k for k in spec if ":" in k and k != "size:in"], "size:in" in spec


class Search:
    def __init__(self, seg):
        self.seg = seg; self.EXPECT = COL if seg == "col" else K12; self.steps = STEPS["col" if seg == "col" else "k12"]
        self.D = G.Design(seg); self.D2 = G.Design(seg, seed=20261030); self.F = G.Design(seg, "validation", "full"); self.rows, self.dec = [], []

    def model(self, D, spec, fixed=None):
        t, si, sabs = split(spec); return G.Model(D, t, si, sabs, fixed)

    def converge(self, M, th0):
        from scipy.optimize import minimize
        M.fit(th0); g = float(np.abs(M.f(M.th)[1]).max()); tries = [("L-BFGS-B", M.ll, g)]
        if g > 1:
            for x0 in (M.th, M.x0()):
                r = minimize(M.f, x0, jac=True, method="BFGS", options=dict(maxiter=5000, gtol=1e-5)); gg = float(np.abs(M.f(r.x)[1]).max()); tries.append(("BFGS", -r.fun, gg))
                if gg <= 1 and -r.fun >= M.ll - 1e-6: M.th, M.ll = r.x, -r.fun; break
        M.tries = tries
        if float(np.abs(M.f(M.th)[1]).max()) > 1: raise RuntimeError(f"no converged fit: {tries}")
        return M

    def run(self, name, spec, th0=None, fixed=None):
        M = self.model(self.D, spec, fixed); M = self.converge(M, None if th0 is None else M.at(th0)); M.robust(); assert M.n_bad == 0
        MF = self.model(self.F, spec, fixed); llv, _ = MF.scores(M.th)
        t = M.table(); t.to_csv(f"{C.T}/estimates_{self.seg}_{name}.csv", index=False); pd.DataFrame(M.V, index=M.names, columns=M.names).to_csv(f"{C.T}/cov_{self.seg}_{name}.csv")
        K = len(M.th); N = self.D.N
        r = dict(model=name, K=K, LL=M.ll, AIC=2 * K - 2 * M.ll, BIC=K * np.log(N) - 2 * M.ll, holdout_LL_per_student=float(llv.mean()), max_grad=M.max_grad, spec=" ".join(spec))
        print(self.seg, name, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "spec"}, flush=True)
        return M, r

    def check(self, M, keep):
        tb = M.table().set_index("parameter"); Cm = M.V / np.outer(M.se, M.se); bad = []
        for k in keep:
            n = pname(k); est, tt = tb.estimate[n], tb.robust_t[n]; ex = self.EXPECT[k]
            ok = ex == "?" or (ex == "+" and est > 0) or (ex == "-" and est < 0); i = M.names.index(n)
            strong = [M.names[j] for j in range(len(M.names)) if j != i and abs(Cm[i, j]) > 0.8 and abs(tb.robust_t.iloc[j]) > abs(tt)]
            if not ok: bad.append((abs(tt), k, f"sign {'+' if est > 0 else '-'} against expected {ex} (t {tt:.2f})"))
            elif abs(tt) < 1.96: bad.append((abs(tt), k, f"not significant (t {tt:.2f})"))
            elif strong and abs(tt) < 4: bad.append((abs(tt), k, f"collinear (|r| > 0.8) with stronger {strong[0]} (t {tt:.2f})"))
        return sorted(bad), tb

    def go(self):
        spec = ["t"]; Mb, rb = self.run("S0", spec); rb.update(step="S0 size + time", kept=True); self.rows.append(rb)
        for step, cands in self.steps:
            cur = spec + cands; M, r = self.run(f"{step.split()[0]}_all", cur, Mb.coef_dict()); lr = 2 * (M.ll - Mb.ll)
            r.update(step=f"{step}: all candidates", lr=lr, df=len(cands), p=chi2.sf(lr, len(cands)), kept=False); self.rows.append(r); keep = list(cands)
            while True:
                bad, tb = self.check(M, keep)
                if not bad: break
                _, k, why = bad[0]; keep.remove(k)
                self.dec.append(dict(step=step, term=k, parameter=pname(k), theory=WHY[k], expected_sign=self.EXPECT[k], estimate=tb.estimate[pname(k)], robust_t=tb.robust_t[pname(k)], decision="drop", reason=why))
                if not keep: break
                M, r = self.run(f"{step.split()[0]}_k{len(keep)}", spec + keep, M.coef_dict()); r.update(step=f"{step}: after dropping {k}", kept=False); self.rows.append(r)
            if not keep: self.save(); continue
            bic_ok = r["BIC"] < rb["BIC"]; ho_ok = r["holdout_LL_per_student"] > rb["holdout_LL_per_student"]
            M2 = self.converge(self.model(self.D2, spec + keep), M.th); tb = M.table().set_index("parameter"); c2 = M2.coef_dict()
            d2 = {k: abs(c2[pname(k)] - tb.estimate[pname(k)]) / tb.robust_se[pname(k)] for k in keep}; unstable = [k for k, v in d2.items() if v >= 1]
            ok = bic_ok and ho_ok and not unstable
            for k in keep:
                why = "kept: expected sign, significant, BIC and held-out LL improve, stable across the second draw" if ok else "dropped with its step: " + "; ".join(
                    x for x, o in (("BIC does not improve", bic_ok), ("held-out LL does not improve", ho_ok), (f"unstable across the second draw ({', '.join(unstable)})", not unstable)) if not o)
                self.dec.append(dict(step=step, term=k, parameter=pname(k), theory=WHY[k], expected_sign=self.EXPECT[k], estimate=tb.estimate[pname(k)], robust_t=tb.robust_t[pname(k)],
                                     second_draw_diff_in_se=d2[k], decision="keep" if ok else "drop", reason=why))
            r["kept"] = ok; r["second_draw_max_diff_in_se"] = max(d2.values())
            if ok: spec = spec + keep; Mb, rb = M, r
            self.save()
        # backward check of the impedance terms entered before S4 (repeated until none offends): a wrong sign is dropped (rule a);
        # a non-significant term is dropped if BIC improves and the held-out LL loses at most 0.001 per student
        spec, Mb, rb = self.backward(spec, Mb, rb)
        # logsum coefficient above 1 (inconsistent with a destination choice above the mode choice): fixed at 1, as in V2c of the
        # workplace model; LR test reported, then the backward check again
        fixed = {}
        if "ls" in spec and Mb.coef_dict()["b_ls"] > 1:
            tb = Mb.table().set_index("parameter"); s1 = [x for x in spec if x != "ls"]; fixed = {"ls": 1.0}
            M, r = self.run("LS1", s1, Mb.coef_dict(), fixed); lr = 2 * (Mb.ll - M.ll); r.update(step="logsum coefficient fixed at 1", lr=lr, df=1, p=chi2.sf(lr, 1), kept=True); self.rows.append(r)
            self.dec.append(dict(step="logsum <= 1", term="ls", parameter="b_ls", theory="logsum coefficient in (0, 1]", expected_sign="+", estimate=tb.estimate["b_ls"], robust_t=tb.robust_t["b_ls"],
                                 decision="fix at 1", reason=f"free estimate {tb.estimate['b_ls']:.3f} > 1; fixed at 1 (LR {lr:.2f}, 1 df, p {chi2.sf(lr, 1):.4f}); BIC {r['BIC']:.1f} vs {rb['BIC']:.1f}, held-out LL {r['holdout_LL_per_student']:.4f} vs {rb['holdout_LL_per_student']:.4f}"))
            spec, Mb, rb = s1, M, r; spec, Mb, rb = self.backward(spec, Mb, rb, fixed)
        self.fixed = fixed
        Mb.table().to_csv(f"{C.T}/estimates_{self.seg}_SELECTED.csv", index=False); pd.DataFrame(Mb.V, index=Mb.names, columns=Mb.names).to_csv(f"{C.T}/cov_{self.seg}_SELECTED.csv")
        json.dump(dict(spec=spec, fixed=self.fixed, LL_sampled=Mb.ll, coef=Mb.coef_dict()), open(f"{C.W}/final_{self.seg}.json", "w"), indent=1); self.save()
        print(self.seg, "final", spec, flush=True)

    def backward(self, spec, Mb, rb, fixed=None):
        while True:
            tb = Mb.table().set_index("parameter"); off = []
            for k in [x for x in spec if x in ("t", "lt", "ls", "intra")]:
                est, tt = tb.estimate[pname(k)], tb.robust_t[pname(k)]; ex = self.EXPECT[k]; ok = (ex == "+" and est > 0) or (ex == "-" and est < 0)
                if not ok: off.append((0, abs(tt), k, est, tt, "wrong sign"))
                elif abs(tt) < 1.96: off.append((1, abs(tt), k, est, tt, "not significant"))
            done = True
            for kind, _, k, est, tt, what in sorted(off):
                s2 = [x for x in spec if x != k]; M, r = self.run(f"B_drop_{k}", s2, Mb.coef_dict(), fixed); r.update(step=f"backward: without {k}"); self.rows.append(r)
                acc = kind == 0 or (r["BIC"] < rb["BIC"] and r["holdout_LL_per_student"] >= rb["holdout_LL_per_student"] - 1e-3)
                self.dec.append(dict(step="backward check", term=k, parameter=pname(k), theory=WHY[k], expected_sign=self.EXPECT[k], estimate=est, robust_t=tt, decision="drop" if acc else "keep",
                                     reason=f"{what} in the selected model (t {tt:.2f}); without it BIC {r['BIC']:.1f} vs {rb['BIC']:.1f}, held-out LL {r['holdout_LL_per_student']:.4f} vs {rb['holdout_LL_per_student']:.4f}"))
                if acc: spec, Mb, rb = s2, M, r; done = False; break
            if done: return spec, Mb, rb

    def save(self):
        pd.DataFrame(self.rows).to_csv(f"{C.T}/stepwise_{self.seg}.csv", index=False); pd.DataFrame(self.dec).to_csv(f"{C.T}/stepwise_{self.seg}_decisions.csv", index=False)


if __name__ == "__main__":
    for seg in (sys.argv[1:] or C.SEG): Search(seg).go()
