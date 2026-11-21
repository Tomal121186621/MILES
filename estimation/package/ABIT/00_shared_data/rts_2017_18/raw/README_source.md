# RTS data for MAST Maryland calibration

**Calibration source = the CLEANED RTS** (per project decision) — the same deduplicated dataset our
tour-based MITO model was estimated & validated on, so MAST's Maryland calibration is consistent with
the rest of the pipeline.

| file | use |
|---|---|
| **`rts_trips_clean.csv`** | **CALIBRATION** — one row per trip, deduplicated (from `01_clean_rts.py`); per-trip mode/purpose/time/OD |
| **`rts_tours.csv`** | **CALIBRATION** — home-based tours extracted from the cleaned trips (tour_mode, n_trips, purpose) |
| `RTS_codebook_data_dictionary.xlsx` | reference — variable/code definitions |
| `RTS_raw_flat_data.csv` | source only (cartesian-inflated raw flat file) — **do NOT calibrate on this**; use the cleaned files |

## Calibration approach (next phase, after the hello-world run)
Build Maryland RTS **targets** from the cleaned data — tour-frequency rates, mode shares by purpose,
trip-length distributions, TOD profiles, stop rates — i.e. the same targets the tour-based model
matched. Then use MAST's `abm/calibration/` module (`CalibrationMuc` → `CalibrationMd`) to calibrate the
Munich-transferred activity-generation / destination / mode-choice / subtour models to these targets.
