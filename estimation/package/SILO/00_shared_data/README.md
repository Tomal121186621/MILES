# Shared data

Sources used by several models, copied once (unchanged) from the project. Paths are relative to `Validation_2026/` unless they start with `../`.

| Folder | Files | Original location | Used by |
|---|---|---|---|
| `acs_pums_2014_2018_5yr/` | ACS PUMS 2014-2018 5-year, household (`csv_h*`) and person (`csv_p*`) files: DC, DE, MD, PA, VA, WV | `../inputs/pums_2018_5yr/` | dwelling and county (through `s03_pums.py`), car ownership |
| `rts_2017_18/` | `RTS_raw_flat_data.csv` (Regional Travel Survey 2017/18), `rts_split.csv` (estimation / validation halves), `tract_zone.csv` (census tract to model zone) | `../ABIT/input/rts/`, `data/`, `3_abit/survey_pop/` | zone level, workplace (licence) |
| `skims/` | `auto_peak_time.csv.gz` (peak car time), `transit_peak_time_d2d_2024.csv.gz` (transit door-to-door) | `2_silo/input/skims/`, `pipeline/test/skims/transit_2024/` | all except car ownership |
| `synthetic_population_2016/` | `dd_2016.csv` (dwellings), `hh_2016.csv` (households) | `2_silo/input/microData/` | zone level (dwellings by type, costs, income shares), inclusive values |
| `zone_system/` | `zoneSystem.csv`, `zones.shp/.shx/.dbf/.prj` (zone polygons), `crimeIndex.csv`; `zoneSystem_inputs_folder.csv` (zone areas used by car ownership) | `2_silo/input/`, `../inputs/zoneSystem.csv` | all |
| `accessibility/` | `accessibility_2016_new_multimodal.csv` (zone level and inclusive values), `accessibility_2016_new.csv` (car-based, zone specification search), `accessibility_2016.csv` (car ownership, workplace), `accessibility_2016_detail.csv` | `side_experiments/respec_2026-11/step_by_step/accessibility_new/`, `data/` | zone, county, car ownership, workplace |
| `resloc_work/` | `pums_movers_est.parquet`, `pums_pool_est.parquet`, `geo_*.csv`, `zone_landuse_2016.csv`, `region_models_final.pkl`, earlier zone and dwelling estimates read by `s06_region.py` (`zone_beta_final.npy`, `dwelling_beta.npy`, names, `dwelling_final.json`) | `2_silo/resloc/work/`, `side_experiments/respec_2026-11/step_by_step/residential/` | dwelling, zone, county, car ownership |
| `county_attributes/` | `seda_county_pool_cs_4.1.csv` (SEDA 4.1 school achievement) | `data/raw/resloc/` | county |
| `school_choice_work/` | students, location mixtures, attendance boundaries, enrolment by zone (`*.parquet`), `final_*.json` | `2_silo/schoolchoice/work/` | the three school models |

Not copied (large, not needed by the final models or only by upstream scripts): see the `input/data/raw/README.md` of each model.
