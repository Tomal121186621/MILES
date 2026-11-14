---
hide:
  - toc
---

# Tour and leg modes

Tour mode choice by segment (car driver is the reference mode), the joint-tour models of the household representative, and the mode of the legs of transit tours.

!!! note "Reading the tables"
    Coefficient: maximum-likelihood estimate with robust (sandwich) standard error; \*\*\* p < 0.001, \*\* p < 0.01, \* p < 0.05. N: observations; K: estimated parameters; LL(β̂): log-likelihood at the estimates; ρ̄²: adjusted rho-square. The same tables can be re-estimated with Biogeme from the estimation package.

### Tour mode: work

Multinomial logit with the generalised cost; weighted to the ACS commute shares (weighted exogenous sample maximum likelihood).

<div class="estfit"><span>N = 9,126</span><span>K = 51</span><span>LL(β̂) = −4,313.1</span><span>ρ̄² = 0.626</span><span>Hold-out: LL −4,284.0</span></div>

<div class="modetab" markdown>

| Variable | All modes | Car driver | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|---:|---:|
| Generalised cost (min) | −0.0038\*\*\*<br><span class='se'>(0.0006)</span> |  |  |  |  |  |  |
| Paid-parking share at the destination |  | −4.6374\*\*\*<br><span class='se'>(0.2515)</span> |  |  |  |  |  |
| Tour with stops |  | 0.6111\*\*\*<br><span class='se'>(0.0746)</span> |  |  |  |  |  |
| Constant |  |  | 0.7865\*<br><span class='se'>(0.3902)</span> | −5.4376\*\*\*<br><span class='se'>(0.8669)</span> | −1.5150\*\*\*<br><span class='se'>(0.3626)</span> | −0.8279\*<br><span class='se'>(0.4096)</span> | −0.6228<br><span class='se'>(0.4312)</span> |
| Round-trip distance (km) |  |  | −0.3247\*\*\*<br><span class='se'>(0.0281)</span> | −0.0733\*\*\*<br><span class='se'>(0.0120)</span> | −0.0007<br><span class='se'>(0.0018)</span> | −0.0049<br><span class='se'>(0.0026)</span> | 0.0025<br><span class='se'>(0.0018)</span> |
| Age (years) |  |  | −0.0186\*\*<br><span class='se'>(0.0057)</span> | −0.0054<br><span class='se'>(0.0079)</span> | −0.0042<br><span class='se'>(0.0042)</span> | −0.0006<br><span class='se'>(0.0043)</span> | −0.0091\*<br><span class='se'>(0.0040)</span> |
| Man |  |  | 0.1232<br><span class='se'>(0.1615)</span> | 0.8784\*\*\*<br><span class='se'>(0.2565)</span> | −0.5478\*\*\*<br><span class='se'>(0.1087)</span> | −0.1651<br><span class='se'>(0.1211)</span> | −0.0488<br><span class='se'>(0.1017)</span> |
| Driving licence |  |  |  | 1.1679<br><span class='se'>(0.6446)</span> | −1.7983\*\*\*<br><span class='se'>(0.3063)</span> | −1.1796\*\*\*<br><span class='se'>(0.3167)</span> | −0.5221<br><span class='se'>(0.3492)</span> |
| Household size |  |  | 0.0807<br><span class='se'>(0.0903)</span> | 0.2245<br><span class='se'>(0.1185)</span> | 0.1267\*<br><span class='se'>(0.0589)</span> | 0.1363<br><span class='se'>(0.0773)</span> | −0.0018<br><span class='se'>(0.0702)</span> |
| Cars |  |  | −0.3702\*\*\*<br><span class='se'>(0.1011)</span> | −0.5194\*\*\*<br><span class='se'>(0.1577)</span> | 0.0210<br><span class='se'>(0.0603)</span> | −0.5990\*\*\*<br><span class='se'>(0.0917)</span> | −0.4599\*\*\*<br><span class='se'>(0.0796)</span> |
| Member under 18 |  |  | −0.4655<br><span class='se'>(0.2534)</span> | −0.5102<br><span class='se'>(0.3484)</span> | −0.2407<br><span class='se'>(0.1632)</span> | −0.4462\*<br><span class='se'>(0.1951)</span> | −0.3887\*<br><span class='se'>(0.1724)</span> |
| Core city |  |  | −0.0939<br><span class='se'>(0.1826)</span> | 1.0220\*\*<br><span class='se'>(0.3420)</span> | −0.1068<br><span class='se'>(0.1246)</span> | 0.1252<br><span class='se'>(0.1451)</span> | 0.5988\*\*\*<br><span class='se'>(0.1359)</span> |
| Rural |  |  |  | −0.4792<br><span class='se'>(0.8800)</span> | 0.3243<br><span class='se'>(0.1844)</span> | −1.3836<br><span class='se'>(1.0693)</span> | −4.3927\*\*\*<br><span class='se'>(0.3533)</span> |

