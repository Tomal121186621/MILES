#!/usr/bin/env python3
"""Group-level mode model of the joint household tours (2026-11-10, TASHA joint-tour representative; GTAModel V4 JointTourRep):
one observation per observed joint group (tours whose main activity is the same joint episode of a household: tasha_distributions
.episodes, same household, purpose, destination tract and arrival window; household + jgid of the main episode; two or more tours
of the mode-choice estimation data), estimated on the estimation half, validation half once.
  representative  the oldest member with car driver available (licence, 16+, a household car; the allocation-consistent
                  availability of m10_car_availability for the observed tour), else the oldest member (car driver not available)
  choice          car driver when a member drove; otherwise the representative's observed mode
  availability    car driver when a member has it available; the other modes as for the representative
  variables       the representative's tour (level of service, person, household, zones, stops, parking), the joint term is
                  constant (every group is joint) and drops out
  identification  (fixed before estimation, the >= 20 records guard of the other models) an alternative chosen by fewer than 20
                  estimation groups keeps only its constant and the level-of-service terms (no person, household, zone or tour terms);
                  a first run with every term (m11_joint_*_firstrun.csv) separated on bus (3 shopping groups: coefficients up to -69)
  specification   the final specification of the individual model of the segment (m08_sequence.py: shopping MNL time + cost;
                  other NL auto + transit, time + cost, acc / rec), every term the individual model kept; a term that does not vary
                  in the group sample drops out
Segments shopping (JS) and other (JO_REC, JO_OTH; rec flag).  Engine: MarylandTourNestedModeChoice, mc.joint.model = group,
coefficient segments shopping_joint / other_joint of tour_mode_choice.csv.
    ~/.venvs/biogeme/bin/python m11_joint_group.py   ->  m11_joint_fit.csv, m11_joint_coef.csv, m11_joint.log"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import m08_sequence as M8, m10_car_availability as CA   # noqa: E402
G, K7, M = M8.G, M8.K7, M8.T3.M
SEGS = ["shopping", "other"]; ALTS = G.ALTS
SOCIO = ["age", "male", "lic", "hhsize", "autos", "kids", "short", "core_o", "rural_o", "core_d", "rural_d", "joint", "acc", "rec"]


def groups(half, seg):
    t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet").reset_index(drop=True); f = M.features2(t, 0.5); blk = CA.blocked(half)
    f.loc[blk, "av_CD"] = 0; ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(t.choice2.values)])
    g = K7.data(half, seg); idx = np.where(t.segment.eq(seg).values & ok)[0]; assert len(idx) == len(g)
    jg = CA.analyse(half)[0].jg.values
    g = g.assign(hh=t.household_id.values[idx], jg=jg[idx])
    rows = []
    for (hh, j), x in g[g.jg >= 0].groupby(["hh", "jg"]):
        if len(x) < 2: continue
        cd = x[x.av_CD > 0]; rep = (cd if len(cd) else x).sort_values("age", kind="stable").iloc[-1].copy()
        rep["choice"] = "CD" if (x.choice == "CD").any() else rep["choice"]
        rep["av_CD"] = float((x.av_CD > 0).any()); rep["y"] = G.NUM[rep["choice"]]; rep["n_members"] = len(x)
        rows.append(rep)
    return pd.DataFrame(rows).reset_index(drop=True)


def spec_of(seg):
    c = pd.read_csv(f"{HERE}/m08_coef.csv"); c = c[(c.segment == seg) & (c.step == "final")].param.tolist()
    socio = [v for v in SOCIO if any(p.startswith(v + "_") for p in c)]
    drop = [f"{v}_{a}" for v in socio for a in ALTS[1:] if f"{v}_{a}" not in c]
    nests = M8.NESTS["auto and transit nests"] if any(p.startswith("mu_") for p in c) else None
    return dict(los=True, socio=socio, stops="stops_CD" in c, park="park_CD" in c, drop=drop), nests, c


def main():
    os.chdir(f"{HERE}/bio"); fit, coef, log = [], [], []
    for seg in SEGS:
        est, val = groups("estimation", seg), groups("validation", seg)
        alts = [a for a in ALTS if est[f"av_{a}"].sum() > 0 and (est.choice == a).sum() > 0]
        s, nests, ind = spec_of(seg); form = M8.FORM[seg]
        rare = [a for a in ALTS[1:] if (est.choice == a).sum() < 20]
        s["drop"] = sorted(set(s["drop"]) | {f"{v}_{a}" for v in s["socio"] for a in rare})
        # a mode no estimation group chose is not identified and not available in the group model (engine: an alternative of a
        # *_joint segment without a constant is unavailable); validation groups that chose it are left out of the validation LL
        nval0 = len(val); val = val[val.choice.isin(alts)].reset_index(drop=True); dropped = nval0 - len(val)
        for a in ALTS:
            if a not in alts: est[f"av_{a}"] = 0.0; val[f"av_{a}"] = 0.0
        t, x = M8.estimate(seg, est, alts, form, s, nests, f"{seg}_joint")
        x["holdout_LL"] = M8.holdout(seg, val, alts, form, s, nests, t.Value.to_dict()); x.update(segment=f"{seg}_joint", step="final", N=len(est), N_validation=len(val), validation_groups_dropped=dropped, alternatives=";".join(alts))
        fit.append(x)
        for n, y in t.iterrows(): coef.append(dict(segment=f"{seg}_joint", step="final", param=n, coef=y.Value, t=y["Robust t-stat."]))
        sh = est.choice.value_counts(normalize=True).round(3).to_dict()
        log.append(f"{seg}_joint: alternatives with fewer than 20 groups (constant and level of service only): {rare}")
        log.append(f"{seg}_joint: {len(est)} groups (validation {len(val)}, {dropped} left out: mode not chosen in the estimation half), alternatives {alts}, choices {sh}; K {x['K']} LL {x['LL']:.1f} BIC {x['BIC']:.1f} validation LL {x['holdout_LL']:.1f} "
                   f"converged {x['converged']}; terms of the individual model not identified here: {sorted(set(ind) - set(t.index))}")
        print(log[-1], flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/m11_joint_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m11_joint_coef.csv", index=False)
    open(f"{HERE}/m11_joint.log", "w").write("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
