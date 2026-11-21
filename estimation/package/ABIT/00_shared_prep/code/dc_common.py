#!/usr/bin/env python3
"""Shared definitions of the estimated destination choice (stage 3, 2026-10-22): zones, zone attributes, skims, the MAST
mode-choice logsum and the variables of the destination utilities.  Used by prep_dc_data.py, estimate_dc.py, validate_dc.py
and pipeline/accessibility.py; every variable here has a one-to-one counterpart in
ABIT/src/main/java/abm/models/maryland/MarylandDestinationChoice.java (method `variable`), so that the utility of the
application is the estimated one.

Zone system: the 1,588 MSTM zones of MAST (ABIT/input/maryland/zone_attributes.csv), indexed 0..1587 in the order of the zone
ids.  Zone attributes are those MAST reads in a 2016 run (MarylandLosDataReader):
  pop   persons of the 2016 base population (3_abit/survey_pop/zone_population_2016.csv; in a synthetic run MAST uses the sampled
        persons x 1/sample.fraction, the same quantity)
  ret, off, oth   jobs of the full SILO job file 2_silo/input/microData/jj_2016.csv by type (RET / OFF / other)
  stu   school occupancy of the stage-2b assignment (2_silo/input/schools_2016.csv, column occupancy) by zone
Skims (minutes, km): car time and distance of the 2016 base (3_abit/skims), door-to-door transit of the 2024 schedule
(pipeline/test/skims/transit_2024: bus_tt, rail_tt00, transit_peak_time; 1000 = not reachable).
All skims are truncated to whole minutes and metres, as MAST's MitoBasedTravelTimes / MitoBasedTravelDistances return them.
Distance convention of the destination utilities: car-distance skim, intrazonal 0.5 sqrt(area) (the stage-3 metric convention,
abit_metrics.dist_matrix).  The mode-choice logsum uses the skims exactly as MAST's mode model reads them (intrazonal distance
= the skim diagonal, 1 km).
"""
# COPY of Validation_2026/3_abit/destination_choice/dc_common.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "00_shared_data"))          # provided inputs
RAW = _os_pkg.environ.get("ABIT_RAW", _os_pkg.path.join(SHARED, "raw"))                                                              # your downloads
REBUILT = _os_pkg.environ.get("ABIT_REBUILT", _os_pkg.path.join(SHARED, "rebuilt"))                  # outputs of this chain
MDATA = REBUILT
import os
import numpy as np
import pandas as pd

ROOT = SHARED  # PATH
V = SHARED; A3 = SHARED; DCD = f"{REBUILT}/work"; WORK = f"{REBUILT}/work"  # PATH
ZONE_ATTR = f"{SHARED}/zones/zone_attributes.csv"  # PATH
ZONES_SHP = f"{RAW}/mstm_zone_system/SMZ_RMZ_02152011inMSTM_EPSG26918.shp"  # PATH
TRACTS = f"{RAW}/tiger_tracts_2010"  # PATH
SKIM_CAR = f"{SHARED}/skims/abit_base_2016"  # PATH
SKIM_TRANSIT = f"{SHARED}/skims/transit_2024_door_to_door"  # PATH
COEF = None  # PATH: previous MAST mode model (coef_calibrated); its logsum is not used by the published models
JOBS = f"{SHARED}/zones/jobs_2016_zone_type.parquet"  # PATH: zone and type columns of jj_2016.csv
SCHOOLS = f"{SHARED}/zones/schools_2016.csv"  # PATH
ZPOP = f"{SHARED}/zones/zone_population_2016.csv"  # PATH
os.makedirs(WORK, exist_ok=True)

DISC = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
KNOTS = [1, 2, 5, 10, 20, 50]                # piecewise-linear distance (km)
DKNOTS = [1, 2, 5, 10, 20]                   # piecewise-linear detour of a stop (km)
INC_CLASS = {1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 1, 7: 2, 8: 2}   # RTS hh_income_detailed -> low (<50k), mid (50-100k), high (100k+)
UNAVAILABLE = 999.0
_cache = {}


