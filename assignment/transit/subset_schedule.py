#!/usr/bin/env python3
"""Subset of an unmapped schedule for the mapper tuning (TRANSIT_BUILD.md, step 3): every rail/subway/tram/ferry line and every k-th
bus line of each feed (sorted by id), all stop facilities (the mapper removes unused ones).  Usage: subset_schedule.py <in> <out> <k>"""
import sys, gzip, re
src, dst, k = sys.argv[1], sys.argv[2], int(sys.argv[3])
lines = []; cur = None; buf = []; head = []; tail = []; state = "head"
with gzip.open(src, "rt") as f:
    for l in f:
        if "<transitLine " in l: state = "line"; buf = [l]; continue
        if state == "line":
            buf.append(l)
            if "</transitLine>" in l: lines.append("".join(buf)); state = "between"
            continue
        (head if state == "head" else tail).append(l)
bykey = {}
for b in lines:
    lid = re.search(r'<transitLine id="([^"]+)"', b).group(1); feed = lid.split(":")[0]; mode = re.search(r"<transportMode>([^<]+)", b).group(1)
    bykey.setdefault((feed, mode), []).append((lid, b))
keep = []
for (feed, mode), L in sorted(bykey.items()):
    L.sort(); keep += [b for i, (_, b) in enumerate(L) if mode != "bus" or i % k == 0]
with gzip.open(dst, "wt") as fo: fo.write("".join(head) + "".join(keep) + "".join(tail))
print(f"{len(keep)} of {len(lines)} lines kept")
