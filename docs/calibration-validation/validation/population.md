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

<div class="vsum"><b>31</b> comparisons · <span class="vb ok">25 within</span> <span class="vb close">3 close</span> <span class="vb out">3 outside</span></div>

| Compared variable | Fit | Result | Note |
|---|---:|:---:|---|
| Persons by age | TVD 0.1 pp | <span class="vb ok">within</span> |  |
| Employment status | TVD 5.3 pp | <span class="vb close">close</span> |  |
| Household size | TVD 5.0 pp | <span class="vb ok">within</span> |  |
| Cars | TVD 2.2 pp | <span class="vb ok">within</span> |  |
| Household income (2016 $) | TVD 3.5 pp | <span class="vb ok">within</span> |  |
| Dwelling type | TVD 2.4 pp | <span class="vb ok">within</span> |  |
| Tenure | TVD 1.0 pp | <span class="vb ok">within</span> |  |
| Home–work car time, 2016 | TVD 16.0 pp | <span class="vb out">outside</span> |  |
| Persons by 5-year age | TVD 2.9 pp | <span class="vb ok">within</span> |  |
| Sex | TVD 0.5 pp | <span class="vb ok">within</span> |  |
| Employed (16+) | TVD 2.5 pp | <span class="vb ok">within</span> |  |
| Race and ethnicity | TVD 3.2 pp | <span class="vb ok">within</span> |  |
| Nationality | TVD 1.8 pp | <span class="vb ok">within</span> |  |
| Relationship | TVD 1.4 pp | <span class="vb ok">within</span> |  |
| Household size (detail) | TVD 5.0 pp | <span class="vb ok">within</span> |  |
| Cars (detail) | TVD 2.3 pp | <span class="vb ok">within</span> |  |
| Household income, detail (2016 $) | TVD 3.8 pp | <span class="vb ok">within</span> |  |
| Person income (2016 $) | TVD 1.7 pp | <span class="vb ok">within</span> |  |
| Dwelling type | TVD 2.4 pp | <span class="vb ok">within</span> |  |
| Tenure | TVD 1.0 pp | <span class="vb ok">within</span> |  |
| Bedrooms | TVD 1.3 pp | <span class="vb ok">within</span> |  |
| Year built | TVD 2.5 pp | <span class="vb ok">within</span> |  |
| Monthly housing cost (2016 $) | TVD 2.2 pp | <span class="vb ok">within</span> |  |
| Persons by county | MAPE 5.0 % | <span class="vb ok">within</span> |  |
| Filled jobs by county | MAPE 7.2 % | <span class="vb close">close</span> |  |
| Home–work car time, 2016 | TVD 16.0 pp | <span class="vb out">outside</span> |  |
| Home–work distance, 2016 | TVD 11.4 pp | <span class="vb out">outside</span> |  |
| Household size × cars | TVD 5.0 pp | <span class="vb ok">within</span> |  |
| Household income × cars | TVD 5.4 pp | <span class="vb close">close</span> |  |
| Households by puma (larger half) | MAPE 1.4 % | <span class="vb ok">within</span> |  |
| Households by puma (smaller half) | MAPE 1.2 % | <span class="vb ok">within</span> |  |
