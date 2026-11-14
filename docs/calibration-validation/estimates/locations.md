# Destinations and stops

Location models of MILES-Day over the full choice set of 1,588 zones, estimated on the survey estimation half.

!!! note "Reading the tables"
    Coefficient: maximum-likelihood estimate with robust (sandwich) standard error; \*\*\* p < 0.001, \*\* p < 0.01, \* p < 0.05. N: observations; K: estimated parameters; LL(β̂): log-likelihood at the estimates; ρ̄²: adjusted rho-square. The same tables can be re-estimated with Biogeme from the estimation package.

### Main destination of discretionary tours

One logit for shopping, recreation, accompanying and other errands over 1,588 zones, with a scale for each purpose.

<div class="estfit"><span>N = 14,341</span><span>K = 71</span><span>LL(β̂) = −49,122.5</span><span>ρ̄² = 0.535</span><span>Hold-out: LL per record −3.352</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***All purposes: Distance and impedance*** | | | |
| Distance 0–1 km (per km) | −3.9489\*\*\* | 0.2517 | < 0.001 |
| Distance 1–2 km | −1.0280\*\*\* | 0.0779 | < 0.001 |
| Distance 2–5 km | −0.5405\*\*\* | 0.0217 | < 0.001 |
| Distance 5–10 km | −0.2295\*\*\* | 0.0107 | < 0.001 |
| Distance 10–20 km | −0.1546\*\*\* | 0.0058 | < 0.001 |
| Distance 20–50 km | −0.0827\*\*\* | 0.0044 | < 0.001 |
| ***All purposes: Boundaries*** | | | |
| Outside the origin county | −0.5531\*\*\* | 0.0369 | < 0.001 |
| Outside the origin state | −0.6451\*\*\* | 0.0621 | < 0.001 |
| ***All purposes: Interactions with ln(distance)*** | | | |
| Ln(distance) × no car | −0.3801\*\*\* | 0.0537 | < 0.001 |
| Ln(distance) × cars < drivers | −0.1524\*\*\* | 0.0329 | < 0.001 |
| Ln(distance) × worker | −0.0504 | 0.0285 | 0.077 |
| Ln(distance) × person < 18 | −0.0039 | 0.0417 | 0.926 |
| Ln(distance) × person 65+ | −0.0742\* | 0.0307 | 0.016 |
| Ln(distance) × household with children | −0.2064\*\*\* | 0.0304 | < 0.001 |
| Ln(distance) × male | −0.0081 | 0.0225 | 0.719 |
| Ln(distance) × one-person household | −0.0795\* | 0.0327 | 0.015 |
| Ln(distance) × AM 6–9 | −0.2487\*\*\* | 0.0404 | < 0.001 |
| Ln(distance) × PM 15–19 | −0.1231\*\*\* | 0.0269 | < 0.001 |
| Ln(distance) × evening 19–6 | −0.0002 | 0.0358 | 0.995 |
| Ln(distance) × tour with at least one stop | 0.4726\*\*\* | 0.0259 | < 0.001 |
| ***Shopping, recreation and other: Size*** | | | |
| μ, ln size | 1.2485\*\*\* | 0.0246 | < 0.001 |
| ***Shopping and other: Distance and impedance*** | | | |
| Car generalised time (min) | −0.0398\*\*\* | 0.0024 | < 0.001 |
| ***Shopping: Same zone*** | | | |
| Intrazonal (destination = home zone) | −1.0378\*\*\* | 0.0603 | < 0.001 |
| ***Shopping: Area*** | | | |
| Baltimore City | −1.1351\*\*\* | 0.1175 | < 0.001 |
| Washington DC | 0.0064 | 0.1514 | 0.966 |
| Central business district | −0.6453\*\*\* | 0.0938 | < 0.001 |
| Virginia | 0.3273\*\* | 0.1047 | 0.002 |
| Delaware, Pennsylvania, West Virginia | 1.3423\*\*\* | 0.1716 | < 0.001 |
| ***Shopping: Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.2153\*\*\* | 0.0242 | < 0.001 |
| Land-use mix (entropy) | 0.0546 | 0.1253 | 0.663 |
| ***Shopping: Size*** | | | |
| θ population (ln weight) | −7.0818\*\*\* | 0.9939 | < 0.001 |
| θ office jobs (ln weight) | −7.0158\*\*\* | 1.9882 | < 0.001 |
| ***Recreation: Same zone*** | | | |
| Intrazonal (destination = home zone) | −0.5627\*\*\* | 0.0739 | < 0.001 |
| ***Recreation: Area*** | | | |
| Baltimore City | −0.2226 | 0.1525 | 0.144 |
| Washington DC | 0.6920\*\*\* | 0.1625 | < 0.001 |
| Central business district | 0.4298\*\*\* | 0.1199 | < 0.001 |
| Virginia | 0.3426\*\* | 0.1159 | 0.003 |
| Delaware, Pennsylvania, West Virginia | 0.0967 | 0.2446 | 0.693 |
| ***Recreation: Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.4192\*\*\* | 0.0428 | < 0.001 |
| Land-use mix (entropy) | 1.4325\*\*\* | 0.2690 | < 0.001 |
| ***Recreation: Distance and impedance*** | | | |
| Car generalised time (min) | −0.0303\*\*\* | 0.0028 | < 0.001 |
| ***Recreation: Size*** | | | |
| θ population (ln weight) | −3.5094\*\*\* | 0.3862 | < 0.001 |
| θ office jobs (ln weight) | −3.8614\*\*\* | 0.3620 | < 0.001 |
| θ school enrolment (ln weight) | −3.8306\*\*\* | 0.3262 | < 0.001 |
| ***Recreation: Scale*** | | | |
| Scale (shopping = 1; p tests against 1) | 0.8003\*\*\* | 0.0180 | < 0.001 |
| ***Accompanying: Same zone*** | | | |
| Intrazonal (destination = home zone) | −0.2063 | 0.1283 | 0.108 |
| ***Accompanying: Area*** | | | |
| Baltimore City | −0.5608\* | 0.2810 | 0.046 |
| Washington DC | 0.5288\* | 0.2436 | 0.030 |
| Central business district | 0.3719 | 0.2182 | 0.088 |
| Virginia | 0.8902\*\* | 0.2712 | 0.001 |
| Delaware, Pennsylvania, West Virginia | 0.3096 | 0.8644 | 0.720 |
| ***Accompanying: Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.1441 | 0.0949 | 0.129 |
| Land-use mix (entropy) | 0.5790 | 0.4588 | 0.207 |
| ***Accompanying: Distance and impedance*** | | | |
| Car generalised time (min) | −0.0634\*\*\* | 0.0108 | < 0.001 |
| ***Accompanying: Size*** | | | |
| θ population (ln weight) | −3.5912\* | 1.3939 | 0.010 |
| θ office jobs (ln weight) | −1.6023 | 1.2258 | 0.191 |
| θ other jobs (ln weight) | −1.0426 | 1.1138 | 0.349 |
| θ school enrolment (ln weight) | 0.1792 | 1.4900 | 0.904 |
| μ, ln size | 0.7108\*\*\* | 0.1350 | < 0.001 |
| ***Accompanying: Scale*** | | | |
| Scale (shopping = 1; p tests against 1) | 0.7808\*\*\* | 0.0380 | < 0.001 |
| ***Other: Same zone*** | | | |
| Intrazonal (destination = home zone) | −0.6166\*\*\* | 0.0831 | < 0.001 |
| ***Other: Area*** | | | |
| Baltimore City | −0.0982 | 0.1542 | 0.525 |
| Washington DC | −0.2853 | 0.1566 | 0.068 |
| Central business district | −0.5147\*\*\* | 0.1408 | < 0.001 |
| Virginia | 0.3924\*\*\* | 0.1121 | < 0.001 |
| Delaware, Pennsylvania, West Virginia | 0.1253 | 0.2606 | 0.631 |
| ***Other: Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.2385\*\*\* | 0.0328 | < 0.001 |
| Land-use mix (entropy) | −1.2335\*\*\* | 0.1794 | < 0.001 |
| ***Other: Size*** | | | |
| θ office jobs (ln weight) | −1.9295\*\*\* | 0.1748 | < 0.001 |
| θ other jobs (ln weight) | −1.1888\*\*\* | 0.1646 | < 0.001 |
| ***Other: Scale*** | | | |
| Scale (shopping = 1; p tests against 1) | 0.7430\*\*\* | 0.0108 | < 0.001 |