# ------------------------------------------------------------------------------------------------ zones
def zones():
    """Zone table in index order with the attributes of the destination utilities."""
    if "z" in _cache: return _cache["z"]
    z = pd.read_csv(ZONE_ATTR).sort_values("id").reset_index(drop=True)
    z["idx"] = np.arange(len(z))
    pop = pd.read_csv(ZPOP).set_index("zone").persons
    z["pop"] = z.id.map(pop).fillna(0).astype(float)
    jj = pd.read_parquet(JOBS)  # PATH: parquet extract (zone, type)
    t = jj.type.astype(str).str.upper()
    jj["k"] = np.where(t.str.startswith("RET"), "ret", np.where(t.str.startswith("OFF"), "off", "oth"))
    c = jj.groupby(["zone", "k"]).size().unstack(fill_value=0)
    for k in ["ret", "off", "oth"]: z[k] = z.id.map(c[k]).fillna(0).astype(float)
    z["jobs"] = z.ret + z.off + z.oth
    sc = pd.read_csv(SCHOOLS, usecols=["zone", "occupancy"]).groupby("zone").occupancy.sum()
    z["stu"] = z.id.map(sc).fillna(0).astype(float)
    z["state"] = z.countyfips // 1000
    z["bc"] = (z.countyfips == 24510).astype(float)               # Baltimore City
    z["dcz"] = (z.countyfips == 11001).astype(float)              # Washington DC
    z["va"] = (z.state == 51).astype(float)                       # Virginia zones
    z["othst"] = z.state.isin([10, 42, 54]).astype(float)         # Delaware, Pennsylvania, West Virginia
    dens = z.jobs / z.area_km2.clip(lower=0.05)
    z["cbd"] = (dens >= 10000).astype(float)                      # central business districts: >= 10,000 jobs per km2
    z["lnretden"] = np.log1p(z.ret / z.area_km2.clip(lower=0.05))  # ln(1 + retail jobs per km2)
    s = z[["pop", "ret", "off", "oth"]].values; sh = s / np.clip(s.sum(1, keepdims=True), 1e-9, None)
    z["mix"] = -(sh * np.log(np.clip(sh, 1e-12, None))).sum(1) / np.log(4)   # land-use mix entropy (0..1)
    z["intra_km"] = 0.5 * np.sqrt(z.area_km2)
    _cache["z"] = z
    return z


def id2idx():
    z = zones(); m = np.full(int(z.id.max()) + 1, -1, dtype=np.int32); m[z.id.values] = z.idx.values; return m


# ------------------------------------------------------------------------------------------------ skims
def _dense(f, scale=1.0, fill=np.nan):
    z = zones(); m = id2idx(); s = pd.read_csv(f, engine="pyarrow")
    a = np.full((len(z), len(z)), fill, dtype=np.float32)
    i, j = m[s.FROM.values], m[s.TO.values]; ok = (i >= 0) & (j >= 0)
    a[i[ok], j[ok]] = s.VALUE.values[ok] * scale
    return a


def skims(car_dir=SKIM_CAR, transit_dir=SKIM_TRANSIT):
    """dict: t (car min), draw (car km as MAST's mode model reads it, diagonal = skim), d (car km, intrazonal 0.5 sqrt(area)),
    bus (bus_tt min), rail (rail_tt00 min), pt (transit_peak_time min); unreachable transit >= 999."""
    key = ("sk", car_dir, transit_dir)
    if key in _cache: return _cache[key]
    z = zones()
    # MAST reads skims through MitoBasedTravelTimes / MitoBasedTravelDistances, which truncate to whole minutes and metres
    t = np.floor(_dense(f"{car_dir}/traveltime_auto.csv.gz"))
    draw = np.floor(_dense(f"{car_dir}/distance_auto.csv.gz")) / 1000.0
    d = draw.copy(); np.fill_diagonal(d, z.intra_km.values.astype(np.float32))
    d = np.where(np.isfinite(d) & (d > 0), d, 300.0).astype(np.float32); d = np.minimum(d, 300.0)
    out = dict(t=t, draw=draw, d=d)
    for k, f in [("bus", "bus_tt"), ("rail", "rail_tt00"), ("pt", "transit_peak_time")]:
        p = f"{transit_dir}/{f}.csv.gz"
        out[k] = np.floor(_dense(p, fill=1000.0)) if os.path.exists(p) else np.full_like(t, 1000.0)
    _cache[key] = out
    return out


# ------------------------------------------------------------------------------------------------ MAST mode-choice logsum
MC_NAME = ["CAR_DRIVER", "WALK", "BIKE", "CAR_PASSENGER", "SHARED_RIDE", "BUS", "TRAIN"]
MC_SKIM = ["t", "t", "t", "t", "t", "bus", "rail"]                    # MarylandFullModeChoice.SKIM (walk/bike read the car skim)
MC_VOT = np.array([30, 0, 0, 30, 40, 15, 15], float)
MC_CPK = np.array([0.12, 0, 0, 0.12, 0.12, 0.50, 0.50])
MC_AUTO = np.array([1, 0, 0, 1, 1, 0, 0], bool)
VOT_REF, VOT_ELAST, VOT_MIN, VOT_MAX = 7018.0, 0.6, 0.4, 2.5
MC_VARS = ["ASC", "age", "male", "license", "hhsize", "hhautos", "coreCity", "medCity", "rural", "gc", "tripLength"]


