#!/bin/sh
: "${ORIOLE_WORKSPACE:?run through the oriole command, or set ORIOLE_WORKSPACE}"
# Usage: sh assignment/transit/fetch_gtfs_regional.sh
# Download the GTFS feeds of the regional operators (TRANSIT_BUILD.md, coverage table) into WORKSPACE/data/raw/<agency>/, one
# folder per agency, with a download log (agency, try, HTTP code, bytes, effective URL, sha256).  For every agency the official URL
# (Mobility Database catalog feeds_v2.csv, data/raw/mobilitydatabase/) is tried first, then the Mobility Database mirror
# (files.mobilitydatabase.org/<id>/latest.zip, the copy the catalog keeps of the official feed).  The files are not opened here.
R="$ORIOLE_WORKSPACE/data/raw"; DAY=$(date +%Y-%m-%d)
get() {  # agency  url...
  a="$1"; shift; mkdir -p "$R/$a"; i=0
  for u in "$@"; do
    i=$((i+1)); out="$R/$a/${a}_gtfs.zip"
    res=$(curl -sL --max-time 180 -A "Mozilla/5.0" -o "$out.part" -w "%{http_code} %{size_download} %{url_effective}" "$u")
    code=${res%% *}; sz=$(echo "$res" | cut -d' ' -f2)
    if [ "$code" = "200" ] && [ "$sz" -gt 1000 ] && unzip -tq "$out.part" >/dev/null 2>&1; then
      mv "$out.part" "$out"; echo "$a try$i OK $res sha256=$(shasum -a 256 "$out" | cut -c1-16)" | tee -a "$R/$a/download_$DAY.log"; return
    fi
    rm -f "$out.part"; echo "$a try$i FAIL $res" | tee -a "$R/$a/download_$DAY.log"
  done
}
get charm_city_circulator https://transportation.baltimorecity.gov/files/cccgtfs824zip https://files.mobilitydatabase.org/tld-288_1/latest.zip https://files.mobilitydatabase.org/ntd-30201/latest.zip https://files.mobilitydatabase.org/mdb-493/latest.zip
get rta_central_maryland http://data.trilliumtransit.com/gtfs/centralmarylandrta-md-us/centralmarylandrta-md-us.zip https://files.mobilitydatabase.org/mdb-489/latest.zip
get anne_arundel_transit https://www.aacounty.org/gtfs https://files.mobilitydatabase.org/ntd-30129/latest.zip
get annapolis_transit "https://www.arcgis.com/sharing/rest/content/items/c307923d57ab4871aff79491b4a1bfd3/data" https://files.mobilitydatabase.org/mdb-2285/latest.zip
get harford_transit_link https://files.mobilitydatabase.org/mdb-501/latest.zip https://github.com/mobilityequity/maryland-local-gtfs/raw/master/Harford_GTFS.zip
get carroll_transit https://files.mobilitydatabase.org/mdb-500/latest.zip https://github.com/mobilityequity/maryland-local-gtfs/raw/master/Carroll_GTFS.zip
get wmata_rail https://api.wmata.com/gtfs/rail-gtfs-static.zip https://files.mobilitydatabase.org/mdb-1847/latest.zip
get wmata_bus https://api.wmata.com/gtfs/bus-gtfs-static.zip https://files.mobilitydatabase.org/mdb-1846/latest.zip
get ride_on https://www.montgomerycountymd.gov/DOT-Transit/Resources/Files/GTFS/RideOnGTFS.zip https://files.mobilitydatabase.org/mdb-488/latest.zip
get thebus_pg https://data.trilliumtransit.com/gtfs/princegeorgescounty-md-us/princegeorgescounty-md-us.zip https://files.mobilitydatabase.org/mdb-477/latest.zip
get amtrak https://content.amtrak.com/content/gtfs/GTFS.zip https://files.mobilitydatabase.org/mdb-11/latest.zip
get harbor_connector http://data.trilliumtransit.com/gtfs/harborconnector-md-us/harborconnector-md-us.zip https://files.mobilitydatabase.org/mdb-618/latest.zip
get towson_loop https://passio3.com/towson/passioTransit/gtfs/google_transit.zip https://files.mobilitydatabase.org/mdb-1784/latest.zip
get bethesda_circulator https://files.mobilitydatabase.org/mdb-231/latest.zip https://github.com/transitland/gtfs-archives-not-hosted-elsewhere/raw/master/bethesdacirculator-md-us.zip