### Stop location: shopping

Location of an intermediate shopping stop by its detour between the previous location and the next anchor.

<div class="estfit"><span>N = 3,979</span><span>K = 23</span><span>LL(β̂) = −9,987.8</span><span>ρ̄² = 0.659</span><span>Hold-out: LL per record −2.527</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Detour and impedance*** | | | |
| Detour 1–2 km | −0.5080\*\*\* | 0.0783 | < 0.001 |
| Detour 2–5 km | −0.2083\*\*\* | 0.0341 | < 0.001 |
| Detour 5–10 km | −0.1438\*\*\* | 0.0218 | < 0.001 |
| Detour 10–20 km | −0.1571\*\*\* | 0.0164 | < 0.001 |
| Detour > 20 km | −0.0389\*\*\* | 0.0085 | < 0.001 |
| Mode-choice logsum, detour | 0.4811\*\*\* | 0.0685 | < 0.001 |
| Car generalised time, detour (min) | −0.0178\* | 0.0069 | 0.010 |
| ***Anchor zones*** | | | |
| Stop in the zone of the previous location | 0.3478\*\*\* | 0.0584 | < 0.001 |
| Stop in the zone of the next anchor | 0.3056\*\*\* | 0.0615 | < 0.001 |
| ***Area*** | | | |
| Baltimore City | −0.8250\*\*\* | 0.1659 | < 0.001 |
| Washington DC | −0.3399\* | 0.1461 | 0.020 |
| Central business district | −0.2221\* | 0.1043 | 0.033 |
| Virginia | 0.1887 | 0.1522 | 0.215 |
| Delaware, Pennsylvania, West Virginia | 0.7742 | 0.5210 | 0.137 |
| ***Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.3662\*\*\* | 0.0379 | < 0.001 |
| Land-use mix (entropy) | −0.4917\*\*\* | 0.1369 | < 0.001 |
| ***Boundaries*** | | | |
| Outside the counties of both anchors | −0.7395\*\*\* | 0.0900 | < 0.001 |
| Outside the states of both anchors | −0.5997\*\* | 0.1896 | 0.002 |
| ***Interactions with ln(1 + detour)*** | | | |
| Ln(1 + detour) × no car | −0.0821 | 0.1325 | 0.536 |
| Ln(1 + detour) × cars < drivers | −0.2759\*\*\* | 0.0674 | < 0.001 |
| Ln(1 + detour) × household size (persons) | 0.0536\*\* | 0.0168 | 0.001 |
| Ln(1 + detour) × tour mode not car | −0.5526\*\*\* | 0.0899 | < 0.001 |
| ***Size*** | | | |
| μ, ln size | 1.2740\*\*\* | 0.0414 | < 0.001 |

