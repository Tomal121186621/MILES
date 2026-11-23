# Tour formation

Binary logits that shape the tours of DAYMAP (Daily Activity Model for Agent Plans): outings from the workplace, their mode, and returns home between episodes.

!!! note "Reading the tables"
    Coefficient: maximum-likelihood estimate, with significance stars \*\*\* p < 0.01, \*\* p < 0.05, \* p < 0.10; robust (sandwich) standard error; two-sided p-value. N: observations; K: estimated parameters; LL(β̂): log-likelihood at the estimates; ρ̄²: adjusted rho-square. Hold-out: fit on the held-out half of the data, which was also used in the specification search. "Reference": the omitted category; "—": removed from the model.

### Outing from the workplace

Whether a work episode at the usual workplace contains at least one outing.

<div class="estfit"><span>N = 8,613</span><span>K = 8</span><span>LL(β̂) = −3,061.5</span><span>ρ̄² = 0.486</span><span>Hold-out: LL −3,093.2</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Constant*** |  |  |  |
| Constant | −4.6092\*\*\* | 0.5251 | <0.001 |
| ***Work episode*** |  |  |  |
| Work duration, 0–4 h (per h) | 0.4033\*\*\* | 0.1439 | 0.005 |
| Work duration, 4–7 h (per h) | 0.5862\*\*\* | 0.0668 | <0.001 |
| Secondary work episode (arrival from 15:00) | −2.0156\*\*\* | 0.7207 | 0.005 |
| ***Time of day*** |  |  |  |
| Arrival at work 7:00–10:00 | reference |  |  |
| Arrival at work before 7:00 | −0.7452\*\*\* | 0.1155 | <0.001 |
| Arrival at work from 10:00 | 0.0870 | 0.1027 | 0.397 |
| ***Workplace and commute*** |  |  |  |
| Workplace zone with at least 10,000 jobs per km² | 0.5497\*\*\* | 0.0705 | <0.001 |
| Ln(1 + home–workplace distance, km) | −0.1786\*\*\* | 0.0373 | <0.001 |

<p class='estnote'>Observations: 8,613 work episodes at the usual workplace; alternatives: 2; parameters: 8. LL(β̂) = −3,061.5; BIC = 6,195.5. Hold-out half (8,561 episodes): LL = −3,093.2. Estimation: Biogeme, robust standard errors. An outing is a work episode at the usual workplace followed by one or more discretionary episodes and a return to the workplace. Work duration: piecewise linear in hours with bends at 4 h and 7 h; secondary work episode: arrival at work from 15:00.</p>

### Mode of the outing

Whether the outing is walked or keeps the mode of the work tour; 7 parameters. The term for fewer cars than drivers is not in the model.

<div class="estfit"><span>N = 1,177</span><span>K = 7</span><span>LL(β̂) = −360.6</span><span>ρ̄² = 0.549</span><span>Hold-out: LL −299.8</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Constant*** |  |  |  |
| Constant (walk) | 4.3240\*\*\* | 0.3610 | <0.001 |
| ***Outing*** |  |  |  |
| Ln(1 + distance workplace–first stop, km) | −2.4743\*\*\* | 0.1870 | <0.001 |
| Arrived at work by other modes | reference |  |  |
| Arrived at work by car, as driver | −2.2785\*\*\* | 0.2626 | <0.001 |
| Arrived at work by car, as passenger | −1.1701\*\* | 0.5325 | 0.028 |
| More than one stop on the outing | −1.0898\*\*\* | 0.3653 | 0.003 |
| ***Workplace zone*** |  |  |  |
| Workplace zone with at least 10,000 jobs per km² | 0.9061\*\*\* | 0.2488 | <0.001 |
| ***Household*** |  |  |  |
| Household with at least one car | reference |  |  |
| No car in the household | 0.5059 | 0.4887 | 0.301 |

<p class='estnote'>Observations: 1,177 outings; alternatives: walk or the mode of the work tour; parameters: 7. LL(β̂) = −360.6; BIC = 770.7. Hold-out half (1,153 outings): LL = −299.8. Estimation: Biogeme, robust standard errors. If the outing does not walk, its legs keep the mode of the work tour (the car stays at the workplace for a walking outing). Mode of the work tour: reference other modes; distance: car distance between the workplace and the first stop. A term for fewer cars than drivers is not included: it is not significant (likelihood-ratio test p = 0.34) and BIC is lower without it.</p>

### Return home between episodes

