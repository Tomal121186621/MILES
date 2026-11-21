---
hide:
  - toc
---

# Tour and leg modes

Tour mode choice by segment (car driver is the reference mode), the joint-tour models of the household representative, and the mode of the legs of transit tours. The tour models have no term for fewer cars than drivers, because cars are allocated within the household in application.

!!! note "Reading the tables"
    Coefficient: maximum-likelihood estimate, with significance stars \*\*\* p < 0.01, \*\* p < 0.05, \* p < 0.10; robust (sandwich) standard error; two-sided p-value. N: observations; K: estimated parameters; LL(β̂): log-likelihood at the estimates; ρ̄²: adjusted rho-square. Hold-out: fit on the held-out half of the data, which was also used in the specification search. "Reference": the omitted category; "—": removed from the model.

### Tour mode: work

Multinomial logit with the generalised cost (value of time 50 % of the hourly household income); weighted to the ACS commute shares (weighted exogenous sample maximum likelihood).

<div class="estfit"><span>N = 9,126</span><span>K = 51</span><span>LL(β̂) = −4,313.1</span><span>ρ̄² = 0.626</span><span>Hold-out: LL −4,284.0</span></div>

<div class="modetab" markdown>

| Variable | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|
| ***Generic and car-driver terms*** |  |  |  |  |  |
| Generalised cost (min) | −0.0038\*\*\* (all modes)<br><span class='se'>(0.0006) <0.001</span> |  |  |  |  |
| Car driver: paid-parking share at the destination | −4.6374\*\*\* (all modes)<br><span class='se'>(0.2515) <0.001</span> |  |  |  |  |
| Car driver: tour with stops | 0.6111\*\*\* (all modes)<br><span class='se'>(0.0746) <0.001</span> |  |  |  |  |
| ***Constant and distance*** |  |  |  |  |  |
| Constant | 0.7865\*\*<br><span class='se'>(0.3902) 0.044</span> | −5.4376\*\*\*<br><span class='se'>(0.8669) <0.001</span> | −1.5150\*\*\*<br><span class='se'>(0.3626) <0.001</span> | −0.8279\*\*<br><span class='se'>(0.4096) 0.043</span> | −0.6228<br><span class='se'>(0.4312) 0.149</span> |
| Round-trip distance (km) | −0.3247\*\*\*<br><span class='se'>(0.0281) <0.001</span> | −0.0733\*\*\*<br><span class='se'>(0.0120) <0.001</span> | −0.0007<br><span class='se'>(0.0018) 0.710</span> | −0.0049\*<br><span class='se'>(0.0026) 0.062</span> | 0.0025<br><span class='se'>(0.0018) 0.170</span> |
| ***Person*** |  |  |  |  |  |
| Age (years) | −0.0186\*\*\*<br><span class='se'>(0.0057) 0.001</span> | −0.0054<br><span class='se'>(0.0079) 0.493</span> | −0.0042<br><span class='se'>(0.0042) 0.312</span> | −0.0006<br><span class='se'>(0.0043) 0.885</span> | −0.0091\*\*<br><span class='se'>(0.0040) 0.022</span> |
| Man | 0.1232<br><span class='se'>(0.1615) 0.446</span> | 0.8784\*\*\*<br><span class='se'>(0.2565) <0.001</span> | −0.5478\*\*\*<br><span class='se'>(0.1087) <0.001</span> | −0.1651<br><span class='se'>(0.1211) 0.173</span> | −0.0488<br><span class='se'>(0.1017) 0.631</span> |
| Driving licence | 0<br><span class='se'>normalised</span> | 1.1679\*<br><span class='se'>(0.6446) 0.070</span> | −1.7983\*\*\*<br><span class='se'>(0.3063) <0.001</span> | −1.1796\*\*\*<br><span class='se'>(0.3167) <0.001</span> | −0.5221<br><span class='se'>(0.3492) 0.135</span> |
| ***Household*** |  |  |  |  |  |
| Household size | 0.0807<br><span class='se'>(0.0903) 0.371</span> | 0.2245\*<br><span class='se'>(0.1185) 0.058</span> | 0.1267\*\*<br><span class='se'>(0.0589) 0.031</span> | 0.1363\*<br><span class='se'>(0.0773) 0.078</span> | −0.0018<br><span class='se'>(0.0702) 0.979</span> |
| Cars | −0.3702\*\*\*<br><span class='se'>(0.1011) <0.001</span> | −0.5194\*\*\*<br><span class='se'>(0.1577) <0.001</span> | 0.0210<br><span class='se'>(0.0603) 0.727</span> | −0.5990\*\*\*<br><span class='se'>(0.0917) <0.001</span> | −0.4599\*\*\*<br><span class='se'>(0.0796) <0.001</span> |
| Member under 18 | −0.4655\*<br><span class='se'>(0.2534) 0.066</span> | −0.5102<br><span class='se'>(0.3484) 0.143</span> | −0.2407<br><span class='se'>(0.1632) 0.140</span> | −0.4462\*\*<br><span class='se'>(0.1951) 0.022</span> | −0.3887\*\*<br><span class='se'>(0.1724) 0.024</span> |
| ***Main activity zone*** |  |  |  |  |  |
| Suburban (reference) | reference |  |  |  |  |
| Core city | −0.0939<br><span class='se'>(0.1826) 0.607</span> | 1.0220\*\*\*<br><span class='se'>(0.3420) 0.003</span> | −0.1068<br><span class='se'>(0.1246) 0.391</span> | 0.1252<br><span class='se'>(0.1451) 0.388</span> | 0.5988\*\*\*<br><span class='se'>(0.1359) <0.001</span> |
| Rural |  | −0.4792<br><span class='se'>(0.8800) 0.586</span> | 0.3243\*<br><span class='se'>(0.1844) 0.079</span> | −1.3836<br><span class='se'>(1.0693) 0.196</span> | −4.3927\*\*\*<br><span class='se'>(0.3533) <0.001</span> |

