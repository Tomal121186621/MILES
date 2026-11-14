# Population code

`population/cvae` is a small PyTorch package with numbered steps; `population/post` adapts its output to the land-use
model.

## Library: `population/cvae/vaelib`

| Module | Role |
|---|---|
| `config` | paths, recode maps, income bands, cardinalities (base year 2016; up to 7 persons; 18 age bands) |
| `pums_io`, `preprocessing`, `crosswalks` | read and recode the PUMS; zone ↔ PUMA ↔ county |
| `dataset` | tensors and the 80/10/10 split by PUMA |
| `model` | the conditional VAE: one-hot input, PUMA embedding, encoder, decoder, household and person heads |
| `train` | cross-entropy + KL with free bits, β annealing, PUMA marginal loss, EMA, early stopping |
| `targets`, `generate` | PUMA targets; sampling |
| `income_bins` | dollar income drawn within the band from the PUMA's records |
| `consistency` | logical rules applied after sampling |
| `zones`, `dwelling`, `workplace`, `silo_export` | zone placement, dwelling attributes, workplaces, SILO files |
| `validate`, `diagnostics`, `analysis` | held-out validation and figures |

## Steps: `population/cvae/steps`

| Step | Does | Writes |
|---|---|---|
| `00_analyze_raw_acs.py` | statistics of the raw PUMS | `outputs/00_raw_analysis/` |
| `01_preprocess.py` | recode to the SILO schema | `01_preprocessed/{hh,pp}.parquet` |
| `02_build_targets.py` | PUMA marginal targets | `02_targets/` |
| `03_train.py` | train | `03_training/<tag>/checkpoint_best.pt`, history, split |
| `04_generate.py` | sample households | `04_generated/{hh,pp}.parquet` |
| `05_workplace.py` | workplaces | `05_workplace/` |
| `06_silo_export.py` | dwellings, SILO CSV | `06_silo_input/{hh,pp,dd,jj}_2016.csv` |
| `07_validate.py` | test-split validation | `07_validation/<tag>/` |
| `08_figures.py`, `09_study_areas.py` | figures; county checks | |

Training options: `--epochs --latent --hidden --enc-depth --dec-depth --free-bits --beta --w-marginal --tag --smoke`.

## Post-processing: `population/post`

| Script | Does |
|---|---|
| `rebalance_population.py` | redraw households per PUMA to ACS household and age controls; place them in zones |
| `zone_weights_2016.py`, `zone_weights_2020.py` | occupied housing units per zone from Census blocks |
| `employment_2016_lodes.py` | jobs by zone and type from LODES |
| `market_vacancy_2016.py`, `zone_vacancy_2016.py` | vacant dwellings on the market |
| `workplace_balanced.py` | gravity workplaces for residents outside the workplace-model area |
| `export_silo_base.py` | final 2016 base files |
| `validate_stage1*.py`, `figures_stage1.py` | validation tables and figures |