Whether a person goes home between two consecutive out-of-home episodes; 33 parameters. The term for fewer cars than drivers is kept: the household car allocation does not cover this choice.

<div class="estfit"><span>N = 28,349</span><span>K = 33</span><span>LL(β̂) = −13,697.0</span><span>ρ̄² = 0.301</span><span>Hold-out: LL −13,771.8</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Constant*** |  |  |  |
| Constant | 0.2860\*\* | 0.1207 | 0.018 |
| ***Detour and distance*** |  |  |  |
| Detour via home (km) | −0.0080\*\* | 0.0034 | 0.018 |
| Ln(1 + detour via home, km) | −0.4645\*\*\* | 0.0410 | <0.001 |
| Distance from home (km) | 0.0067\*\*\* | 0.0013 | <0.001 |
| ***Episodes*** |  |  |  |
| Preceding episode: other individual discretionary | reference |  |  |
| Preceding episode: work | −0.2370\*\*\* | 0.0526 | <0.001 |
| Preceding episode: school | −0.0491 | 0.0888 | 0.580 |
| Preceding episode: accompanying | −0.0478 | 0.0554 | 0.388 |
| Preceding episode: shopping | 0.1653\*\*\* | 0.0415 | <0.001 |
| Preceding episode: joint | 0.6576\*\*\* | 0.0763 | <0.001 |
| Following episode: other individual discretionary | reference |  |  |
| Following episode: work | −0.8090\*\*\* | 0.0698 | <0.001 |
| Following episode: school | −0.2001\* | 0.1064 | 0.060 |
| Following episode: accompanying | 0.4622\*\*\* | 0.0504 | <0.001 |
| Following episode: shopping | −0.7064\*\*\* | 0.0392 | <0.001 |
| Following episode: joint | 1.2098\*\*\* | 0.0599 | <0.001 |
| ***Joint episodes*** |  |  |  |
| Both episodes joint | −2.2242\*\*\* | 0.1081 | <0.001 |
| Joint episode next to a work or school episode | 0.5146\*\*\* | 0.0822 | <0.001 |
| ***Person*** |  |  |  |
| Person type: non-worker | reference |  |  |
| Person type: worker | −0.2405\*\*\* | 0.0561 | <0.001 |
| Person type: K–12 student | −0.1929\* | 0.1099 | 0.079 |
| Person type: post-secondary student | −0.1478 | 0.1093 | 0.176 |
| Person type: retiree | −0.1698\*\*\* | 0.0594 | 0.004 |
| Person type: child under 5 | −0.2725\*\* | 0.1249 | 0.029 |
| Female | −0.1202\*\*\* | 0.0305 | <0.001 |
| Driving licence | 0.4137\*\*\* | 0.0848 | <0.001 |
| ***Household*** |  |  |  |
| Household size (persons) | 0.1267\*\*\* | 0.0167 | <0.001 |
| Household income \$50–100k | reference |  |  |
| Household income below \$50k | −0.1886\*\*\* | 0.0491 | <0.001 |
| Household income \$100k or more | 0.1125\*\*\* | 0.0348 | 0.001 |
| Cars in the household: at least as many as drivers | reference |  |  |
| No car in the household | 0.0650 | 0.0745 | 0.383 |
| Fewer cars than drivers in the household | −0.1200\*\*\* | 0.0448 | 0.007 |
| Child under 16 in the household | −0.2205\*\*\* | 0.0487 | <0.001 |
| ***Day pattern*** |  |  |  |
| Number of out-of-home episodes in the day | −0.1497\*\*\* | 0.0087 | <0.001 |
| ***Time of day*** |  |  |  |
| End of the preceding episode 9:00–15:00 | reference |  |  |
| End of the preceding episode before 9:00 | −0.0793 | 0.0583 | 0.174 |
| End of the preceding episode 15–19 | −0.3433\*\*\* | 0.0363 | <0.001 |
| End of the preceding episode after 19:00 | −1.3199\*\*\* | 0.0823 | <0.001 |

<p class='estnote'>Observations: 28,349 pairs of consecutive out-of-home episodes; alternatives: 2; parameters: 33. LL(β̂) = −13,697.0; BIC = 27,732.2. Hold-out half (28,327 pairs): LL = −13,771.8. Estimation: maximum likelihood (robust sandwich covariance). y = 1 if the person returned home between two consecutive out-of-home episodes; pairs inside an outing from the workplace and pairs of two work episodes are excluded. Income bands: household income.</p>
