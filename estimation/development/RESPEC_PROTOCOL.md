# Re-specification protocol for all estimated choice models (2026-11-06)

Author's request: the variable sets look unorganised and differ between similar models without a visible reason. Re-specify every
model with ONE documented rule per model family, test other variables, make the models more robust, then update the
article tables and the estimation-tables PDF. The chain (SILO calibration, MAST 20 runs, MATSim 5 seeds) is re-run AFTER the
author has reviewed the new estimates.

**Status (2026-11-06): side experiment.** Folder `side_experiments/respec_2026-11/`. It does not change the modelling stack,
the article or the validation results. The author decides later whether to adopt it; until then no swap-in, no chain re-run.

## Hard rules
- Never overwrite the current coefficient files, engine inputs, or article tables. Write everything under `respec/<family>/`
  (scripts, results, coefficient files in the engine's format, and article-format tables `respec/article_tables/<same name>.tex`).
- Estimation data, samples and splits stay as they are: ACS PUMS (estimation 80 % / held out 20 % / 2019-21 out of time) and
  the RTS estimation half / hold-out half. Never fit to traffic counts or to validation targets.
- Every variable must be one the chain can forecast for future years (produced by SILO, MAST, the skims or a fixed zone
  attribute). No race or ethnicity. No endogenous composition proxies (e.g. share of young workers in the workplace zone).
- Disk: about 2.4 GB free. Keep intermediate files small; do not write large caches; delete your own temp files.
- At most the two estimation agents run at once; Biogeme is in `~/.venvs/biogeme`.

## 1 Fixed variable blocks (same order, same labels in every table of a family)
Each family gets a base specification decided BEFORE estimation. The base is the same for every segment of the family
(e.g. all destination purposes, all tour-mode purposes, all income groups) and is kept even where a term is not
significant, unless it has the wrong sign with |t| > 2 (then report it and drop it, consistently explained).

Block order of every table:
1. Constants / alternative-specific constants
2. Impedance (time, distance, generalised cost, logsum)
3. Size term (μ, log weights)
4. Attributes of the alternative (zone, dwelling, county)
5. Boundaries and areas (same zone, other county/state, regions)
6. Person / household × impedance interactions
7. Person / household × alternative-attribute interactions
8. Nest / inclusive-value parameters

## 2 Candidate variables
For each family write the candidate list in advance (`respec/<family>/CANDIDATES.md`): variable, definition, data source,
expected sign, literature reason, forecastable by the chain (yes/how). Include variables NOT in the current models where the
data exist locally (`data/raw`: ACS tract, LODES, NCES, crime, FHFA, parking, NTD, GTFS, Census, PEP, ...). Candidates rejected
before estimation are listed with the reason (not forecastable, no data, endogenous, identical to another term).

## 3 Selection rule (same for all families)
Candidates are added block by block in the order above. A candidate is kept when all hold:
- expected sign;
- robust |t| ≥ 1.96;
- BIC lower AND hold-out log-likelihood higher than without it.
Within a family a candidate kept for one segment is tested in all segments; it is kept in all segments where it passes
(report where it does not, rather than silently dropping it). Then a final backward check of non-base terms with |t| < 1.96.

## 4 Robustness checks (report all, per model)
1. Swap halves: re-estimate on the hold-out half (RTS) or the held-out PUMS sample; LR test of equal coefficients;
   per-coefficient z of the difference.
2. Household (cluster) bootstrap of the standard errors, 100 replications where runtime allows (state the number), compared
   with the robust sandwich s.e.
3. Collinearity: correlation matrix of the estimates; flag |r| > 0.9; condition number of the Hessian.
4. Hold-out fit against the current model of record (log-likelihood per observation, plus the model's main aggregate
   check, e.g. trip-length KS, mode shares, flow correlation).
5. Plausibility: elasticities / values of time / willingness to pay within literature ranges.

## 5 Outputs per family
- `respec/<family>/REPORT.md`: candidates, selection log (LR, BIC, hold-out per step), final estimates, robustness checks,
  comparison with the current model of record (fit, key coefficients), and a plain-language list of what changed and why.
- New coefficient files in the engine format (same column names as the current files; name them `*_respec.csv`).
- Article-format tables `respec/article_tables/<current file name>.tex` (same layout and footnotes as the current tables,
  rows in the block order of section 1), and updated variables tables where variables were added or removed
  (`respec/article_tables/tab_*_vars.tex`).