</div>

<p class='estnote'>Observations: 9,126 tours (estimation half of the Regional Travel Survey 2017/18); alternatives: 6; parameters: 51; LL = −4,313.1; BIC = 9,091.3; hold-out half: LL = −4,284.0. Level of service: generalised cost GC = T + 60 C / VOT (minutes), VOT = 0.5 × household income / 2,080 h; choice-based sample weights (ACS commute shares). Times and costs of the round trip. Core city and rural: area type of the zone of the main activity.</p>

<p class='estnote'>Each cell: coefficient with stars; below it, the robust standard error in brackets and the p-value.</p>

### Tour mode: school

Neither time nor cost is significant; only distance is kept.

<div class="estfit"><span>N = 2,651</span><span>K = 34</span><span>LL(β̂) = −972.5</span><span>ρ̄² = 0.651</span><span>Hold-out: LL −1,096.5</span></div>

<div class="modetab" markdown>

| Variable | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|
| ***Generic and car-driver terms*** |  |  |  |  |  |
| Car driver: paid-parking share at the destination | −5.2938\*\*\* (all modes)<br><span class='se'>(1.1770) <0.001</span> |  |  |  |  |
| ***Constant and distance*** |  |  |  |  |  |
| Constant | −0.3336<br><span class='se'>(0.8190) 0.684</span> | −3.9468\*\*\*<br><span class='se'>(1.0869) <0.001</span> | −1.5688\*\*<br><span class='se'>(0.7448) 0.035</span> | −1.4070\*<br><span class='se'>(0.8415) 0.095</span> | −0.5817<br><span class='se'>(0.8488) 0.493</span> |
| Round-trip distance (km) | −0.3743\*\*\*<br><span class='se'>(0.0460) <0.001</span> | −0.2252\*\*\*<br><span class='se'>(0.0443) <0.001</span> | −0.0249\*\*\*<br><span class='se'>(0.0080) 0.002</span> | −0.0183<br><span class='se'>(0.0150) 0.224</span> | −0.0117<br><span class='se'>(0.0090) 0.193</span> |
| ***Person*** |  |  |  |  |  |
| Age (years) | −0.0062<br><span class='se'>(0.0139) 0.657</span> | 0.0069<br><span class='se'>(0.0175) 0.693</span> | −0.0221\*<br><span class='se'>(0.0119) 0.065</span> | −0.0105<br><span class='se'>(0.0120) 0.380</span> | −0.0105<br><span class='se'>(0.0120) 0.380</span> |
| Man | 0.5770\*<br><span class='se'>(0.3138) 0.066</span> | 1.4520\*\*\*<br><span class='se'>(0.5197) 0.005</span> | 0.3062<br><span class='se'>(0.2751) 0.266</span> | 0.4556<br><span class='se'>(0.3305) 0.168</span> | 0.4556<br><span class='se'>(0.3305) 0.168</span> |
| Driving licence | 0<br><span class='se'>normalised</span> | −0.3671<br><span class='se'>(0.6382) 0.565</span> | −0.9519\*\*<br><span class='se'>(0.4766) 0.046</span> | −0.0148<br><span class='se'>(0.5219) 0.977</span> | −0.0148<br><span class='se'>(0.5219) 0.977</span> |
| ***Household*** |  |  |  |  |  |
| Household size | 0.3656\*\*\*<br><span class='se'>(0.1315) 0.005</span> | 0.6560\*\*\*<br><span class='se'>(0.1852) <0.001</span> | 0.3565\*\*\*<br><span class='se'>(0.1178) 0.002</span> | 0.4493\*\*\*<br><span class='se'>(0.1439) 0.002</span> | 0.4493\*\*\*<br><span class='se'>(0.1439) 0.002</span> |
| Cars | −0.4870\*\*<br><span class='se'>(0.1902) 0.010</span> | −0.1205<br><span class='se'>(0.3290) 0.714</span> | −0.0624<br><span class='se'>(0.1539) 0.685</span> | −1.1721\*\*\*<br><span class='se'>(0.2266) <0.001</span> | −1.1721\*\*\*<br><span class='se'>(0.2266) <0.001</span> |
| Member under 18 | −0.8537\*<br><span class='se'>(0.5031) 0.090</span> | −2.3450\*\*\*<br><span class='se'>(0.5989) <0.001</span> | 0.3682<br><span class='se'>(0.3419) 0.282</span> | −1.6117\*\*\*<br><span class='se'>(0.4550) <0.001</span> | −1.6117\*\*\*<br><span class='se'>(0.4550) <0.001</span> |

