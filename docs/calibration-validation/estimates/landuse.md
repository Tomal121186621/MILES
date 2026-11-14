# Land use and workplaces

Residential location (three levels), car ownership and workplace choice, estimated on ACS PUMS households and the estimation half of the 2017/18 Regional Travel Survey.

!!! note "Reading the tables"
    Coefficient: maximum-likelihood estimate with robust (sandwich) standard error; \*\*\* p < 0.001, \*\* p < 0.01, \* p < 0.05. N: observations; K: estimated parameters; LL(β̂): log-likelihood at the estimates; ρ̄²: adjusted rho-square. The same tables can be re-estimated with Biogeme from the estimation package.

### Residential location: county

Upper level of the nested residential-location model: the county a moving household chooses, with the inclusive values of the zone and dwelling levels. ACS PUMS movers 2014–18.

<div class="estfit"><span>N = 15,163</span><span>K = 14</span><span>LL(β̂) = −15,959.4</span><span>ρ̄² = 0.714</span><span>Hold-out: ρ² 0.714</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Car time to another county (per min)*** | | | |
| Under 20 min | 0 (reference) | | |
| 20–60 min | −0.0305\*\*\* | 0.0019 | < 0.001 |
| Over 60 min | −0.0085\*\*\* | 0.0007 | < 0.001 |
| 20–60 min × ln income | 0.0047\*\*\* | 0.0009 | < 0.001 |
| Over 60 min × ln income | 0.0032\*\*\* | 0.0006 | < 0.001 |
| ***Staying near the origin*** | | | |
| Previous county | 2.1962\*\*\* | 0.0840 | < 0.001 |
| County bordering the previous county | 0.9149\*\*\* | 0.0522 | < 0.001 |
| Same state as the origin | 0.9090\*\*\* | 0.0373 | < 0.001 |
| ***Inclusive values of the dwelling choice*** | | | |
| Zone × structure type, λB | 0.3885\*\*\* | 0.0165 | < 0.001 |
| Dwelling, λA | 0.9240\*\*\* | 0.0582 | < 0.001 |
| ***Commute*** | | | |
| Commute: sum_workers ln(1+t) | −2.1432\*\*\* | 0.0386 | < 0.001 |
| Commute × ln income | 0.4514\*\*\* | 0.0362 | < 0.001 |
| ***Age of the oldest member*** | | | |
| Previous county × (age - 50)/10 | 0.0816\*\*\* | 0.0138 | < 0.001 |
| ***Schools and crime*** | | | |
| School learning growth (SD per grade) | 1.9934\*\*\* | 0.5232 | < 0.001 |
| Crime index × children | −1.0535\*\*\* | 0.1110 | < 0.001 |

### Residential location: zone and structure type

Middle level: the zone and dwelling type within the county; 30 sampled alternatives, weighted by the survey household weights. Survey estimation half.

