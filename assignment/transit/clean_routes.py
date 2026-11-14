#!/usr/bin/env python3
"""Remove detour loops and U-turns from the mapped transit routes (TRANSIT_BUILD.md, step 4).
pt2matsim's pseudo-routing picks one candidate link per stop; when it picks the link of the opposite direction, or a link one block
off, the route reaches the stop by a U-turn (a->b, b->a) or a loop around a block and the plausibility check reports a
DirectionChangeWarning or LoopWarning.  For every route, a stretch of the link sequence that leaves a node and returns to it (the
from-node of link j equals the from-node of an earlier link i) and contains no link referenced by a stop of the route is cut out:
links i..j-1 are removed, the sequence stays connected (link i-1 ends where link j starts) and every stop keeps its link in order.
Stretches that contain a stop link are kept (the bus must pass the stop) and stay in the plausibility report.
Usage: python3 -I assignment/transit/clean_routes.py <schedule.xml.gz> <network.xml.gz> <out schedule.xml.gz> <report.json>"""
import sys, gzip, re, json, collections
src, net, dst, rep = sys.argv[1:5]
frm, to = {}, {}
with gzip.open(net, "rt") as f:
    for l in f:
        if "<link " in l: m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)"', l); frm[m.group(1)] = m.group(2); to[m.group(1)] = m.group(3)
stop_link = {}
lines = gzip.open(src, "rt").read().split("\n")
for l in lines:
    if "<stopFacility " in l:
        m = re.search(r'id="([^"]+)".*?linkRefId="([^"]+)"', l); stop_link[m.group(1)] = m.group(2)
out = []; i = 0; stats = collections.Counter(); per_feed = collections.Counter(); feed = None
while i < len(lines):
    l = lines[i]
    if "<transitLine " in l: feed = re.search(r'id="([^:"]+)', l).group(1)
    if "<transitRoute " in l:
        # collect the route block
        j = i; block = []
        while "</transitRoute>" not in lines[j]: block.append(lines[j]); j += 1
        block.append(lines[j])
        stops = [re.search(r'refId="([^"]+)"', b).group(1) for b in block if "<stop refId=" in b]
        slinks = {stop_link[s] for s in stops}
        li = [k for k, b in enumerate(block) if "<link refId=" in b]; seq = [re.search(r'refId="([^"]+)"', block[k]).group(1) for k in li]
        changed = True; removed = 0
        while changed:
            changed = False; first = {}
            for k, lk in enumerate(seq):
                n = frm[lk]
                if n in first:
                    a = first[n]
                    if a > 0 and not any(x in slinks for x in seq[a:k]):
                        removed += k - a; seq = seq[:a] + seq[k:]; changed = True; stats["loops_cut"] += 1; per_feed[feed] += 1; break
                first[n] = k
        assert all(to[seq[k]] == frm[seq[k + 1]] for k in range(len(seq) - 1)), "route not connected after cleaning"
        if removed: stats["routes_changed"] += 1; stats["links_removed"] += removed
        stats["routes"] += 1
        ind = re.match(r"\s*", block[li[0]]).group(0) if li else "\t\t\t\t"
        newblock = block[:li[0]] + [f'{ind}<link refId="{x}"/>' for x in seq] + block[li[-1] + 1:] if li else block
        out.extend(newblock); i = j + 1; continue
    out.append(l); i += 1
with gzip.open(dst, "wt") as fo: fo.write("\n".join(out))
rec = dict(stats) | {"loops_cut_by_feed": dict(per_feed)}; json.dump(rec, open(rep, "w"), indent=1); print(rec)
