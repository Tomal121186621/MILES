"""Shared definitions of the 2024 temporal validation of ABIT (3_abit/temporal_2024): paths, geography, the decoding of the
ACS journey-to-work variables, the episode-to-activity rule for the ATUS diaries and the activity measures computed in the
same way for the model, the travel surveys and the time-use diaries.

Activity definition (one activity per trip, at the trip's destination, as in Roorda et al. 2008 and 3_abit/validate_survey.py):
start = arrival time, duration = departure of the next trip minus the arrival (none for the last trip of the day), type =
work, school, shopping, other, return home.  Model types: WORK, EDUCATION -> school, SHOPPING, HOME -> return home; RECREATION,
ACCOMPANY, OTHER and SUBTOUR (work-based sub-tour stops) -> other.
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, re, zipfile, io
import numpy as np
import pandas as pd

ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
A3 = f"{V}/3_abit"; T24 = f"{A3}/temporal_2024"; RAW = f"{V}/data/raw"; DATA = f"{V}/data"
OUT = f"{T24}/data"                      # derived tables of this study
# model under test (2026-10-23): T24_MODEL=final -> the model of record (TASHA-style generation with the estimated components,
# behavioural set 3_abit/coef_tasha, frozen in temporal_2024/frozen_final); run and measure names carry the prefix 'fin_'.
# Unset: the earlier frozen model (coef_calibrated, frozen/).
import os as _os
# T24_MODEL=mc (2026-10-26): the model of record with the estimated tour mode choice (GC form), frozen in frozen_mc, prefix 'mc_'
MODEL = _os.environ.get("T24_MODEL", "frozen"); PFX = {"final": "fin_", "mc": "mc_"}.get(MODEL, "")
RTS = f"{ABIT_HOME}/input/rts"
ZONE_ATTR = f"{ABIT_HOME}/input/maryland/zone_attributes.csv"
ZONES_SHP = f"{ABIT_HOME}/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp"
PUMS1 = f"{RAW}/pums_2024_1yr"; PUMS5_2024 = f"{ROOT}/inputs/pums_2024_5yr"; PUMS5_2019 = f"{ROOT}/inputs/pums_2019_5yr"
CODELIST = f"{RAW}/pums_docs/ACSPUMS2024CodeLists.xls"; DICT24 = f"{RAW}/pums_docs/PUMS_Data_Dictionary_2024.csv"
TYPES = ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME"]
TLAB = {"WORK": "Work", "SCHOOL": "School", "SHOPPING": "Shopping", "OTHER": "Other", "HOME": "Return home", "ALL": "Total"}
MODEL_TYPE = {"WORK": "WORK", "EDUCATION": "SCHOOL", "SHOPPING": "SHOPPING", "HOME": "HOME"}
BALTIMORE = [24003, 24005, 24013, 24025, 24027, 24510]          # Baltimore Metropolitan Council region (six jurisdictions)
BALT_CBSA = BALTIMORE + [24035]                                  # Baltimore-Columbia-Towson CBSA 12580 (adds Queen Anne's)
os.makedirs(OUT, exist_ok=True)


def mtype(p):
    return pd.Series(p).astype(str).map(MODEL_TYPE).fillna("OTHER").values


# ------------------------------------------------------------------------------------------------ geography
def geo_lookup():
    """2020 PUMA -> county (one row per state, county, PUMA) and county -> POWPUMA, from the 2024 PUMS code list."""
    f = f"{OUT}/puma20_county_powpuma.csv"
    if os.path.exists(f): return pd.read_csv(f)
    d = pd.read_excel(CODELIST, "Geography Lookup List", header=None)
    d = d[pd.to_numeric(d[0], errors="coerce").notna() & pd.to_numeric(d[4], errors="coerce").notna()]
    g = pd.DataFrame({"state": d[0].astype(int), "county": d[0].astype(int) * 1000 + d[1].astype(int), "county_name": d[2].astype(str).str.strip(),
                      "puma": d[4].astype(int), "powsp": pd.to_numeric(d[5], errors="coerce"), "powpuma": pd.to_numeric(d[6], errors="coerce")})
    g = g[g.state.isin([10, 11, 24, 42, 51, 54])]; g.to_csv(f, index=False); return g


def county_group():
    """county FIPS -> analysis unit = the place-of-work PUMA (a county or a group of small counties) and its label."""
    g = geo_lookup().drop_duplicates("county")
    lab = g.groupby(["state", "powpuma"]).county_name.apply(lambda s: " + ".join(sorted(set(s.str.replace(" County", "", regex=False)))))
    g["unit"] = g.state * 100000 + g.powpuma
    g["unit_label"] = [lab[(s, p)] for s, p in zip(g.state, g.powpuma)]
    return g.set_index("county")[["unit", "unit_label", "county_name"]]


def zone_county():
    z = pd.read_csv(ZONE_ATTR); return z.set_index("id").countyfips.astype(int)


def zone_puma20():
    """MSTM zone -> 2020 PUMA (Maryland zones; the PUMA polygon containing the zone's representative point)."""
    f = f"{OUT}/zone_puma20.csv"
    if os.path.exists(f): return pd.read_csv(f).set_index("zone").puma
    import geopandas as gpd
    z = gpd.read_file(ZONES_SHP)[["id", "geometry"]]
    z["geometry"] = z.geometry.representative_point()
    p = gpd.read_file(f"{RAW}/tiger_puma/puma20/tl_2022_24_puma20.shp").to_crs(z.crs)
    j = gpd.sjoin(z, p[["PUMACE20", "geometry"]], how="left", predicate="within").drop_duplicates("id")
    zc = zone_county(); j = j[j["id"].map(zc).fillna(0).astype(int) // 1000 == 24]
    out = pd.DataFrame({"zone": j["id"].astype(int), "puma": pd.to_numeric(j.PUMACE20, errors="coerce")})
    miss = out.puma.isna()
    if miss.any():   # nearest PUMA for points on the coast line
        jj = gpd.sjoin_nearest(z[z["id"].isin(out.zone[miss])], p[["PUMACE20", "geometry"]], how="left").drop_duplicates("id")
        out.loc[miss, "puma"] = out.loc[miss, "zone"].map(jj.set_index("id").PUMACE20.astype(int))
    out["puma"] = out.puma.astype(int); out.to_csv(f, index=False); return out.set_index("zone").puma


# ------------------------------------------------------------------------------------------------ ACS journey to work
def jwdp_minutes():
    """JWDP code -> (start minute, end minute) of the departure interval, parsed from the 2024 data dictionary."""
    d = pd.read_csv(DICT24, header=None, names=list(range(7)), dtype=str)
    d = d[(d[0] == "VAL") & (d[1] == "JWDP") & (d[4] != "bbb")]
    def mins(s):
        m = re.match(r"\s*(\d+):(\d+)\s*([ap])\.m\.", s); h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        h = h % 12 + (12 if ap == "p" else 0); return h * 60 + mi
    out = {}
    for code, lab in zip(d[4], d[6]):
        a, b = lab.split(" to "); out[int(code)] = (mins(a), mins(b) + 1)
    return out


JWTRNS_MODE = {1: "Car", 2: "Bus", 3: "Rail", 4: "Rail", 5: "Rail", 6: "Other", 7: "Other", 8: "Car", 9: "Bicycle", 10: "Walk", 11: "Worked at home", 12: "Other"}
MODEL_MODE = {"CAR_DRIVER": "Car, driver", "CAR_PASSENGER": "Car, passenger", "BUS": "Bus", "TRAIN": "Rail", "WALK": "Walk", "BIKE": "Bicycle"}
COMMUTE_MODES = ["Car, driver", "Car, passenger", "Bus", "Rail", "Walk", "Bicycle", "Other"]
TT_BINS = [0, 10, 15, 20, 25, 30, 35, 45, 60, 90, 1e9]
TT_LABELS = ["< 10", "10–14", "15–19", "20–24", "25–29", "30–34", "35–44", "45–59", "60–89", "90+"]


def acs_mode_shares(p, w="PWGTP"):
    """Commute mode shares of ACS commuters (JWTRNS 1-10, 12).  Car: drove alone -> driver; a k-person carpool counts 1/k as
    driver and (k-1)/k as passenger (the ACS does not record who drove); motorcycle -> driver; taxi, ferry, other -> other."""
    j = p.JWTRNS.values; k = p.JWRIP.fillna(1).clip(lower=1).values; wt = p[w].values.astype(float)
    sh = {}
    sh["Car, driver"] = (wt * ((j == 1) / k + (j == 8))).sum(); sh["Car, passenger"] = (wt * (j == 1) * (1 - 1 / k)).sum()
    sh["Bus"] = wt[j == 2].sum(); sh["Rail"] = wt[np.isin(j, [3, 4, 5])].sum(); sh["Walk"] = wt[j == 10].sum(); sh["Bicycle"] = wt[j == 9].sum()
    sh["Other"] = wt[np.isin(j, [6, 7, 12])].sum(); tot = sum(sh.values())
    return pd.Series({m: v / tot for m, v in sh.items()})


def read_pums_persons(zpath, cols, years=None):
    """Person file of a PUMS zip (all columns read as numbers where possible); years filters the 5-year file by SERIALNO year."""
    with zipfile.ZipFile(zpath) as z:
        n = [x for x in z.namelist() if x.endswith(".csv")][0]
        with z.open(n) as f:
            hdr = f.readline().decode().strip().split(",")
        use = [c for c in cols if c in hdr]
        with z.open(n) as f:
            p = pd.read_csv(f, usecols=use, dtype={"SERIALNO": str}, low_memory=False)
    if years is not None: p = p[p.SERIALNO.str[:4].astype(int).isin(years)]
    return p


def wshare(mask, w):
    w = np.asarray(w, float); return float((np.asarray(mask) * w).sum() / w.sum()) if w.sum() > 0 else np.nan


def sdr_se(stat, df, wcol="PWGTP"):
    """ACS successive-difference replicate standard error of stat(df, weight column): sqrt(4/80 * sum (x_r - x)^2)."""
    x0 = stat(df, wcol); xr = np.array([stat(df, f"{wcol}{r}") for r in range(1, 81)])
    return float(np.sqrt(4 / 80 * ((xr - x0) ** 2).sum(axis=0))) if np.ndim(x0) == 0 else np.sqrt(4 / 80 * ((xr - x0) ** 2).sum(axis=0))


# ------------------------------------------------------------------------------------------------ activities from trips
def acts_from_legs(legs):
    """Model legs of the representative weekday (Monday, departure 0..1439 min) -> activities.
    legs: person_id, previous_purpose, start_time_min, next_purpose, end_time, mode, time_min, distance_m, start_zone, end_zone."""
    l = legs[(legs.start_time_min >= 0) & (legs.start_time_min < 1440)].sort_values(["person_id", "start_time_min"], kind="stable")
    a = pd.DataFrame({"pid": l.person_id.values, "type": mtype(l.next_purpose), "purpose": l.next_purpose.astype(str).values,
                      "o_home": (l.previous_purpose.astype(str) == "HOME").values, "dep": l.start_time_min.values.astype(float),
                      "start_min": l.end_time.values.astype(float), "mode": l["mode"].astype(str).values, "tt": l.time_min.values.astype(float),
                      "km": l.distance_m.values / 1000.0, "zone": l.end_zone.values})
    nxt = a.groupby("pid").dep.shift(-1); a["dur"] = nxt - a.start_min
    a["start_min"] = a.start_min % 1440
    return a


def chain_ids(pid, o_home):
    pid = np.asarray(pid); new = np.asarray(o_home) | np.r_[True, pid[1:] != pid[:-1]]; return np.cumsum(new)


def commute_from_acts(a):
    """Per person with a work activity: departure from home before the first work activity, arrival at work, travel time
    (sum of the trip times from the home departure to the work arrival, stops excluded) and the mode of the trip arriving at work."""
    a = a.reset_index(drop=True); a["i"] = np.arange(len(a))
    fw = a[a.type == "WORK"].groupby("pid").i.min()
    a["first_work_i"] = a.pid.map(fw)
    b = a[a.first_work_i.notna() & (a.i <= a.first_work_i)]
    hd = b[b.o_home].groupby("pid").i.max()            # last trip leaving home before (or at) the first work arrival
    w = a.loc[fw.values].set_index("pid")
    out = pd.DataFrame({"pid": fw.index})
    out["leave_i"] = out.pid.map(hd)
    out = out[out.leave_i.notna()]
    out["dep"] = a.dep.values[out.leave_i.astype(int).values] % 1440
    out["arr"] = w.loc[out.pid, "start_min"].values
    ctt = np.r_[0.0, np.cumsum(a.tt.values)]                       # travel time of the trips leave_i..first work (stops excluded)
    li = out.leave_i.astype(int).values; fi = a.first_work_i.groupby(a.pid).first().loc[out.pid].astype(int).values
    out["tt"] = ctt[fi + 1] - ctt[li]; out["n_trips"] = fi + 1 - li
    out["mode"] = w.loc[out.pid, "mode"].values
    return out.drop(columns="leave_i")


def hourly_shares(start_min, w):
    h = (np.asarray(start_min) // 60).astype(int) % 24
    s = pd.Series(np.asarray(w, float)).groupby(h).sum().reindex(range(24), fill_value=0.0); return s / s.sum()


def hourly_mean(start_min, val, w, min_n=0):
    h = (np.asarray(start_min) // 60).astype(int) % 24; v = np.asarray(val, float); w = np.asarray(w, float); m = np.isfinite(v)
    num = pd.Series(v[m] * w[m]).groupby(h[m]).sum(); den = pd.Series(w[m]).groupby(h[m]).sum(); n = pd.Series(h[m]).value_counts()
    return (num / den).reindex(range(24)).where(n.reindex(range(24), fill_value=0) >= min_n)


# ------------------------------------------------------------------------------------------------ KS statistics
def ks_values(a, b):
    """Roorda's KS on two sets of hourly values (as activity/validation/validate_survey.ks_values): D and asymptotic P."""
    from scipy.special import kolmogorov
    a = np.sort(np.asarray(a, float)); b = np.sort(np.asarray(b, float)); n, m = len(a), len(b)
    if n == 0 or m == 0: return np.nan, np.nan, 0
    x = np.concatenate([a, b]); d = np.max(np.abs(np.searchsorted(a, x, "right") / n - np.searchsorted(b, x, "right") / m))
    ne = n * m / (n + m); return float(d), float(kolmogorov((np.sqrt(ne) + 0.12 + 0.11 / np.sqrt(ne)) * d)), n


def ks_weighted(x1, w1, x2, w2):
    """Two-sample KS D between weighted samples and P with Kish effective sizes."""
    from scipy.special import kolmogorov
    x1 = np.asarray(x1, float); x2 = np.asarray(x2, float); w1 = np.asarray(w1, float); w2 = np.asarray(w2, float)
    xs = np.unique(np.concatenate([x1, x2]))
    def cdf(x, w):
        o = np.argsort(x); cw = np.cumsum(w[o]) / w.sum(); return np.r_[0, cw][np.searchsorted(x[o], xs, "right")]
    d = float(np.max(np.abs(cdf(x1, w1) - cdf(x2, w2))))
    n1 = w1.sum() ** 2 / (w1 ** 2).sum(); n2 = w2.sum() ** 2 / (w2 ** 2).sum(); ne = n1 * n2 / (n1 + n2)
    return d, float(kolmogorov((np.sqrt(ne) + 0.12 + 0.11 / np.sqrt(ne)) * d)), n1, n2
