# Activities

MILES-Day is run on the observed households of the **survey hold-out half** (validation) and on the **2024 population** against independent sources: ATUS time-use diaries, the ACS 2024 commute and LODES. Error bars: ten replications.

<div class="miles-numbers">
<div><b>+1.2 %</b><span>activities on held-out households</span></div>
<div><b>≤ 2 pp</b><span>start times per hour (all types but shopping)</span></div>
<div><b>≤ 2.1 pp</b><span>tour mode shares, hold-out half</span></div>
<div><b>54.4 / 54.0 %</b><span>work in home county, model / ACS 2024</span></div>
</div>

## Estimation and validation strategy

TASHA was estimated on the 1996 Transportation Tomorrow Survey of Toronto and validated on the 2001 survey, a
different year (Roorda, Miller and Habib, 2008). No regional travel diary has been collected in Baltimore and Washington
since the 2017/18 Regional Travel Survey, so MILES-Day replaces the second survey year with a split of the households
and with independent sources for the forecast year.

| | TASHA (Roorda et al., 2008) | MILES-Day |
|---|---|---|
| Estimation data | Toronto travel survey, 1996 | Regional Travel Survey 2017/18, **estimation half** (10,889 households) |
| Verification | Same survey, same households | Estimation half: the model run on the observed households it was estimated on |
| Validation | Toronto travel survey, 2001 (another year) | **Hold-out half** (10,899 households), drawn at random by home county and household size, used in no estimation or calibration step |
| Chain test | – | The model run on the **synthetic population**, compared with the hold-out half: separates the error of the activity model from that of the population |
| Forecast year | 2001 households | **2024 population** of the land-use model against independent sources: ATUS 2021–24 time use, ACS 2024 commute, LODES flows |
| Replications | – | Ten per test; bands show their 90 % range |
| Measures | Start time, duration by start hour, trips per chain, distance by start hour; Kolmogorov–Smirnov D and P on hourly values | The same four, the same statistic; plus activities, distances and tour modes by type |

Every distribution, frequency and coefficient of MILES-Day comes from the estimation half; none is adjusted to the
hold-out half or to 2024 data. The hold-out half was consulted more than once during the specification search of some
models, so its fit is close to, but not fully, an independent test.

!!! info "How to read the figures"
    Orange: model; dark grey: observed; light grey: a second observed source. Error bars: range of the five land-use seeds or of the ten activity-model replications. Each panel shows one fit measure: for a distribution the total variation distance (TVD, percentage points of the population that would have to change class); for shares that are not one distribution, the mean absolute difference (MAD, percentage points); otherwise the mean absolute percentage error (MAPE).

## Main results

<figure markdown>
  ![](../../assets/img/validation/fig_val_stage3.png)
  <figcaption>Activity model against observed data. (a) activities per person, hold-out half; (b) mean distance, hold-out half; (c) tour mode, hold-out half; (d) car-driver trip length, hold-out half; (e) activities per person, 2024; (f) persons with the activity, 2024; (g) commute mode, 2024; (h) own-county work share, 2024.</figcaption>
</figure>

## TASHA-type validation

The four tests of TASHA's validation, in the same form, for the three settings. Observed: the weighted survey; model:
mean and 90 % band of ten replications; D and P: Kolmogorov–Smirnov statistic on the hourly values (TASHA reported P
above 0.86 for start times).

=== "Validation (hold-out half)"

    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_start_validation.png)
      <figcaption>Activity start times.</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_duration_validation.png)
      <figcaption>Mean activity duration by start hour.</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_distance_validation.png)
      <figcaption>Average distance to the activity by start hour (zone-to-zone distance for model and survey).</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_chains_validation.png)
      <figcaption>Trips per home-based chain.</figcaption>
    </figure>

=== "Verification (estimation half)"

    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_start_verification.png)
      <figcaption>Activity start times.</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_duration_verification.png)
      <figcaption>Mean activity duration by start hour.</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_distance_verification.png)
      <figcaption>Average distance to the activity by start hour.</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_chains_verification.png)
      <figcaption>Trips per home-based chain.</figcaption>
    </figure>

=== "Chain test (synthetic population)"

    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_start_chain.png)
      <figcaption>Activity start times, model on the synthetic population against the hold-out half.</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_duration_chain.png)
      <figcaption>Mean activity duration by start hour.</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_distance_chain.png)
      <figcaption>Average distance to the activity by start hour.</figcaption>
    </figure>
    <figure markdown>
      ![](../../assets/img/validation/tasha/fig_abit_chains_chain.png)
      <figcaption>Trips per home-based chain.</figcaption>
    </figure>

### Kolmogorov–Smirnov statistics

<span class="vb ok">P ≥ 0.05</span>: the model's hourly distribution is not distinguishable from the survey's at the 5 %
level. Durations of shopping and other activities are the exception: gaps between episodes follow from independently
drawn start times, and stays at home between tours are long.

