# School location

Students assigned to schools in every simulated year, against the survey students of the same counties and the ACS
enrolment. Model: mean of the five land-use seeds.

<div class="miles-numbers">
<div><b>2 %</b><span>mean difference of the number of students by age from the ACS 2024 (aligned: a consistency check)</span></div>
<div><b>1–4 min</b><span>longer car time to the assigned school than the survey students report, by school level, 2024</span></div>
<div><b>2–11 pp</b><span>fewer students attend a school in their home county than in the survey</span></div>
</div>

<div class="miles-key" markdown>
<div class="miles-key-sw"><span><i style="background:#e8811a"></i>Model</span><span><i style="background:#3b4252"></i>Observed</span><span><i style="background:#b5b3ab"></i>Second observed source</span><span><i class="bar"></i>Range of the five land-use seeds</span></div>

| Fit measure in the panel title | Used for | Meaning |
|---|---|---|
| **TVD**, percentage points | a distribution (the classes add up to 100 %) | share of the students that would have to change class to match the observed |
| **MAPE**, % | rates, means and counts | mean absolute difference as a percentage of the observed value |

</div>

<figure markdown>
  ![](../../assets/img/validation/fig_s_val_stage2_schools.png)
  <figcaption>Schools in the chain against observed data. (a) students by age, 2024 (aligned); (b) car time to school, 2024; (c) car time to school, 2016; (d) school in home county, 2024; (e) school zone holds the attendance-zone school, 2024; (f) car time to school, K–8, 2024; (g) car time to school, high school, 2024; (h) car time to school, college, 2024. Observed: ACS enrolment (a); students of both halves of the travel survey 2017/18, weighted (b–h).</figcaption>
</figure>

Student numbers are a consistency check, because student status is aligned to the ACS enrolment rates. Model students
are restricted to the home counties of the survey students. The attendance-zone share counts homes covered by attendance
boundaries.

## Why the car time to school is too long

The assigned schools are 1 to 4 minutes farther by car than the schools of the survey students (2024: K–8 14.9 against
13.7 min, high school 17.5 against 15.7, college 34.7 against 30.3), and home-county shares are 2 to 11 points low. Most
of the gap is already present in the base year. It grows for high school and college as the population changes while
the school inventory and its capacities stay fixed. Enrolment is an upper limit, enforced by shadow prices, so students
who do not find a seat at a near school are sent to a farther one. The observed times are those of the 2017/18 survey
students, so the 2024 comparison also carries seven years of change in where students live.
