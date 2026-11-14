#!/usr/bin/env python3
"""Collinearity of the final workplace model (workplace/w04_sequence.py 'final', wdc.py; WDC_LOGSUM=workplace/logsum_new.npy as in
the final run), estimation half, chosen + 99 sampled zones (wdc.Model draws, seed 20261106), unweighted as in the estimation.
The size term ln S at the final size weights is shown with the variables (its coefficient is mu).
    python3 c_silo_workplace.py   ->  workplace_var_corr.png, workplace_est_corr.png, workplace_pairs.csv, workplace_facts.json"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); WP = os.path.join(os.path.dirname(HERE), "workplace")
os.environ.setdefault("WDC_LOGSUM", f"{WP}/logsum_new.npy")
sys.path.insert(0, WP); sys.path.insert(0, HERE)
import c_silo_common as CC   # noqa: E402
import wdc   # noqa: E402

TEX = ["mu", "g_OFF", "g_IND", "g_OTH", "t", "lt", "t*female_c", "t*young_c", "t*old_c", "t*g1_c", "t*g3_c", "t*g4_c", "t*lic_c", "t*hhs_c",
       "t*kids_c", "t*w2_c", "t*rurh_c", "intra", "cc", "cs", "dcw", "accw", "reg_bc", "reg_mopg", "reg_nvc", "reg_nvo", "reg_mdo", "reg_oth", "z_off_sh*g1",
       "z_off_sh*g4", "z_ret_sh*young", "z_ind_sh*female", "z_hiearn", "z_hiearn*g1", "z_hiearn*g3", "z_hiearn*g4"]   # row order of est_jobchoice_new.tex
# 2026-11-09 re-run: person variables of the time interactions centred at their estimation-half mean ('_c'), DC area dummy removed
SIZE = ["mu", "g_OFF", "g_IND", "g_OTH"]


def main():
    fr = pd.read_csv(f"{WP}/w04_fit.csv"); fin = fr[fr.step == "final"].iloc[0]; terms = fin.terms.split(); assert not bool(fin.seg)
    co = pd.read_csv(f"{WP}/w04_coef.csv"); co = co[co.step == "final"].set_index("param").coef
    LAB = dict(zip(TEX, CC.tex_labels(f"{os.path.dirname(HERE)}/tables_new/est_jobchoice_new.tex"))); LAB["lnS"] = "ln size S (job-type weighted, final weights)"
    assert sorted(TEX) == sorted(terms + SIZE)
    M0 = wdc.Model(terms)

    def run(drop=(), replace=None):
        if drop:
            m = wdc.Model([t for t in terms if t not in drop])
        else:
            m = M0
            if replace:
                m = wdc.Model(terms); m.X = M0.X.copy()
                for k, v in replace.items(): m.X[:, :, terms.index(k)] = v
        m.fit(np.array([co.get(n, 0.0) for n in m.names])); m.robust()
        return dict(LL=m.LL, K=m.K, N=m.N, names=list(m.names), b=m.th, se=m.se, cov=m.cov, conv=m.conv)

    base = run(); print("LL", base["LL"], "reported", fin.LL, "grad", base["conv"], flush=True); assert abs(base["LL"] - fin.LL) < 0.1
    # size term at the final weights
    th = base["b"]; K = len(terms); lw = np.zeros(4); lw[1:] = th[K + 1:K + 4]; lnS = np.log(np.maximum((np.exp(lw)[None, None, :] * M0.Nj).sum(2), 1e-300))
    X = M0.X; av = np.ones(X.shape[:2], bool); ix = terms.index
    inter = {}
    for t in terms:
        if "*" in t:
            mn = t.split("*")[0]
            if mn in terms:
                q = t.split("*")[1].removesuffix("_c"); band = "income" if q in ("g1", "g3", "g4") else "age" if q in ("young", "old") else None
                inter[t] = (mn, CC.zratio(X, ix(t), ix(mn), av), band)
    for k, (m, z, _) in inter.items():
        assert np.allclose(X[:, :, ix(k)], X[:, :, ix(m)] * z[:, None], atol=1e-6), k
    sets = [({"t", "lt"}, "functional form of one variable (time and ln(1 + time))"),
            ({n for n in terms if n.startswith("reg_")}, "members of one band set (area of the workplace)")]
    # re-order the estimates as in the table (variables: model order)
    p = [base["names"].index(n) for n in TEX]
    base_t = dict(base, names=TEX, b=base["b"][p], se=base["se"][p], cov=base["cov"][np.ix_(p, p)])
    CC.run_alt_model("workplace", "Workplace choice, final model", X, terms, av, np.ones(M0.N), LAB, inter, sets, base_t,
                     lambda drop, replace: run(drop, replace), protect=SIZE, extra_vars=[("lnS", lnS[:, :, None])])


if __name__ == "__main__":
    main()
