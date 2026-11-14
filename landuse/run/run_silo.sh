#!/usr/bin/env bash
: "${MILES_HOME:=$(cd "$(dirname "$0")/../.." && pwd)}"
: "${MILES_WORKSPACE:?run through the miles command, or set MILES_WORKSPACE}"
# Run the rebuilt SILO (branch baltimore-2026) on a properties file.  Usage: bash landuse/run/run_silo.sh <properties> [xmx]
# Classpath: the freshly built reactor jars first (maryland, siloCore, matsim2silo; built in WORKSPACE/2_silo/engine), then the
# Maven dependency classpath of landuse/run/classpath.txt (jar paths under $HOME/.m2, expanded here).
set -euo pipefail
PROPS="${1:?properties file}"; XMX="${2:-28g}"
S="${MILES_WORKSPACE}/2_silo"; E="$S/engine"
# compiled class directories first (always current after mvn compile), then the reactor jars, then the dependency classpath
# stage 2b: the schools extension (extensions/schools) is a reactor module, compiled with -pl siloCore,extensions/schools,useCases/maryland
CP="$E/useCases/maryland/target/classes:$E/siloCore/target/classes:$E/extensions/schools/target/classes:$E/useCases/matsim2silo/target/classes:$E/useCases/maryland/target/maryland-0.1.0-SNAPSHOT.jar:$E/siloCore/target/siloCore-0.1.0-SNAPSHOT.jar:$E/extensions/schools/target/schools-0.1.0-SNAPSHOT.jar:$E/useCases/matsim2silo/target/matsim2silo-0.1.0-SNAPSHOT.jar:$(sed "s|\$HOME|$HOME|g" "$MILES_HOME/landuse/run/classpath.txt")"
JAVA="$(/usr/libexec/java_home -v 21)/bin/java"
NAME="$(basename "$PROPS" .properties)"; LOG="$S/run/logs/$NAME.log"; mkdir -p "$S/run/logs"
echo "[run_silo] $NAME  xmx=$XMX  $(date '+%F %T')" | tee -a "$S/run/logs/runs.log"
"$JAVA" -Xmx"$XMX" ${SILO_JAVA_OPTS:-} -Dlog4j2.formatMsgNoLookups=true -Dlog4j2.configurationFile="$MILES_HOME/landuse/run/log4j2_quiet.xml" -cp "$CP" de.tum.bgu.msm.run.SiloMstm "$PROPS" > "$LOG" 2>&1; rc=$?
echo "[run_silo] $NAME exit $rc  $(date '+%F %T')" | tee -a "$S/run/logs/runs.log"; exit $rc