</div>

<p class='estnote'>Observations: 2,651 tours (estimation half of the Regional Travel Survey 2017/18); alternatives: 6; parameters: 34; LL = −972.5; BIC = 2,213.0; hold-out half: LL = −1,096.5. Level of service: round-trip distance on every mode (travel time is not significant for school tours); bus and train share the person and household coefficients (one value shown in both columns). Times and costs of the round trip. Core city and rural: area type of the zone of the main activity.</p>

<p class='estnote'>Each cell: coefficient with stars; below it, the robust standard error in brackets and the p-value.</p>

### Tour mode: shopping

Time and cost enter separately.

<div class="estfit"><span>N = 3,206</span><span>K = 44</span><span>LL(β̂) = −1,150.2</span><span>ρ̄² = 0.713</span><span>Hold-out: LL −1,107.0</span></div>

<div class="modetab" markdown>

| Variable | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|
| ***Generic and car-driver terms*** |  |  |  |  |  |
| Travel time (min) | −0.0128\*\*\* (all modes)<br><span class='se'>(0.0030) <0.001</span> |  |  |  |  |
| Travel cost (\$) | −0.0624\*\*\* (all modes)<br><span class='se'>(0.0182) <0.001</span> |  |  |  |  |
| Car driver: paid-parking share at the destination | −4.1023\*\*\* (all modes)<br><span class='se'>(1.3967) 0.003</span> |  |  |  |  |
| Car driver: tour with stops | 0.3945\*\*\* (all modes)<br><span class='se'>(0.1273) 0.002</span> |  |  |  |  |
| ***Constant and distance*** |  |  |  |  |  |
| Constant | 2.9289\*\*\*<br><span class='se'>(0.5614) <0.001</span> | −2.3327<br><span class='se'>(1.5420) 0.130</span> | −2.1902\*\*\*<br><span class='se'>(0.4841) <0.001</span> | −0.5279<br><span class='se'>(0.9225) 0.567</span> | 0.2299<br><span class='se'>(1.2740) 0.857</span> |
| Round-trip distance (km) | −0.5637\*\*\*<br><span class='se'>(0.0603) <0.001</span> | −0.1002\*<br><span class='se'>(0.0595) 0.092</span> |  |  |  |
| ***Person*** |  |  |  |  |  |
| Age (years) | −0.0253\*\*\*<br><span class='se'>(0.0063) <0.001</span> | −0.0473\*\*\*<br><span class='se'>(0.0128) <0.001</span> | 0.0044<br><span class='se'>(0.0053) 0.405</span> | 0.0103<br><span class='se'>(0.0110) 0.348</span> | −0.0081<br><span class='se'>(0.0129) 0.533</span> |
| Man | −0.0813<br><span class='se'>(0.2075) 0.695</span> | 0.8361<br><span class='se'>(0.6277) 0.183</span> | −1.4446\*\*\*<br><span class='se'>(0.1668) <0.001</span> | −0.5768<br><span class='se'>(0.3683) 0.117</span> | −0.7478<br><span class='se'>(0.5258) 0.155</span> |
| Driving licence | 0<br><span class='se'>normalised</span> | 0.6230<br><span class='se'>(0.8757) 0.477</span> | −2.3233\*\*\*<br><span class='se'>(0.3839) <0.001</span> | −1.3038\*\*\*<br><span class='se'>(0.4694) 0.005</span> | 0.0109<br><span class='se'>(0.6896) 0.987</span> |
| ***Household*** |  |  |  |  |  |
| Household size | −0.1676<br><span class='se'>(0.1478) 0.257</span> | −0.3609<br><span class='se'>(0.3145) 0.251</span> |  | −0.0387<br><span class='se'>(0.2667) 0.885</span> | −0.2744<br><span class='se'>(0.4016) 0.494</span> |
| Cars | −0.7759\*\*\*<br><span class='se'>(0.1979) <0.001</span> | −0.1824<br><span class='se'>(0.3515) 0.604</span> | 0.2224\*\*\*<br><span class='se'>(0.0765) 0.004</span> | −1.5403\*\*\*<br><span class='se'>(0.3075) <0.001</span> | −0.7252\*\*<br><span class='se'>(0.3591) 0.043</span> |
| Member under 18 | −0.9645\*\*\*<br><span class='se'>(0.3692) 0.009</span> | −1.4126<br><span class='se'>(1.0641) 0.184</span> | −1.2228\*\*\*<br><span class='se'>(0.2179) <0.001</span> | −0.4264<br><span class='se'>(0.8144) 0.601</span> | −1.0792<br><span class='se'>(1.3374) 0.420</span> |
| ***Tour*** |  |  |  |  |  |
| Joint household tour | 0.8974\*\*\*<br><span class='se'>(0.2747) 0.001</span> | 1.3931\*\*<br><span class='se'>(0.6334) 0.028</span> | 4.2055\*\*\*<br><span class='se'>(0.2082) <0.001</span> | 0.8448<br><span class='se'>(0.5284) 0.110</span> | −0.4445<br><span class='se'>(1.1019) 0.687</span> |