def mc_coef(purpose, coef_dir=COEF):
    """Coefficients of MarylandFullModeChoice for the purpose (the re-anchored set of the coefficient directory, the file the
    destination choice reads at construction, before the mode model re-anchors again)."""
    f = f"{coef_dir}/modechoice_full_{purpose.lower()}.csv"
    c = pd.read_csv(f).set_index("variable")[MC_NAME]
    return {v: c.loc[v].values.astype(float) for v in MC_VARS}


def mode_logsum(purpose, orig, dest, person, sk, toll=0.0, coef_dir=COEF):
    """ln sum_m exp(V_m) of MAST's mode model (MarylandFullModeChoice.probabilities) for origin indices `orig` (N) and
    destination indices `dest` (N x J).  person: dict of arrays (N): age, male, lic, hhsize, autos, inc_month (household, USD)."""
    c = mc_coef(purpose, coef_dir); z = zones(); bb = z.bbsr.values[orig]
    o = orig[:, None]
    dist = sk["draw"][o, dest].astype(np.float64)
    vf = np.clip((np.maximum(1.0, person["inc_month"]) / VOT_REF) ** VOT_ELAST, VOT_MIN, VOT_MAX)[:, None]
    base = {v: np.asarray(person[k], float)[:, None] for v, k in [("age", "age"), ("male", "male"), ("license", "lic"), ("hhsize", "hhsize"), ("hhautos", "autos")]}
    core = (bb == 10).astype(float)[:, None]; med = (bb == 20).astype(float)[:, None]; rur = (bb == 40).astype(float)[:, None]
    vs = []
    for m in range(7):
        time = sk[MC_SKIM[m]][o, dest].astype(np.float64)
        money = dist * MC_CPK[m] + (toll if MC_AUTO[m] else 0.0)
        votm = MC_VOT[m] * vf
        gc = np.where(votm > 0, time + money * 60.0 / np.where(votm > 0, votm, 1.0), 0.0)
        v = (c["ASC"][m] + c["age"][m] * base["age"] + c["male"][m] * base["male"] + c["license"][m] * base["license"]
             + c["hhsize"][m] * base["hhsize"] + c["hhautos"][m] * base["hhautos"] + c["coreCity"][m] * core + c["medCity"][m] * med
             + c["rural"][m] * rur + c["gc"][m] * gc + c["tripLength"][m] * dist)
        vs.append(v)
    vs = np.stack(vs, 0); mx = vs.max(0)
    return mx + np.log(np.exp(vs - mx).sum(0))


def car_gt(orig, dest, inc_month, sk, toll=0.0):
    """Car generalized time (min) of MAST's car-driver alternative: time + (0.12 $/km x distance + toll) x 60 / VOT_hh, VOT_hh =
    30 $/h x the household's income factor (MarylandFullModeChoice).  orig (N), dest (N x J) indices; inc_month (N)."""
    vf = np.clip((np.maximum(1.0, inc_month) / VOT_REF) ** VOT_ELAST, VOT_MIN, VOT_MAX)[:, None]
    o = orig[:, None] if np.ndim(orig) == 1 else orig
    return sk["t"][o, dest].astype(np.float64) + (sk["draw"][o, dest] * MC_CPK[0] + toll) * 60.0 / (MC_VOT[0] * vf)


def mc_cost_coef(purpose, inc_month, coef_dir=COEF):
    """d V_car / d $ of MAST's car-driver utility (gc coefficient x 60 / VOT) for a household income: the money scale of the
    mode logsum (used for accessibility in money units)."""
    c = mc_coef(purpose, coef_dir)
    vf = np.clip((np.maximum(1.0, inc_month) / VOT_REF) ** VOT_ELAST, VOT_MIN, VOT_MAX)
    return c["gc"][0] * 60.0 / (MC_VOT[0] * vf)


# ------------------------------------------------------------------------------------------------ utility variables
def pw(x, knots):
    """Piecewise-linear basis: segment lengths of x in [0,k1], [k1,k2], ..., [k_last, inf)."""
    edges = [0.0] + list(knots) + [np.inf]
    return [np.clip(x - lo, 0, hi - lo) for lo, hi in zip(edges[:-1], edges[1:])]


def pw_names(prefix, knots):
    edges = [0] + list(knots)
    return [f"{prefix}_{lo}_{hi}" for lo, hi in zip(edges, list(knots) + ["inf"])]