### Stop location: recreation

Location of an intermediate recreation stop.

<div class="estfit"><span>N = 5,064</span><span>K = 22</span><span>LL(β̂) = −15,801.1</span><span>ρ̄² = 0.576</span><span>Hold-out: LL per record −3.195</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Detour and impedance*** | | | |
| Detour 1–2 km | −0.5150\*\*\* | 0.0682 | < 0.001 |
| Detour 2–5 km | −0.1479\*\*\* | 0.0278 | < 0.001 |
| Detour 5–10 km | −0.0906\*\*\* | 0.0175 | < 0.001 |
| Detour 10–20 km | −0.1542\*\*\* | 0.0097 | < 0.001 |
| Detour > 20 km | −0.0349\*\*\* | 0.0029 | < 0.001 |
| Mode-choice logsum, detour | 1.2937\*\*\* | 0.0807 | < 0.001 |
| ***Anchor zones*** | | | |
| Stop in the zone of the previous location | 0.4737\*\*\* | 0.0539 | < 0.001 |
| Stop in the zone of the next anchor | 0.3115\*\*\* | 0.0556 | < 0.001 |
| ***Area*** | | | |
| Baltimore City | −0.2281\* | 0.1091 | 0.037 |
| Washington DC | 0.4872\*\*\* | 0.1041 | < 0.001 |
| Central business district | 0.7511\*\*\* | 0.0803 | < 0.001 |
| Virginia | 0.1107 | 0.1051 | 0.292 |
| Delaware, Pennsylvania, West Virginia | 0.8568\*\*\* | 0.2259 | < 0.001 |
| ***Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.4138\*\*\* | 0.0224 | < 0.001 |
| Land-use mix (entropy) | 0.1896 | 0.1166 | 0.104 |
| ***Boundaries*** | | | |
| Outside the counties of both anchors | −0.8623\*\*\* | 0.0700 | < 0.001 |
| Outside the states of both anchors | −0.4874\*\*\* | 0.1232 | < 0.001 |
| ***Interactions with ln(1 + detour)*** | | | |
| Ln(1 + detour) × tour mode not car | −0.3499\*\*\* | 0.0491 | < 0.001 |
| Ln(1 + detour) × inbound stop | 0.1338\*\*\* | 0.0302 | < 0.001 |
| ***Size*** | | | |
| θ population (ln weight) | −4.7310\*\*\* | 0.2295 | < 0.001 |
| θ office jobs (ln weight) | −4.6293\*\*\* | 0.3132 | < 0.001 |
| θ school pupils (ln weight) | −5.0794\*\*\* | 0.4358 | < 0.001 |