</div>

<p class='estnote'>Observations: 3,206 tours (estimation half of the Regional Travel Survey 2017/18); alternatives: 6; parameters: 44; LL = −1,150.2; BIC = 2,655.7; hold-out half: LL = −1,107.0. Level of service: travel time and cost separately. Times and costs of the round trip. Core city and rural: area type of the zone of the main activity.</p>

<p class='estnote'>Each cell: coefficient with stars; below it, the robust standard error in brackets and the p-value.</p>

### Tour mode: other

Nested logit: car driver with car passenger, bus with train; time and cost enter separately.

<div class="estfit"><span>N = 10,405</span><span>K = 57</span><span>LL(β̂) = −4,916.7</span><span>ρ̄² = 0.623</span><span>Hold-out: LL −5,049.8</span></div>

<div class="modetab" markdown>

| Variable | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|
| ***Generic and car-driver terms*** |  |  |  |  |  |
| Travel time (min) | −0.0051\*\*\* (all modes)<br><span class='se'>(0.0013) <0.001</span> |  |  |  |  |
| Travel cost (\$) | −0.0075\*\* (all modes)<br><span class='se'>(0.0034) 0.028</span> |  |  |  |  |
| Car driver: paid-parking share at the destination | −1.9767\*\*\* (all modes)<br><span class='se'>(0.3587) <0.001</span> |  |  |  |  |
| Car driver: tour with stops | 0.2120\*\*\* (all modes)<br><span class='se'>(0.0523) <0.001</span> |  |  |  |  |
| Nest parameter, car driver and passenger | 2.0177\*\*\* (all modes)<br><span class='se'>(0.2129) <0.001</span> |  |  |  |  |
| Nest parameter, bus and train | 1.2566 (all modes)<br><span class='se'>(0.1905) 0.178</span> |  |  |  |  |
| ***Constant and distance*** |  |  |  |  |  |
| Constant | 0.9676\*\*\*<br><span class='se'>(0.2384) <0.001</span> | −3.2901\*\*\*<br><span class='se'>(0.5486) <0.001</span> | −0.0793<br><span class='se'>(0.1689) 0.639</span> | −0.5664<br><span class='se'>(0.4575) 0.216</span> | 0.0277<br><span class='se'>(0.4135) 0.947</span> |
| Round-trip distance (km) | −0.3963\*\*\*<br><span class='se'>(0.0198) <0.001</span> | −0.1181\*\*\*<br><span class='se'>(0.0177) <0.001</span> |  |  |  |
| ***Person*** |  |  |  |  |  |
| Age (years) | −0.0101\*\*\*<br><span class='se'>(0.0027) <0.001</span> | −0.0180\*\*\*<br><span class='se'>(0.0064) 0.005</span> | −0.0023\*<br><span class='se'>(0.0014) 0.095</span> | 0.0084<br><span class='se'>(0.0051) 0.104</span> | −0.0012<br><span class='se'>(0.0048) 0.801</span> |
| Man | −0.1413<br><span class='se'>(0.0913) 0.122</span> | 0.5363\*\*<br><span class='se'>(0.2506) 0.032</span> | −0.6536\*\*\*<br><span class='se'>(0.0685) <0.001</span> | −0.2031<br><span class='se'>(0.1924) 0.291</span> | −0.3199\*<br><span class='se'>(0.1778) 0.072</span> |
| Driving licence | 0<br><span class='se'>normalised</span> | −0.2210<br><span class='se'>(0.3678) 0.548</span> | −1.2811\*\*\*<br><span class='se'>(0.1915) <0.001</span> | −1.6587\*\*\*<br><span class='se'>(0.2567) <0.001</span> | −0.9749\*\*\*<br><span class='se'>(0.2756) <0.001</span> |
| ***Household*** |  |  |  |  |  |
| Household size | 0.0283<br><span class='se'>(0.0513) 0.581</span> | 0.2054<br><span class='se'>(0.1249) 0.100</span> | −0.0061<br><span class='se'>(0.0273) 0.823</span> | 0.3605\*\*\*<br><span class='se'>(0.1314) 0.006</span> | 0.0768<br><span class='se'>(0.1063) 0.470</span> |
| Cars | −0.4642\*\*\*<br><span class='se'>(0.0661) <0.001</span> | −0.5179\*\*<br><span class='se'>(0.2022) 0.010</span> | 0.0871\*\*\*<br><span class='se'>(0.0229) <0.001</span> | −2.0093\*\*\*<br><span class='se'>(0.1974) <0.001</span> | −0.8189\*\*\*<br><span class='se'>(0.1676) <0.001</span> |
| Member under 18 | −0.0257<br><span class='se'>(0.1453) 0.860</span> | −0.2430<br><span class='se'>(0.3699) 0.511</span> | −0.5620\*\*\*<br><span class='se'>(0.0877) <0.001</span> | −1.2776\*\*\*<br><span class='se'>(0.4338) 0.003</span> | −1.0061\*\*\*<br><span class='se'>(0.3863) 0.009</span> |
| ***Tour*** |  |  |  |  |  |
| Joint household tour | 0.3484\*\*\*<br><span class='se'>(0.1204) 0.004</span> | −0.2983<br><span class='se'>(0.2673) 0.265</span> | 1.4181\*\*\*<br><span class='se'>(0.1424) <0.001</span> | 0.3935<br><span class='se'>(0.2623) 0.134</span> | 0.4521\*<br><span class='se'>(0.2386) 0.058</span> |
| Accompanying | 0.4473\*\*\*<br><span class='se'>(0.1417) 0.002</span> | −1.3657\*\*<br><span class='se'>(0.6429) 0.034</span> | −0.0562<br><span class='se'>(0.0978) 0.566</span> | −0.5405<br><span class='se'>(0.4238) 0.202</span> | −1.4764\*\*<br><span class='se'>(0.5768) 0.010</span> |
| Recreation | 0.8960\*\*\*<br><span class='se'>(0.1031) <0.001</span> | 1.6520\*\*\*<br><span class='se'>(0.3079) <0.001</span> | 0.1309\*\*\*<br><span class='se'>(0.0433) 0.003</span> | −0.0636<br><span class='se'>(0.1992) 0.749</span> | 0.4287\*\*<br><span class='se'>(0.1842) 0.020</span> |

