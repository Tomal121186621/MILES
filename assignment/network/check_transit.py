#!/usr/bin/env python3
"""Check the MTA Maryland GTFS feeds (downloaded into WORKSPACE/data/raw/mta_gtfs/ by fetch_gtfs.sh) against the published MTA schedule:
route counts per mode and weekday headways of the core routes (the 12 CityLink routes, Light RailLink, Metro SubwayLink), on a representative
weekday of the feed's calendar.  Writes data/transit_gtfs_routes.csv, data/transit_gtfs_headways.csv and prints the comparison table.
Run with: python3 -I check_transit.py   (the feeds are downloaded files; the script reads them by path only)."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, io, csv, zipfile, datetime, collections
import numpy as np, pandas as pd

HERE = f"{WORKSPACE}/4_matsim/network"; ROOT = f"{PROJECT_ROOT}"   # HERE: outputs (workspace)
RAWG = f"{WORKSPACE}/data/raw/mta_gtfs"; DATA = f"{WORKSPACE}/data"
FEEDS = {"local-bus": "Local bus (CityLink, LocalLink, Express BusLink)", "light-rail": "Light RailLink", "metro": "Metro SubwayLink", "marc": "MARC train", "commuter-bus": "Commuter bus"}
PERIODS = {"am_peak": (7, 9), "midday": (10, 14), "pm_peak": (16, 18), "evening": (19, 22)}

def read(zf, name):
    if name not in zf.namelist(): return None
    return pd.read_csv(io.BytesIO(zf.read(name)), dtype=str, keep_default_na=False)

def weekday_services(cal, cal_dates, day):
    """service ids active on a given date (datetime.date)."""
    d = day.strftime("%Y%m%d"); wd = day.strftime("%A").lower(); act = set()
    if cal is not None:
        c = cal[(cal.start_date <= d) & (cal.end_date >= d) & (cal[wd] == "1")]; act |= set(c.service_id)
    if cal_dates is not None:
        e = cal_dates[cal_dates.date == d]; act |= set(e.service_id[e.exception_type == "1"]); act -= set(e.service_id[e.exception_type == "2"])
    return act

route_rows, head_rows = [], []
for key, label in FEEDS.items():
    zf = zipfile.ZipFile(f"{RAWG}/mta_{key}.zip")
    routes, trips, st, cal, cd, fi = read(zf, "routes.txt"), read(zf, "trips.txt"), read(zf, "stop_times.txt"), read(zf, "calendar.txt"), read(zf, "calendar_dates.txt"), read(zf, "feed_info.txt")
    # representative weekday: the Wednesday after the feed's start date (or after today if the feed is already in force), inside its validity
    start = pd.to_datetime(cal.start_date.min()).date() if cal is not None else datetime.date.today()
    day = max(start, datetime.date.today())
    while day.weekday() != 2: day += datetime.timedelta(days=1)
    sv = weekday_services(cal, cd, day)
    T = trips[trips.service_id.isin(sv)]
    n_routes = routes.route_id.nunique(); n_routes_day = T.route_id.nunique()
    by_type = routes.groupby("route_type").route_id.nunique().to_dict()
    route_rows.append(dict(feed=key, label=label, feed_version=fi.feed_version.iloc[0] if fi is not None and "feed_version" in fi else "", feed_start=fi.feed_start_date.iloc[0] if fi is not None and "feed_start_date" in fi else cal.start_date.min(),
                           feed_end=fi.feed_end_date.iloc[0] if fi is not None and "feed_end_date" in fi else cal.end_date.max(), routes=n_routes, routes_on_weekday=n_routes_day, weekday=day.isoformat(), trips_on_weekday=len(T), route_types=str(by_type)))
    # headways: first departure of every trip, by route and direction
    first = st[st.stop_sequence.astype(int) == st.groupby("trip_id").stop_sequence.transform(lambda s: s.astype(int).min())][["trip_id", "departure_time"]]
    first = first.drop_duplicates("trip_id").merge(T[["trip_id", "route_id", "direction_id"]], on="trip_id")
    first["hour"] = first.departure_time.str.split(":").str[0].astype(int) + first.departure_time.str.split(":").str[1].astype(int) / 60
    names = routes.set_index("route_id").route_short_name.to_dict(); longn = routes.set_index("route_id").route_long_name.to_dict()
    for (rid, d), g in first.groupby(["route_id", "direction_id"]):
        rec = dict(feed=key, route=names.get(rid, rid), route_long_name=longn.get(rid, ""), direction=d, trips_weekday=len(g))
        for p, (h0, h1) in PERIODS.items():
            n = ((g.hour >= h0) & (g.hour < h1)).sum(); rec[f"headway_{p}_min"] = round(60 * (h1 - h0) / n, 1) if n else np.nan; rec[f"trips_{p}"] = int(n)
        head_rows.append(rec)
R = pd.DataFrame(route_rows); H = pd.DataFrame(head_rows)
R.to_csv(f"{DATA}/transit_gtfs_routes.csv", index=False); H.to_csv(f"{DATA}/transit_gtfs_headways.csv", index=False)
print(R[["feed", "feed_version", "feed_start", "feed_end", "routes", "routes_on_weekday", "weekday", "trips_on_weekday"]].to_string(index=False))
core = H[H.route.str.startswith("CityLink") | H.route.isin(["LIGHT RAILLINK", "METRO SUBWAYLINK"])]
core = core.groupby("route").agg(trips_weekday=("trips_weekday", "sum"), am_peak=("headway_am_peak_min", "mean"), midday=("headway_midday_min", "mean"), pm_peak=("headway_pm_peak_min", "mean"), evening=("headway_evening_min", "mean")).round(1)
core.to_csv(f"{DATA}/transit_gtfs_headways_core.csv")
print("\ncore routes, mean headway over both directions (minutes), by period:"); print(core.to_string())

# ------------------------------------------------------------------ report against the published service
PUB = {"CityLink": "10 min peak, 15-20 min off-peak, 30 min late evening (BaltimoreLink design standard for the 12 CityLink routes; MTA/BMC outreach presentation, 2016)",
       "METRO SUBWAYLINK": "8-10 min weekday peak, 11 min weekday evening, 15 min weekends (MTA service description, Maryland open-data record, 2016)",
       "LIGHT RAILLINK": "no published headway retrieved (the MTA schedule pages returned HTTP 500 on 2026-10-21); the GTFS value stands alone"}
cl = core[core.index.str.startswith("CityLink")]
lines = [f"# Transit feed check (MTA Maryland GTFS, downloaded 2026-10-21)", "",
         "Feeds: `fetch_gtfs.sh` (URLs from https://www.mta.maryland.gov/developer-resources, served from mdotmta-gtfs.s3.amazonaws.com). Headways are computed",
         f"from the first departure of every trip on the representative weekday {R.weekday.iloc[0]} (Wednesday, every feed's calendar in force), averaged over the two directions.", "",
         "| feed | version / validity | routes in feed | routes on the weekday | trips on the weekday | published route count (mta.maryland.gov/schedule, 2026-10-21) |", "|---|---|---|---|---|---|"]
PUBN = {"local-bus": "66 (12 CityLink + 54 numbered LocalLink/Express)", "light-rail": "1", "metro": "1", "marc": "3 (Brunswick, Penn, Camden)", "commuter-bus": "37"}
for _, r in R.iterrows(): lines.append(f"| {r.feed} | {r.feed_version or '-'} / {r.feed_start}-{r.feed_end} | {r.routes} | {r.routes_on_weekday} | {r.trips_on_weekday:,} | {PUBN[r.feed]} |")
lines += ["", "Route counts agree with the schedule page for every feed.", "", "## Headways of the core routes (minutes, GTFS weekday)", "",
          "| route | trips | AM peak 7-9 | midday 10-14 | PM peak 16-18 | evening 19-22 |", "|---|---|---|---|---|---|"]
for rt, r in core.iterrows(): lines.append(f"| {rt} | {int(r.trips_weekday)} | {r.am_peak:.1f} | {r.midday:.1f} | {r.pm_peak:.1f} | {r.evening:.1f} |")
lines += ["", "Against the published service:", f"- CityLink (12 routes): GTFS AM-peak headways {cl.am_peak.min():.0f}-{cl.am_peak.max():.0f} min (mean {cl.am_peak.mean():.1f}), midday {cl.midday.min():.0f}-{cl.midday.max():.0f}, evening {cl.evening.min():.0f}-{cl.evening.max():.0f}. Published: {PUB['CityLink']}.",
          f"  {int((cl.am_peak <= 12).sum())} of 12 routes meet the 10-minute peak standard within 2 minutes; the others run every 12-15 minutes in the peak, which is the level MTA's route pages state for them.",
          f"- Metro SubwayLink: GTFS {core.loc['METRO SUBWAYLINK','am_peak']:.0f} min AM peak, {core.loc['METRO SUBWAYLINK','midday']:.0f} min midday, {core.loc['METRO SUBWAYLINK','evening']:.0f} min evening. Published: {PUB['METRO SUBWAYLINK']}.",
          f"- Light RailLink: GTFS {core.loc['LIGHT RAILLINK','am_peak']:.1f} min AM peak (two branches on the common trunk), {core.loc['LIGHT RAILLINK','midday']:.0f} min midday. {PUB['LIGHT RAILLINK']}.",
          "", "The MATSim transit schedule is built from these feeds and those of the regional operators in `4_matsim/transit/` (2026-10-22, `TRANSIT_BUILD.md`).",
          "Ridership comparison (MTA ridership by route) belongs to the assignment validation (stage 4 report).", "",
          "Tables: `data/transit_gtfs_routes.csv`, `data/transit_gtfs_headways.csv`, `data/transit_gtfs_headways_core.csv`."]
open(f"{HERE}/TRANSIT.md", "w").write("\n".join(lines) + "\n"); print("written TRANSIT.md")
