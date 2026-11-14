#!/bin/sh
# Download the five MTA Maryland GTFS static feeds (URLs from https://www.mta.maryland.gov/developer-resources) into
# Validation_2026/data/raw/mta_gtfs/ and record the download date.  The MTA URLs redirect to mdotmta-gtfs.s3.amazonaws.com.
D="$(cd "$(dirname "$0")/../../data" && pwd)/raw/mta_gtfs"; mkdir -p "$D"
for f in local-bus light-rail metro marc commuter-bus; do
  curl -sL -o "$D/mta_$f.zip" -w "$f %{http_code} %{size_download} %{url_effective}\n" "https://feeds.mta.maryland.gov/gtfs/$f"
done | tee "$D/download_$(date -u +%Y-%m-%d).log"
