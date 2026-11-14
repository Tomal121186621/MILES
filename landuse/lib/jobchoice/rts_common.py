#!/usr/bin/env python3
"""Shared definitions of the RTS workplace-choice model (rts_03_estimate.py, rts_04_validate.py, rts_05_export.py).

Zones: the 1,588 model zones in the order of their ids (index 0..1587); alternatives = the 1,587 zones with jobs in the 2016 base.
Variables of the utility of workplace zone j for a worker living in zone h (one function, `feat`, serves the Biogeme database on
the sampled alternatives and the full-choice-set application, so the two use the same utility):
  t      car peak time h -> j (min), input/skims/auto_peak_time.csv.gz (the engine skim)
  lt     ln(1 + t)
  ls     work-tour mode-choice logsum of the worker's segment (car availability x income group), rts_02_logsum.py
  intra  j = h (same zone)
  cs     j in another state than h;  cc  j in another county (zone counties, input/job_choice_zones.csv);  dc  j in DC, h not in DC
  reg_X  workplace region X (REGIONS below; base: the Baltimore suburbs)
Person variables (products 'key*var'): female, young (age < 30), old (age >= 55), kids (children under 18 in the household),
  w2 (2+ workers), car0 (no car), car1 (fewer cars than workers), g1 (<40k), g3 (75-125k), g4 (>125k; 40-75k is the base),
  hva (home in Virginia), hdc (home in DC).  g1/g3/g4 and ls depend on the income group, which the likelihood mixes over.
Size term: mu * ln(RET_j + e^g_OFF OFF_j + e^g_IND IND_j + e^g_OTH OTH_j), 2016 base jobs by type (all jobs, filled and vacant)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import numpy as np, pandas as pd
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; S = f"{V}/2_silo"
JC = f"{S}/jobchoice"; W = f"{JC}/work_rts"; T = f"{JC}/tables_rts"; SEC = ["RET", "OFF", "IND", "OTH"]
# workplace regions of the regional constants (county FIPS of the zone system; 51919 = Fairfax County + Fairfax City + Falls Church,
# 51942 = Prince William + Manassas + Manassas Park in the zone system)
REGIONS = {"bc": [24510], "mopg": [24031, 24033], "dc": [11001], "nvc": [51013, 51510], "nvo": [51919, 51107, 51942, 51059, 51600, 51610, 51153, 51683, 51685]}
REGION_BASE = "bmc"   # Anne Arundel, Baltimore County, Carroll, Harford, Howard
BMC = [24003, 24005, 24013, 24025, 24027]
_c = {}


def zones():
    if "z" in _c: return _c["z"]
    zs = pd.read_csv(f"{S}/input/zoneSystem.csv").sort_values("ZoneId").reset_index(drop=True)
    J = pd.read_parquet(f"{JC}/work/zones.parquet").set_index("zone").reindex(zs.ZoneId.values)
    z = pd.DataFrame({"zone": zs.ZoneId.values, "state": zs.STFIPS.values, "county": zs.COUNTYFIPS.values})
    for s in SEC: z[s] = J[s].fillna(0).values.astype(float)
    z["jobs"] = z[SEC].sum(axis=1)
    reg = np.full(len(z), "other", dtype=object); reg[np.isin(z.county, BMC)] = "bmc"
    for k, v in REGIONS.items(): reg[np.isin(z.county, v)] = k
    reg[(z.state == 24) & (reg == "other")] = "mdo"
    z["region"] = reg; _c["z"] = z; return z


def tt():
    if "tt" in _c: return _c["tt"]
    z = zones(); zi = pd.Series(np.arange(len(z)), index=z.zone)
    sk = pd.read_csv(f"{S}/input/skims/auto_peak_time.csv.gz"); M = np.full((len(z), len(z)), np.nan, np.float32)
    M[zi[sk.FROM].values, zi[sk.TO].values] = sk.VALUE.values; assert np.isfinite(M).all(); _c["tt"] = M; return M


def ls():
    if "ls" not in _c: _c["ls"] = np.load(f"{W}/logsum.npy", mmap_mode="r")
    return _c["ls"]


def zidx():
    z = zones(); return pd.Series(np.arange(len(z)), index=z.zone)


SLOT_DEP = ("ls", "g1", "g3", "g4")


def slot_dependent(key):
    return any(p in SLOT_DEP for p in key.split("*"))


def pvar(name, P, rec, g):
    """person variable for records rec (index into the person table P); g = income group (1..4) of the slot"""
    if name == "female": return P.female.values[rec].astype(float)
    if name == "young": return (P.age.values[rec] < 30).astype(float)
    if name == "old": return (P.age.values[rec] >= 55).astype(float)
    if name == "kids": return (P.children.values[rec] > 0).astype(float)
    if name == "w2": return (P.workers.values[rec] >= 2).astype(float)
    if name == "car0": return (P.car_seg.values[rec] == 0).astype(float)
    if name == "car1": return (P.car_seg.values[rec] == 1).astype(float)
    if name in ("g1", "g3", "g4"): return (g == int(name[1])).astype(float)
    if name == "hva": return (P.state_h.values[rec] == 51).astype(float)
    if name == "hdc": return (P.state_h.values[rec] == 11).astype(float)
    if name == "wt": return (P.wtperfin.values / P.wtperfin.values.mean())[rec]   # DuMouchel-Duncan test only (rts_06_tests.py)
    raise KeyError(name)


def base_feat(key, h, A, P, rec, g):
    z = zones(); st = z.state.values; ct = z.county.values; hh = h[:, None]
    if key == "t": return tt()[hh, A].astype(float)
    if key == "lt": return np.log1p(tt()[hh, A].astype(float))
    if key == "ls": return ls()[P.car_seg.values[rec][:, None], (g - 1)[:, None], hh, A].astype(float)
    if key == "intra": return (A == hh).astype(float)
    if key == "cs": return (st[A] != st[hh]).astype(float)
    if key == "cc": return (ct[A] != ct[hh]).astype(float)
    if key == "dc": return ((st[A] == 11) & (st[hh] != 11)).astype(float)
    if key.startswith("reg_"): return (np.asarray(z.region, dtype=object)[A] == key[4:]).astype(float)
    raise KeyError(key)


def feat(key, h, A, P, rec, g):
    parts = key.split("*"); x = base_feat(parts[0], h, A, P, rec, g)
    for q in parts[1:]: x = x * pvar(q, P, rec, g)[:, None]
    return x


def size(A, e, mu=None):
    """mu * ln sum_k e^g_k N_jk for the zone index matrix A, coefficients e (dict-like)"""
    z = zones(); s = z.RET.values + np.exp(e.get("g_OFF", 0)) * z.OFF.values + np.exp(e.get("g_IND", 0)) * z.IND.values + np.exp(e.get("g_OTH", 0)) * z.OTH.values
    m = e.get("mu_size", 1.0) if mu is None else mu
    return m * np.log(np.maximum(s, 1e-300))[A]


def slots(P):
    """two income-group slots per record: (ga, pa, gb, pb), pb = 0 for a record with one group"""
    pg = P[["pg1", "pg2", "pg3", "pg4"]].values; o = np.argsort(-pg, axis=1, kind="stable")
    ga = o[:, 0] + 1; gb = o[:, 1] + 1; pa = pg[np.arange(len(P)), o[:, 0]]; pb = pg[np.arange(len(P)), o[:, 1]]
    assert np.allclose(pa + pb, 1.0), "a record has more than two income groups"
    gb = np.where(pb > 0, gb, ga); return ga, pa, gb, pb


def utility(terms, e, h, A, P, rec, g):
    U = size(A, e)
    for k in terms: U = U + e.get(k, 0.0) * feat(k, h, A, P, rec, g)
    return U


def full_probs(terms, e, P, rec, alts, chunk=400):
    """generator of (records, probability matrix over `alts`) on the full choice set, mixed over the income slots"""
    ga, pa, gb, pb = slots(P)
    for s in range(0, len(rec), chunk):
        r = rec[s:s + chunk]; h = P.hidx.values[r]; A = np.broadcast_to(alts, (len(r), len(alts)))
        Pm = 0
        for g, pw in ((ga[r], pa[r]), (gb[r], pb[r])):
            U = utility(terms, e, h, A, P, r, g); U -= U.max(axis=1, keepdims=True); E = np.exp(U); Pm = Pm + pw[:, None] * E / E.sum(axis=1, keepdims=True)
        yield r, Pm


def persons(half=None, known_income=True):
    P = pd.read_parquet(f"{W}/workers.parquet")
    if half: P = P[P.half == half]
    if known_income: P = P[P.inc_known == 1]
    zi = zidx(); P = P.reset_index(drop=True); P["hidx"] = zi[P.hz].values; P["widx"] = zi[P.wz].values
    return P