| Measure | Activity | Verification<br>(estimation half) | Validation<br>(hold-out half) | Chain test<br>(synthetic population) |
|---|---|---|---|---|
| Start time | Work | D 0.083 · <span class="vb ok">P 1.00</span> | D 0.125 · <span class="vb ok">P 0.99</span> | D 0.125 · <span class="vb ok">P 0.99</span> |
| Start time | School | D 0.136 · <span class="vb ok">P 0.98</span> | D 0.190 · <span class="vb ok">P 0.80</span> | D 0.182 · <span class="vb ok">P 0.82</span> |
| Start time | Shopping | D 0.208 · <span class="vb ok">P 0.62</span> | D 0.208 · <span class="vb ok">P 0.62</span> | D 0.208 · <span class="vb ok">P 0.62</span> |
| Start time | Other | D 0.167 · <span class="vb ok">P 0.86</span> | D 0.167 · <span class="vb ok">P 0.86</span> | D 0.125 · <span class="vb ok">P 0.99</span> |
| Start time | Return home | D 0.125 · <span class="vb ok">P 0.99</span> | D 0.125 · <span class="vb ok">P 0.99</span> | D 0.125 · <span class="vb ok">P 0.99</span> |
| Start time | All activities | D 0.125 · <span class="vb ok">P 0.99</span> | D 0.167 · <span class="vb ok">P 0.86</span> | D 0.125 · <span class="vb ok">P 0.99</span> |
| Duration by start hour | Work | D 0.158 · <span class="vb ok">P 0.96</span> | D 0.158 · <span class="vb ok">P 0.96</span> | D 0.158 · <span class="vb ok">P 0.96</span> |
| Duration by start hour | School | D 0.143 · <span class="vb ok">P 1.00</span> | D 0.286 · <span class="vb ok">P 0.54</span> | D 0.286 · <span class="vb ok">P 0.54</span> |
| Duration by start hour | Shopping | D 0.294 · <span class="vb ok">P 0.39</span> | D 0.444 · <span class="vb out">P 0.04</span> | D 0.421 · <span class="vb out">P 0.05</span> |
| Duration by start hour | Other | D 0.478 · <span class="vb out">P 0.01</span> | D 0.391 · <span class="vb out">P 0.04</span> | D 0.435 · <span class="vb out">P 0.02</span> |
| Duration by start hour | Return home | D 0.211 · <span class="vb ok">P 0.74</span> | D 0.211 · <span class="vb ok">P 0.74</span> | D 0.211 · <span class="vb ok">P 0.74</span> |
| Duration by start hour | All activities | D 0.250 · <span class="vb ok">P 0.39</span> | D 0.261 · <span class="vb ok">P 0.36</span> | D 0.261 · <span class="vb ok">P 0.36</span> |
| Distance by start hour | All activities | D 0.208 · <span class="vb ok">P 0.62</span> | D 0.250 · <span class="vb ok">P 0.39</span> | D 0.250 · <span class="vb ok">P 0.39</span> |
| Trips per home-based chain | All activities | D 0.250 · <span class="vb ok">P 0.93</span> | D 0.250 · <span class="vb ok">P 0.93</span> | D 0.250 · <span class="vb ok">P 0.93</span> |


## In detail

=== "Hold-out households"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage3_survey.png)
      <figcaption>(a) activities per person, hold-out half; (b) mean distance, hold-out half; (c) activities per person by person type, hold-out half; (d) activities per person by home area, hold-out half.</figcaption>
    </figure>
    

=== "Hold-out, more"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage3_survey_b.png)
      <figcaption>(a) mean distance by person type, hold-out half; (b) mean distance by home area, hold-out half; (c) activity start time, hold-out half; (d) mean activity duration, hold-out half; (e) trips per person, hold-out half; (f) mean trip length, hold-out half.</figcaption>
    </figure>
    

=== "Modes"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage3_modes.png)
      <figcaption>(a) tour mode, work, hold-out half; (b) tour mode, school, hold-out half; (c) tour mode, shopping, hold-out half; (d) tour mode, recreation, hold-out half; (e) tour mode, accompanying, hold-out half; (f) tour mode, other errands, hold-out half.</figcaption>
    </figure>
    

=== "Modes, more"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage3_modes_b.png)
      <figcaption>(a) car-driver share of tours by household cars; (b) car-driver share of tours by distance; (c) car-driver trip length, hold-out half; (d) discretionary activities of workers on workdays, hold-out half; (e) discretionary activities on separate tours, hold-out half.</figcaption>
    </figure>
    

=== "2024 activities"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage3_y2024.png)
      <figcaption>(a) activities per person, 2024; (b) persons with the activity, 2024; (c) mean activity duration, 2024; (d) activity start time, 2024; (e) trip mode, all trips, 2024; (f) commute mode, 2024.</figcaption>
    </figure>
    

=== "2024 geography"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage3_y2024b.png)
      <figcaption>(a) own-county work share, 2024; (b) activities per person, Baltimore area, 2024; (c) mean distance, Baltimore area, 2024; (d) trips per home-based chain, 2024.</figcaption>
    </figure>
    

=== "2024 commute"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage3_commute.png)
      <figcaption>(a) departure from home to work, 2024; (b) travel time to work, 2024; (c) commute shares, 2024; (d) travel time to work, 2024.</figcaption>
    </figure>
    