</div>

<p class='estnote'>Cells: coefficient (robust standard error). Car driver is the reference mode.</p>

### Tour mode: school

Multinomial logit; time and cost are not significant and only distance is kept.

<div class="estfit"><span>N = 2,651</span><span>K = 34</span><span>LL(β̂) = −972.5</span><span>ρ̄² = 0.651</span><span>Hold-out: LL −1,096.5</span></div>

<div class="modetab" markdown>

| Variable | Car driver | Walk | Bike | Car passenger | Bus | Train | Bus and train (shared) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Paid-parking share at the destination | −5.2938\*\*\*<br><span class='se'>(1.1770)</span> |  |  |  |  |  |  |
| Constant |  | −0.3336<br><span class='se'>(0.8190)</span> | −3.9468\*\*\*<br><span class='se'>(1.0869)</span> | −1.5688\*<br><span class='se'>(0.7448)</span> | −1.4070<br><span class='se'>(0.8415)</span> | −0.5817<br><span class='se'>(0.8488)</span> |  |
| Round-trip distance (km) |  | −0.3743\*\*\*<br><span class='se'>(0.0460)</span> | −0.2252\*\*\*<br><span class='se'>(0.0443)</span> | −0.0249\*\*<br><span class='se'>(0.0080)</span> | −0.0183<br><span class='se'>(0.0150)</span> | −0.0117<br><span class='se'>(0.0090)</span> |  |
| Age (years) |  | −0.0062<br><span class='se'>(0.0139)</span> | 0.0069<br><span class='se'>(0.0175)</span> | −0.0221<br><span class='se'>(0.0119)</span> |  |  | −0.0105<br><span class='se'>(0.0120)</span> |
| Man |  | 0.5770<br><span class='se'>(0.3138)</span> | 1.4520\*\*<br><span class='se'>(0.5197)</span> | 0.3062<br><span class='se'>(0.2751)</span> |  |  | 0.4556<br><span class='se'>(0.3305)</span> |
| Driving licence |  |  | −0.3671<br><span class='se'>(0.6382)</span> | −0.9519\*<br><span class='se'>(0.4766)</span> |  |  | −0.0148<br><span class='se'>(0.5219)</span> |
| Household size |  | 0.3656\*\*<br><span class='se'>(0.1315)</span> | 0.6560\*\*\*<br><span class='se'>(0.1852)</span> | 0.3565\*\*<br><span class='se'>(0.1178)</span> |  |  | 0.4493\*\*<br><span class='se'>(0.1439)</span> |
| Cars |  | −0.4870\*<br><span class='se'>(0.1902)</span> | −0.1205<br><span class='se'>(0.3290)</span> | −0.0624<br><span class='se'>(0.1539)</span> |  |  | −1.1721\*\*\*<br><span class='se'>(0.2266)</span> |
| Member under 18 |  | −0.8537<br><span class='se'>(0.5031)</span> | −2.3450\*\*\*<br><span class='se'>(0.5989)</span> | 0.3682<br><span class='se'>(0.3419)</span> |  |  | −1.6117\*\*\*<br><span class='se'>(0.4550)</span> |

</div>

<p class='estnote'>Cells: coefficient (robust standard error). Car driver is the reference mode.</p>

### Tour mode: shopping

Multinomial logit with separate travel time and cost.

<div class="estfit"><span>N = 3,206</span><span>K = 44</span><span>LL(β̂) = −1,150.2</span><span>ρ̄² = 0.713</span><span>Hold-out: LL −1,107.0</span></div>

<div class="modetab" markdown>

