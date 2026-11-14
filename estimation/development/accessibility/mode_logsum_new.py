#!/usr/bin/env python3
"""Mode-choice logsum of the RE-ESTIMATED tour mode-choice models (respec 2026-11).

    mode_logsum_new(purpose, orig, dest, person, sk_or_features)  ->  ln sum_m exp(V_m)   (NL: sum over nests)

Models (final rows of ../mode_choice/m08_coef.csv, school: ../mode_choice/m09_coef.csv):
  work      MNL, generalised cost GC on CD, CP, BUS, TRAIN (VOT = 0.5 x income / 2,080 h), km on every non-reference mode,
            person / household terms, main-activity zone core / rural, parking share and stops on CD
  shopping  MNL, time + cost on CD, CP, BUS, TRAIN, km on WK, BK; person / household terms, joint; parking, stops on CD
  other     NL (Biogeme lognested, mu >= 1): nests auto {CD, CP}, transit {BUS, TRAIN}, WK and BK their own nests; time + cost;
            joint, acc, rec; parking, stops on CD.  recreation -> other with rec = 1, accompany -> other with acc = 1
  school    MNL, round-trip km on every non-reference mode, no time; bus and train share the person / household terms (_PT)
Variables exactly as in estimation (3_abit/mode_choice/mc_common.tour_los2 / features2, m03 / m06 / m07, estimate_hh.prep):
round-trip car minutes of the period skims (outbound period = arrival at the main activity, return period = its end), km on the
car-distance skim, bus / train door-to-door minutes and fares (fare_rule; train with drive access where walk access has no rail
path), availability (CD: licence, car, age >= 16; bus / train: a path in both halves; walk <= 12 km, bike <= 50 km round trip),
paid-parking share of the destination area (results/parking_paid_share.csv, prep_tours.park_area).
person: dict of scalars or arrays (N): age, male, lic, hhsize, autos, drivers, children (or kids), inc_year (USD / yr, household),
joint, stops (0-1, means allowed), pout, pret (period index 0 AM, 1 MD, 2 PM, 3 NT; default MD, MD).
orig: (N,) zone indices (dc_common.zones order); dest: (N,) or (N, J).  sk_or_features: None / the mc_common LOS (computed from
the period skims), or a DataFrame of features (columns of features() below) to evaluate directly (then orig / dest are unused).
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd

HERE = f"{ESTIMATION_RESULTS}/accessibility_new"                         # results (data)
SBS = ESTIMATION_RESULTS; MCD = f"{SBS}/mode_choice"                      # tour mode-choice results (data)
MCD_CODE = f"{ORIOLE_HOME}/estimation/development/tour_mode_choice"       # tour mode-choice scripts (code)
V26 = f"{WORKSPACE}"
sys.path.insert(0, f"{ORIOLE_HOME}/activity/lib/mode_choice")
import mc_common as M     # noqa: E402
C = M.C

ALTS = ["CD", "WK", "BK", "CP", "BUS", "TRAIN"]
MOT = ["CD", "CP", "BUS", "TRAIN"]
SOCIO = ["age", "male", "lic", "hhsize", "autos", "kids", "short", "joint", "acc", "rec", "core_o", "rural_o", "core_d", "rural_d"]
MODEL_OF = {"work": "work", "shopping": "shopping", "other": "other", "recreation": "other", "accompany": "other", "school": "school",
            "WORK": "work", "SHOPPING": "shopping", "OTHER": "other", "RECREATION": "other", "ACCOMPANY": "other", "EDUCATION": "school"}
FORM = {"work": "GC", "shopping": "TC", "other": "TC", "school": "KM"}
NESTS = {"other": {"auto": ["CD", "CP"], "transit": ["BUS", "TRAIN"]}}
_coef = {}


def coef(model):
    """final coefficients {param: value} of a re-estimated mode model"""
    if model not in _coef:
        f, seg = (f"{MCD}/m09_coef.csv", "school") if model == "school" else (f"{MCD}/m08_coef.csv", model)
        c = pd.read_csv(f); c = c[(c.segment == seg) & (c.step == "final")]
        assert len(c) > 0, f"no final coefficients for {model}"
        _coef[model] = dict(zip(c.param, c.coef.astype(float)))
    return _coef[model]


def park_area(m):
    """3_abit/mode_choice/prep_tours.park_area (destination area class of the paid-parking share)"""
    z = C.zones(); cbd, bc, dc = z.cbd.values[m], z.bc.values[m], z.dcz.values[m]
    return np.select([(bc == 1) & (cbd == 1), bc == 1, (dc == 1) & (cbd == 1), dc == 1, cbd == 1], [0, 1, 2, 3, 4], 5)


def los(h, m, pout, pret):
    """round-trip level of service (mc_common.tour_los2) for flat arrays of home / main zone indices and periods"""
    h = np.asarray(h, np.int64).ravel(); m = np.asarray(m, np.int64).ravel()
    pout = np.broadcast_to(np.asarray(pout, np.int64), h.shape); pret = np.broadcast_to(np.asarray(pret, np.int64), h.shape)
    v = M.tour_los2(h, m, pout, pret); v["h"] = h; v["m"] = m
    return v


def _b(x, n):
    return np.broadcast_to(np.asarray(x, float), (n,)) if np.ndim(x) == 0 else np.asarray(x, float).ravel()


def features(v, person, purpose):
    """model variables (features2 + m03/m06/m07/estimate_hh.prep) from a LOS dict v (flat arrays of length n) and person
    attributes broadcastable to n"""
    n = len(v["h"]); P = {k: _b(x, n) for k, x in person.items() if k not in ("pout", "pret")}
    f = {}
    inc = np.maximum(P["inc_year"], M.INC_FLOOR); vot = M.VOT_SHARE * inc / M.HOURS_YEAR
    car, km = np.asarray(v["car_min"], float), np.asarray(v["km"], float)
    f["km"] = km
    f["gc_CD"] = car + 60.0 * (km * M.OPC_KM) / vot; f["gc_CP"] = car
    f["t_CD"] = car; f["c_CD"] = km * M.OPC_KM; f["t_CP"] = car; f["c_CP"] = np.zeros(n)
    for a, md in [("BUS", "bus"), ("TRAIN", "train")]:
        ok = np.asarray(v[f"{md}_ok"], bool)
        f[f"gc_{a}"] = np.where(ok, v[f"{md}_t"] + 60.0 * v[f"{md}_c"] / vot, 0.0)
        f[f"t_{a}"] = np.where(ok, v[f"{md}_t"], 0.0); f[f"c_{a}"] = np.where(ok, v[f"{md}_c"], 0.0)
        f[f"av_{a}"] = ok.astype(float)
    for k in ["age", "male", "lic", "hhsize", "autos"]: f[k] = P[k]
    kids = P["kids"] if "kids" in P else (P["children"] > 0).astype(float)
    f["kids"] = kids
    f["short"] = P["short"] if "short" in P else ((P["autos"] > 0) & (P["autos"] < P["drivers"])).astype(float)
    f["joint"] = P.get("joint", np.zeros(n)); f["stops"] = P.get("stops", np.zeros(n))
    pu = str(purpose).upper()
    f["acc"] = P["acc"] if "acc" in P else np.full(n, float(pu == "ACCOMPANY"))
    f["rec"] = P["rec"] if "rec" in P else np.full(n, float(pu == "RECREATION"))
    bb = C.zones().bbsr.values
    f["core_o"] = (bb[v["h"]] == 10).astype(float); f["rural_o"] = (bb[v["h"]] == 40).astype(float)
    f["core_d"] = (bb[v["m"]] == 10).astype(float); f["rural_d"] = (bb[v["m"]] == 40).astype(float)
    f["park"] = M.park_share()[park_area(v["m"])]
    f["av_CD"] = ((P["lic"] > 0) & (P["autos"] > 0) & (P["age"] >= 16)).astype(float)
    f["av_CP"] = np.ones(n)
    f["av_WK"] = (km <= 2 * M.WALK_MAX_KM).astype(float); f["av_BK"] = (km <= 2 * M.BIKE_MAX_KM).astype(float)
    return f


def utilities(model, f):
    """dict alt -> V (n,), dict alt -> availability (n,) of the re-estimated model"""
    b = coef(model); form = FORM[model]; n = len(f["km"]); V, AV = {}, {}
    for a in ALTS:
        v = np.zeros(n) if a == "CD" else np.full(n, b.get(f"ASC_{a}", 0.0))
        if a != "CD":
            tag = "PT" if a in ("BUS", "TRAIN") and any(k.endswith("_PT") for k in b) else a
            for s in SOCIO:
                k = f"{s}_{tag}"
                if k in b: v = v + b[k] * f[s]
            if f"km_{a}" in b: v = v + b[f"km_{a}"] * f["km"]
        if a in MOT:
            if form == "GC" and "gc" in b: v = v + b["gc"] * f[f"gc_{a}"]
            if form in ("TC", "KM"):
                if "time" in b: v = v + b["time"] * f[f"t_{a}"]
                if "cost" in b: v = v + b["cost"] * f[f"c_{a}"]
        if a in ("BUS", "TRAIN") and "ovt" in b: v = v + b["ovt"] * f[f"ovt_{a}"]
        if a == "CD":
            if "park_CD" in b: v = v + b["park_CD"] * f["park"]
            if "stops_CD" in b: v = v + b["stops_CD"] * f["stops"]
        V[a] = v; AV[a] = np.asarray(f[f"av_{a}"], float) > 0
    return V, AV


def nest_terms(model, V, AV):
    """list of (mu, [alts]) of the model (singletons: mu = 1)"""
    b = coef(model); ne = NESTS.get(model, {}); used = set(); out = []
    for k, mem in ne.items(): out.append((b[f"mu_{k}"], mem)); used |= set(mem)
    out += [(1.0, [a]) for a in ALTS if a not in used]
    return out


def logsum_and_logp(model, V, AV):
    """logsum (n,) and log P of every alternative (dict) in Biogeme's lognested form (MNL when the model has no nests)"""
    with np.errstate(invalid="ignore", divide="ignore"): return _lsp(model, V, AV)


