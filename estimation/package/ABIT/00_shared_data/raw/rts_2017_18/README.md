# raw/rts_2017_18

**2017/18 Regional Travel Survey (Baltimore and Washington regions), household travel survey, weekday travel day** (Baltimore Metropolitan Council (BMC) and the National Capital Region Transportation Planning Board (TPB) at the Metropolitan Washington Council of Governments (MWCOG))

- URL: https://www.baltometro.org/ and https://www.mwcog.org/ (verify: no download page is documented in the project; the data are released on request)
- How: Request the 2017/18 Regional Travel Survey public-use files from BMC (Baltimore region) or MWCOG/TPB (Washington region). The project used one flat file in which every trip row carries its household and person fields (household, person, trip and vehicle tables joined): RTS_raw_flat_data.csv, with the codebook RTS_codebook_data_dictionary.xlsx (sheets Household, Person, Trip, Vehicle). The two cleaned files rts_trips_clean.csv (163,290 trips, deduplicated) and rts_tours.csv (57,627 home-based tours) were made by 01_clean_rts.py of the tour-based MITO project; that script is not on this machine, so these two files are shipped and cannot be rebuilt here. Survey weights: wthhfin, wtperfin, wttrdfin. If you receive separate household / person / trip / vehicle tables instead, join them on household_id, person_id (persno) and tripid to the flat layout of the codebook.
- Files: RTS_raw_flat_data.csv, RTS_codebook_data_dictionary.xlsx, rts_trips_clean.csv, rts_tours.csv
- Notes: Status: provided (copies). Licence: survey data of the MPOs; do not redistribute without their agreement.


- Files shipped: none in this folder (2026-11-17): the chain reads the survey from 00_shared_data/rts_2017_18/raw (.csv.gz copies), not from here.