| Variable | All modes | Car driver | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|---:|---:|
| Travel time (min) | −0.0128\*\*\*<br><span class='se'>(0.0030)</span> |  |  |  |  |  |  |
| Travel cost (\) | −0.0624\*\*\*<br><span class='se'>(0.0182)</span> |  |  |  |  |  |  |
| Paid-parking share at the destination |  | −4.1023\*\*<br><span class='se'>(1.3967)</span> |  |  |  |  |  |
| Tour with stops |  | 0.3945\*\*<br><span class='se'>(0.1273)</span> |  |  |  |  |  |
| Constant |  |  | 2.9289\*\*\*<br><span class='se'>(0.5614)</span> | −2.3327<br><span class='se'>(1.5420)</span> | −2.1902\*\*\*<br><span class='se'>(0.4841)</span> | −0.5279<br><span class='se'>(0.9225)</span> | 0.2299<br><span class='se'>(1.2740)</span> |
| Round-trip distance (km) |  |  | −0.5637\*\*\*<br><span class='se'>(0.0603)</span> | −0.1002<br><span class='se'>(0.0595)</span> |  |  |  |
| Age (years) |  |  | −0.0253\*\*\*<br><span class='se'>(0.0063)</span> | −0.0473\*\*\*<br><span class='se'>(0.0128)</span> | 0.0044<br><span class='se'>(0.0053)</span> | 0.0103<br><span class='se'>(0.0110)</span> | −0.0081<br><span class='se'>(0.0129)</span> |
| Man |  |  | −0.0813<br><span class='se'>(0.2075)</span> | 0.8361<br><span class='se'>(0.6277)</span> | −1.4446\*\*\*<br><span class='se'>(0.1668)</span> | −0.5768<br><span class='se'>(0.3683)</span> | −0.7478<br><span class='se'>(0.5258)</span> |
| Driving licence |  |  |  | 0.6230<br><span class='se'>(0.8757)</span> | −2.3233\*\*\*<br><span class='se'>(0.3839)</span> | −1.3038\*\*<br><span class='se'>(0.4694)</span> | 0.0109<br><span class='se'>(0.6896)</span> |
| Household size |  |  | −0.1676<br><span class='se'>(0.1478)</span> | −0.3609<br><span class='se'>(0.3145)</span> |  | −0.0387<br><span class='se'>(0.2667)</span> | −0.2744<br><span class='se'>(0.4016)</span> |
| Cars |  |  | −0.7759\*\*\*<br><span class='se'>(0.1979)</span> | −0.1824<br><span class='se'>(0.3515)</span> | 0.2224\*\*<br><span class='se'>(0.0765)</span> | −1.5403\*\*\*<br><span class='se'>(0.3075)</span> | −0.7252\*<br><span class='se'>(0.3591)</span> |
| Member under 18 |  |  | −0.9645\*\*<br><span class='se'>(0.3692)</span> | −1.4126<br><span class='se'>(1.0641)</span> | −1.2228\*\*\*<br><span class='se'>(0.2179)</span> | −0.4264<br><span class='se'>(0.8144)</span> | −1.0792<br><span class='se'>(1.3374)</span> |
| Joint household tour |  |  | 0.8974\*\*<br><span class='se'>(0.2747)</span> | 1.3931\*<br><span class='se'>(0.6334)</span> | 4.2055\*\*\*<br><span class='se'>(0.2082)</span> | 0.8448<br><span class='se'>(0.5284)</span> | −0.4445<br><span class='se'>(1.1019)</span> |

</div>

<p class='estnote'>Cells: coefficient (robust standard error). Car driver is the reference mode.</p>

### Tour mode: other

Nested logit (car driver with car passenger, bus with train) with separate travel time and cost.

<div class="estfit"><span>N = 10,405</span><span>K = 57</span><span>LL(β̂) = −4,916.7</span><span>ρ̄² = 0.623</span><span>Hold-out: LL −5,049.8</span></div>

<div class="modetab" markdown>

