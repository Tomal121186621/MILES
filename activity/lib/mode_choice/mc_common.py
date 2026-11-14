#!/usr/bin/env python3
"""Shared definitions of the tour mode choice (stage 3, 2026-10-26): periods, level of service, costs, availability and the
utility variables.  Every quantity here has a one-to-one counterpart in
ABIT/src/main/java/abm/models/maryland/MarylandTourNestedModeChoice.java, so that the application uses the estimated utility.

Tour level of service (round trip).  Outbound half: home -> main activity in the period of the START of the main activity;
return half: main activity -> home in the period of its END (ABIT knows both times when it chooses the tour mode).
Periods: AM 06-09, MD 09-15, PM 15-19, NT 19-06 (start / end time modulo 24 h).
  car       minutes: base AM car skim x the MATSim period profile (car_period_skims.py); intrazonal: the skim diagonal
            km: car-distance skim, intrazonal 0.5 sqrt(area) (the stage-3 distance convention)
  transit   walk access (transit_period_skims.py, walk): in-vehicle (incl. transfer walks and waits), first wait, access + egress
            walk, transfers; available when both halves have a path in their period (NT has no path after 23:00)
            drive access (drive): car access minutes, in-vehicle, first wait, egress walk, transfers; available when the
            household has a car and the person a licence, both halves have a drive-access path, and the drive-access path saves at
            least 1 minute over the walk-access path or the walk-access path does not exist
  walk/bike round-trip km on the car-distance skim; walk available up to 2 x 6 km, bike up to 2 x 25 km
Money (2017 dollars):
  auto operating cost 0.179 $/mile = 0.1112 $/km: AAA "Your Driving Costs" 2017 for the average new vehicle at 15,000 mi/yr,
            fuel ~10.0 cents/mi + maintenance and repair $1,186 / 15,000 mi = 7.9 cents/mi (the IRS business rate of 2017, 53.5
            cents/mi, includes depreciation and insurance, which do not vary with the trip).  The car driver pays; the passenger 0.
  parking   the RTS records whether a driver paid for parking (park_pay) but not the amount; the car-driver utility carries the
            share of paid parking at the destination area (estimation half), see PARK_AREA
  fare      per half-tour, fare_rule: MTA $1.80, WMATA Metrorail by distance and period, Metrobus $2.00, MARC by distance
  toll      the toll hook adds a per-half-tour amount (MarylandTourNestedModeChoice.setToll) to the car-driver cost
Income: household income as ABIT sums it (12 x sum of persons' int(annual/12), USD/yr).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/mode_choice"; A3 = os.path.dirname(HERE)
sys.path.insert(0, f"{TERP_HOME}/activity/lib/destination_choice"); sys.path.insert(0, f"{TERP_HOME}/activity/lib")
import dc_common as C   # noqa: E402

WORK = f"{HERE}/work"; RES = f"{HERE}/results"; SK = f"{WORK}/skims"
os.makedirs(RES, exist_ok=True)
PERIODS = ["AM", "MD", "PM", "NT"]
OPC_KM = 0.179 / 1.60934            # $/km
FARE = 1.80
WALK_MAX_KM, BIKE_MAX_KM = 6.0, 25.0
DRIVE_ACCESS_KMH = 25.0             # effective car speed on the beeline of the drive-access legs (transit_period_skims.py)
ALTS = ["CD", "CP", "TW", "TD", "WK", "BK"]   # car driver, car passenger, transit walk access, transit drive access, walk, bike
ALT_NAME = {"CD": "car driver", "CP": "car passenger", "TW": "transit, walk access", "TD": "transit, drive access", "WK": "walk", "BK": "bike"}
SEGMENTS = ["work", "school", "shopping", "other"]
SEG_OF = {"WORK": "work", "EDUCATION": "school", "SHOPPING": "shopping", "OTHER": "other", "RECREATION": "other", "ACCOMPANY": "other"}
_cache = {}


def period(minute):
    h = (np.asarray(minute) % 1440) // 60
    return np.select([(h >= 6) & (h < 9), (h >= 9) & (h < 15), (h >= 15) & (h < 19)], [0, 1, 2], 3)


def marc_fare(km):
    return np.minimum(8.0, 4.0 + km / 15.0)


def los():
    """Dense matrices (zone index order of dc_common.zones): car_t[p], d (km), and per access a in (walk, drive) and period p the
    raptor components: all, acc, egr, wait, ivt, trf, rail (share of departures on rail) with NaN where there is no path."""
    if "los" in _cache: return _cache["los"]
    z = C.zones(); m = C.id2idx(); n = len(z); sk = C.skims()
    out = {"d": sk["d"].astype(np.float32), "car_t": []}
    for p in PERIODS:
        out["car_t"].append(np.floor(C._dense(f"{SK}/car_time_{p}.csv.gz")).astype(np.float32))
    for acc in ["walk", "drive"]:
        for p in PERIODS:
            f = f"{SK}/raptor_{acc}_{p}.csv.gz"; r = pd.read_csv(f, engine="pyarrow"); r = r[r.ALL.notna()]
            i, j = m[r.FROM.values], m[r.TO.values]; M = {}
            for k, col in [("all", "ALL"), ("acc", "ACCESS"), ("egr", "EGRESS"), ("wait", "WAIT"), ("trf", "TRANSFERS"), ("rail", "RAILSHARE")]:
                a = np.full((n, n), np.nan, np.float32); a[i, j] = r[col].values; M[k] = a
            rb = pd.read_csv(f, engine="pyarrow"); rb = rb[rb.BUS.notna()]; a = np.full((n, n), np.nan, np.float32)
            a[m[rb.FROM.values], m[rb.TO.values]] = rb.BUS.values; M["bus"] = a      # bus-only schedule, door to door
            M["ivt"] = np.maximum(0, M["all"] - M["acc"] - M["egr"] - M["wait"])
            out[(acc, p)] = M
    # regional prior (MSTM base skims of 3_abit/skims, AM peak, the transit LOS of zone pairs outside the MTA network the raptor
    # routes, e.g. WMATA in the Washington region): one-way minutes min(bus, rail), NaN without a path; rail = 1 when rail is faster
    bus = C._dense(f"{C.SKIM_CAR}/bus_tt.csv.gz", fill=1000.0); rail = C._dense(f"{C.SKIM_CAR}/rail_tt00.csv.gz", fill=0.0)
    bus = np.where(bus < 999, bus, np.nan); rail = np.where(rail > 0, rail, np.nan)
    out["prior_bus"] = bus.astype(np.float32); out["prior_train"] = rail.astype(np.float32)
    out["prior_t"] = np.fmin(bus, rail).astype(np.float32); out["prior_rail"] = (np.nan_to_num(rail, nan=1e9) < np.nan_to_num(bus, nan=1e9)).astype(np.float32)
    _cache["los"] = out
    return out


WMATA_COUNTIES = [11001, 24031, 24033, 51013, 51510, 51059, 51600, 51610, 51107, 51153, 51683, 51685]


def wmata_zone():
    if "wm" not in _cache: _cache["wm"] = np.isin(C.zones().countyfips.values, WMATA_COUNTIES)
    return _cache["wm"]


def fare_rule(rail, km, o, d, peak):
    """one-way fare (2017 $) of a transit path with rail share `rail` and car-distance km between zone indices o and d:
       MARC: rail path longer than 30 km, min(8, 4 + km / 15) (Penn line Baltimore-Washington $8, BWI-Baltimore $5)
       WMATA (both ends in the Washington region, WMATA_COUNTIES): Metrorail from 25 June 2017 peak $2.25-$6.00, off-peak
            $2.00-$3.85, interpolated linearly between the minimum (up to 3 mi) and the maximum (15 mi and more) on the car-distance
            skim (the composite-mile schedule is not reproduced); Metrobus and the county buses $2.00
       MTA (all other paths): $1.80 single-trip fare (local bus, light rail, Metro subway; from 25 June 2017)"""
    wm = wmata_zone(); both = wm[o] & wm[d]; mi = km / 1.60934; x = np.clip((mi - 3.0) / 12.0, 0.0, 1.0)
    rail_wm = np.where(peak, 2.25 + x * (6.00 - 2.25), 2.00 + x * (3.85 - 2.00))
    return np.where((rail >= 0.5) & (km > 30.0), marc_fare(km), np.where(both, np.where(rail >= 0.5, rail_wm, 2.00), FARE))


def fare(L, acc, p, o, d):
    """fare of one half-tour on the path of (acc, p) between o and d (index arrays), fare_rule"""
    M = L[(acc, p)]; km = L["d"][o, d]
    return fare_rule(M["rail"][o, d], km, o, d, p in ("AM", "PM"))


def tour_los(h, m, pout, pret):
    """Round-trip variables of tours with home zone index h, main zone index m, outbound / return period index arrays."""
    L = los(); h = np.asarray(h); m = np.asarray(m); pout = np.asarray(pout); pret = np.asarray(pret)
    ct = np.stack(L["car_t"]); v = {}
    v["car_min"] = ct[pout, h, m] + ct[pret, m, h]
    v["km"] = L["d"][h, m] + L["d"][m, h]
    for acc, tag in [("walk", "tw"), ("drive", "td")]:
        parts = {k: np.zeros(len(h)) for k in ["ivt", "wait", "acc", "egr", "trf", "fare", "rail"]}; ok = np.ones(len(h), bool)
        # walk access: outbound home -> main, return main -> home.  Drive access: the car leg is at the home end in both halves, so
        # the return half is approximated by the home -> main drive-access path in the return period (no main -> home skim with
        # a drive egress exists)
        halves = [(h, m, pout), (m, h, pret)] if acc == "walk" else [(h, m, pout), (h, m, pret)]
        for a, b, pp in halves:
            for pi in range(4):
                s = pp == pi
                if not s.any(): continue
                M = L[(acc, PERIODS[pi])]; aa, bb = a[s], b[s]
                ok[s] &= np.isfinite(M["all"][aa, bb])
                for k in ["ivt", "wait", "trf", "acc", "egr"]: parts[k][s] += np.nan_to_num(M[k][aa, bb])
                parts["rail"][s] += np.nan_to_num(M["rail"][aa, bb]) / 2
                parts["fare"][s] += fare(L, acc, PERIODS[pi], aa, bb)
        ok &= h != m
        for k, x in parts.items(): v[f"{tag}_{k}"] = np.where(ok, x, 0.0)
        v[f"{tag}_ok"] = ok
    # drive access only when it adds something over walk access
    tw_tot = v["tw_ivt"] + v["tw_wait"] + v["tw_acc"] + v["tw_egr"]; td_tot = v["td_ivt"] + v["td_wait"] + v["td_acc"] + v["td_egr"]
    v["td_ok"] &= ~v["tw_ok"] | (td_tot < tw_tot - 1.0)
    v["td_cost_access"] = v["td_acc"] / 60.0 * DRIVE_ACCESS_KMH * OPC_KM
    # regional prior where neither raptor regime has a path (both halves, h != m): time = round trip of the prior skim; the same
    # value for both access forms; MTA fare rule per half on the prior's rail flag
    pt = L["prior_t"][h, m] + L["prior_t"][m, h]; pok = np.isfinite(pt) & (h != m) & ~v["tw_ok"] & ~(v["td_ok"])
    pr = (L["prior_rail"][h, m] + L["prior_rail"][m, h]) / 2
    pf = fare_rule(L["prior_rail"][h, m], L["d"][h, m], h, m, np.isin(pout, [0, 2])) + fare_rule(L["prior_rail"][m, h], L["d"][m, h], m, h, np.isin(pret, [0, 2]))
    v["prior_ok"] = pok; v["prior_time"] = np.where(pok, pt, 0.0); v["prior_fare"] = np.where(pok, pf, 0.0); v["prior_rail"] = np.where(pok, pr, 0.0)
    return v


# ------------------------------------------------------------------------------------------------ utility variables
INC_REF = 84216.0                    # $/yr: the reference household income of the chain (median household income of the 2016 synthetic population)
INC_FLOOR = 5000.0
PARK_SHARE_FILE = f"{RES}/parking_paid_share.csv"
AVAIL = {"CD": "av_CD", "CP": "av_CP", "TW": "av_TW", "TD": "av_TD", "WK": "av_WK", "BK": "av_BK"}


def park_share():
    s = pd.read_csv(PARK_SHARE_FILE).set_index("park_area").share
    return np.array([s.get(k, 0.0) for k in range(6)])


def features(t):
    """Model variables of the tours t (columns of prep_tours / of the ABIT application).  Returns a DataFrame of numbers."""
    f = pd.DataFrame(index=t.index)
    f["car_min"] = t.car_min; f["km"] = t.km
    f["cost_cd"] = t.km * OPC_KM + t.get("toll", 0.0)
    f["park"] = park_share()[t.park_area.values.astype(int)]
    f["tw_ivt"] = t.tw_ivt; f["tw_wait"] = t.tw_wait; f["tw_walk"] = t.tw_acc + t.tw_egr; f["tw_trf"] = t.tw_trf; f["tw_cost"] = np.where(t.tw_ok, t.tw_fare, 0.0)
    f["td_ivt"] = t.td_ivt; f["td_wait"] = t.td_wait; f["td_drive"] = t.td_acc; f["td_walk"] = t.td_egr; f["td_trf"] = t.td_trf
    f["td_cost"] = np.where(t.td_ok, t.td_fare + t.td_cost_access, 0.0)
    f["pr_time"] = t.prior_time; f["pr_cost"] = t.prior_fare; f["prior"] = t.prior_ok.astype(float)
    f["tw_cost"] = f.tw_cost + f.pr_cost; f["td_cost"] = f.td_cost + f.pr_cost
    f["inc_r"] = np.maximum(t.inc_year.values, INC_FLOOR) / INC_REF
    f["inc_lo"] = (t.inc_year < 50000).astype(float); f["inc_hi"] = (t.inc_year >= 100000).astype(float)
    f["zero_car"] = (t.autos <= 0).astype(float); f["car_def"] = ((t.autos > 0) & (t.autos < t.drivers)).astype(float)
    f["cpd"] = np.minimum(t.autos / np.maximum(t.drivers, 1), 1.5)
    f["child"] = (t.age < 16).astype(float); f["teen"] = ((t.age >= 16) & (t.age < 18)).astype(float); f["senior"] = (t.age >= 65).astype(float)
    f["hhsize"] = t.hhsize.astype(float); f["male"] = t.male.astype(float); f["lic"] = t.lic.astype(float)
    f["lnden_h"] = t.lnden_h; f["lnden_m"] = t.lnden_m; f["cbd_m"] = t.cbd_m.astype(float)
    f["stops"] = t.stops.astype(float)
    f["railp"] = np.where(t.tw_ok, t.tw_rail, np.where(t.td_ok, t.td_rail, t.prior_rail))   # rail share of the transit path (0-1, mean of the halves)
    f["railp_td"] = np.where(t.td_ok, t.td_rail, t.prior_rail)
    f["wash"] = wmata_zone()[t.h.values].astype(float)          # home in the Washington region (WMATA_COUNTIES)
    f["lnkm"] = np.log(np.maximum(t.km.values, 0.5))     # ln(round-trip km): trip-length effect on the preference for a mode
    f["rec"] = t.purpose.eq("RECREATION").astype(float); f["esc"] = t.purpose.eq("ACCOMPANY").astype(float)
    f["joint"] = t.joint.astype(float)
    f["av_CD"] = ((t.lic > 0) & (t.autos > 0) & (t.age >= 16)).astype(int)
    f["av_CP"] = 1
    f["av_TW"] = (t.tw_ok | t.prior_ok).astype(int)
    f["av_TD"] = ((t.td_ok | t.prior_ok) & (t.autos > 0) & (t.lic > 0)).astype(int)
    f["av_WK"] = (t.km <= 2 * WALK_MAX_KM).astype(int)
    f["av_BK"] = (t.km <= 2 * BIKE_MAX_KM).astype(int)
    return f


# ================================================================================================ GC specification (2026-10-26)
# The model of record follows the specification of Chayan & Cirillo (2024) re-estimated as a tour model: per segment an MNL / NL
# over six modes with mode-specific coefficients on the constant, age, male, licence, household size, household autos, area type
# (core / rural, medium the base; at the home end, the main-activity end tested), the generalised cost GC (minutes) and the tour
# length (round-trip km).  Shared ride is folded into car passenger (the RTS codes taxi and ride hailing, not carpool membership).
#   GC_m = T_m + 60 C_m / VOT_h,  VOT_h = s x household income / 2,080 h ($/h), s = 0.5 (USDOT 2016 revised guidance, local personal
#   travel; sensitivity s = 0.35, 0.70), household income floored at $5,000/yr.  T and C of the round trip:
#   CD     car minutes (period skims); C = km x 0.1112 $/km + toll
#   CP     car minutes; C = 0 (the driver pays)
#   BUS    door-to-door minutes on the bus-only schedule (walk access: access, waits, in-vehicle, transfers); fare per half-tour
#   TRAIN  door-to-door minutes of the full-schedule path when it uses rail (rail share >= 0.5), walk access, else drive access
#          (C adds the car operating cost of the access leg); fare per half-tour with the rail fare rule
#   WK, BK no GC (the published form): tour length only
#   prior  a half without a raptor path takes the regional (MSTM) bus / rail skim of the base when it has one (1 % of the tours)
ALTS2 = ["CD", "WK", "BK", "CP", "BUS", "TRAIN"]
ALT2_NAME = {"CD": "car driver", "WK": "walk", "BK": "bike", "CP": "car passenger", "BUS": "bus", "TRAIN": "train"}
VOT_SHARE = 0.5; HOURS_YEAR = 2080.0


def tour_los2(h, m, pout, pret):
    """round-trip time, money and availability of bus and train (GC specification) + car minutes and km"""
    L = los(); h = np.asarray(h); m = np.asarray(m); pout = np.asarray(pout); pret = np.asarray(pret)
    ct = np.stack(L["car_t"]); v = {"car_min": ct[pout, h, m] + ct[pret, m, h], "km": L["d"][h, m] + L["d"][m, h]}
    n = len(h)
    for mode in ["bus", "train"]:
        T = np.zeros(n); Cm = np.zeros(n); ok = h != m; rail_used = np.zeros(n); drive = np.zeros(n); prior = np.zeros(n)
        for a, b, pp in [(h, m, pout), (m, h, pret)]:
            t1 = np.full(n, np.nan); c1 = np.zeros(n)
            for pi in range(4):
                s = pp == pi
                if not s.any(): continue
                W = L[("walk", PERIODS[pi])]; D = L[("drive", PERIODS[pi])]; aa, bb = a[s], b[s]; km = L["d"][aa, bb]; peak = pi in (0, 2)
                if mode == "bus":
                    t = W["bus"][aa, bb]; c = fare_rule(np.zeros(len(aa)), km, aa, bb, peak)
                    pr = L["prior_bus"][aa, bb]; use_p = ~np.isfinite(t) & np.isfinite(pr)
                    t = np.where(use_p, pr, t); prior[s] += use_p / 2
                else:
                    tw = np.where(W["rail"][aa, bb] >= 0.5, W["all"][aa, bb], np.nan)
                    # drive access at the home end: outbound h -> m, return approximated by h -> m in the return period
                    hh_, mm_ = (aa, bb) if a is h else (bb, aa)
                    td = np.where(D["rail"][hh_, mm_] >= 0.5, D["all"][hh_, mm_], np.nan)
                    use_d = ~np.isfinite(tw) & np.isfinite(td)
                    t = np.where(use_d, td, tw); c = fare_rule(np.ones(len(aa)), km, aa, bb, peak) + np.where(use_d, np.nan_to_num(D["acc"][hh_, mm_]) / 60.0 * DRIVE_ACCESS_KMH * OPC_KM, 0.0)
                    drive[s] += use_d / 2
                    pr = L["prior_train"][aa, bb]; use_p = ~np.isfinite(t) & np.isfinite(pr)
                    t = np.where(use_p, pr, t); prior[s] += use_p / 2
                t1[s] = t; c1[s] = c
            ok &= np.isfinite(t1); T += np.nan_to_num(t1); Cm += c1
        v[f"{mode}_ok"] = ok; v[f"{mode}_t"] = np.where(ok, T, 0.0); v[f"{mode}_c"] = np.where(ok, Cm, 0.0)
        v[f"{mode}_drive"] = np.where(ok, drive, 0.0); v[f"{mode}_prior"] = np.where(ok, prior, 0.0)
    return v


def features2(t, vot_share=VOT_SHARE):
    """variables of the GC specification for the tours t"""
    f = pd.DataFrame(index=t.index)
    inc = np.maximum(t.inc_year.values, INC_FLOOR); vot = vot_share * inc / HOURS_YEAR; f["vot"] = vot
    toll = t["toll"].values if "toll" in t else 0.0
    f["gc_CD"] = t.car_min + 60.0 * (t.km * OPC_KM + toll) / vot
    f["gc_CP"] = t.car_min.astype(float)
    f["gc_BUS"] = np.where(t.bus_ok, t.bus_t + 60.0 * t.bus_c / vot, 0.0)
    f["gc_TRAIN"] = np.where(t.train_ok, t.train_t + 60.0 * t.train_c / vot, 0.0)
    f["km"] = t.km.astype(float)
    f["age"] = t.age.astype(float); f["male"] = t.male.astype(float); f["lic"] = t.lic.astype(float)
    f["hhsize"] = t.hhsize.astype(float); f["autos"] = t.autos.astype(float)
    bb = C.zones().bbsr.values
    f["core_o"] = (bb[t.h.values] == 10).astype(float); f["rural_o"] = (bb[t.h.values] == 40).astype(float)
    f["core_d"] = (bb[t.m.values] == 10).astype(float); f["rural_d"] = (bb[t.m.values] == 40).astype(float)
    f["av_CD"] = ((t.lic > 0) & (t.autos > 0) & (t.age >= 16)).astype(int)
    f["av_CP"] = 1
    f["av_BUS"] = t.bus_ok.astype(int); f["av_TRAIN"] = t.train_ok.astype(int)
    f["av_WK"] = (t.km <= 2 * WALK_MAX_KM).astype(int); f["av_BK"] = (t.km <= 2 * BIKE_MAX_KM).astype(int)
    return f
