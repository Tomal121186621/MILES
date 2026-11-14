#!/usr/bin/env python3
"""Observed weekday activity benchmarks from the American Time Use Survey (ATUS 2003-2024 multi-year files, data/raw/atus):

    python3 -I activity/lib/reporting_2024/bench_atus.py   -> temporal_2024/data/atus_persons.parquet, atus_acts.parquet, atus_summary.csv

Diaries: weekday diary days (TUDIARYDAY 2-6) that are not holidays (TRHOLIDAY 0), respondents 15+; weight TUFNWGTP (the final
weight of 2006-2024 files; for 2020 the file also has TU20FWGT, not used: 2020 is outside both periods).
Periods: 2021-2024 (the forecast year's benchmark: four years pooled because a single year holds about 100 Maryland weekday
diaries) and 2017-2019 (the base-survey period, for the observed change).  Pools: Maryland (GESTFIPS 24) and DC + Maryland +
Virginia (11, 24, 51).

Episodes -> activities (comparable with one activity per trip): the diary is cut into stays at every travel episode (activity
code 18xxxx); a stay that follows a travel episode is an activity at the destination of that trip.  Location of a stay: home
when its episodes are at the respondent's home or yard (TEWHERE 1; episodes without a recorded place -- sleeping, grooming,
personal activities -- take the place of the preceding episode), else away.  Type of an away stay: the category with the most
minutes among work and work-related (05), education (06), consumer purchases (07 -> shopping) and everything else (other);
a stay at home is a return home.  Start = start of the stay (minutes after midnight), duration = length of the stay (the last
stay of the diary, which ends at the 4:00 cut-off, has none).  The first stay of the diary (before any trip) is not an activity.
Work on the diary day: a work stay away from home.  Commute: the last trip leaving home before the first work stay; departure =
start of that trip, travel time = the travel episodes of the trips up to the arrival at work (stops excluded); mode of the trip arriving at work (TEWHERE 12 car driver,
13 passenger, 14 walk, 15 bus, 16 subway/train, 17 bicycle, else other).
"""
import sys, os, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import t24common as C

A = f"{C.RAW}/atus"
MODE = {12: "Car, driver", 13: "Car, passenger", 14: "Walk", 15: "Bus", 16: "Rail", 17: "Bicycle"}


def rd(name, cols):
    with zipfile.ZipFile(f"{A}/{name}-0324.zip") as z:
        with z.open(f"{name}_0324.dat") as f: return pd.read_csv(f, usecols=cols, low_memory=False)


def load():
    r = rd("atusresp", ["TUCASEID", "TUYEAR", "TUDIARYDAY", "TRHOLIDAY", "TUFNWGTP", "TELFS"])
    r = r[r.TUYEAR.isin([2017, 2018, 2019, 2021, 2022, 2023, 2024]) & r.TUDIARYDAY.between(2, 6) & (r.TRHOLIDAY == 0)]
    s = rd("atussum", ["TUCASEID", "TEAGE", "TESEX", "TESCHENR", "TESCHLVL"]); r = r.merge(s, on="TUCASEID")
    st = []
    with zipfile.ZipFile(f"{A}/atuscps-0324.zip") as z:
        with z.open("atuscps_0324.dat") as f:
            for ch in pd.read_csv(f, usecols=["TUCASEID", "GESTFIPS"], chunksize=500_000): st.append(ch[ch.TUCASEID.isin(r.TUCASEID)].drop_duplicates("TUCASEID"))
    r = r.merge(pd.concat(st).drop_duplicates("TUCASEID"), on="TUCASEID")
    r = r[r.GESTFIPS.isin([11, 24, 51]) & (r.TEAGE >= 15)].copy()
    r["period"] = np.where(r.TUYEAR >= 2021, "2021-2024", "2017-2019"); r["employed"] = r.TELFS.isin([1, 2])
    r["student"] = r.TESCHENR.eq(1)
    a = rd("atusact", ["TUCASEID", "TUACTIVITY_N", "TUSTARTTIM", "TUACTDUR24", "TRCODEP", "TEWHERE"]); a = a[a.TUCASEID.isin(r.TUCASEID)]
    return r, a.sort_values(["TUCASEID", "TUACTIVITY_N"])


