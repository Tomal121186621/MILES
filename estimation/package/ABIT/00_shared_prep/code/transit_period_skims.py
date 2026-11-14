#!/usr/bin/env python3
"""Transit level of service by period for the tour mode choice (SwissRailRaptor on the regional GTFS schedule of the 2024
transit build, see NET / SCH below; pipeline/java/TransitSkim.java with the waiting time and the number of transfers).

    python3 transit_period_skims.py [--periods AM,MD,PM,NT] [--access walk,drive] [--threads 6]

Periods (departures drawn every STEP minutes in the window; the skim value is the mean over the departures that arrive within
180 min, a pair is reachable when half of the departures do):
    AM 06-09 (15 min)   MD 09-15 (30 min)   PM 15-19 (15 min)   NT 19-23 (30 min)
Access:
    walk   access and egress walks within 1,600 m at 1.23 m/s with beeline factor 1.3 (the base_transit2024 convention)
    drive  access by car within 15 km of the origin centroid at an effective 25 km/h on the beeline (teleported 9.0 m/s, factor
           1.3), egress walk within 1,600 m.  Used for the drive-access transit alternative (park and ride, kiss and ride).
Raw output per period and access: work/skims/raptor_<access>_<P>.csv.gz with FROM,TO,ALL,BUS,RAILSHARE,ACCESS,EGRESS,WAIT,TRANSFERS
(minutes; in-vehicle time incl. transfer walks and waits = ALL - ACCESS - EGRESS - WAIT).  Pairs not in the file have no path."""
# COPY of Validation_2026/3_abit/mode_choice/transit_period_skims.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "00_shared_data"))          # provided inputs
RAW = _os_pkg.environ.get("ABIT_RAW", _os_pkg.path.join(SHARED, "raw"))                                                              # your downloads
REBUILT = _os_pkg.environ.get("ABIT_REBUILT", _os_pkg.path.join(SHARED, "rebuilt"))                  # outputs of this chain
MDATA = REBUILT
import argparse, os, subprocess, time
ROOT = SHARED; V = SHARED  # PATH
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f"{REBUILT}/skims/mode_choice_periods"; CLS = f"{RAW}/matsim_tools/tsclasses"; os.makedirs(OUT, exist_ok=True)  # PATH: TransitSkim classes compiled from TransitSkim.java
JAR = f"{RAW}/matsim_tools/baltimore-matsim-1.0.jar"  # PATH: MATSim 2024.0 run jar of the project
# regional schedule: every feed of 4_matsim/transit/merge_gtfs.py without the clip to the Maryland road network (merge_gtfs_full.py:
# WMATA Metrorail and Metrobus in DC and Virginia, Ride On, TheBus, MTA, MARC, Amtrak), converted unmapped by pt2matsim
# Gtfs2TransitSchedule (service day Wednesday 2026-10-21); TransitSkim gives unmapped routes artificial links (the raptor routes on
# the timetable).  The assignment's mapped schedule (4_matsim/transit/transitSchedule_2024) stops at the Maryland network.
NET = f"{RAW}/matsim_network_2024/network_2024_pt.xml.gz"; SCH = f"{REBUILT}/gtfs_full/schedule_unmapped.xml.gz"; VEH = f"{REBUILT}/gtfs_full/vehicles.xml.gz"  # PATH
CENT = f"{SHARED}/skims/transit_2024_door_to_door/centroids.csv"  # PATH
PERIODS = {"AM": (6, 9, 15), "MD": (9, 15, 30), "PM": (15, 19, 15), "NT": (19, 23, 30)}
ACCESS = {"walk": [], "drive": ["-Dskim.access.speed=9.0", "-Dskim.access.radius=15000"]}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--periods", default="AM,MD,PM,NT"); ap.add_argument("--access", default="walk,drive")
    ap.add_argument("--threads", type=int, default=6); ap.add_argument("--xmx", default="6g"); a = ap.parse_args()
    java = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip() + "/bin/java"
    for acc in a.access.split(","):
        for p in a.periods.split(","):
            f0, f1, st = PERIODS[p]; out = f"{OUT}/raptor_{acc}_{p}.csv.gz"
            if os.path.exists(out): print(out, "exists"); continue
            t0 = time.time()
            cmd = [java, f"-Xmx{a.xmx}"] + ACCESS[acc] + ["-cp", f"{CLS}:{JAR}", "de.umd.skim.TransitSkim", NET, SCH, VEH, CENT, out + ".part", str(f0), str(f1), str(st), "1600", "0", str(a.threads), "180"]
            with open(f"{OUT}/raptor_{acc}_{p}.log", "w") as lf: rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT).returncode
            if rc != 0: raise SystemExit(f"TransitSkim {acc} {p} failed; see {OUT}/raptor_{acc}_{p}.log")
            os.replace(out + ".part", out); print(f"{acc} {p}: {time.time() - t0:.0f} s", flush=True)
