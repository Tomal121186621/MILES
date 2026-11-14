#!/bin/bash
: "${TERP_HOME:=$(cd "$(dirname "$0")/.." && pwd)}"
: "${TERP_WORKSPACE:?run through the terp command, or set TERP_WORKSPACE}"
# MATSim 2024 validation runs with the re-specified ABIT models (2026-11-10; copy of run_seeds.sh: population of the ABIT 2024 replication fin24_s08 of run_respec, runs root pipeline/runs_respec, link hours data/link_hours_respec; same config, network, tolls, iterations, sample and seeds). Record: MATSim 2024 validation runs (2026-11-02): seeds 1-5 one after the other, 10 % sample, 100 iterations, network 2024 (Key Bridge closed),
# harbor tolls 2024, population without synthetic traffic (--no-gateways: all chain persons touching the BMR, no gateways, no inflow cap; 2026-11-02 restart) of the ABIT 2024 replication fin24_tw_s01, USDOT value of time (run_chain.py MATSIM_STRAT).
# After each seed: hourly link volumes extracted from the final events (extract_link_hours.py), then the events files and the
# duplicate iteration plans are deleted (disk); kept: output_plans, final link stats, score/mode/travel statistics, logs.
# Stops (does not start the next seed) when free disk falls below MIN_FREE_GB.
# Usage: nohup bash assignment/run_seeds.sh [first_seed] [last_seed] > run_seeds.out 2>&1 &
V="${TERP_WORKSPACE}"
R="$V/pipeline/runs_respec"; OUTD="$V/4_matsim/validation/data/link_hours_respec"; LOG="$V/4_matsim/validation/run_seeds_respec.log"
TOLL="$V/4_matsim/network/roadpricing_HARB_2024.xml"; POP="$V/pipeline/runs/matsim_pop/2024_respec/population_2024_scc.xml.gz"   # pipeline/snap_to_network.py applied: activities kept off the 7 dead-end car links
MIN_FREE_GB=7; mkdir -p "$OUTD"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
free_gb() { df -g "$V" | awk 'NR==2{print $4}'; }
for s in $(seq "${1:-1}" "${2:-5}"); do
  d="$R/matsim/2024_s$s"
  if [ -f "$OUTD/link_hours_s$s.csv.gz" ] && [ -f "$d/.done.json" ]; then log "seed $s: done, skipped"; continue; fi
  f=$(free_gb); if [ "$f" -lt "$MIN_FREE_GB" ]; then log "seed $s: NOT started, free disk ${f} GB < ${MIN_FREE_GB} GB - stop"; exit 2; fi
  log "seed $s: start (free disk ${f} GB)"; t0=$(date +%s)
  python3 "${TERP_HOME}/pipeline/run_chain.py" --runs-root "$R" matsim 2024 2024 "$s" --iterations 100 --sample 0.1 --toll "$TOLL" --plans "$POP" >> "$LOG" 2>&1
  rc=$?; log "seed $s: run_chain exit $rc after $(( ($(date +%s) - t0) / 60 )) min"
  if [ $rc -ne 0 ] || [ ! -f "$d/output_events.xml.gz" ]; then log "seed $s: FAILED - stop"; exit 1; fi
  cp "$V/pipeline/logs/matsim_2024_s$s.log" "$d/matsim_console.log" 2>/dev/null
  python3 "${TERP_HOME}/assignment/validation/extract_link_hours.py" "$d/output_events.xml.gz" "$d/output_transitVehicles.xml.gz" "$OUTD/link_hours_s$s.csv.gz" >> "$LOG" 2>&1
  if [ $? -ne 0 ]; then log "seed $s: extraction FAILED - events kept, stop"; exit 1; fi
  du -sh "$d" >> "$LOG"
  rm -f "$d/output_events.xml.gz" "$d"/ITERS/it.*/*.events.xml.gz "$d"/ITERS/it.*/*.plans.xml.gz "$d"/ITERS/it.*/*.trips.csv.gz "$d"/ITERS/it.*/*.legs.csv.gz
  log "seed $s: events and iteration plans deleted; kept $(du -sh "$d" | cut -f1); free disk $(free_gb) GB"
done
log "all seeds done"
