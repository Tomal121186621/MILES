# School location

!!! abstract "At a glance"

    | | |
    |---|---|
    | **Engine** | Inside SILO (Java), every simulated year |
    | **Code** | `landuse/schools` |
    | **Models** | Three multinomial logits: K–8, high school, college |
    | **Sensitive to** | Car time, attendance boundaries, enrolment and capacity, school composition |
    | **Produces** | The school of every student |


Every simulated year, inside SILO, students are assigned to schools by three multinomial logits over the zones with enrolment of
the student's band:

| Band | Zones | Observations |
|---|---|---|
| K–8 | 1,144 | 1,509 |
| High school | 719 | 668 |
| College | 141 | 673 |

Each model has a size term in which public enrolment inside the home's attendance boundary is a separate component,
car time, boundary terms and the own-race share of the zone's enrolment of the band. The K–8 and high-school models add
the share of enrolment in charter or magnet schools, and the K–8 model the test-score quality of the zone's public
schools (with a weaker effect for incomes under \$40k). The attendance boundary dominates public K–12 choice: an
in-boundary seat weighs about 470 times an out-of-boundary public seat in K–8 and 72 times in high school.

| Band | Parameters | Hold-out log-likelihood per student |
|---|---:|---:|
| K–8 | 13 | −1.953 |
| High school | 6 | −1.810 |
| College | 9 | −2.789 |

The own-race share is recomputed every year from the current students; quality and the charter-or-magnet share are
fixed inputs. Enrolment is an upper limit, enforced by shadow prices, and student status is aligned to the ACS
enrolment rates. Full estimates: [School location](../calibration-validation/estimates/schools.md).