</div>

<p class='estnote'>Observations: 10,405 tours (estimation half of the Regional Travel Survey 2017/18); alternatives: 6; parameters: 57; LL = −4,916.7; BIC = 10,360.6; hold-out half: LL = −5,049.8. Level of service: travel time and cost separately; nested logit with car driver and passenger in one nest and bus and train in another (nest parameters μ ≥ 1). Times and costs of the round trip. Core city and rural: area type of the zone of the main activity.</p>

<p class='estnote'>Each cell: coefficient with stars; below it, the robust standard error in brackets and the p-value.</p>

### Tour mode: joint shopping tours

Group-level model of the household representative, one observation per joint group; train is not available.

<div class="estfit"><span>N = 452</span><span>K = 15</span><span>LL(β̂) = −112.8</span><span>ρ̄² = 0.780</span><span>Hold-out: LL −94.0</span></div>

<div class="modetab" markdown>

| Variable | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|
| ***Generic and car-driver terms*** |  |  |  |  |  |
| Travel time (min) | −0.0106 (all modes)<br><span class='se'>(0.0066) 0.112</span> |  |  |  |  |
| Travel cost (\$) | −0.0781 (all modes)<br><span class='se'>(0.0791) 0.324</span> |  |  |  |  |
| Car driver: paid-parking share at the destination | −4.8848 (all modes)<br><span class='se'>(3.2558) 0.134</span> |  |  |  |  |
| Car driver: tour with stops | 0.2655 (all modes)<br><span class='se'>(0.4132) 0.520</span> |  |  |  |  |
| ***Constant and distance*** |  |  |  |  |  |
| Constant | 4.7851\*\*<br><span class='se'>(1.8901) 0.011</span> | −2.5461\*\*\*<br><span class='se'>(0.9833) 0.010</span> | −3.7854\*\*\*<br><span class='se'>(0.5066) <0.001</span> | −4.1331\*\*\*<br><span class='se'>(0.6807) <0.001</span> |  |
| Round-trip distance (km) | −0.7373\*\*<br><span class='se'>(0.3413) 0.031</span> | −0.4050\*\*\*<br><span class='se'>(0.1555) 0.009</span> |  |  |  |
| ***Person*** |  |  |  |  |  |
| Age (years) | −0.0221<br><span class='se'>(0.0172) 0.199</span> |  |  |  |  |
| Man | 0.2108<br><span class='se'>(0.6248) 0.736</span> |  |  |  |  |
| Driving licence | 0<br><span class='se'>normalised</span> |  |  |  |  |
| ***Household*** |  |  |  |  |  |
| Household size | −0.9192<br><span class='se'>(0.7359) 0.212</span> |  |  |  |  |
| Cars | −0.3860<br><span class='se'>(0.3969) 0.331</span> |  |  |  |  |
| Member under 18 | −0.6997<br><span class='se'>(1.4525) 0.630</span> |  |  |  |  |

