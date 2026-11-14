# Synthetic population

The 2016 synthetic population against the ACS PUMS 2014–2018 of Maryland, the held-out PUMS test split, county estimates, LODES jobs and the reported commutes of the travel survey.

<div class="miles-numbers">
<div><b>≤ 5.3 pp</b><span>TVD of every attribute, Maryland</span></div>
<div><b>97 %</b><span>of held-out person combinations generated</span></div>
<div><b>96.5 %</b><span>of PUMA × class cells within ±5 pp</span></div>
<div><b>33.7 / 34.2</b><span>min home–work car time, model / survey</span></div>
</div>

!!! info "How to read the figures"
    Orange: model; dark grey: observed; light grey: a second observed source. Error bars: range of the five land-use seeds or of the ten activity-model replications. Each panel shows one fit measure: for a distribution the total variation distance (TVD, percentage points of the population that would have to change class); for shares that are not one distribution, the mean absolute difference (MAD, percentage points); otherwise the mean absolute percentage error (MAPE).

## Main results

<figure markdown>
  ![](../../assets/img/validation/fig_val_stage1.png)
  <figcaption>Synthetic population of 2016 against observed data, Maryland. (a) persons by age; (b) employment status; (c) household size; (d) cars; (e) household income (2016 $); (f) dwelling type; (g) tenure; (h) home–work car time, 2016.</figcaption>
</figure>

## In detail

=== "Persons"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage1_persons.png)
      <figcaption>(a) persons by 5-year age; (b) sex; (c) employed (16+); (d) race and ethnicity; (e) nationality; (f) relationship.</figcaption>
    </figure>
    

=== "Households"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage1_households.png)
      <figcaption>(a) household size (detail); (b) cars (detail); (c) household income, detail (2016 $); (d) person income (2016 $).</figcaption>
    </figure>
    

=== "Dwellings"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage1_dwellings.png)
      <figcaption>(a) dwelling type; (b) tenure; (c) bedrooms; (d) year built; (e) monthly housing cost (2016 $).</figcaption>
    </figure>
    

=== "Counties and commute"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage1_spatial.png)
      <figcaption>(a) persons by county; (b) filled jobs by county; (c) home–work car time, 2016; (d) home–work distance, 2016.</figcaption>
    </figure>
    

=== "Joint tables and PUMAs"

    <figure markdown>
      ![](../../assets/img/validation/fig_s_val_stage1_joint.png)
      <figcaption>(a) household size × cars; (b) household income × cars; (c) households by PUMA (larger half); (d) households by PUMA (smaller half).</figcaption>
    </figure>
    

## Generative quality on held-out households

<figure markdown>
  ![](../../assets/img/val_pop_quality.png)
  <figcaption>SRMSE of every pair of attributes against the held-out test split: below the diagonal the synthetic population, above it the training split (the sampling floor).</figcaption>
</figure>

## Scorecard

<p class="vsum">31 comparisons: 25 within the limit, 3 close, 3 outside.</p>

| Compared variable | Fit | Result | Note |
|---|---:|:---:|---|
| Persons by age | TVD 0.1 pp | Within |  |
| Employment status | TVD 5.3 pp | Close |  |
| Household size | TVD 5.0 pp | Within |  |
| Cars | TVD 2.2 pp | Within |  |
| Household income (2016 $) | TVD 3.5 pp | Within |  |
| Dwelling type | TVD 2.4 pp | Within |  |
| Tenure | TVD 1.0 pp | Within |  |
| Home–work car time, 2016 | TVD 16.0 pp | Outside |  |
| Persons by 5-year age | TVD 2.9 pp | Within |  |
| Sex | TVD 0.5 pp | Within |  |
| Employed (16+) | TVD 2.5 pp | Within |  |
| Race and ethnicity | TVD 3.2 pp | Within |  |
| Nationality | TVD 1.8 pp | Within |  |
| Relationship | TVD 1.4 pp | Within |  |
| Household size (detail) | TVD 5.0 pp | Within |  |
| Cars (detail) | TVD 2.3 pp | Within |  |
| Household income, detail (2016 $) | TVD 3.8 pp | Within |  |
| Person income (2016 $) | TVD 1.7 pp | Within |  |
| Dwelling type | TVD 2.4 pp | Within |  |
| Tenure | TVD 1.0 pp | Within |  |
| Bedrooms | TVD 1.3 pp | Within |  |
| Year built | TVD 2.5 pp | Within |  |
| Monthly housing cost (2016 $) | TVD 2.2 pp | Within |  |
| Persons by county | MAPE 5.0 % | Within |  |
| Filled jobs by county | MAPE 7.2 % | Close |  |
| Home–work car time, 2016 | TVD 16.0 pp | Outside |  |
| Home–work distance, 2016 | TVD 11.4 pp | Outside |  |
| Household size × cars | TVD 5.0 pp | Within |  |
| Household income × cars | TVD 5.4 pp | Close |  |
| Households by puma (larger half) | MAPE 1.4 % | Within |  |
| Households by puma (smaller half) | MAPE 1.2 % | Within |  |