def stays(a):
    a = a.copy()
    hh, mm, _ = zip(*a.TUSTARTTIM.str.split(":")); a["t0"] = np.array(hh, int) * 60 + np.array(mm, int)
    a["t0"] = np.where(a.t0 < 240, a.t0 + 1440, a.t0)                     # diary runs 4:00 -> 4:00
    a["travel"] = a.TRCODEP // 10000 == 18
    w = a.TEWHERE.where(a.TEWHERE > 0)
    home = np.where(a.travel, np.nan, np.where(w == 1, 1.0, np.where(w.notna(), 0.0, np.nan)))
    a["home"] = pd.Series(home, index=a.index).groupby(a.TUCASEID).ffill().fillna(1.0)
    a.loc[a.travel, "home"] = np.nan
    major = a.TRCODEP // 10000
    a["cat"] = np.select([major == 5, major == 6, major == 7], ["WORK", "SCHOOL", "SHOPPING"], "OTHER")
    # stay ids: new stay after every travel episode and at every home/away switch
    first = a.TUCASEID.ne(a.TUCASEID.shift())
    prev_travel = a.travel.shift(fill_value=False) & ~first
    switch = a.home.ne(a.groupby("TUCASEID").home.shift()) & a.home.notna()
    a["new"] = (~a.travel) & (first | prev_travel | switch)
    a["sid"] = a.new.cumsum()
    a["after_trip"] = prev_travel
    nt = a[~a.travel]
    g = nt.groupby("sid").agg(cid=("TUCASEID", "first"), start=("t0", "min"), dur=("TUACTDUR24", "sum"), home=("home", "first"), after_trip=("after_trip", "first"),
                               first_of_day=("TUACTIVITY_N", "min"))
    mins = nt.pivot_table(index="sid", columns="cat", values="TUACTDUR24", aggfunc="sum", fill_value=0).reindex(columns=["WORK", "SCHOOL", "SHOPPING", "OTHER"], fill_value=0)
    g["type"] = np.where(g.home == 1, "HOME", mins.idxmax(axis=1).reindex(g.index).values)
    last = g.groupby("cid").start.transform("max") == g.start
    g.loc[last, "dur"] = np.nan
    g = g[g.after_trip & (g.first_of_day > 1)]
    # the trip arriving at each activity: the travel episodes just before the stay
    tr = a[a.travel].copy(); tr["next_sid"] = tr.sid + 1                       # a travel episode belongs to the stay that follows it
    trip = tr.groupby("next_sid").agg(dep=("t0", "min"), mode_code=("TEWHERE", "last"), n_legs=("t0", "size"), trip_tt=("TUACTDUR24", "sum"))
    g = g.join(trip, how="left"); g["mode"] = g.mode_code.map(MODE).fillna("Other")
    g["start_min"] = g.start % 1440
    return g.reset_index()


def commute(g):
    """Per respondent with a work stay: the trips from the last departure from home before the first work stay up to the arrival
    at work; departure = start of the first of these trips, travel time = the sum of their travel episodes (stops excluded)."""
    out = []
    for cid, d in g.sort_values(["cid", "start"]).groupby("cid"):
        wk = np.where(d.type.values == "WORK")[0]
        if not len(wk): continue
        i = wk[0]; hm = np.where(d.type.values[:i] == "HOME")[0]
        j = hm[-1] + 1 if len(hm) else 0                     # first trip after the last return home (else the first trip of the day)
        out.append(dict(cid=cid, dep=d.dep.values[j] % 1440, arr=d.start.values[i] % 1440, tt=float(d.trip_tt.values[j:i + 1].sum()),
                        n_trips=i + 1 - j, mode=d["mode"].values[i]))
    return pd.DataFrame(out)


if __name__ == "__main__":
    r, a = load(); print("weekday diaries 15+ (DC/MD/VA):", len(r), flush=True)
    g = stays(a); g = g.merge(r[["TUCASEID", "TUFNWGTP"]], left_on="cid", right_on="TUCASEID").drop(columns="TUCASEID")
    cm = commute(g); r = r.merge(cm.rename(columns={"cid": "TUCASEID"}), on="TUCASEID", how="left")
    cnt = g.pivot_table(index="cid", columns="type", values="start", aggfunc="size", fill_value=0).reindex(columns=C.TYPES, fill_value=0)
    for t in C.TYPES: r[f"n_{t}"] = r.TUCASEID.map(cnt[t]).fillna(0).astype(int)
    r["n_ALL"] = r[[f"n_{t}" for t in C.TYPES]].sum(axis=1)
    r["work_away"] = r.n_WORK > 0
    r.to_parquet(f"{C.OUT}/atus_persons.parquet", index=False); g.to_parquet(f"{C.OUT}/atus_acts.parquet", index=False)
    S = []
    for pool, st in [("Maryland", [24]), ("DC + Maryland + Virginia", [11, 24, 51])]:
        for per in ["2017-2019", "2021-2024"]:
            p = r[r.GESTFIPS.isin(st) & (r.period == per)]; w = p.TUFNWGTP
            S.append(dict(pool=pool, period=per, metric="weekday diaries, persons 15+", value=len(p), n=len(p)))
            S.append(dict(pool=pool, period=per, metric="employed respondents", value=int(p.employed.sum()), n=int(p.employed.sum())))
            e = p[p.employed]
            S.append(dict(pool=pool, period=per, metric="employed: share with work away from home", value=C.wshare(e.work_away, e.TUFNWGTP), n=len(e)))
            for t in C.TYPES + ["ALL"]:
                S.append(dict(pool=pool, period=per, metric=f"activities per person: {t}", value=float(np.average(p[f"n_{t}"], weights=w)), n=len(p)))
                S.append(dict(pool=pool, period=per, metric=f"participation: {t}", value=C.wshare(p[f"n_{t}"] > 0, w), n=len(p)))
            c = p[p.tt.notna() & (p.tt > 0)]
            S.append(dict(pool=pool, period=per, metric="commute: mean travel time (min)", value=float(np.average(c.tt, weights=c.TUFNWGTP)), n=len(c)))
            S.append(dict(pool=pool, period=per, metric="commute: mean departure (min after midnight)", value=float(np.average(c.dep, weights=c.TUFNWGTP)), n=len(c)))
    S = pd.DataFrame(S); S.to_csv(f"{C.OUT}/atus_summary.csv", index=False)
    print(S.pivot_table(index="metric", columns=["pool", "period"], values="value").round(3).to_string())
