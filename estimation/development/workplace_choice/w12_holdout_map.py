#!/usr/bin/env python3
"""Hold-out validation of the final workplace choice model (w13_drop_off_g4.py step D, 24 terms; coefficients w13_coef.csv, the same
as 2_silo/input/workplace_choice_coefficients.csv), as maps.  No re-estimation.  (2026-11-20: was step C0 of w10_race_fix.py, 25 terms.)

Workers: the hold-out half of the survey workers (full choice set: all zones with jobs, as wdc.Model.holdout_ll).  The hold-out
log-likelihood at the step-D coefficients is asserted against w13_fit.csv (-46,905.49).  For every zone with jobs:
  observed share = hold-out workers whose workplace is in the zone / N;   model share = sum of predicted probabilities / N.
Zones -> PUMAs by the zone -> PUMA shares of the residential crosswalk (../holdout_maps.zone_to_puma); counties by zoneSystem.
Writes w12_holdout_map.pdf / .png, w12_holdout_puma.csv, w12_holdout_county.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE); sys.path.insert(0, f"{os.path.dirname(CODE)}/residential_location")   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import w08_candidates as W8   # noqa: E402  (sets the own-race share and transit-time bases; its main() is not run)
import wdc, w07_simplify as W7   # noqa: E402
import holdout_maps as HM        # noqa: E402

# ---- the set-up of w10_race_fix.py (corrected race coding, car1 variable), without its estimation
r = pd.read_csv(f"{ABIT_HOME}/input/rts/RTS_raw_flat_data.csv", usecols=["person_id", "race_ethnicity", "race_ethnicity_hispanic", "home_state_county_fips"],
                low_memory=False).drop_duplicates("person_id")
nh = r[r.race_ethnicity_hispanic != 1]
cc = nh.groupby("home_state_county_fips").race_ethnicity.agg(c4=lambda x: (x == 4).sum(), c1=lambda x: (x == 1).sum())
tpb = r.home_state_county_fips.isin(set(cc.index[cc.c4 > cc.c1])).values
code, hf = r.race_ethnicity.values, r.race_ethnicity_hispanic.values
hisp = (hf == 1) | (tpb & (code == 1)); white = ~hisp & ((~tpb & (code == 1)) | (tpb & (code == 4))); black = ~hisp & (code == 2)
race = pd.Series(np.select([white, black, hisp], [0, 1, 2], 3), index=r.person_id.values)
wdc.D["p_race"] = W8.P.person_id.map(race).fillna(3).astype(int).values
_pv = wdc.pvar
def pvar(name, P):
    if name == "car1": return (P["car_seg"] == 1).astype(float)
    return _pv(name, P)
wdc.pvar = pvar


def holdout_probs(m, chunk=250):
    """full-set probabilities of the hold-out workers summed by zone (AZ order), observed counts, log-likelihood"""
    P = wdc.persons(est=False); N = len(P["g"]); K = len(m.terms); b, mu = m.th[:K], m.th[K]; g = m.th[K + 1:K + 4]
    psum = np.zeros(len(wdc.AZ)); obs = np.zeros(len(wdc.AZ)); ll = 0.0
    for s in range(0, N, chunk):
        rr = np.arange(s, min(s + chunk, N)); Q = {k: v[rr] for k, v in P.items()}
        A = np.broadcast_to(wdc.AZ, (len(rr), len(wdc.AZ)))
        U = sum(bk * wdc.feat(k, Q["hidx"], A, Q) for bk, k in zip(b, m.terms))
        lw = np.zeros((len(rr), 4)); lw[:, 1:] = g
        S = np.einsum("mc,nc->nm", wdc.JOBS[wdc.AZ], np.exp(lw)); U = U + mu * np.log(np.maximum(S, 1e-300))
        U = U - U.max(1, keepdims=True); E = np.exp(U); Pr = E / E.sum(1, keepdims=True)
        ch = np.searchsorted(wdc.AZ, Q["widx"]); ll += np.log(Pr[np.arange(len(rr)), ch]).sum()
        psum += Pr.sum(0); np.add.at(obs, ch, 1.0)
    return psum, obs, ll, N


def main():
    f13 = pd.read_csv(f"{HERE}/w13_fit.csv").set_index("step"); terms = f13.loc["D"].terms.split()
    c = pd.read_csv(f"{HERE}/w13_coef.csv"); c = c[c.step == "D"].set_index("param").coef
    m = W7.Equal(terms); m.th = np.array([c[n] if n in c.index else 0.0 for n in m.names])
    assert all(n in c.index for n in m.names if not n.startswith("g_")), "coefficient missing"
    psum, obs, ll, N = holdout_probs(m)
    ref = f13.loc["D"].validation_LL
    print(f"hold-out LL {ll:.4f} (w13_fit {ref:.4f}), N {N}"); assert abs(ll - ref) < 1e-4
    zid = pd.read_csv(f"{HM.V}/2_silo/input/zoneSystem.csv").sort_values("ZoneId").ZoneId.values[wdc.AZ]
    Pt, Ct = HM.aggregate(pd.Series(100 * obs / N, index=zid), pd.Series(100 * psum / N, index=zid))
    Pt.to_csv(f"{HERE}/w12_holdout_puma.csv", index=False); Ct.to_csv(f"{HERE}/w12_holdout_county.csv", index=False)
    sp, sc = HM.stats(Pt), HM.stats(Ct)
    print(f"PUMA: r {sp['r']:.3f} MAD {sp['mad']:.3f} pp max |d| {Pt.diff_pp.abs().max():.2f}; county ({sc['n']}): r {sc['r']:.3f} MAD {sc['mad']:.3f} pp; LL per worker {ll / N:.4f}")
    for T, k in ((Pt, "puma7"), (Ct, "county")):
        print(T.reindex(T.diff_pp.abs().sort_values(ascending=False).index).head(6).round(2).to_string(index=False))
    # upper row: the Baltimore-Washington region, where the survey workers live and work; lower row: Baltimore City and County
    ext = HM.bounds(HM.BW); zb = HM.bounds([24510, 24005], 2000)
    bins = HM.nice_bins(max(Pt.observed_pct.max(), Pt.model_pct.max()))
    rows = [dict(table=Pt, level="puma", who="workers", label="Baltimore\u2013Washington", extent=ext, box=zb, bins=bins),
            dict(table=Pt, level="puma", who="workers", label="Baltimore City and County", extent=zb, bins=bins,
                 stat_b=f"Correlation {sp['r']:.2f}", stat_c=f"Mean absolute difference {sp['mad']:.2f} pp\nLog-likelihood per worker {ll / N:.3f}")]
    HM.draw(rows, f"{HERE}/w12_holdout_map", f"Areas: Public Use Microdata Areas of the workplace; lines: counties; {N:,} hold-out survey workers.\n"
            "The hold-out half was also used in the specification search.", height=4.6)


if __name__ == "__main__":
    main()