</div>

<p class='estnote'>Observations: 452 joint groups (estimation half of the Regional Travel Survey 2017/18); alternatives: 6; parameters: 15; LL = −112.8; BIC = 317.4; hold-out half: LL = −94.0. Level of service: travel time and cost separately; one observation per joint household group, variables of the group's representative (the oldest member with car driver available); car driver when a member drove; modes chosen by fewer than 20 groups have only the constant (train: not chosen, not available). Times and costs of the round trip. Core city and rural: area type of the zone of the main activity.</p>

<p class='estnote'>Each cell: coefficient with stars; below it, the robust standard error in brackets and the p-value.</p>

### Tour mode: joint recreation and other tours

Group-level model of the household representative, one observation per joint group.

<div class="estfit"><span>N = 1,296</span><span>K = 25</span><span>LL(β̂) = −450.3</span><span>ρ̄² = 0.710</span><span>Hold-out: LL −459.1</span></div>

<div class="modetab" markdown>

| Variable | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|
| ***Generic and car-driver terms*** |  |  |  |  |  |
| Travel time (min) | −0.0006 (all modes)<br><span class='se'>(0.0027) 0.828</span> |  |  |  |  |
| Travel cost (\$) | −0.0128 (all modes)<br><span class='se'>(0.0225) 0.571</span> |  |  |  |  |
| Car driver: paid-parking share at the destination | −5.2992\*\* (all modes)<br><span class='se'>(2.1856) 0.015</span> |  |  |  |  |
| Car driver: tour with stops | 0.2586 (all modes)<br><span class='se'>(0.2201) 0.240</span> |  |  |  |  |
| Nest parameter, car driver and passenger | 1.0000 (all modes)<br><span class='se'>(0.5840) 1.000</span> |  |  |  |  |
| Nest parameter, bus and train | 2.3060 (all modes)<br><span class='se'>(1.2305) 0.289</span> |  |  |  |  |
| ***Constant and distance*** |  |  |  |  |  |
| Constant | −0.1628<br><span class='se'>(0.9673) 0.866</span> | −3.9778\*\*\*<br><span class='se'>(0.6681) <0.001</span> | −1.4047\*<br><span class='se'>(0.8030) 0.080</span> | −4.0962\*\*\*<br><span class='se'>(0.3896) <0.001</span> | −2.9432\*\*\*<br><span class='se'>(0.4791) <0.001</span> |
| Round-trip distance (km) | −0.5030\*\*\*<br><span class='se'>(0.0692) <0.001</span> | −0.1157\*<br><span class='se'>(0.0625) 0.064</span> |  |  |  |
| ***Person*** |  |  |  |  |  |
| Age (years) | −0.0142<br><span class='se'>(0.0114) 0.215</span> |  | −0.0214<br><span class='se'>(0.0220) 0.332</span> |  |  |
| Man | 0.0683<br><span class='se'>(0.3360) 0.839</span> |  | 0.3127<br><span class='se'>(0.3451) 0.365</span> |  |  |
| Driving licence | 0<br><span class='se'>normalised</span> |  | −1.7927<br><span class='se'>(1.3292) 0.177</span> |  |  |
| ***Household*** |  |  |  |  |  |
| Household size | −0.0409<br><span class='se'>(0.2035) 0.841</span> |  | 0.1969<br><span class='se'>(0.1693) 0.245</span> |  |  |
| Cars | −0.2167<br><span class='se'>(0.2765) 0.433</span> |  | 0.2205<br><span class='se'>(0.2345) 0.347</span> |  |  |
| Member under 18 | 0.8055<br><span class='se'>(0.5310) 0.129</span> |  | −0.8904\*<br><span class='se'>(0.5041) 0.077</span> |  |  |
| ***Tour*** |  |  |  |  |  |
| Recreation | 1.6269\*\*\*<br><span class='se'>(0.4356) <0.001</span> |  | 0.0087<br><span class='se'>(0.3139) 0.978</span> |  |  |

