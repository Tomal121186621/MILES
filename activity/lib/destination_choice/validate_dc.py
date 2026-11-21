#!/usr/bin/env python3
"""Validation of the estimated destination choice on the held-out VALIDATION half (stage 3, 2026-10-22).

    python3 activity/lib/destination_choice/validate_dc.py heldout      # full-choice-set predictions for every record of both halves
    python3 activity/lib/destination_choice/validate_dc.py sim          # simulated MAST runs (survey population of the validation half, chain): before / after
    python3 activity/lib/destination_choice/validate_dc.py figures      # figures (paperstyle, strict checks)

heldout: for every segment and both halves, the probabilities of all 1,588 zones under
  mnl      the estimated MNL (Biogeme estimates, results/biogeme_<segment>.csv), exactly as MAST applies it;
  gravity  primary destinations: the calibrated gravity form of MAST (MarylandDestinationChoice, coef_calibrated:
           P_j ~ attraction_j x [(t+1)^b1 e^(b2 t) + w2 (t+1)^p2 e^(b3 t)] x exp(band constant of d_ij));
           stops: the corridor rule of MarylandStopModel (point at U(0.15, 0.85) of the home - primary segment with a lateral
           offset U(-0.15, 0.15) x segment length, nearest zone centroid), probabilities by Monte Carlo (400 draws per record);
  uniform  1 / 1,588.
Measures: predictive log-likelihood sum_n ln sum_z b_zt P_n(z) (measurement model of prep_dc_data.py; probabilities floored
at 1e-12 for the corridor rule, whose support is the corridor only); trip-length distribution (bins of rts_common.DIST_BINS;
primary: distance from home, stops: distance from the preceding anchor, home outbound / primary destination inbound; car-skim
distance, intrazonal 0.5 sqrt(area); observed: the zone of the tract internal point), mean, KS statistic on the binned CDF and
coincidence ratio; destination area shares; intrazonal share; county-to-county flow matrix (home county x destination
county; dissimilarity index = half the sum of absolute share differences).  All observed and predicted summaries are weighted
with the survey trip weight.  Outputs: results/heldout_*.csv.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, f"{MILES_HOME}/activity/lib"); sys.path.insert(0, f"{MILES_HOME}/activity/survey")
import dc_common as C
from rts_common import DIST_BINS, DIST_LABELS

RES = f"{C.DCD}/results"; os.makedirs(RES, exist_ok=True)
SEGMENTS = [f"{p}_{k}" for p in C.DISC for k in ["primary", "stop"]]
AREA = {24510: "Baltimore City", 11001: "Washington DC"}
INNER = {24005, 24003, 24027, 24031, 24033, 51013, 51510, 51919}
AREAS = ["Baltimore City", "Washington DC", "inner suburbs", "outer counties"]


def area_of_county(c):
    c = np.asarray(c).astype(int)
    return np.where(c == 24510, 0, np.where(c == 11001, 1, np.where(np.isin(c, list(INNER)), 2, 3)))


def final_model(segment):
    """(spec, parameter vector in spec.params() order): Biogeme estimates when present, else the torch search estimates."""
    import dc_model as M
    o = pickle.load(open(f"{C.WORK}/search_{segment}.pkl", "rb")); F = o["models"]["F"]; spec = F["spec"]
    x = dict(zip(F["table"].param, F["table"].value)); src = "torch"
    f = f"{RES}/biogeme_{segment}.csv"
    if os.path.exists(f):
        b = pd.read_csv(f); x = dict(zip(b.Name, b.Value)); src = "biogeme"
    return spec, np.array([x[p] for p in spec.params()]), src


# ------------------------------------------------------------------------------------------------ old models
def gravity_matrix(purpose, sk):
    """P[i, j] of the calibrated gravity form for every home zone i (1588 x 1588)."""
    z = C.zones(); cf = C.COEF
    a = pd.read_csv(f"{cf}/dest_attraction.csv").set_index("purpose").loc[purpose]
    attr = 1.0 + a["hh.total"] * z["pop"].values + a["jj.total"] * z.jobs.values + a["jj.retail"] * z.ret.values + a["jj.office"] * z.off.values \
        + a["jj.other"] * z.oth.values + a["students"] * z.stu.values
    fp = pd.read_csv(f"{cf}/dest_friction_power.csv").set_index("purpose").loc[purpose]
    t = sk["t"].astype(np.float64); t = np.where((t >= 0) & (t <= 600), t, 600.0)
    fr = np.power(t + 1.0, fp.b_logtime) * np.exp(fp.b_time * t)
    if fp.w2 != 0: fr += fp.w2 * np.power(t + 1.0, fp.p2) * np.exp(fp.b2 * t)
    bd = pd.read_csv(f"{cf}/dest_distance_bands.csv"); bd = bd[bd.purpose == purpose].sort_values("lo_km")
    if len(bd):
        km = sk["d"].astype(np.float64)
        b = np.searchsorted(bd.lo_km.values, km, side="right") - 1
        fr *= np.exp(bd.constant.values[np.clip(b, 0, len(bd) - 1)])
    w = attr[None, :] * fr
    return w / w.sum(1, keepdims=True)


def corridor_probs(rec, n_draw=400, seed=2026):
    """Monte Carlo zone probabilities of the corridor rule (MarylandStopModel.intermediateLocation) for each stop record."""
    from scipy.spatial import cKDTree
    z = C.zones(); xy = z[["x", "y"]].values; tree = cKDTree(xy); rng = np.random.default_rng(seed)
    a = xy[rec.home_idx.values]; b = xy[rec.anchor_b.values]; d = b - a; seg = np.hypot(d[:, 0], d[:, 1])
    P = np.zeros((len(rec), len(z)), dtype=np.float32)
    f = 0.15 + rng.random((len(rec), n_draw)) * 0.70; lat = (rng.random((len(rec), n_draw)) - 0.5) * 0.30
    nx = np.where(seg > 1, -d[:, 1] / np.maximum(seg, 1e-9), 0); ny = np.where(seg > 1, d[:, 0] / np.maximum(seg, 1e-9), 0)
    px = a[:, 0:1] + f * d[:, 0:1] + nx[:, None] * lat * seg[:, None]; py = a[:, 1:2] + f * d[:, 1:2] + ny[:, None] * lat * seg[:, None]
    _, zi = tree.query(np.stack([px.ravel(), py.ravel()], 1)); zi = zi.reshape(len(rec), n_draw)
    for k in range(len(rec)): P[k] = np.bincount(zi[k], minlength=len(z)) / n_draw
    return P


# ------------------------------------------------------------------------------------------------ summaries
def tld_of(P, dist, w):
    """weighted binned distribution of the trip distance under probabilities P (n x Z) with distances dist (n x Z)."""
    h = np.zeros(len(DIST_LABELS)); b = np.clip(np.searchsorted(DIST_BINS, dist, side="right") - 1, 0, len(DIST_LABELS) - 1)
    for k in range(len(DIST_LABELS)): h[k] = (w[:, None] * P * (b == k)).sum()
    return h, float((w[:, None] * P * dist).sum())


def heldout():
    import dc_model as M
    sk = C.skims(); z = C.zones(); cz = z.countyfips.values; areaz = area_of_county(cz)
    counties = sorted(set(cz)); cidx = {c: i for i, c in enumerate(counties)}; zc = np.array([cidx[c] for c in cz])
    LL, TLD, AR, FL, INTRA = [], [], [], [], []
    for seg in SEGMENTS:
        pur, kind = seg.split("_"); spec, xv, src = final_model(seg); G = gravity_matrix(pur, sk) if kind == "primary" else None
        for half in ["estimation", "validation"]:
            rec = pd.read_parquet(f"{C.WORK}/dc_records_{half}.parquet"); cand = pd.read_parquet(f"{C.WORK}/dc_cand_{half}.parquet")
            rec = rec[(rec.purpose == pur) & (rec.kind == kind)].reset_index(drop=True); cand = cand[cand.rec.isin(rec.rec)]
            acc = {m: dict(ll=0.0, zero=0, tld=np.zeros(len(DIST_LABELS)), km=0.0, area=np.zeros(4), intra=0.0, flow=np.zeros((len(counties), len(counties))))
                   for m in ["mnl", "gravity", "uniform", "observed"]}
            W = 0.0; n = 0
            for sub, P, logb in M.predict_full(rec, cand, spec, xv, pur, sk, chunk=1000):
                w = sub.w.values.astype(float); W += w.sum(); n += len(sub)
                o = sub.home_idx.values
                prev = np.where(sub.position.values == "in", sub.anchor_b.values, o) if kind == "stop" else o
                dist = sk["d"][prev][:, :].astype(np.float64)
                B = np.exp(logb)
                Pg = G[o] if kind == "primary" else corridor_probs(sub)
                Pu = np.full_like(P, 1.0 / P.shape[1])
                ok = sub.dzone_pt.values >= 0
                Po = np.zeros_like(P); Po[np.where(ok)[0], sub.dzone_pt.values[ok]] = 1.0
                for m, PP in [("mnl", P), ("gravity", Pg), ("uniform", Pu), ("observed", Po)]:
                    a = acc[m]
                    if m != "observed":
                        lt = (B * PP).sum(1); a["zero"] += int((lt <= 0).sum()); a["ll"] += float(np.log(np.maximum(lt, 1e-12)).sum())
                    h, km = tld_of(PP, dist, w); a["tld"] += h; a["km"] += km
                    for k in range(4): a["area"][k] += float((w[:, None] * PP * (areaz == k)[None, :]).sum())
                    intra_z = (np.arange(PP.shape[1])[None, :] == (o[:, None] if kind == "primary" else prev[:, None]))
                    a["intra"] += float((w[:, None] * PP * intra_z).sum())
                    hz = zc[o]
                    for hc in np.unique(hz):
                        mrow = hz == hc
                        a["flow"][hc] += np.bincount(zc, weights=(w[mrow, None] * PP[mrow]).sum(0), minlength=len(counties))
            for m, a in acc.items():
                if m != "observed": LL.append(dict(segment=seg, half=half, model=m, N=n, LL=a["ll"], LL_per_obs=a["ll"] / n, zero_prob=a["zero"], source=src))
                tl = a["tld"] / a["tld"].sum()
                for k, lab in enumerate(DIST_LABELS): TLD.append(dict(segment=seg, half=half, model=m, bin=lab, share=tl[k]))
                TLD.append(dict(segment=seg, half=half, model=m, bin="mean_km", share=a["km"] / W))
                for k, lab in enumerate(AREAS): AR.append(dict(segment=seg, half=half, model=m, area=lab, share=a["area"][k] / W))
                INTRA.append(dict(segment=seg, half=half, model=m, intrazonal=a["intra"] / W))
                f = a["flow"] / a["flow"].sum()
                for i, j in zip(*np.nonzero(f > 0)): FL.append(dict(segment=seg, half=half, model=m, home_county=counties[i], dest_county=counties[j], share=f[i, j]))
            print(f"{seg} {half}: N {n}, LL mnl {acc['mnl']['ll']:.1f}, gravity {acc['gravity']['ll']:.1f} ({acc['gravity']['zero']} zero), uniform {acc['uniform']['ll']:.1f}", flush=True)
    pd.DataFrame(LL).to_csv(f"{RES}/heldout_ll.csv", index=False); pd.DataFrame(TLD).to_csv(f"{RES}/heldout_tld.csv", index=False)
    pd.DataFrame(AR).to_csv(f"{RES}/heldout_area.csv", index=False); pd.DataFrame(INTRA).to_csv(f"{RES}/heldout_intrazonal.csv", index=False)
    pd.DataFrame(FL).to_csv(f"{RES}/heldout_flows.csv", index=False)
    summarize()


def ks_cr(p, q):
    p = np.asarray(p, float); q = np.asarray(q, float)
    return float(np.max(np.abs(np.cumsum(p) - np.cumsum(q)))), float(np.minimum(p, q).sum() / np.maximum(p, q).sum())


def summarize():
    T = pd.read_csv(f"{RES}/heldout_tld.csv"); F = pd.read_csv(f"{RES}/heldout_flows.csv"); A = pd.read_csv(f"{RES}/heldout_area.csv")
    I = pd.read_csv(f"{RES}/heldout_intrazonal.csv"); L = pd.read_csv(f"{RES}/heldout_ll.csv")
    rows = []
    for (seg, half), g in T.groupby(["segment", "half"]):
        ob = g[(g.model == "observed") & (g.bin != "mean_km")].set_index("bin").share.reindex(DIST_LABELS)
        for m in ["mnl", "gravity"]:
            pm = g[(g.model == m) & (g.bin != "mean_km")].set_index("bin").share.reindex(DIST_LABELS)
            ks, cr = ks_cr(pm, ob)
            fo = F[(F.segment == seg) & (F.half == half) & (F.model == "observed")].set_index(["home_county", "dest_county"]).share
            fm = F[(F.segment == seg) & (F.half == half) & (F.model == m)].set_index(["home_county", "dest_county"]).share
            idx = fo.index.union(fm.index); di = 0.5 * float(np.abs(fo.reindex(idx, fill_value=0) - fm.reindex(idx, fill_value=0)).sum())
            own_o = float(fo[[i for i in fo.index if i[0] == i[1]]].sum()); own_m = float(fm[[i for i in fm.index if i[0] == i[1]]].sum())
            ar = A[(A.segment == seg) & (A.half == half)]
            ll = L[(L.segment == seg) & (L.half == half)].set_index("model")
            rows.append(dict(segment=seg, half=half, model=m, N=int(ll.loc[m, "N"]), LL=ll.loc[m, "LL"], LL_uniform=ll.loc["uniform", "LL"],
                             rho2_vs_uniform=1 - ll.loc[m, "LL"] / ll.loc["uniform", "LL"], zero_prob=int(ll.loc[m, "zero_prob"]),
                             mean_km_obs=float(g[(g.model == "observed") & (g.bin == "mean_km")].share.iloc[0]), mean_km_model=float(g[(g.model == m) & (g.bin == "mean_km")].share.iloc[0]),
                             KS_binned=ks, CR=cr, intrazonal_obs=float(I[(I.segment == seg) & (I.half == half) & (I.model == "observed")].intrazonal.iloc[0]),
                             intrazonal_model=float(I[(I.segment == seg) & (I.half == half) & (I.model == m)].intrazonal.iloc[0]),
                             **{f"{a}_obs": float(ar[(ar.model == "observed") & (ar.area == a)].share.iloc[0]) for a in AREAS},
                             **{f"{a}_model": float(ar[(ar.model == m) & (ar.area == a)].share.iloc[0]) for a in AREAS},
                             flow_dissimilarity=di, own_county_obs=own_o, own_county_model=own_m))
    S = pd.DataFrame(rows); S.to_csv(f"{RES}/heldout_summary.csv", index=False); print(S.round(3).to_string())
    return S


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "heldout"
    if cmd == "heldout": heldout()
    elif cmd == "summary": summarize()
    elif cmd == "sim":
        import validate_dc_sim; validate_dc_sim.main(sys.argv[2:])
    elif cmd == "figures":
        import figures_dc; figures_dc.main()
