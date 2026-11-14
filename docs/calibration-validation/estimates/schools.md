# School location

Three multinomial logits over the zones with enrolment of the student's band, estimated on the survey estimation half with the full choice set.

!!! note "Reading the tables"
    Coefficient: maximum-likelihood estimate with robust (sandwich) standard error; \*\*\* p < 0.001, \*\* p < 0.01, \* p < 0.05. N: observations; K: estimated parameters; LL(β̂): log-likelihood at the estimates; ρ̄²: adjusted rho-square. The same tables can be re-estimated with Biogeme from the estimation package.

### School location: kindergarten to grade 8

Choice of the school zone over all zones with K–8 enrolment, with the attendance boundary as a separate size component. Survey estimation half.

<div class="estfit"><span>N = 1,509</span><span>K = 9</span><span>LL(β̂) = −2,941.0</span><span>ρ̄² = 0.717</span><span>Hold-out: LL per student −1.983</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Size*** | | | |
| Size coefficient mu | 0.4954\*\*\* | 0.0491 | < 0.001 |
| In-boundary public enrolment, log weight | 6.0411\*\*\* | 0.5019 | < 0.001 |
| Private enrolment, log weight | 0.7823\* | 0.3358 | 0.020 |
| ***Car time*** | | | |
| Car time (min) | −0.0963\*\*\* | 0.0183 | < 0.001 |
| Ln(1+time) | −0.7727\* | 0.3649 | 0.034 |
| ***Boundaries*** | | | |
| Same zone | 0.3406\*\*\* | 0.1021 | < 0.001 |
| Other county × public share | −2.2521\*\*\* | 0.2016 | < 0.001 |
| ***Interactions with car time*** | | | |
| Time × no car | −0.1100\*\* | 0.0353 | 0.002 |
| Time × fewer cars than drivers | −0.0282 | 0.0149 | 0.058 |

### School location: high school

Choice of the school zone over all zones with high-school enrolment. Survey estimation half.

<div class="estfit"><span>N = 668</span><span>K = 5</span><span>LL(β̂) = −1,243.3</span><span>ρ̄² = 0.716</span><span>Hold-out: LL per student −1.853</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Size*** | | | |
| Size coefficient mu | 0.6788\*\*\* | 0.0613 | < 0.001 |
| In-boundary public enrolment, log weight | 4.2150\*\*\* | 0.4252 | < 0.001 |
| Private enrolment, log weight | 0.2471 | 0.2737 | 0.366 |
| ***Car time*** | | | |
| Car time (min) | −0.1044\*\*\* | 0.0071 | < 0.001 |
| ***Boundaries*** | | | |
| Other county × public share | −2.5167\*\*\* | 0.3076 | < 0.001 |

### School location: college

Choice of the college zone over all zones with college enrolment. Survey estimation half.

<div class="estfit"><span>N = 673</span><span>K = 9</span><span>LL(β̂) = −1,827.8</span><span>ρ̄² = 0.448</span><span>Hold-out: LL per student −2.824</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Size*** | | | |
| Size coefficient mu | 0.5362\*\*\* | 0.0309 | < 0.001 |
| Private 4-year enrolment, log weight | −1.2928\*\*\* | 0.2529 | < 0.001 |
| 2-year enrolment, log weight | −0.8526\*\*\* | 0.2257 | < 0.001 |
| ***Car time*** | | | |
| Car time (min) | −0.0385\*\*\* | 0.0085 | < 0.001 |
| Ln(1+time) | −1.1630\*\*\* | 0.3180 | < 0.001 |
| ***Boundaries*** | | | |
| Other county | −0.5675\*\*\* | 0.1325 | < 0.001 |
| Other state | −0.6713\*\*\* | 0.1346 | < 0.001 |
| ***Interactions with car time*** | | | |
| Time × income <40k | −0.0218 | 0.0118 | 0.064 |
| Time × income 125k+ | 0.0174\*\* | 0.0054 | 0.001 |