### Stop location: accompanying

Location of an intermediate drop-off or pick-up stop.

<div class="estfit"><span>N = 3,515</span><span>K = 26</span><span>LL(β̂) = −12,417.5</span><span>ρ̄² = 0.520</span><span>Hold-out: LL per record −3.406</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Detour and impedance*** | | | |
| Detour 0–1 km (per km) | 0.4508\*\*\* | 0.1172 | < 0.001 |
| Detour 1–2 km | −0.3258\*\*\* | 0.0948 | < 0.001 |
| Detour 2–5 km | −0.1724\*\*\* | 0.0312 | < 0.001 |
| Detour 5–10 km | −0.0893\*\*\* | 0.0181 | < 0.001 |
| Detour 10–20 km | −0.1286\*\*\* | 0.0098 | < 0.001 |
| Detour > 20 km | −0.0526\*\*\* | 0.0038 | < 0.001 |
| Mode-choice logsum, detour | 1.0694\*\*\* | 0.1213 | < 0.001 |
| ***Anchor zones*** | | | |
| Stop in the zone of the previous location | 0.5497\*\*\* | 0.0672 | < 0.001 |
| Stop in the zone of the next anchor | 0.2702\*\*\* | 0.0704 | < 0.001 |
| ***Area*** | | | |
| Baltimore City | −0.1668 | 0.1347 | 0.215 |
| Washington DC | 0.0066 | 0.1236 | 0.958 |
| Central business district | 0.8265\*\*\* | 0.1342 | < 0.001 |
| Virginia | 0.2195 | 0.1161 | 0.059 |
| Delaware, Pennsylvania, West Virginia | −0.3250 | 0.4267 | 0.446 |
| ***Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.5678\*\*\* | 0.0415 | < 0.001 |
| Land-use mix (entropy) | −0.4895\*\*\* | 0.1364 | < 0.001 |
| ***Boundaries*** | | | |
| Outside the counties of both anchors | −1.0294\*\*\* | 0.0792 | < 0.001 |
| Outside the states of both anchors | −0.1963 | 0.1357 | 0.148 |
| ***Interactions with ln(1 + detour)*** | | | |
| Ln(1 + detour) × no car | −0.0369 | 0.2580 | 0.886 |
| Ln(1 + detour) × cars < drivers | −0.1049\* | 0.0486 | 0.031 |
| Ln(1 + detour) × tour mode not car | −0.3387\*\*\* | 0.0718 | < 0.001 |
| ***Size*** | | | |
| θ population (ln weight) | −2.4517\*\*\* | 0.4054 | < 0.001 |
| θ retail jobs (ln weight) | 3.7616\*\*\* | 0.2578 | < 0.001 |
| θ office jobs (ln weight) | −1.3766 | 0.7184 | 0.055 |
| θ other jobs (ln weight) | −0.9279 | 0.5471 | 0.090 |
| μ, ln size | 0.9199\*\*\* | 0.0381 | < 0.001 |