| Variable | All modes | Car driver | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|---:|---:|
| Travel time (min) | −0.0051\*\*\*<br><span class='se'>(0.0013)</span> |  |  |  |  |  |  |
| Travel cost (\) | −0.0075\*<br><span class='se'>(0.0034)</span> |  |  |  |  |  |  |
| Paid-parking share at the destination |  | −1.9767\*\*\*<br><span class='se'>(0.3587)</span> |  |  |  |  |  |
| Tour with stops |  | 0.2120\*\*\*<br><span class='se'>(0.0523)</span> |  |  |  |  |  |
| Nest parameter, car driver and passenger | 2.0177\*\*\*<br><span class='se'>(0.2129)</span> |  |  |  |  |  |  |
| Nest parameter, bus and train | 1.2566<br><span class='se'>(0.1905)</span> |  |  |  |  |  |  |
| Constant |  |  | 0.9676\*\*\*<br><span class='se'>(0.2384)</span> | −3.2901\*\*\*<br><span class='se'>(0.5486)</span> | −0.0793<br><span class='se'>(0.1689)</span> | −0.5664<br><span class='se'>(0.4575)</span> | 0.0277<br><span class='se'>(0.4135)</span> |
| Round-trip distance (km) |  |  | −0.3963\*\*\*<br><span class='se'>(0.0198)</span> | −0.1181\*\*\*<br><span class='se'>(0.0177)</span> |  |  |  |
| Age (years) |  |  | −0.0101\*\*\*<br><span class='se'>(0.0027)</span> | −0.0180\*\*<br><span class='se'>(0.0064)</span> | −0.0023<br><span class='se'>(0.0014)</span> | 0.0084<br><span class='se'>(0.0051)</span> | −0.0012<br><span class='se'>(0.0048)</span> |
| Man |  |  | −0.1413<br><span class='se'>(0.0913)</span> | 0.5363\*<br><span class='se'>(0.2506)</span> | −0.6536\*\*\*<br><span class='se'>(0.0685)</span> | −0.2031<br><span class='se'>(0.1924)</span> | −0.3199<br><span class='se'>(0.1778)</span> |
| Driving licence |  |  |  | −0.2210<br><span class='se'>(0.3678)</span> | −1.2811\*\*\*<br><span class='se'>(0.1915)</span> | −1.6587\*\*\*<br><span class='se'>(0.2567)</span> | −0.9749\*\*\*<br><span class='se'>(0.2756)</span> |
| Household size |  |  | 0.0283<br><span class='se'>(0.0513)</span> | 0.2054<br><span class='se'>(0.1249)</span> | −0.0061<br><span class='se'>(0.0273)</span> | 0.3605\*\*<br><span class='se'>(0.1314)</span> | 0.0768<br><span class='se'>(0.1063)</span> |
| Cars |  |  | −0.4642\*\*\*<br><span class='se'>(0.0661)</span> | −0.5179\*<br><span class='se'>(0.2022)</span> | 0.0871\*\*\*<br><span class='se'>(0.0229)</span> | −2.0093\*\*\*<br><span class='se'>(0.1974)</span> | −0.8189\*\*\*<br><span class='se'>(0.1676)</span> |
| Member under 18 |  |  | −0.0257<br><span class='se'>(0.1453)</span> | −0.2430<br><span class='se'>(0.3699)</span> | −0.5620\*\*\*<br><span class='se'>(0.0877)</span> | −1.2776\*\*<br><span class='se'>(0.4338)</span> | −1.0061\*\*<br><span class='se'>(0.3863)</span> |
| Joint household tour |  |  | 0.3484\*\*<br><span class='se'>(0.1204)</span> | −0.2983<br><span class='se'>(0.2673)</span> | 1.4181\*\*\*<br><span class='se'>(0.1424)</span> | 0.3935<br><span class='se'>(0.2623)</span> | 0.4521<br><span class='se'>(0.2386)</span> |
| Accompanying |  |  | 0.4473\*\*<br><span class='se'>(0.1417)</span> | −1.3657\*<br><span class='se'>(0.6429)</span> | −0.0562<br><span class='se'>(0.0978)</span> | −0.5405<br><span class='se'>(0.4238)</span> | −1.4764\*<br><span class='se'>(0.5768)</span> |
| Recreation |  |  | 0.8960\*\*\*<br><span class='se'>(0.1031)</span> | 1.6520\*\*\*<br><span class='se'>(0.3079)</span> | 0.1309\*\*<br><span class='se'>(0.0433)</span> | −0.0636<br><span class='se'>(0.1992)</span> | 0.4287\*<br><span class='se'>(0.1842)</span> |

</div>

<p class='estnote'>Cells: coefficient (robust standard error). Car driver is the reference mode.</p>

