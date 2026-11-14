# School location

!!! abstract "At a glance"

    | | |
    |---|---|
    | **Engine** | Python, run after every SILO year |
    | **Code** | `landuse/schools` |
    | **Models** | Three multinomial logits: K–8, high school, college |
    | **Sensitive to** | Car time, attendance boundaries, enrolment and capacity |
    | **Produces** | The school of every student |


Every simulated year, students are assigned to schools by three multinomial logits over the zones with enrolment of
the student's band:

| Band | Zones | Observations |
|---|---|---|
| K–8 | 1,144 | 1,509 |
| High school | 719 | 668 |
| College | 141 | 673 |

Each model has a size term in which public enrolment inside the home's attendance zone is a separate component, car
time and boundary terms. The attendance boundary dominates public K–12 choice: an in-boundary seat weighs about 420
times an out-of-boundary public seat in K–8 and 68 times in high school. Enrolment is an upper limit, enforced by
shadow prices, and student status is aligned to the ACS enrolment rates.

