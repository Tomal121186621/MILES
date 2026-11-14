#!/bin/sh
: "${ORIOLE_WORKSPACE:?run through the oriole command, or set ORIOLE_WORKSPACE}"
# Download the five MTA Maryland GTFS static feeds (URLs from https://www.mta.maryland.gov/developer-resources) into
# WORKSPACE/data/raw/mta_gtfs/ and record the download date.  The MTA URLs redirect to mdotmta-gtfs.s3.amazonaws.com.
# Usage: sh assignment/network/fetch_gtfs.sh
D="$ORIOLE_WORKSPACE/data/raw/mta_gtfs"; mkdir -p "$D"
for f in local-bus light-rail metro marc commuter-bus; do
  curl -sL -o "$D/mta_$f.zip" -w "$f %{http_code} %{size_download} %{url_effective}\n" "https://feeds.mta.maryland.gov/gtfs/$f"
done | tee "$D/download_$(date -u +%Y-%m-%d).log"