<div class="estfit"><span>N = 10,655</span><span>K = 15</span><span>LL(β̂) = −28,089.7</span><span>ρ̄² = 0.224</span><span>Hold-out: ρ² 0.139 (full choice set)</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Size*** | | | |
| Ln dwellings of the structure type in the zone (theta) | 1.0875\*\*\* | 0.0164 | < 0.001 |
| ***Accessibility (logsum of the household's segment)*** | | | |
| Non-work accessibility | 0.5123\*\*\* | 0.0738 | < 0.001 |
| Non-work accessibility × oldest member under 35 | 0.4388\*\*\* | 0.0870 | < 0.001 |
| Non-work accessibility × oldest member 50–64 | −0.3431\*\*\* | 0.0627 | < 0.001 |
| Non-work accessibility × oldest member 65+ | −0.1515\* | 0.0671 | 0.024 |
| Non-work accessibility × (household size - 1, at most 5) | −0.1441\*\*\* | 0.0226 | < 0.001 |
| ***Commute*** | | | |
| Commute: sum_workers ln(1+t) | −1.3012\*\*\* | 0.0495 | < 0.001 |
| ***Zone price level*** | | | |
| Ln mean monthly housing cost of the zone | −0.5048\*\* | 0.1552 | 0.001 |
| Ln zone cost × ln income | 1.2163\*\*\* | 0.2090 | < 0.001 |
| Ln zone cost × (household size - 1, at most 5) | −0.3643\*\*\* | 0.0871 | < 0.001 |
| ***Neighbours*** | | | |
| Share of same-income households in the zone | 1.7169\*\*\* | 0.4655 | < 0.001 |
| ***Land use of the zone*** | | | |
| Ln dwellings per acre | −0.3847\*\*\* | 0.0317 | < 0.001 |
| Ln dwellings per acre × no car | 0.5085\*\*\* | 0.1018 | < 0.001 |
| Ln dwellings per acre × children | −0.0569 | 0.0349 | 0.103 |
| Ln(1 + retail jobs per km^2) | 0.0305\* | 0.0134 | 0.023 |

### Residential location: dwelling

Lower level: the dwelling within the PUMA; 30 sampled alternatives. ACS PUMS movers 2014–18.

<div class="estfit"><span>N = 15,163</span><span>K = 38</span><span>LL(β̂) = −47,688.2</span><span>ρ̄² = 0.075</span><span>Hold-out: ρ² 0.082</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Housing cost*** | | | |
| Cost share of income, slope below 30 % | 2.2014\*\*\* | 0.4618 | < 0.001 |
| Cost share of income, slope 30–50 % | −6.7986\*\*\* | 0.2920 | < 0.001 |
| X ln income | −4.6584\*\*\* | 0.3474 | < 0.001 |
| Cost share of income, slope above 50 % | −2.7052\*\*\* | 0.2000 | < 0.001 |
| X ln income | −1.1702\*\*\* | 0.0863 | < 0.001 |
| Ln monthly housing cost | 0.1868\* | 0.0752 | 0.013 |
| X ln income | 0.3830\*\*\* | 0.0341 | < 0.001 |
| ***Size and age of the dwelling*** | | | |
| Bedroom shortfall (per bedroom) | −0.8743\*\*\* | 0.0297 | < 0.001 |
| X ln income | −0.2195\*\*\* | 0.0265 | < 0.001 |
| Bedroom excess (per bedroom) | −0.2528\*\*\* | 0.0140 | < 0.001 |
| X ln income | 0.1543\*\*\* | 0.0138 | < 0.001 |
| Built in the last five years | −0.0274 | 0.0364 | 0.452 |
| X ln income | 0.1153\*\* | 0.0356 | 0.001 |
| ***Structure type: single-family attached (reference: single-family detached)*** | | | |
| Constant | 0.1309\* | 0.0590 | 0.027 |
| X children | −0.2164\*\*\* | 0.0557 | < 0.001 |
| X oldest member under 35 | 0.1610\* | 0.0636 | 0.011 |
| X oldest member 50–64 | −0.1778\* | 0.0761 | 0.019 |
| X oldest member 65+ | −0.1530 | 0.1015 | 0.132 |
| X ln income | −0.1220\*\*\* | 0.0313 | < 0.001 |
| ***Structure type: multifamily 2-4 units (reference: single-family detached)*** | | | |
| Constant | 0.0780 | 0.0882 | 0.377 |
| X (household size - 1) | −0.1011\* | 0.0448 | 0.024 |
| X children | −0.1970 | 0.1102 | 0.074 |
| X oldest member under 35 | 0.2743\*\* | 0.0898 | 0.002 |
| X oldest member 50–64 | −0.2671\* | 0.1146 | 0.020 |
| X oldest member 65+ | −0.3780\*\* | 0.1454 | 0.009 |
| X ln income | −0.3138\*\*\* | 0.0438 | < 0.001 |
| ***Structure type: multifamily 5+ units (reference: single-family detached)*** | | | |
| Constant | −0.0494 | 0.0626 | 0.430 |
| X (household size - 1) | −0.1557\*\*\* | 0.0304 | < 0.001 |
| X children | −0.1819\* | 0.0721 | 0.012 |
| X oldest member under 35 | 0.4494\*\*\* | 0.0612 | < 0.001 |
| X oldest member 50–64 | −0.0327 | 0.0745 | 0.660 |
| X oldest member 65+ | 0.4850\*\*\* | 0.0897 | < 0.001 |
| X ln income | −0.2448\*\*\* | 0.0363 | < 0.001 |
| ***Structure type: mobile home or other (reference: single-family detached)*** | | | |
| Constant | −0.2142 | 0.1275 | 0.093 |
| X oldest member under 35 | −0.0801 | 0.1665 | 0.630 |
| X oldest member 50–64 | 0.2580 | 0.1741 | 0.138 |
| X oldest member 65+ | 0.1130 | 0.2199 | 0.607 |
| X ln income | −0.4740\*\*\* | 0.0665 | < 0.001 |

### Car ownership

Multinomial logit over 0, 1, 2 and 3+ cars; every variable has its own coefficient for each alternative (0 cars = reference). ACS PUMS households 2014–18.

<div class="estfit"><span>N = 91,348</span><span>K = 51</span><span>LL(β̂) = −80,664.0</span><span>ρ̄² = 0.363</span><span>Hold-out: ρ² 0.358</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***One car versus none*** | | | |
| Constant | 1.5342\*\*\* | 0.2176 | < 0.001 |
| Workers | −0.5910\*\*\* | 0.0453 | < 0.001 |
| Non-working persons aged 16+ | −0.7173\*\*\* | 0.0399 | < 0.001 |
| Children under 16 | −0.1733\*\*\* | 0.0219 | < 0.001 |
| Single-person household | −0.3179\*\*\* | 0.0557 | < 0.001 |
| Age of the oldest member ((age - 45) / 10) | −0.0613\*\*\* | 0.0132 | < 0.001 |
| Age of the oldest member, squared | −0.0341\*\*\* | 0.0040 | < 0.001 |
| Ln income, slope under 25k | 0.5075\*\*\* | 0.0369 | < 0.001 |
| Ln income, slope 25–50k | 1.7727\*\*\* | 0.0856 | < 0.001 |
| Ln income, slope 50–100k | 0.4458\*\*\* | 0.0989 | < 0.001 |
| Ln income, slope above 100k | −0.3512\*\*\* | 0.1002 | < 0.001 |
| Single-family detached dwelling | 0.3662\*\*\* | 0.0433 | < 0.001 |
| Multifamily dwelling | −0.2275\*\*\* | 0.0416 | < 0.001 |
| Bedrooms | 0.3465\*\*\* | 0.0206 | < 0.001 |
| Ln dwelling density of the PUMA (per km^2) | −0.1135\*\*\* | 0.0195 | < 0.001 |
| Non-work accessibility gain from a car (logsum) | 1.4236\*\*\* | 0.1252 | < 0.001 |
| Ln income × ln dwelling density (centred) | 0.0605\*\*\* | 0.0139 | < 0.001 |
| ***Two cars versus none*** | | | |
| Constant | 0.8291\*\*\* | 0.2396 | < 0.001 |
| Workers | −0.1209\*\* | 0.0429 | 0.005 |
| Non-working persons aged 16+ | −0.4847\*\*\* | 0.0363 | < 0.001 |
| Children under 16 | −0.2778\*\*\* | 0.0224 | < 0.001 |
| Single-person household | −2.2801\*\*\* | 0.0567 | < 0.001 |
| Age of the oldest member ((age - 45) / 10) | −0.1115\*\*\* | 0.0152 | < 0.001 |
| Age of the oldest member, squared | −0.0430\*\*\* | 0.0046 | < 0.001 |
| Ln income, slope under 25k | 0.4565\*\*\* | 0.0522 | < 0.001 |
| Ln income, slope 25–50k | 2.4088\*\*\* | 0.1014 | < 0.001 |
| Ln income, slope 50–100k | 1.4280\*\*\* | 0.1024 | < 0.001 |
| Ln income, slope above 100k | 0.1358 | 0.0999 | 0.174 |
| Single-family detached dwelling | 0.9722\*\*\* | 0.0459 | < 0.001 |
| Multifamily dwelling | −0.6951\*\*\* | 0.0467 | < 0.001 |
| Bedrooms | 0.4924\*\*\* | 0.0229 | < 0.001 |
| Ln dwelling density of the PUMA (per km^2) | −0.2619\*\*\* | 0.0206 | < 0.001 |
| Non-work accessibility gain from a car (logsum) | 1.8495\*\*\* | 0.1445 | < 0.001 |
| Ln income × ln dwelling density (centred) | 0.0241 | 0.0156 | 0.122 |
| ***Three or more cars versus none*** | | | |
| Constant | −3.0365\*\*\* | 0.2832 | < 0.001 |
| Workers | 1.0537\*\*\* | 0.0454 | < 0.001 |
| Non-working persons aged 16+ | 0.3677\*\*\* | 0.0381 | < 0.001 |
| Children under 16 | −0.4315\*\*\* | 0.0246 | < 0.001 |
| Single-person household | −1.7009\*\*\* | 0.0699 | < 0.001 |
| Age of the oldest member ((age - 45) / 10) | 0.0468\* | 0.0190 | 0.014 |
| Age of the oldest member, squared | −0.1010\*\*\* | 0.0058 | < 0.001 |
| Ln income, slope under 25k | 0.1754\* | 0.0822 | 0.033 |
| Ln income, slope 25–50k | 2.4995\*\*\* | 0.1370 | < 0.001 |
| Ln income, slope 50–100k | 1.5995\*\*\* | 0.1131 | < 0.001 |
| Ln income, slope above 100k | 0.2591\* | 0.1025 | 0.011 |
| Single-family detached dwelling | 1.6895\*\*\* | 0.0521 | < 0.001 |
| Multifamily dwelling | −1.1689\*\*\* | 0.0689 | < 0.001 |
| Bedrooms | 0.6110\*\*\* | 0.0253 | < 0.001 |
| Ln dwelling density of the PUMA (per km^2) | −0.4176\*\*\* | 0.0226 | < 0.001 |
| Non-work accessibility gain from a car (logsum) | 2.2972\*\*\* | 0.1764 | < 0.001 |
| Ln income × ln dwelling density (centred) | −0.0352\* | 0.0175 | 0.045 |

### Workplace choice

Choice of the workplace zone among the zones with jobs, with a size term over job types; the chosen zone and 99 sampled zones. Survey estimation half.

<div class="estfit"><span>N = 9,707</span><span>K = 36</span><span>LL(β̂) = −21,334.3</span><span>ρ̄² = 0.522</span><span>Hold-out: LL per worker −4.808 (all zones)</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Size*** | | | |
| Size coefficient mu | 0.8489\*\*\* | 0.0151 | < 0.001 |
| Office jobs, log weight | −0.5350\*\* | 0.1795 | 0.003 |
| Industrial jobs, log weight | −0.6907\*\*\* | 0.2001 | < 0.001 |
| Other jobs, log weight | −0.1777 | 0.2113 | 0.400 |
| ***Car time*** | | | |
| Time (min) | −0.0692\*\*\* | 0.0032 | < 0.001 |
| Ln(1+time) | −0.4844\*\*\* | 0.1041 | < 0.001 |
| ***Car time x person*** | | | |
| Time × woman | −0.0155\*\*\* | 0.0017 | < 0.001 |
| Time × age <30 | −0.0158\*\*\* | 0.0030 | < 0.001 |
| Time × age 55+ | −0.0049\* | 0.0021 | 0.018 |
| Time × income <40k | −0.0195\*\*\* | 0.0055 | < 0.001 |
| Time × income 75–125k | 0.0076\*\* | 0.0024 | 0.002 |
| Time × income 125k+ | 0.0122\*\*\* | 0.0027 | < 0.001 |
| Time × driving licence | 0.0280\*\*\* | 0.0073 | < 0.001 |
| Time × household size | −0.0022\* | 0.0011 | 0.034 |
| Time × children in the household | 0.0031 | 0.0026 | 0.229 |
| Time × two or more workers | −0.0014 | 0.0021 | 0.514 |
| Time × rural home zone | 0.0077\*\*\* | 0.0019 | < 0.001 |
| ***Borders and the District*** | | | |
| Same zone | 0.6405\*\*\* | 0.0869 | < 0.001 |
| Other county | −0.2794\*\*\* | 0.0372 | < 0.001 |
| Other state | −0.7637\*\*\* | 0.0554 | < 0.001 |
| DC workplace, home outside DC | 1.0973\*\*\* | 0.0999 | < 0.001 |
| ***Accessibility of the workplace*** | | | |
| Non-work accessibility (logsum) of the workplace zone | −0.0889\*\* | 0.0285 | 0.002 |
| ***Workplace regions*** | | | |
| Baltimore City | −0.0830 | 0.0557 | 0.136 |
| Montgomery and Prince George's | 0.1126\* | 0.0460 | 0.014 |
| Arlington and Alexandria | 0.4285\*\*\* | 0.0775 | < 0.001 |
| Other Northern Virginia | 0.0478 | 0.0731 | 0.513 |
| Rest of Maryland | 0.0822 | 0.0960 | 0.392 |
| Other states | −0.1437 | 0.1436 | 0.317 |
| ***Job mix x person*** | | | |
| Office share × income <40k | −0.5725\* | 0.2623 | 0.029 |
| Office share × income 125k+ | 0.0903 | 0.1427 | 0.527 |
| Retail share × age <30 | 1.2806\*\*\* | 0.2194 | < 0.001 |
| Industrial share × woman | −1.3588\*\*\* | 0.1758 | < 0.001 |
| ***Wage proxy*** | | | |
| High-wage share | 1.8532\*\*\* | 0.2009 | < 0.001 |
| High-wage share × income <40k | −1.0012\* | 0.3920 | 0.011 |
| High-wage share × income 75–125k | 1.0819\*\*\* | 0.2006 | < 0.001 |
| High-wage share × income 125k+ | 1.6792\*\*\* | 0.2318 | < 0.001 |

