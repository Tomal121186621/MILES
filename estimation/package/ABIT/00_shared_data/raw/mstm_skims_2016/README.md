# raw/mstm_skims_2016

**Maryland Statewide Transportation Model (MSTM) 2016 skims, 1,588 SMZ/RMZ zones** (Maryland Department of Transportation (MDOT SHA), via the project's MAST Maryland set-up (ABIT/input/mito_los/skims))

- URL: https://www.roads.maryland.gov/ (verify: MSTM data are provided by MDOT on request; no download page is documented)
- How: Obtain the MSTM 2016 skims in OMX format (matrix mat1, lookups origins / destinations): traveltime_auto.omx (AM-peak car time, min), distance_auto.omx (car distance, m), bus_tt.omx (bus time, min; 1000 = no path, 5 intrazonal), rail_tt00.omx (rail time, min; 0 = no rail path). convert_mstm_skims.py turns them into the csv.gz files the models read.
- Files: traveltime_auto.omx, distance_auto.omx, bus_tt.omx, rail_tt00.omx
- Notes: Status: the converted csv.gz are provided in 00_shared_data/skims/abit_base_2016 (bus_tt and rail_tt00 there are the 2016 MSTM transit skims; the location models read the 2024 door-to-door transit skims instead).


- Files shipped: bus_tt.omx, distance_auto.omx, rail_tt00.omx, traveltime_auto.omx, copied 2026-11-17 from ABIT/input/mito_los/skims (project-relative to VAE-SILO-MITO-MATSIM).
