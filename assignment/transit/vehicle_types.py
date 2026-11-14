#!/usr/bin/env python3
"""Transit vehicles of a mapped schedule (TRANSIT_BUILD.md, "Vehicle types"): one vehicle per departure (the vehicleRefId of the
schedule), its type by agency (id prefix of the line) and mode.  Nominal values per type (seats, standing places, length, passenger
car equivalents, door times per passenger; sources in TRANSIT_BUILD.md):
  bus_local   40-ft low-floor bus (MTA, WMATA, Ride On, TheBus, RTA, county services)  38 seats + 32 standing, 12.2 m, PCE 2.0
  bus_coach   MTA commuter coach (45-ft over-the-road)                                  57 seats,              13.7 m, PCE 2.5
  light_rail  MTA Light RailLink, 2-car train                                          170 seats + 200 st.,    58 m
  metro_mta   MTA Metro SubwayLink, 4-car train                                        304 seats + 360 st.,    92 m
  metro_wmata WMATA Metrorail, 8-car train                                             512 seats + 880 st.,   183 m
  rail_marc   MARC, locomotive + 6 bi-level coaches                                    780 seats,             180 m
  rail_amtrak Amtrak Northeast Regional / Acela                                        550 seats,             200 m
  ferry       Harbor Connector boat                                                     50 seats,              15 m
Rail and ferry types run on their own (rail or artificial) links; their PCE only matters on those links.
--scale F (the MATSim sample, e.g. 0.1): passenger capacity and PCE multiplied by F (capacity rounded up to >= 1), so that a bus of
a 10 % run takes the road space of 10 % of a bus on the 10 %-capacity network and carries 10 % of a bus load (MATSim practice for
sample runs).
Usage: python3 -I vehicle_types.py <schedule.xml.gz> <vehicles out.xml.gz> [--scale F]"""
import sys, gzip, re, math, collections
sched, out = sys.argv[1], sys.argv[2]; F = float(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 1.0
TYPES = {"bus_local": (38, 32, 12.2, 2.0, "bus", 2.0, 1.5), "bus_coach": (57, 0, 13.7, 2.5, "bus", 3.0, 3.0), "light_rail": (170, 200, 58, 5.2, "tram", 0.5, 0.5),
         "metro_mta": (304, 360, 92, 4.4, "subway", 0.25, 0.25), "metro_wmata": (512, 880, 183, 4.4, "subway", 0.25, 0.25), "rail_marc": (780, 0, 180, 27.1, "rail", 0.5, 0.5),
         "rail_amtrak": (550, 0, 200, 27.1, "rail", 0.5, 0.5), "ferry": (50, 0, 15, 1.0, "ferry", 2.0, 2.0)}
def vtype(feed, mode):
    if mode == "bus": return "bus_coach" if feed == "cb" else "bus_local"
    if mode == "tram": return "light_rail"
    if mode == "subway": return "metro_wmata" if feed == "wmr" else "metro_mta"
    if mode == "rail": return "rail_amtrak" if feed == "amt" else "rail_marc"
    if mode == "ferry": return "ferry"
    raise SystemExit(f"no vehicle type for {feed} {mode}")
veh = {}; feed = mode = None
with gzip.open(sched, "rt") as f:
    for line in f:
        if "<transitLine " in line: feed = re.search(r'id="([^:"]+)', line).group(1)
        elif "<transportMode>" in line: mode = re.search(r"<transportMode>([^<]+)", line).group(1)
        elif "<departure " in line: veh[re.search(r'vehicleRefId="([^"]+)"', line).group(1)] = vtype(feed, mode)
x = ['<?xml version="1.0" encoding="UTF-8"?>', '<vehicleDefinitions xmlns="http://www.matsim.org/files/dtd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.matsim.org/files/dtd http://www.matsim.org/files/dtd/vehicleDefinitions_v2.0.xsd">']
for t, (seats, stand, length, pce, nm, acc, egr) in TYPES.items():
    s, st = max(1, math.ceil(seats * F)), (math.ceil(stand * F) if stand else 0)
    x += [f'\t<vehicleType id="{t}">', "\t\t<attributes>", f'\t\t\t<attribute name="accessTimeInSecondsPerPerson" class="java.lang.Double">{acc}</attribute>',
          '\t\t\t<attribute name="doorOperationMode" class="org.matsim.vehicles.VehicleType$DoorOperationMode">serial</attribute>',
          f'\t\t\t<attribute name="egressTimeInSecondsPerPerson" class="java.lang.Double">{egr}</attribute>', "\t\t</attributes>",
          f'\t\t<capacity seats="{s}" standingRoomInPersons="{st}"/>', f'\t\t<length meter="{length}"/>', '\t\t<width meter="2.6"/>',
          f'\t\t<passengerCarEquivalents pce="{pce * F:.4f}"/>', f'\t\t<networkMode networkMode="{nm}"/>', '\t\t<flowEfficiencyFactor factor="1.0"/>', "\t</vehicleType>"]
for v, t in sorted(veh.items()): x.append(f'\t<vehicle id="{v}" type="{t}"/>')
x.append("</vehicleDefinitions>")
with gzip.open(out, "wt") as fo: fo.write("\n".join(x) + "\n")
print(f"{len(veh):,} vehicles, scale {F}:", dict(collections.Counter(veh.values())), "->", out)
