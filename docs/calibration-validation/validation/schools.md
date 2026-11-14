# School location

Students assigned to schools in every simulated year, against the survey students of the same counties and the ACS enrolment.

<div class="oriole-numbers">
<div><b>2 %</b><span>students by age, error against the ACS</span></div>
<div><b>1–4 min</b><span>assigned schools farther than surveyed</span></div>
<div><b>420×</b><span>weight of an in-boundary K–8 seat</span></div>
</div>

!!! info "How to read the figures"
    Orange: model; dark grey: observed; light grey: a second observed source. Error bars: range of the five land-use seeds or of the ten activity-model replications. Each panel shows one fit measure: for a distribution the total variation distance (TVD, percentage points of the population that would have to change class), otherwise the mean absolute percentage error (MAPE).

<figure markdown>
  ![](../../assets/img/validation/fig_s_val_stage2_schools.png)
  <figcaption>Schools, 2024 (2016 where stated). (a) students by age, 2024; (b) car time to school, 2024; (c) car time to school, 2016; (d) school in home county, 2024; (e) school zone holds the attendance-zone school, 2024; (f) car time to school, K–8, 2024; (g) car time to school, high school, 2024; (h) car time to school, college, 2024.</figcaption>
</figure>

## Scorecard

<div class="vsum"><b>8</b> comparisons · <span class="vb ok">1 within</span> <span class="vb close">5 close</span> <span class="vb out">2 outside</span></div>

| Compared variable | Fit | Result |
|---|---:|:---:|
| Students by age, 2024 | MAPE 2.0 % | <span class="vb ok">within</span> |
| Car time to school, 2024 | MAPE 12 % | <span class="vb out">outside</span> |
| Car time to school, 2016 | MAPE 8.3 % | <span class="vb close">close</span> |
| School in home county, 2024 | MAPE 8.3 % | <span class="vb close">close</span> |
| School zone holds the attendance-zone school, 2024 | MAPE 8.2 % | <span class="vb close">close</span> |
| Car time to school, k–8, 2024 | TVD 6.7 pp | <span class="vb close">close</span> |
| Car time to school, high school, 2024 | TVD 6.2 pp | <span class="vb close">close</span> |
| Car time to school, college, 2024 | TVD 11.8 pp | <span class="vb out">outside</span> |