### Tour mode: joint shopping tours

Group-level model applied by the household representative; one observation per joint group.

<div class="estfit"><span>N = 452</span><span>K = 15</span><span>LL(β̂) = −112.8</span><span>ρ̄² = 0.780</span><span>Hold-out: LL −94.0</span></div>

<div class="modetab" markdown>

| Variable | All modes | Car driver | Walk | Bike | Car passenger | Bus |
|---|---:|---:|---:|---:|---:|---:|
| Travel time (min) | −0.0106<br><span class='se'>(0.0066)</span> |  |  |  |  |  |
| Travel cost (\) | −0.0781<br><span class='se'>(0.0791)</span> |  |  |  |  |  |
| Paid-parking share at the destination |  | −4.8848<br><span class='se'>(3.2558)</span> |  |  |  |  |
| Tour with stops |  | 0.2655<br><span class='se'>(0.4132)</span> |  |  |  |  |
| Constant |  |  | 4.7851\*<br><span class='se'>(1.8901)</span> | −2.5461\*<br><span class='se'>(0.9833)</span> | −3.7854\*\*\*<br><span class='se'>(0.5066)</span> | −4.1331\*\*\*<br><span class='se'>(0.6807)</span> |
| Round-trip distance (km) |  |  | −0.7373\*<br><span class='se'>(0.3413)</span> | −0.4050\*\*<br><span class='se'>(0.1555)</span> |  |  |
| Age (years) |  |  | −0.0221<br><span class='se'>(0.0172)</span> |  |  |  |
| Man |  |  | 0.2108<br><span class='se'>(0.6248)</span> |  |  |  |
| Household size |  |  | −0.9192<br><span class='se'>(0.7359)</span> |  |  |  |
| Cars |  |  | −0.3860<br><span class='se'>(0.3969)</span> |  |  |  |
| Member under 18 |  |  | −0.6997<br><span class='se'>(1.4525)</span> |  |  |  |

</div>

<p class='estnote'>Cells: coefficient (robust standard error). Car driver is the reference mode.</p>

### Tour mode: joint recreation and other tours

Group-level model applied by the household representative; one observation per joint group.

<div class="estfit"><span>N = 1,296</span><span>K = 25</span><span>LL(β̂) = −450.3</span><span>ρ̄² = 0.710</span><span>Hold-out: LL −459.1</span></div>

<div class="modetab" markdown>

| Variable | All modes | Car driver | Walk | Bike | Car passenger | Bus | Train |
|---|---:|---:|---:|---:|---:|---:|---:|
| Travel time (min) | −0.0006<br><span class='se'>(0.0027)</span> |  |  |  |  |  |  |
| Travel cost (\) | −0.0128<br><span class='se'>(0.0225)</span> |  |  |  |  |  |  |
| Paid-parking share at the destination |  | −5.2992\*<br><span class='se'>(2.1856)</span> |  |  |  |  |  |
| Tour with stops |  | 0.2586<br><span class='se'>(0.2201)</span> |  |  |  |  |  |
| Nest parameter, car driver and passenger | 1.0000<br><span class='se'>(0.5840)</span> |  |  |  |  |  |  |
| Nest parameter, bus and train | 2.3060<br><span class='se'>(1.2305)</span> |  |  |  |  |  |  |
| Constant |  |  | −0.1628<br><span class='se'>(0.9673)</span> | −3.9778\*\*\*<br><span class='se'>(0.6681)</span> | −1.4047<br><span class='se'>(0.8030)</span> | −4.0962\*\*\*<br><span class='se'>(0.3896)</span> | −2.9432\*\*\*<br><span class='se'>(0.4791)</span> |
| Round-trip distance (km) |  |  | −0.5030\*\*\*<br><span class='se'>(0.0692)</span> | −0.1157<br><span class='se'>(0.0625)</span> |  |  |  |
| Age (years) |  |  | −0.0142<br><span class='se'>(0.0114)</span> |  | −0.0214<br><span class='se'>(0.0220)</span> |  |  |
| Man |  |  | 0.0683<br><span class='se'>(0.3360)</span> |  | 0.3127<br><span class='se'>(0.3451)</span> |  |  |
| Driving licence |  |  |  |  | −1.7927<br><span class='se'>(1.3292)</span> |  |  |
| Household size |  |  | −0.0409<br><span class='se'>(0.2035)</span> |  | 0.1969<br><span class='se'>(0.1693)</span> |  |  |
| Cars |  |  | −0.2167<br><span class='se'>(0.2765)</span> |  | 0.2205<br><span class='se'>(0.2345)</span> |  |  |
| Member under 18 |  |  | 0.8055<br><span class='se'>(0.5310)</span> |  | −0.8904<br><span class='se'>(0.5041)</span> |  |  |
| Recreation |  |  | 1.6269\*\*\*<br><span class='se'>(0.4356)</span> |  | 0.0087<br><span class='se'>(0.3139)</span> |  |  |

