#!/usr/bin/env python3
"""Sequential anchors of the discretionary stop MNLs (stage 3 finalisation, 2026-10-23).

    python3 activity/lib/tasha_estimation/estimate_stops_seq.py   -> results/seq_estimates.csv, seq_heldout.csv, dest_choice_stop_seq.csv

The stop MNLs of destination_choice/ (final specifications F) place a stop by its detour between the two tour anchors, home and
the primary destination.  A tour with several stops then gets independent draws around the same corridor, and the legs between
consecutive stops are too long (estimation half, zone skim: 9.7 km observed between two individual episodes, 12.3 km in the
TASHA runs).  Here the same final specifications are re-estimated with sequential anchors: a = the location the person comes
from (the origin of the trip to the stop: home, the primary destination or the previous stop), b = the next anchor of the tour
(the primary destination for an outbound stop, home for an inbound stop); impedance = the detour d(a, j) + d(j, b) - d(a, b);
the other variables as in F (intra_a / intra_b = the stop in the zone of a / b).  Maximum likelihood on the estimation half,
same engine and sampling (dc_model, R = 40, seed 2026; robust s.e.), warm start at the F estimates.  Held-out test (both halves,
full choice set): the mean distance of the leg to the stop (from a), observed against predicted, for the pooled-anchor model F
applied with anchors (home, primary) and the sequential model applied with (a, b).  ABIT: MarylandTashaGenerator relocates the
stops of a chain in time order with these anchors when the coefficient file carries the sequential models (relocate.stops.sequential).
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, pickle, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import te_common as T            # noqa: E402
import dc_common as C            # noqa: E402
import dc_model as M             # noqa: E402
import estimate_dc as E          # noqa: E402
from survey_population import tract_zone, geoid   # noqa: E402

SEGS = [f"{p}_stop" for p in C.DISC]


def with_seq(rec):
    """origin zone of the trip to the stop (tract point), anchors a = origin, b = primary (outbound) / home (inbound)"""
    t = pd.read_csv(f"{T.RTS}/rts_trips_clean.csv", usecols=["tripid", "o_tract_fips"], low_memory=False).set_index("tripid")
    r = pd.read_csv(f"{T.RTS}/RTS_raw_flat_data.csv", usecols=["tripid", "o_state_county_fips"], low_memory=False).drop_duplicates("tripid").set_index("tripid")
    tz = tract_zone().set_index("geoid").zone; m = C.id2idx()
    g = geoid(rec.tripid.map(r.o_state_county_fips), rec.tripid.map(t.o_tract_fips)); oz = g.map(tz).fillna(-1).astype(int).values
    rec = rec.assign(a_idx=np.where(oz > 0, m[np.clip(oz, 0, None)], -1))
    rec = rec[rec.a_idx >= 0].copy()
    rec["home0"] = rec.home_idx; rec["prim0"] = rec.anchor_b
    rec["anchor_b"] = np.where(rec.position == "in", rec.home0, rec.prim0).astype(int); rec["home_idx"] = rec.a_idx.astype(int)
    return rec.reset_index(drop=True)


def final(seg):
    o = pickle.load(open(f"{C.WORK}/search_{seg}.pkl", "rb")); F = o["models"]["F"]; spec = F["spec"]
    x = dict(zip(F["table"].param, F["table"].value)); b = f"{C.DCD}/results/biogeme_{seg}.csv"
    if os.path.exists(b): bb = pd.read_csv(b); x = dict(zip(bb.Name, bb.Value))
    return spec, x


def leg_pred(rec, cand, spec, xv, pur, sk, a_col):
    out = []
    for sub, P, _ in M.predict_full(rec, cand, spec, xv, pur, sk):
        out.append((P * sk["d"][sub[a_col].values]).sum(1))
    return np.concatenate(out)


def main():
    sk = C.skims(); tabs, ho, coef = [], [], []
    for seg in SEGS:
        pur = seg.split("_")[0]; spec, x0 = final(seg)
        rec, cand = E.load("estimation", seg); rs = with_seq(rec); cs = cand[cand.rec.isin(rs.rec)]
        sets = M.sample_sets(rs, cs, pur, R=E.R_BASE, seed=2026)
        r1 = E.fit(spec, rs, *sets, pur, sk, x0=x0)
        t = r1["table"].assign(segment=seg, N=len(rs), LL=r1["LL"]); tabs.append(t); v = t.set_index("param").value
        coef += [dict(segment=seg.replace("_stop", "_seq_stop"), variable="mu_size", value=float(v["mu_size"])), dict(segment=seg.replace("_stop", "_seq_stop"), variable=f"size_{spec.size_base}", value=1.0)]
        coef += [dict(segment=seg.replace("_stop", "_seq_stop"), variable=f"size_{c}", value=float(np.exp(v[f"theta_{c}"]))) for c in spec.size_comps]
        coef += [dict(segment=seg.replace("_stop", "_seq_stop"), variable=k, value=float(v[k])) for k in spec.linear]
        print(seg, "N", len(rs), "LL", round(r1["LL"], 1), flush=True)
        for half in ["estimation", "validation"]:
            rh, ch = E.load(half, seg); rh = with_seq(rh); ch = ch[ch.rec.isin(rh.rec)]
            ok = rh.dzone_pt.values >= 0; obs = np.average(sk["d"][rh.a_idx.values[ok], rh.dzone_pt.values[ok]], weights=rh.w.values[ok])
            # pooled F with the anchors home, primary (as ABIT applied it)
            r0 = rh.assign(home_idx=rh.home0, anchor_b=rh.prim0)
            pF = leg_pred(r0, ch, spec, np.array([x0[p] for p in spec.params()]), pur, sk, "a_idx")
            pS = leg_pred(rh, ch, spec, r1["x"].numpy(), pur, sk, "a_idx")
            for pos in ["out", "in", "all"]:
                s_ = np.ones(len(rh), bool) if pos == "all" else (rh.position.values == pos)
                o_ = s_ & ok
                ho.append(dict(segment=seg, half=half, position=pos, N=int(s_.sum()), km_leg_obs=float(np.average(sk["d"][rh.a_idx.values[o_], rh.dzone_pt.values[o_]], weights=rh.w.values[o_])),
                               km_leg_pooled_F=float(np.average(pF[s_], weights=rh.w.values[s_])), km_leg_sequential=float(np.average(pS[s_], weights=rh.w.values[s_]))))
    pd.concat(tabs).to_csv(f"{T.RES}/seq_estimates.csv", index=False); pd.DataFrame(ho).to_csv(f"{T.RES}/seq_heldout.csv", index=False)
    pd.DataFrame(coef).to_csv(f"{T.RES}/dest_choice_stop_seq.csv", index=False)
    print(pd.DataFrame(ho).round(2).to_string())


if __name__ == "__main__":
    main()