## Scorecard

<div class="vsum"><b>43</b> comparisons · <span class="vb ok">25 within</span> <span class="vb close">13 close</span> <span class="vb out">5 outside</span></div>

| Compared variable | Fit | Result | Note |
|---|---:|:---:|---|
| Activities per person, hold-out half | MAPE 2.8 % | <span class="vb ok">within</span> |  |
| Mean distance, hold-out half | MAPE 2.6 % | <span class="vb ok">within</span> |  |
| Tour mode, hold-out half | TVD 2.6 pp | <span class="vb ok">within</span> |  |
| Car-driver trip length, hold-out half | MAD 0.6 pp | <span class="vb ok">within</span> |  |
| Activities per person, 2024 | MAPE 24 % | <span class="vb out">outside</span> | ATUS: 279 Maryland diaries |
| Persons with the activity, 2024 | MAD 8.4 pp | <span class="vb close">close</span> | ATUS: 279 Maryland diaries |
| Commute mode, 2024 | TVD 7.8 pp | <span class="vb close">close</span> |  |
| Own-county work share, 2024 | MAD 2.8 pp | <span class="vb ok">within</span> |  |
| Activities per person, hold-out half | MAPE 2.7 % | <span class="vb ok">within</span> |  |
| Mean distance, hold-out half | MAPE 2.6 % | <span class="vb ok">within</span> |  |
| Activities per person by person type, hold-out half | MAPE 3.2 % | <span class="vb ok">within</span> |  |
| Activities per person by home area, hold-out half | MAPE 1.6 % | <span class="vb ok">within</span> |  |
| Mean distance by person type, hold-out half | MAPE 7.1 % | <span class="vb close">close</span> |  |
| Mean distance by home area, hold-out half | MAPE 6.1 % | <span class="vb close">close</span> |  |
| Activity start time, hold-out half | TVD 4.0 pp | <span class="vb ok">within</span> |  |
| Mean activity duration, hold-out half | MAPE 11 % | <span class="vb out">outside</span> |  |
| Trips per person, hold-out half | MAPE 0.7 % | <span class="vb ok">within</span> |  |
| Mean trip length, hold-out half | MAPE 5.2 % | <span class="vb close">close</span> |  |
| Tour mode, work, hold-out half | TVD 6.4 pp | <span class="vb close">close</span> |  |
| Tour mode, school, hold-out half | TVD 1.8 pp | <span class="vb ok">within</span> |  |
| Tour mode, shopping, hold-out half | TVD 5.1 pp | <span class="vb close">close</span> |  |
| Tour mode, recreation, hold-out half | TVD 2.5 pp | <span class="vb ok">within</span> |  |
| Tour mode, accompanying, hold-out half | TVD 5.0 pp | <span class="vb ok">within</span> |  |
| Tour mode, other errands, hold-out half | TVD 1.5 pp | <span class="vb ok">within</span> |  |
| Car-driver share of tours by household cars | MAD 1.7 pp | <span class="vb ok">within</span> |  |
| Car-driver share of tours by distance | MAD 2.2 pp | <span class="vb ok">within</span> |  |
| Car-driver trip length, hold-out half | MAD 0.6 pp | <span class="vb ok">within</span> |  |
| Discretionary activities of workers on workdays, hold-out half | TVD 3.1 pp | <span class="vb ok">within</span> |  |
| Discretionary activities on separate tours, hold-out half | MAD 0.7 pp | <span class="vb ok">within</span> |  |
| Activities per person, 2024 | MAPE 24 % | <span class="vb out">outside</span> | ATUS: 279 Maryland diaries |
| Persons with the activity, 2024 | MAD 8.4 pp | <span class="vb close">close</span> | ATUS: 279 Maryland diaries |
| Mean activity duration, 2024 | MAPE 9.6 % | <span class="vb close">close</span> |  |
| Activity start time, 2024 | TVD 4.5 pp | <span class="vb ok">within</span> |  |
| Trip mode, all trips, 2024 | TVD 2.5 pp | <span class="vb ok">within</span> |  |
| Commute mode, 2024 | TVD 7.8 pp | <span class="vb close">close</span> |  |
| Departure from home to work, 2024 | TVD 7.7 pp | <span class="vb close">close</span> |  |
| Travel time to work, 2024 | TVD 16.1 pp | <span class="vb out">outside</span> | ACS: self-reported door-to-door time, rounded |
| Commute shares, 2024 | MAD 8.5 pp | <span class="vb close">close</span> |  |
| Travel time to work, 2024 | MAPE 14 % | <span class="vb out">outside</span> | ACS: self-reported door-to-door time, rounded |
| Own-county work share, 2024 | MAD 3.6 pp | <span class="vb ok">within</span> |  |
| Activities per person, baltimore area, 2024 | MAPE 3.5 % | <span class="vb ok">within</span> |  |
| Mean distance, baltimore area, 2024 | MAPE 9.6 % | <span class="vb close">close</span> |  |
| Trips per home-based chain, 2024 | MAD 1.7 pp | <span class="vb ok">within</span> |  |
