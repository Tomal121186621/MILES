# Inputs of the TASHA distributions

All inputs are shared, in `../../../00_shared_data`:
- `rts_2017_18/raw`: RTS_raw_flat_data.csv.gz, rts_trips_clean.csv.gz (trips, activities, tracts, weights)
- `rts_2017_18/split/rts_split.csv`: estimation / validation half of each household (only the estimation half is used)
- `rts_2017_18/survey_pop`: survey population of the estimation half (persons_map.csv, pp.csv: segments, weights, licence), tract_zone.csv
- `zones/zone_attributes.csv`, `skims/abit_base_2016/distance_auto.csv.gz`: distance matrix of the location bands
