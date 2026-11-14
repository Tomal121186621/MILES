#!/usr/bin/env python3
"""Mapper input network (TRANSIT_BUILD.md, step 3): network_<Y> without the transit-only links of the earlier chain's pt2matsim
mapping that network_v8_supply carried over (modes containing "artificial", e.g. "bus,artificial" and stop-facility loop links, with
their "pt_..." nodes).  Left in, the mapper routes buses over these old artificial links (e.g. a 34.6 km straight link of a 2026-06
commuter-bus mapping).  Every car, bus, rail, subway and light-rail link built from OpenStreetMap is kept unchanged.
Usage: python3 -I clean_network.py <network.xml.gz> <out.xml.gz>"""
import sys, gzip, re
src, dst = sys.argv[1], sys.argv[2]; drop = set(); keep_nodes = set()
with gzip.open(src, "rt") as f:
    for l in f:
        if "<link " in l:
            m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)"', l); modes = re.search(r'modes="([^"]*)"', l).group(1).split(",")
            if "artificial" in modes: drop.add(m.group(1))
            else: keep_nodes.update(m.groups()[1:])
nl = nn = 0; skip = False
with gzip.open(src, "rt") as f, gzip.open(dst, "wt") as fo:
    for l in f:
        if not skip and "<node " in l:
            nid = re.search(r'id="([^"]+)"', l).group(1)
            if nid not in keep_nodes: nn += 1; skip = not l.rstrip().endswith("/>"); continue
        elif not skip and "<link " in l:
            lid = re.search(r'id="([^"]+)"', l).group(1)
            if lid in drop: nl += 1; skip = not l.rstrip().endswith("/>"); continue
        if skip:
            if "</node>" in l or "</link>" in l: skip = False
            continue
        fo.write(l)
print(f"{src}: dropped {nl} artificial links and {nn} nodes without other links -> {dst}")
