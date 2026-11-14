# Tour formation

Binary logits that shape the tours of MILES-Day: outings from the workplace, their mode, and returns home between episodes.

!!! note "Reading the tables"
    Coefficient: maximum-likelihood estimate with robust (sandwich) standard error; \*\*\* p < 0.001, \*\* p < 0.01, \* p < 0.05. N: observations; K: estimated parameters; LL(β̂): log-likelihood at the estimates; ρ̄²: adjusted rho-square. The same tables can be re-estimated with Biogeme from the estimation package.

### Outing from the workplace

Binary logit: whether a work episode at the usual workplace contains an outing.

<div class="estfit"><span>N = 8,613</span><span>K = 8</span><span>LL(β̂) = −3,061.5</span><span>ρ̄² = 0.486</span><span>Hold-out: LL −3,093.2</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Constant*** | | | |
| Constant | −4.6092\*\*\* | 0.5251 | < 0.001 |
| ***Work episode*** | | | |
| Work duration, 0–4 h (per h) | 0.4033\*\* | 0.1439 | 0.005 |
| Work duration, 4–7 h (per h) | 0.5862\*\*\* | 0.0668 | < 0.001 |
| Secondary work episode (arrival from 15:00) | −2.0156\*\* | 0.7207 | 0.005 |
| ***Time of day*** | | | |
| Arrival at work before 7:00 | −0.7452\*\*\* | 0.1155 | < 0.001 |
| Arrival at work from 10:00 | 0.0870 | 0.1027 | 0.397 |
| ***Workplace and commute*** | | | |
| Workplace zone with at least 10,000 jobs per km^2 | 0.5497\*\*\* | 0.0705 | < 0.001 |
| Ln(1 + home–workplace distance, km) | −0.1786\*\*\* | 0.0373 | < 0.001 |

### Mode of the outing

Binary logit: whether the outing is walked or keeps the mode of the work tour.

<div class="estfit"><span>N = 1,177</span><span>K = 8</span><span>LL(β̂) = −360.2</span><span>ρ̄² = 0.549</span><span>Hold-out: LL −299.7</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Constant*** | | | |
| Constant (walk) | 4.2063\*\*\* | 0.3813 | < 0.001 |
| ***Outing*** | | | |
| Ln(1 + distance workplace–first stop, km) | −2.4674\*\*\* | 0.1860 | < 0.001 |
| Arrived at work by car, as driver | −2.1987\*\*\* | 0.2776 | < 0.001 |
| Arrived at work by car, as passenger | −1.1481\* | 0.5309 | 0.031 |
| More than one stop on the outing | −1.0600\*\* | 0.3644 | 0.004 |
| ***Workplace zone*** | | | |
| Workplace zone with at least 10,000 jobs per km^2 | 0.9208\*\*\* | 0.2476 | < 0.001 |
| ***Household*** | | | |
| No car in the household | 0.6053 | 0.5009 | 0.227 |
| Fewer cars than drivers in the household | 0.2643 | 0.2958 | 0.372 |

### Return home between episodes

Binary logit: whether a person goes home between two consecutive out-of-home episodes.

<div class="estfit"><span>N = 28,349</span><span>K = 33</span><span>LL(β̂) = −13,697.0</span><span>ρ̄² = 0.301</span><span>Hold-out: LL −13,771.8</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Constant*** | | | |
| Constant | 0.2860\* | 0.1207 | 0.018 |
| ***Detour and distance*** | | | |
| Detour via home (km) | −0.0080\* | 0.0034 | 0.018 |
| Ln(1 + detour via home, km) | −0.4645\*\*\* | 0.0410 | < 0.001 |
| Distance from home (km) | 0.0067\*\*\* | 0.0013 | < 0.001 |
| ***Episodes*** | | | |
| Preceding episode: work | −0.2370\*\*\* | 0.0526 | < 0.001 |
| Preceding episode: school | −0.0491 | 0.0888 | 0.580 |
| Preceding episode: accompanying | −0.0478 | 0.0554 | 0.388 |
| Preceding episode: shopping | 0.1653\*\*\* | 0.0415 | < 0.001 |
| Preceding episode: joint | 0.6576\*\*\* | 0.0763 | < 0.001 |
| Following episode: work | −0.8090\*\*\* | 0.0698 | < 0.001 |
| Following episode: school | −0.2001 | 0.1064 | 0.060 |
| Following episode: accompanying | 0.4622\*\*\* | 0.0504 | < 0.001 |
| Following episode: shopping | −0.7064\*\*\* | 0.0392 | < 0.001 |
| Following episode: joint | 1.2098\*\*\* | 0.0599 | < 0.001 |
| ***Joint episodes*** | | | |
| Both episodes joint | −2.2242\*\*\* | 0.1081 | < 0.001 |
| Joint episode next to a work or school episode | 0.5146\*\*\* | 0.0822 | < 0.001 |
| ***Person*** | | | |
| Person type: worker | −0.2405\*\*\* | 0.0561 | < 0.001 |
| Person type: K–12 student | −0.1929 | 0.1099 | 0.079 |
| Person type: post-secondary student | −0.1478 | 0.1093 | 0.176 |
| Person type: retiree | −0.1698\*\* | 0.0594 | 0.004 |
| Person type: child under 5 | −0.2725\* | 0.1249 | 0.029 |
| Female | −0.1202\*\*\* | 0.0305 | < 0.001 |
| Driving licence | 0.4137\*\*\* | 0.0848 | < 0.001 |
| ***Household*** | | | |
| Household size (persons) | 0.1267\*\*\* | 0.0167 | < 0.001 |
| Household income below \50k | −0.1886\*\*\* | 0.0491 | < 0.001 |
| Household income \100k or more | 0.1125\*\* | 0.0348 | 0.001 |
| No car in the household | 0.0650 | 0.0745 | 0.383 |
| Fewer cars than drivers in the household | −0.1200\*\* | 0.0448 | 0.007 |
| Child under 16 in the household | −0.2205\*\*\* | 0.0487 | < 0.001 |
| ***Day pattern*** | | | |
| Number of out-of-home episodes in the day | −0.1497\*\*\* | 0.0087 | < 0.001 |
| ***Time of day*** | | | |
| End of the preceding episode before 9:00 | −0.0793 | 0.0583 | 0.174 |
| End of the preceding episode 15–19 | −0.3433\*\*\* | 0.0363 | < 0.001 |
| End of the preceding episode after 19:00 | −1.3199\*\*\* | 0.0823 | < 0.001 |

