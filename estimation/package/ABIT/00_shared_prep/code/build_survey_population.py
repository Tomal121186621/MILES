#!/usr/bin/env python3
"""Survey population of both halves (survey_population.build, unchanged): households, persons, dwellings and the person map of
the RTS households in the DAYMAP input format.

    python3 build_survey_population.py [--rebuild-zone-files]
        reads  raw survey files, the split (provided 00_shared_data/rts_2017_18/split), schools_2016.csv (00_shared_data/zones)
               tract_zone.csv and zone_population_2016.csv: provided copies unless --rebuild-zone-files, which rebuilds them from
               raw/census_gazetteer_2010/Gaz_tracts_national.txt + raw/mstm_zone_system (geopandas) and
               raw/synthetic_population_2016/{pp,dd}_2016.csv
        writes rebuilt/rts_2017_18/survey_pop/{tract_zone.csv, zone_population_2016.csv, estimation/*, validation/*}
"""
import os, sys, shutil
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pkg_paths import SHARED, out
import survey_population as SP      # noqa: E402

od = os.path.dirname(out("rts_2017_18/survey_pop/x"))
if "--rebuild-zone-files" not in sys.argv:
    for f in ["tract_zone.csv", "zone_population_2016.csv"]:
        shutil.copy(f"{SHARED}/rts_2017_18/survey_pop/{f}", f"{od}/{f}")
SP.OUTD = od
SP.tract_zone(); SP.zone_population()
for half in ["estimation", "validation"]:
    SP.build(half)
