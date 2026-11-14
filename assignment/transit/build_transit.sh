#!/bin/sh
# Build the MATSim transit input of the integrated loop (TRANSIT_BUILD.md): all GTFS feeds of the network area -> one weekday ->
# pt2matsim schedule -> shape-guided mapping onto network_2024 and network_2026 -> loop/U-turn cleaning -> vehicles -> checks.
# Every Java process <= 9 GB, one at a time.  Run from anywhere: sh 4_matsim/transit/build_transit.sh
set -e
T="$(cd "$(dirname "$0")" && pwd)"; V="$(cd "$T/../.." && pwd)"; JH=$(/usr/libexec/java_home -v 21); J="$JH/bin/java"
PT2="$V/../Updated MATSim/tools/pt2matsim/target/pt2matsim-24.4-shaded.jar"
mkdir -p "$T/logs" "$T/work"
python3 -I "$T/merge_gtfs.py" "$V/data/raw" "$V/4_matsim/network/network_2024.xml.gz" "$T/gtfs_merged" > "$T/logs/merge_gtfs.log" 2>&1
"$J" -Xmx8g -cp "$PT2" org.matsim.pt2matsim.run.Gtfs2TransitSchedule "$T/gtfs_merged/" 20261021 EPSG:26985 "$T/work/schedule_unmapped.xml.gz" "$T/work/transitVehicles_gtfs.xml.gz" > "$T/logs/gtfs2matsim.log" 2>&1
"$JH/bin/javac" -nowarn -d "$T/java/classes" -cp "$PT2" "$T/java/MapWithShapes.java"
for Y in 2024 2026; do
  python3 -I "$T/clean_network.py" "$V/4_matsim/network/network_$Y.xml.gz" "$T/work/network_${Y}_clean.xml.gz" > "$T/logs/clean_network_$Y.log"
  python3 -I "$T/make_ptmapper_config.py" "$T/ptmapper_config_$Y.xml" "$T/work/network_${Y}_clean.xml.gz" "$T/work/schedule_unmapped.xml.gz" "$T/network_${Y}_pt.xml.gz" "$T/work/transitSchedule_${Y}_mapped.xml.gz" \
      travelCostType=travelTime candidateDistanceMultiplier=1.2 maxLinkCandidateDistance=90.0 nLinkThreshold=6 routingWithCandidateDistance=true maxTravelCostFactor=5.0 scheduleFreespeedModes=artificial,rail,subway numOfThreads=10 > /dev/null
  "$J" -Xmx9g -Dcorridors.parallel=true -cp "$T/java/classes:$PT2" de.umd.transit.MapWithShapes "$T/ptmapper_config_$Y.xml" "$T/gtfs_merged/shapes.txt" EPSG:26985 300 100 > "$T/logs/ptmapper_$Y.log" 2>&1
  python3 -I "$T/clean_routes.py" "$T/work/transitSchedule_${Y}_mapped.xml.gz" "$T/network_${Y}_pt.xml.gz" "$T/transitSchedule_$Y.xml.gz" "$T/logs/clean_routes_$Y.json" > "$T/logs/clean_routes_$Y.log"
  python3 -I "$T/vehicle_types.py" "$T/transitSchedule_$Y.xml.gz" "$T/transitVehicles_$Y.xml.gz" > "$T/logs/vehicle_types_$Y.log"
  "$J" -Xmx8g -cp "$PT2" org.matsim.pt2matsim.run.CheckMappedSchedulePlausibility "$T/transitSchedule_$Y.xml.gz" "$T/network_${Y}_pt.xml.gz" EPSG:26985 "$T/plausibility_$Y/" > "$T/logs/plausibility_$Y.log" 2>&1 || true   # the last step (histogram png) fails on the JAI image plugin; the csv and geojson are written before
  python3 -I "$T/validate_mapping.py" "$T/transitSchedule_$Y.xml.gz" "$T/network_${Y}_pt.xml.gz" "$V/4_matsim/network/network_$Y.xml.gz" "$T/gtfs_merged" "$V/data/transit_gtfs_headways_core.csv" "$T/validation_$Y.json" "$T/plausibility_$Y/allPlausibilityWarnings.csv" > "$T/logs/validate_$Y.log" 2>&1
done
echo "transit build done"