</div>

<p class='estnote'>Observations: 1,296 joint groups (estimation half of the Regional Travel Survey 2017/18); alternatives: 6; parameters: 25; LL = −450.3; BIC = 1,079.7; hold-out half: LL = −459.1. Level of service: travel time and cost separately; nested logit as for individual other tours; one observation per joint household group, variables of the group's representative (the oldest member with car driver available); car driver when a member drove; modes chosen by fewer than 20 groups have only the constant. Times and costs of the round trip. Core city and rural: area type of the zone of the main activity.</p>

<p class='estnote'>Each cell: coefficient with stars; below it, the robust standard error in brackets and the p-value.</p>

### Mode of the legs of transit tours

Multinomial logit over transit, walk, car passenger, car driver and bicycle for each leg of a tour whose main mode is transit; 35 parameters. Car driver is available only with a household car that is free over the tour window, and the model was estimated under the same rule. The term for fewer cars than drivers is kept, because the car allocation covers only part of that effect.

<div class="estfit"><span>N = 6,773</span><span>K = 35</span><span>LL(β̂) = −3,421.5</span><span>ρ̄² = 0.621</span><span>Hold-out: LL −3,291.0</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| ***Constants (reference: transit)*** |  |  |  |
| Constant: walk | 2.2760\*\*\* | 0.2022 | <0.001 |
| Constant: car passenger | −0.0368 | 0.2183 | 0.866 |
| Constant: car driver | 0.9506\*\*\* | 0.2837 | <0.001 |
| Constant: bike | −3.7510\*\*\* | 0.2474 | <0.001 |
| ***Position of the leg*** |  |  |  |
| First leg: walk | −1.3038\*\*\* | 0.1482 | <0.001 |
| First leg: car passenger | −0.2812\*\* | 0.1362 | 0.039 |
| First leg: car driver | 0.4342\*\*\* | 0.1574 | 0.006 |
| Last leg: walk | −1.1436\*\*\* | 0.1265 | <0.001 |
| Last leg: car passenger | −0.3519\*\*\* | 0.1218 | 0.004 |
| Leg at the main activity: walk | −1.1097\*\*\* | 0.1171 | <0.001 |
| Leg at the main activity: car passenger | −1.3937\*\*\* | 0.1072 | <0.001 |
| Leg at the main activity: car driver | −2.9781\*\*\* | 0.1621 | <0.001 |
| ***Distance and transit service*** |  |  |  |
| Distance (km): walk | −0.8467\*\*\* | 0.0424 | <0.001 |
| Distance (km): bike | −0.1966\*\*\* | 0.0314 | <0.001 |
| Ln(1 + distance, km): car passenger | −0.5194\*\*\* | 0.0685 | <0.001 |
| Ln(1 + distance, km): car driver | −0.7058\*\*\* | 0.0795 | <0.001 |
| Transit time (10 min): transit | −0.0480\*\* | 0.0196 | 0.014 |
| No transit path: transit | −0.8350\*\*\* | 0.1289 | <0.001 |
| ***Earlier legs of the tour*** |  |  |  |
| Previous leg by car, as driver: car driver | 2.6033\*\*\* | 0.2100 | <0.001 |
| First leg by car, as driver (on the last leg): car driver | 1.8572\*\*\* | 0.2718 | <0.001 |
| Previous leg by car, as passenger: car passenger | 1.5461\*\*\* | 0.1414 | <0.001 |
| Previous leg on foot: walk | 0.5986\*\*\* | 0.1404 | <0.001 |
| ***Person and household*** |  |  |  |
| No car in the household: car passenger | −0.5090\*\*\* | 0.1260 | <0.001 |
| Fewer cars than drivers in the household: car driver | −0.6447\*\*\* | 0.1656 | <0.001 |
| Age under 18: car passenger | 0.4976\*\* | 0.2308 | 0.031 |
| Age 65 or over: car passenger | −0.4406\*\* | 0.2226 | 0.048 |
| Driving licence: car passenger | −0.3626\*\* | 0.1440 | 0.012 |
| ***Tour*** |  |  |  |
| Work tour: walk | 0.6076\*\*\* | 0.1232 | <0.001 |
| Work tour: car passenger | 0.5830\*\*\* | 0.1606 | <0.001 |
| Work tour: car driver | 0.5469\*\*\* | 0.2061 | 0.008 |
| School tour: car passenger | 0.5168\*\* | 0.2100 | 0.014 |
| Leaves in the peak: car passenger | −0.5883\*\*\* | 0.1030 | <0.001 |
| Leaves in the peak: walk | −0.3247\*\*\* | 0.1061 | 0.002 |
| Home in the Washington region: walk | 0.2675\*\* | 0.1270 | 0.035 |
| Home in the Washington region: car driver | −0.8802\*\*\* | 0.1447 | <0.001 |

<p class='estnote'>Observations: 6,773 legs of transit tours; alternatives: transit (reference), walk, car passenger, car driver, bike; parameters: 35. LL(0) = −9,119.4; LL(β̂) = −3,421.5; BIC = 7,151.7. Hold-out half (6,417 legs): LL = −3,291.0. Availability: walk up to 8 km, bike up to 30 km; car driver with a driving licence, age 16 or over and a household car that is free over the tour window (not taken by the household's car-driver tours that overlap it). Legs of outings from the workplace are not included. Estimation: Biogeme, unweighted, robust standard errors.</p>