### Stop location: other errands

Location of an intermediate stop for other errands.

<div class="estfit"><span>N = 8,055</span><span>K = 23</span><span>LL(β̂) = −24,580.1</span><span>ρ̄² = 0.586</span><span>Hold-out: LL per record −3.024</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Detour and impedance*** | | | |
| Detour 1–2 km | −0.3803\*\*\* | 0.0519 | < 0.001 |
| Detour 2–5 km | −0.2100\*\*\* | 0.0223 | < 0.001 |
| Detour 5–10 km | −0.0746\*\*\* | 0.0140 | < 0.001 |
| Detour 10–20 km | −0.1484\*\*\* | 0.0083 | < 0.001 |
| Detour > 20 km | −0.0230\*\*\* | 0.0044 | < 0.001 |
| Mode-choice logsum, detour | 1.5254\*\*\* | 0.1011 | < 0.001 |
| Car generalised time, detour (min) | −0.0089\* | 0.0036 | 0.013 |
| ***Anchor zones*** | | | |
| Stop in the zone of the previous location | 0.5333\*\*\* | 0.0414 | < 0.001 |
| Stop in the zone of the next anchor | 0.1903\*\*\* | 0.0433 | < 0.001 |
| ***Area*** | | | |
| Baltimore City | −0.1198 | 0.0868 | 0.167 |
| Washington DC | −0.1640 | 0.0966 | 0.090 |
| Central business district | 0.3425\*\*\* | 0.0775 | < 0.001 |
| Virginia | 0.1240 | 0.0914 | 0.175 |
| Delaware, Pennsylvania, West Virginia | −0.3285 | 0.2441 | 0.178 |
| ***Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.3612\*\*\* | 0.0249 | < 0.001 |
| Land-use mix (entropy) | −0.0611 | 0.0994 | 0.539 |
| ***Boundaries*** | | | |
| Outside the counties of both anchors | −1.0353\*\*\* | 0.0587 | < 0.001 |
| Outside the states of both anchors | −0.2522\* | 0.1012 | 0.013 |
| ***Interactions with ln(1 + detour)*** | | | |
| Ln(1 + detour) × tour mode not car | −0.3297\*\*\* | 0.0458 | < 0.001 |
| ***Size*** | | | |
| θ office jobs (ln weight) | −3.8285\*\*\* | 0.2137 | < 0.001 |
| θ other jobs (ln weight) | −3.3780\*\*\* | 0.2348 | < 0.001 |
| θ school pupils (ln weight) | −6.2719\*\*\* | 1.1856 | < 0.001 |
| μ, ln size | 0.9388\*\*\* | 0.0251 | < 0.001 |

### Outing from the workplace: first stop

Location of the first stop of an outing that starts and ends at the workplace.

