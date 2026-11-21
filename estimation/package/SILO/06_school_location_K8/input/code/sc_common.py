#!/usr/bin/env python3
# Copy of 2_silo/schoolchoice/sc_common.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Shared definitions of the RTS school location choice (sc_*.py), the conventions of the workplace model (2_silo/jobchoice/rts_*.py).

Zones: the 1,588 model zones in id order (2_silo/input/zoneSystem.csv); car peak time input/skims/auto_peak_time.csv.gz (the engine skim).
Segments (SEG): k8 (RTS school_type 2, K-8), hs (3, 9-12), col (6/7/8, 2-year, 4-year, graduate pooled).
Bands of the school inventory (input/schools_2016.csv, 2_silo/schools/build_schools.py): elementary (K-5), middle (6-8), high (9-12),
postsec; a K-8 student goes to the elementary band at ages <= 10 and to the middle band at 11+ (SchoolDataMd.bandForAge: 5-10, 11-13).
Size components by zone and band (work/zone_size.parquet, sc_01_data.py):
  K-12: pub (CCD), priv (PSS) enrolment of the band;
  college: pub4 (IPEDS SECTOR 1, public 4-year), priv4 (SECTOR 2-3, private 4-year), cc (SECTOR 4-9: 2-year and less-than-2-year)."""
import os, numpy as np, pandas as pd
ROOT = os.environ.get("MILES_PROJECT_ROOT", ""); V = f"{ROOT}/Validation_2026"; S = f"{V}/2_silo"; RAW = f"{V}/data/raw"
SC = f"{S}/schoolchoice"; JC = f"{S}/jobchoice"
SHD = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../00_shared_data"))   # PATH (package)
W = f"{SHD}/school_choice_work"; T = W; FIG = W   # PATH (package): data of sc_00 / sc_01 (copied); tables / figures of the original scripts not used
for d in (W, T, FIG): os.makedirs(d, exist_ok=True)
CRS = 26918
SEG = ["k8", "hs", "col"]
SEG_LABEL = {"k8": "elementary/middle (K-8)", "hs": "high school (9-12)", "col": "college/university"}
COMP = {"k8": ["pub", "priv"], "hs": ["pub", "priv"], "col": ["pub4", "priv4", "cc"]}   # first component = reference (weight 1)
_c = {}


def zones():
    if "z" in _c: return _c["z"]
    zs = pd.read_csv(f"{SHD}/zone_system/zoneSystem.csv").sort_values("ZoneId").reset_index(drop=True)
    z = pd.DataFrame({"zone": zs.ZoneId.values, "state": zs.STFIPS.values, "county": zs.COUNTYFIPS.values}); _c["z"] = z; return z


def zidx():
    z = zones(); return pd.Series(np.arange(len(z)), index=z.zone)


def tt():
    if "tt" in _c: return _c["tt"]
    z = zones(); zi = zidx(); sk = pd.read_csv(f"{SHD}/skims/auto_peak_time.csv.gz"); M = np.full((len(z), len(z)), np.nan, np.float32)
    M[zi[sk.FROM].values, zi[sk.TO].values] = sk.VALUE.values; assert np.isfinite(M).all(); _c["tt"] = M; return M


def km():
    """zone-to-zone road distance (km) of the mode-choice LOS (3_abit/mode_choice/mc_common.los()['d'])"""
    if "km" in _c: return _c["km"]
    import sys; sys.path.insert(0, f"{V}/3_abit/mode_choice"); import mc_common as M   # noqa: E402
    d = np.asarray(M.los()["d"], np.float32); _c["km"] = d; return d


def size():
    """dict band -> component -> enrolment by zone index (1,588)"""
    if "size" in _c: return _c["size"]
    q = pd.read_parquet(f"{W}/zone_size.parquet"); zi = zidx(); out = {}
    for (b, c), g in q.groupby(["band", "comp"]):
        a = np.zeros(len(zi)); a[zi[g.zone].values] = g.n.values; out.setdefault(b, {})[c] = a
    _c["size"] = out; return out


def band_of(seg, age):
    if seg == "k8": return np.where(np.asarray(age) <= 10, "elementary", "middle")
    return np.full(len(age), "high" if seg == "hs" else "postsec", dtype=object)
