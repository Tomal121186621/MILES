#!/usr/bin/env python3
"""Write a pt2matsim PublicTransitMapping config (TRANSIT_BUILD.md).  Mode rules: bus -> links with car or bus (the road network),
tram (Light RailLink) -> light_rail/tram links, subway (Metro SubwayLink, WMATA Metrorail) -> subway links, rail (MARC, Amtrak) -> rail/train
links, ferry -> no network mode (artificial links).  The other values are arguments (the tuning of step 3).
Usage: make_ptmapper_config.py <out.xml> <network> <schedule in> <network out> <schedule out> [key=value ...]
keys: maxLinkCandidateDistance nLinkThreshold candidateDistanceMultiplier travelCostType routingWithCandidateDistance maxTravelCostFactor numOfThreads"""
import sys
out, net, sin, nout, sout = sys.argv[1:6]
P = {"candidateDistanceMultiplier": "1.6", "maxLinkCandidateDistance": "90.0", "maxTravelCostFactor": "5.0", "nLinkThreshold": "6", "numOfThreads": "10",
     "routingWithCandidateDistance": "true", "travelCostType": "linkLength", "modesToKeepOnCleanUp": "car", "removeNotUsedStopFacilities": "true", "scheduleFreespeedModes": "artificial"}
for kv in sys.argv[6:]: k, v = kv.split("="); assert k in P, k; P[k] = v
MODES = {"bus": "car,bus", "tram": "light_rail,tram", "subway": "subway", "rail": "rail,train", "ferry": ""}
x = ['<?xml version="1.0" encoding="UTF-8"?>', '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">', "<config>", '\t<module name="PublicTransitMapping" >']
x += [f'\t\t<param name="{k}" value="{v}" />' for k, v in sorted(P.items())]
x += [f'\t\t<param name="inputNetworkFile" value="{net}" />', f'\t\t<param name="inputScheduleFile" value="{sin}" />', f'\t\t<param name="outputNetworkFile" value="{nout}" />', f'\t\t<param name="outputScheduleFile" value="{sout}" />']
for m, nm in MODES.items(): x += ['\t\t<parameterset type="transportModeAssignment" >', f'\t\t\t<param name="networkModes" value="{nm}" />', f'\t\t\t<param name="scheduleMode" value="{m}" />', "\t\t</parameterset>"]
x += ["\t</module>", "</config>"]; open(out, "w").write("\n".join(x) + "\n"); print("written", out, P)