<div class="estfit"><span>N = 1,180</span><span>K = 13</span><span>LL(β̂) = −3,089.9</span><span>ρ̄² = 0.665</span><span>Hold-out: LL per record −2.715</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Distance and impedance*** | | | |
| Distance 0–1 km (per km) | −5.5813\*\*\* | 0.4576 | < 0.001 |
| Distance 1–2 km | −1.1903\*\*\* | 0.2060 | < 0.001 |
| Distance 2–5 km | −0.3162\*\*\* | 0.0794 | < 0.001 |
| Distance 5–10 km | −0.3256\*\*\* | 0.0478 | < 0.001 |
| Distance 10–20 km | −0.1042\*\* | 0.0387 | 0.007 |
| Distance 20–50 km | −0.0502 | 0.0303 | 0.098 |
| Car generalised time (min) | −0.0716\*\* | 0.0235 | 0.002 |
| ***Same zone*** | | | |
| Intrazonal (destination = workplace zone) | −0.2414 | 0.1600 | 0.131 |
| ***Boundaries*** | | | |
| Outside the workplace county | −1.3701\*\*\* | 0.1842 | < 0.001 |
| ***Size*** | | | |
| θ population (ln weight) | −5.5334\*\*\* | 1.5769 | < 0.001 |
| θ office jobs (ln weight) | −2.5016\*\*\* | 0.3190 | < 0.001 |
| θ other jobs (ln weight) | −3.2305\*\*\* | 0.8060 | < 0.001 |
| μ, ln size | 0.8516\*\*\* | 0.0611 | < 0.001 |

### Work business: workers with a usual workplace

Location of work-business episodes, with home and workplace as anchors.

<div class="estfit"><span>N = 1,539</span><span>K = 22</span><span>LL(β̂) = −8,402.2</span><span>ρ̄² = 0.312</span><span>Hold-out: LL per record −5.541</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Detour and impedance*** | | | |
| Detour 0–1 km (per km) | 0.8611\*\*\* | 0.1932 | < 0.001 |
| Detour 1–2 km | −0.7482\*\*\* | 0.1749 | < 0.001 |
| Detour 2–5 km | −0.0724 | 0.0603 | 0.230 |
| Detour 5–10 km | −0.0111 | 0.0315 | 0.724 |
| Detour 10–20 km | −0.0632\*\*\* | 0.0134 | < 0.001 |
| Detour > 20 km | −0.0127\* | 0.0050 | 0.011 |
| Car generalised time, detour (min) | −0.0136\*\* | 0.0046 | 0.003 |
| ***Same zone*** | | | |
| Stop in the home zone | 1.1106\*\*\* | 0.1215 | < 0.001 |
| Stop in the workplace zone | −0.5247\*\* | 0.1637 | 0.001 |
| ***Land use*** | | | |
| Ln(1 + retail jobs per km^2) | −0.0802\*\* | 0.0294 | 0.006 |
| Land-use mix (entropy) | 0.5928\* | 0.2662 | 0.026 |
| ***Boundaries*** | | | |
| Outside the counties of both anchors | −1.0162\*\*\* | 0.0818 | < 0.001 |
| ***Interactions with ln(1 + detour)*** | | | |
| Ln(1 + detour) × no car | −0.1163 | 0.1178 | 0.323 |
| Ln(1 + detour) × cars < drivers | −0.2729\*\*\* | 0.0723 | < 0.001 |
| Ln(1 + detour) × AM 6–9 | 0.0428 | 0.0532 | 0.422 |
| Ln(1 + detour) × PM 15–19 | −0.2424\*\*\* | 0.0584 | < 0.001 |
| Ln(1 + detour) × evening 19–6 | −0.2277\* | 0.1001 | 0.023 |
| ***Size*** | | | |
| θ population (ln weight) | −2.2439\*\*\* | 0.5863 | < 0.001 |
| θ office jobs (ln weight) | −0.2926 | 0.4013 | 0.466 |
| θ other jobs (ln weight) | −0.6868 | 0.4647 | 0.139 |
| θ school pupils (ln weight) | −2.0439\*\* | 0.7482 | 0.006 |
| μ, ln size | 0.8539\*\*\* | 0.0441 | < 0.001 |

### Work business: other persons

Location of work-business episodes of persons without a usual workplace.

