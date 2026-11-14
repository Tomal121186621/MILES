#!/usr/bin/env python3
"""Transit level of service by period for the tour mode choice (SwissRailRaptor on the regional GTFS schedule of the 2024
transit build, see NET / SCH below; pipeline/java/TransitSkim.java with the waiting time and the number of transfers).

    python3 activity/lib/mode_choice/transit_period_skims.py [--periods AM,MD,PM,NT] [--access walk,drive] [--threads 6]

Periods (departures drawn every STEP minutes in the window; the skim value is the mean over the departures that arrive within
180 min, a pair is reachable when half of the departures do):
    AM 06-09 (15 min)   MD 09-15 (30 min)   PM 15-19 (15 min)   NT 19-23 (30 min)
Access:
    walk   access and egress walks within 1,600 m at 1.23 m/s with beeline factor 1.3 (the base_transit2024 convention)
    drive  access by car within 15 km of the origin centroid at an effective 25 km/h on the beeline (teleported 9.0 m/s, factor
           1.3), egress walk within 1,600 m.  Used for the drive-access transit alternative (park and ride, kiss and ride).
Raw output per period and access: work/skims/raptor_<access>_<P>.csv.gz with FROM,TO,ALL,BUS,RAILSHARE,ACCESS,EGRESS,WAIT,TRANSFERS
(minutes; in-vehicle time incl. transfer walks and waits = ALL - ACCESS - EGRESS - WAIT).  Pairs not in the file have no path."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, os, subprocess, time
ROOT = PROJECT_ROOT; V = WORKSPACE
HERE = f"{V}/3_abit/mode_choice"; OUT = f"{HERE}/work/skims"; CLS = f"{HERE}/work/tsclasses"
JAR = f"{MATSIM_HOME}/code/matsim-run/target/baltimore-matsim-1.0.jar"
# regional schedule: every feed of 4_matsim/transit/merge_gtfs.py without the clip to the Maryland road network (merge_gtfs_full.py:
# WMATA Metrorail and Metrobus in DC and Virginia, Ride On, TheBus, MTA, MARC, Amtrak), converted unmapped by pt2matsim
# Gtfs2TransitSchedule (service day Wednesday 2026-10-21); TransitSkim gives unmapped routes artificial links (the raptor routes on
# the timetable).  The assignment's mapped schedule (4_matsim/transit/transitSchedule_2024) stops at the Maryland network.
NET = f"{V}/4_matsim/transit/network_2024_pt.xml.gz"; SCH = f"{HERE}/work/gtfs_full/schedule_unmapped.xml.gz"; VEH = f"{HERE}/work/gtfs_full/vehicles.xml.gz"
CENT = f"{V}/pipeline/test/skims/transit_2024/centroids.csv"
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