</div>

<p class='estnote'>Cells: coefficient (robust standard error). Car driver is the reference mode.</p>

### Mode of the legs of transit tours

Multinomial logit over transit, walk, car passenger, car driver and bicycle for each leg of a tour whose main mode is transit.

<div class="estfit"><span>N = 6,792</span><span>K = 35</span><span>LL(β̂) = −3,501.8</span><span>Hold-out: LL −3,366.7</span></div>

| Variable | Coefficient | Robust s.e. | p |
|---|---:|---:|---:|
| Walk | 2.2663\*\*\* | 0.2011 | < 0.001 |
| Car passenger | −0.0416 | 0.2183 | 0.849 |
| Car driver | 0.8006\*\* | 0.2725 | 0.003 |
| Bike | −3.7509\*\*\* | 0.2473 | < 0.001 |
| First leg walk | −1.2897\*\*\* | 0.1475 | < 0.001 |
| First leg car passenger | −0.2788\* | 0.1363 | 0.041 |
| First leg car driver | 0.3594\* | 0.1510 | 0.017 |
| Last leg walk | −1.1393\*\*\* | 0.1263 | < 0.001 |
| Last leg car passenger | −0.3426\*\* | 0.1218 | 0.005 |
| Leg at main activity walk | −1.1085\*\*\* | 0.1168 | < 0.001 |
| Leg at main activity car passenger | −1.3923\*\*\* | 0.1069 | < 0.001 |
| Leg at main activity car driver | −2.9221\*\*\* | 0.1565 | < 0.001 |
| Km walk | −0.8488\*\*\* | 0.0423 | < 0.001 |
| Km bike | −0.1966\*\*\* | 0.0314 | < 0.001 |
| Ln 1 plus km car passenger | −0.5190\*\*\* | 0.0685 | < 0.001 |
| Ln 1 plus km car driver | −0.6729\*\*\* | 0.0770 | < 0.001 |
| Transit time 10min transit | −0.0480\* | 0.0194 | 0.013 |
| No transit path transit | −0.8385\*\*\* | 0.1280 | < 0.001 |
| Previous leg car driver car driver | 2.6465\*\*\* | 0.2000 | < 0.001 |
| First leg car driver on last leg car driver | 1.7846\*\*\* | 0.2643 | < 0.001 |
| Previous leg car passenger car passenger | 1.5384\*\*\* | 0.1411 | < 0.001 |
| Previous leg walk walk | 0.6057\*\*\* | 0.1404 | < 0.001 |
| No car car passenger | −0.5074\*\*\* | 0.1261 | < 0.001 |
| Fewer cars than drivers car driver | −0.9591\*\*\* | 0.1469 | < 0.001 |
| Age under 18 car passenger | 0.4971\* | 0.2306 | 0.031 |
| Age 65 plus car passenger | −0.4436\* | 0.2226 | 0.046 |
| Driving licence car passenger | −0.3637\* | 0.1440 | 0.012 |
| Work tour walk | 0.6010\*\*\* | 0.1230 | < 0.001 |
| Work tour car passenger | 0.5762\*\*\* | 0.1606 | < 0.001 |
| Work tour car driver | 0.5471\*\* | 0.2004 | 0.006 |
| School tour car passenger | 0.5118\* | 0.2097 | 0.015 |
| Peak departure car passenger | −0.5817\*\*\* | 0.1030 | < 0.001 |
| Peak departure walk | −0.3149\*\* | 0.1057 | 0.003 |
| Home in washington region walk | 0.2755\* | 0.1264 | 0.029 |
| Home in washington region car driver | −0.7515\*\*\* | 0.1373 | < 0.001 |

