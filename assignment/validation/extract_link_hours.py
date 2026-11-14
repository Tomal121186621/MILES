#!/usr/bin/env python3
"""Hourly link volumes of one MATSim run from its final events, so the events file (several GB) can be deleted.
For every link and hour (0-35, the 36 h simulation): vehicles entering the link, by class
    car   = resident cars (MATSim vehicle id = person id; x 10 in the validation for the 10 % sample)
    bus   = transit buses (vehicle type bus_local / bus_coach; real number of departures, x 1)
    pt_other = other transit vehicles (rail, ferry) on their own links
and for cars the sum of link travel times (left link - entered link, s) and the number of those passages, so that
congested link travel times by hour remain available (e.g. for skims) after the events are gone.
Usage: extract_link_hours.py <events.xml.gz> <transitVehicles.xml.gz> <out.csv.gz>"""
import sys, gzip, re, collections, time
import pandas as pd
ev, vf, out = sys.argv[1:4]; t0 = time.time()
vt = {}
for line in gzip.open(vf, "rt"):
    m = re.search(r'<vehicle id="([^"]+)" type="([^"]+)"', line)
    if m: vt[m.group(1)] = "bus" if m.group(2).startswith("bus") else "pt_other"
cnt = collections.Counter(); tts = collections.Counter(); ttn = collections.Counter(); enter = {}
def attr(line, k):
    i = line.find(f' {k}="'); i += len(k) + 3; return line[i:line.index('"', i)]
n = 0
with gzip.open(ev, "rt") as f:
    for line in f:
        if 'type="entered link"' in line:
            t = float(attr(line, "time")); v = attr(line, "vehicle"); l = attr(line, "link"); c = vt.get(v, "car")
            cnt[(l, int(t // 3600), c)] += 1; n += 1
            if c == "car": enter[v] = (l, t)
        elif 'type="left link"' in line:
            v = attr(line, "vehicle"); e = enter.pop(v, None)
            if e is not None:
                l, t = e; k = (l, int(t // 3600)); tts[k] += float(attr(line, "time")) - t; ttn[k] += 1
        elif 'type="vehicle leaves traffic"' in line:
            enter.pop(attr(line, "vehicle"), None)   # a trip's last link: no 'left link' (and the next trip must not close it)
rows = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0])
for (l, h, c), k in cnt.items(): rows[(l, h)][{"car": 0, "bus": 1, "pt_other": 2}[c]] = k
for k, s in tts.items(): rows[k][3] = s; rows[k][4] = ttn[k]
D = pd.DataFrame([(l, h, *v) for (l, h), v in rows.items()], columns=["link", "hour", "car", "bus", "pt_other", "car_tt_sum_s", "car_tt_n"])
D.sort_values(["link", "hour"]).to_csv(out, index=False, compression="gzip", float_format="%.1f")
print(f"{n:,} link entries, {len(D):,} link-hours, {D.link.nunique():,} links; car {D.car.sum():,} bus {D.bus.sum():,} pt_other {D.pt_other.sum():,} -> {out} ({time.time() - t0:.0f} s)")
