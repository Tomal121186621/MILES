#!/usr/bin/env python3
"""Observed travel-survey activities in the activity format of t24common (one activity per trip, at its destination):

    python3 -I activity/lib/reporting_2024/obs_surveys.py   -> temporal_2024/data/rts_persons.parquet, rts_acts.parquet, nhts_persons.parquet, nhts_acts.parquet

RTS 2017/18 (the base survey, travel days Oct 2017 - Jul 2019, all weekdays): the households of the model input of both halves
(3_abit/survey_pop/<half>/persons_map.csv: travellers and the imputed non-travelling members, weight w), their trips in
rts_trips_clean.csv (dep_min, arr_min, distance in driving miles, travel_mode -> 3_abit/rts_common.MODE_MAP; activity codes ->
rts_common.ACT_PURPOSE).  Usual work at home: j1_workplace_loc 3 among workers with an answer (travellers only).
NHTS 2017 (independent check of the same period): weekday travel days (TRAVDAY 2-6) of households in the Baltimore-Columbia-
Towson CBSA (HH_CBSA 12580), persons 5+ (the NHTS diary age), weight WTPERFIN (trips WTTRDFIN); trip purpose WHYTO: 1, 2 home;
3 work; 8 school; 11 buy goods (shopping); 7 change of mode is not an activity (the trip is joined to the next one); else other.
Distance TRPMILES (network distance of the reported trip ends).
"""
import sys, os, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")
import numpy as np, pandas as pd
import t24common as C
from rts_common import ACT_PURPOSE, MODE_MAP, MI_KM

TYPE_OF = {"WORK": "WORK", "EDUCATION": "SCHOOL", "SHOPPING": "SHOPPING", "HOME": "HOME"}


def rts():
    pm = pd.concat([pd.read_csv(f"{C.A3}/survey_pop/{h}/persons_map.csv").assign(half=h) for h in ["estimation", "validation"]], ignore_index=True)
    t = pd.read_csv(f"{C.RTS}/rts_trips_clean.csv", usecols=["household_id", "person_id", "tripno", "o_activity", "d_activity", "dep_min", "arr_min", "distance", "travel_mode", "wttrdfin"], low_memory=False)
    t = t[t.person_id.isin(pm.person_id)].sort_values(["person_id", "tripno"])
    a = pd.DataFrame({"pid": t.person_id.values, "type": t.d_activity.map(ACT_PURPOSE).fillna("OTHER").map(TYPE_OF).fillna("OTHER").values,
                      "o_home": t.o_activity.eq(1).values, "dep": t.dep_min.values.astype(float), "start_min": t.arr_min.values % 1440,
                      "mode": t.travel_mode.map(MODE_MAP).map(C.MODEL_MODE).fillna("Other").values, "tt": (t.arr_min - t.dep_min).values.astype(float),
                      "km": np.where(t.distance >= 0, np.minimum(t.distance * MI_KM, 300), np.nan), "w": t.wttrdfin.values})
    a["dur"] = a.groupby("pid").dep.shift(-1) - t.arr_min.values
    r = pd.read_csv(f"{C.RTS}/RTS_raw_flat_data.csv", usecols=["person_id", "j1_workplace_loc", "employment_status"], low_memory=False).drop_duplicates("person_id").set_index("person_id")
    pm["usual_wfh"] = pm.person_id.map(r.j1_workplace_loc).eq(3); pm["wfh_known"] = pm.person_id.map(r.j1_workplace_loc).isin([1, 2, 3, 4])
    return pm, a


def nhts():
    z = zipfile.ZipFile(f"{C.RAW}/nhts/2016_csv.zip")
    h = pd.read_csv(z.open("hhpub.csv"), usecols=["HOUSEID", "TRAVDAY", "HH_CBSA", "WTHHFIN"], dtype={"HOUSEID": str, "HH_CBSA": str})
    h = h[(h.HH_CBSA == "12580") & h.TRAVDAY.between(2, 6)]
    p = pd.read_csv(z.open("perpub.csv"), usecols=["HOUSEID", "PERSONID", "R_AGE", "WORKER", "WTPERFIN"], dtype={"HOUSEID": str})
    p = p[p.HOUSEID.isin(h.HOUSEID) & (p.R_AGE >= 5)].copy(); p["pid"] = p.HOUSEID + "_" + p.PERSONID.astype(str)
    t = pd.read_csv(z.open("trippub.csv"), usecols=["HOUSEID", "PERSONID", "TDTRPNUM", "STRTTIME", "ENDTIME", "TRVLCMIN", "TRPMILES", "TRPTRANS", "DRVR_FLG", "WHYFROM", "WHYTO", "WTTRDFIN"],
                    dtype={"HOUSEID": str})
    t = t[t.HOUSEID.isin(h.HOUSEID)].copy(); t["pid"] = t.HOUSEID + "_" + t.PERSONID.astype(str); t = t[t.pid.isin(p.pid)].sort_values(["pid", "TDTRPNUM"])
    t["dep"] = (t.STRTTIME // 100) * 60 + t.STRTTIME % 100; t["arr"] = (t.ENDTIME // 100) * 60 + t.ENDTIME % 100
    t["miles"] = t.TRPMILES.where(t.TRPMILES >= 0)
    # join change-of-mode legs (WHYTO 7) to the next trip of the person
    grp = (t.WHYTO.shift().eq(7) & t.pid.eq(t.pid.shift())).map(lambda b: 0 if b else 1).cumsum()
    t["g"] = grp.values
    j = t.groupby("g").agg(pid=("pid", "first"), dep=("dep", "first"), arr=("arr", "last"), miles=("miles", "sum"), whyto=("WHYTO", "last"), whyfrom=("WHYFROM", "first"),
                           w=("WTTRDFIN", "first"), tt=("TRVLCMIN", "sum"))
    typ = np.select([j.whyto.isin([1, 2]), j.whyto.eq(3), j.whyto.eq(8), j.whyto.eq(11)], ["HOME", "WORK", "SCHOOL", "SHOPPING"], "OTHER")
    a = pd.DataFrame({"pid": j.pid.values, "type": typ, "o_home": j.whyfrom.isin([1, 2]).values, "dep": j.dep.values.astype(float), "start_min": j.arr.values % 1440,
                      "tt": j.tt.values.astype(float), "km": np.minimum(j.miles.values * MI_KM, 300), "w": j.w.values, "mode": "n/a"})
    a["dur"] = a.groupby("pid").dep.shift(-1) - a.start_min
    return p, a, h


if __name__ == "__main__":
    pm, a = rts(); pm.to_parquet(f"{C.OUT}/rts_persons.parquet", index=False); a.to_parquet(f"{C.OUT}/rts_acts.parquet", index=False)
    print("RTS persons", len(pm), "activities", len(a))
    p, b, h = nhts(); p.to_parquet(f"{C.OUT}/nhts_persons.parquet", index=False); b.to_parquet(f"{C.OUT}/nhts_acts.parquet", index=False)
    print("NHTS Baltimore CBSA weekday households", len(h), "persons 5+", len(p), "activities", len(b))