def _lsp(model, V, AV):
    nl = []; lp = {}; G = {}
    for mu, mem in nest_terms(model, V, AV):
        X = np.stack([np.where(AV[a], mu * V[a], -np.inf) for a in mem])
        mx = np.max(X, 0); fin = np.isfinite(mx); mx0 = np.where(fin, mx, 0.0)
        lse = np.where(fin, mx0 + np.log(np.exp(X - mx0).sum(0)), -np.inf)       # ln sum_{i in m} exp(mu V_i)
        g = lse / mu; nl.append(g)
        for a, x in zip(mem, X): lp[a] = x - lse                                 # ln P(i | m)
        for a in mem: G[a] = g
    S = np.stack(nl); mx = S.max(0); top = mx + np.log(np.exp(S - mx).sum(0))
    for a in lp: lp[a] = lp[a] + G[a] - top
    return top, lp


def mode_logsum_new(purpose, orig, dest, person, sk_or_features=None):
    """ln sum_m exp(V_m) (NL: ln sum_nests exp((1/mu) ln sum_{i in nest} exp(mu V_i))) of the re-estimated model of `purpose`.
    Returns an array of the broadcast shape of (orig[:, None], dest) when dest is 2-D, else (N,)."""
    model = MODEL_OF[purpose]
    if isinstance(sk_or_features, (pd.DataFrame, dict)) and "av_CD" in sk_or_features:
        f = {k: np.asarray(sk_or_features[k]) for k in sk_or_features}; shape = (len(f["km"]),)
    else:
        orig = np.asarray(orig); dest = np.asarray(dest)
        if dest.ndim == 2: o = np.broadcast_to(orig[:, None], dest.shape); shape = dest.shape
        else: o = orig; shape = dest.shape
        pout = person.get("pout", 1); pret = person.get("pret", 1)
        J = shape[1] if len(shape) == 2 else 1
        rep = lambda x: (np.repeat(np.asarray(x), J) if (np.ndim(x) == 1 and len(shape) == 2) else x)
        v = los(o, dest, rep(pout), rep(pret))
        f = features(v, {k: rep(x) for k, x in person.items()}, purpose)
    V, AV = utilities(model, f); ls, _ = logsum_and_logp(model, V, AV)
    return ls.reshape(shape)