<div class="estfit"><span>N = 1,259</span><span>K = 19</span><span>LL(β̂) = −6,766.7</span><span>ρ̄² = 0.297</span><span>Hold-out: LL per record −5.588</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Distance and impedance*** | | | |
| Distance 1–2 km | −2.2205\*\*\* | 0.2555 | < 0.001 |
| Distance 2–5 km | −0.1198 | 0.0818 | 0.143 |
| Distance 5–10 km | −0.1715\*\*\* | 0.0327 | < 0.001 |
| Distance 10–20 km | −0.1153\*\*\* | 0.0138 | < 0.001 |
| Distance 20–50 km | −0.0798\*\*\* | 0.0053 | < 0.001 |
| Distance > 50 km | −0.0390\*\*\* | 0.0033 | < 0.001 |
| ***Same zone*** | | | |
| Intrazonal (destination = home zone) | 0.6269\*\*\* | 0.1782 | < 0.001 |
| ***Area*** | | | |
| Baltimore City | −0.1409 | 0.0999 | 0.158 |
| Washington DC | 0.1273 | 0.1406 | 0.365 |
| Virginia | −0.1645 | 0.1281 | 0.199 |
| Delaware, Pennsylvania, West Virginia | −0.8010\*\*\* | 0.2142 | < 0.001 |
| ***Boundaries*** | | | |
| Outside the origin county | −0.2972\*\*\* | 0.0863 | < 0.001 |
| ***Interactions with ln(distance)*** | | | |
| Ln(distance) × income < \50k | −0.1223 | 0.0671 | 0.068 |
| Ln(distance) × income ≥q \100k | 0.1043 | 0.0639 | 0.103 |
| Ln(distance) × worker | 0.3669\*\*\* | 0.0565 | < 0.001 |
| ***Size*** | | | |
| θ office jobs (ln weight) | −0.5587 | 0.3015 | 0.064 |
| θ other jobs (ln weight) | −0.0792 | 0.3270 | 0.809 |
| θ school pupils (ln weight) | −3.0742\* | 1.3999 | 0.028 |
| μ, ln size | 0.7309\*\*\* | 0.0342 | < 0.001 |

### Work trips of persons who work at home

Location of the work trips of persons whose usual workplace is home.

<div class="estfit"><span>N = 366</span><span>K = 6</span><span>LL(β̂) = −1,634.6</span><span>ρ̄² = 0.431</span><span>Hold-out: LL per record −4.375</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Distance and impedance*** | | | |
| Distance (km) | −0.0180\*\*\* | 0.0049 | < 0.001 |
| Ln(distance, km) | −1.4059\*\*\* | 0.1380 | < 0.001 |
| ***Same zone*** | | | |
| Intrazonal (destination = home zone) | 1.2092\*\*\* | 0.2609 | < 0.001 |
| ***Boundaries*** | | | |
| Outside the origin county | −0.4478\* | 0.1900 | 0.018 |
| ***Size*** | | | |
| θ population (ln weight) | −2.0456\*\*\* | 0.4009 | < 0.001 |
| μ, ln size | 0.7477\*\*\* | 0.0778 | < 0.001 |

### School and daycare without a school record

One pooled model for school episodes of persons without a school record and daycare of children under 5, with a purpose scale.

<div class="estfit"><span>N = 846</span><span>K = 11</span><span>LL(β̂) = −3,706.8</span><span>ρ̄² = 0.453</span><span>Hold-out: LL per record −4.280</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Distance and impedance*** | | | |
| Ln(distance, km) (shared) | −1.0349 | 0.0640 |  |
| ***Land use*** | | | |
| Ln(1 + retail jobs per km2) (shared) | −0.1383 | 0.0328 |  |
| Land-use mix (entropy) (shared) | 1.3441 | 0.2701 |  |
| ***Boundaries*** | | | |
| Outside the origin county (shared) | −0.5721 | 0.1198 |  |
| Outside the origin state (shared) | −0.5208 | 0.1677 |  |
| ***Distance and impedance*** | | | |
| Car generalised time (min) (shared) | −0.0480 | 0.0046 |  |
| ***Size*** | | | |
| Theta population (ln weight), non-student school | −2.6083 | 0.2803 |  |
| Theta office jobs (ln weight), non-student school | −1.5241 | 0.2714 |  |
| Theta school pupils (ln weight), daycare | −0.7555 | 0.6794 |  |
| Theta population (ln weight), daycare | −0.8610 | 0.5918 |  |
| ***Scale*** | | | |
| Scale, daycare | 1.2279 | 0.0464 |  |

