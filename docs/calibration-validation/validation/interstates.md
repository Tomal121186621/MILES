# Interstates, station by station

Simulated weekday traffic on the interstates of the study area against the 2024 MDOT SHA counts at every matched mainline station. Model: passenger vehicles (cars of residents and of in-commuters), mean of five seeds, scaled from the 10 % sample. Count: average annual weekday traffic 2024, all vehicles, and passenger vehicles after removing the station's truck and bus share (the classified share where the station is classified, otherwise the regional share). FHWA limit: the maximum deviation for the station's volume group in the FHWA Travel Model Validation and Reasonableness Checking Manual. Stations are listed in milepoint order.

The model carries residents of the six counties and workers commuting into them. Through traffic, visitors and trucks are not simulated, so ratios below 1 are expected on the through routes (I-95, I-70, I-83 north of the Beltway).

## Summary by route

| Route | Stations | Count, passenger vehicles | Model | Model ÷ count | %RMSE | Within FHWA limit |
|---|---:|---:|---:|---:|---:|---:|
| [I-695](#i695) | 40 | 5,266,150 | 4,772,852 | 0.91 | 14.2 | 19 of 40 |
| [I-95](#i95) | 20 | 2,793,180 | 1,835,080 | 0.66 | 39.7 | 0 of 20 |
| [I-83](#i83) | 17 | 1,462,300 | 1,383,690 | 0.95 | 15.5 | 9 of 17 |
| [I-97](#i97) | 8 | 870,390 | 738,890 | 0.85 | 21.3 | 3 of 8 |
| [I-895](#i895) | 16 | 722,410 | 784,993 | 1.09 | 41.0 | 5 of 16 |
| [I-70](#i70) | 7 | 521,060 | 496,370 | 0.95 | 7.5 | 5 of 7 |
| [I-195](#i195) | 4 | 152,210 | 112,640 | 0.74 | 42.2 | 0 of 4 |
| [I-395](#i395) | 1 | 62,410 | 61,030 | 0.98 | 2.2 | 1 of 1 |
| [I-595](#i595) | 6 | 658,580 | 356,780 | 0.54 | 51.1 | 0 of 6 |
| [I-795](#i795) | 3 | 239,350 | 238,390 | 1.00 | 19.5 | 0 of 3 |
| **All interstates** | **122** | **12,748,040** | **10,780,715** | **0.85** | **28.6** | **42 of 122** |

## I-695

Baltimore Beltway.

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| P0077 | .15 mi north of Hollins Ferry Rd | Baltimore | 6 | 135,700 | 125,200 | 103,800 (278) | 0.83 | ±10 % | no |
| B1115 | .30 mi S of IS95 | Baltimore | 6 | 131,000 | 120,800 | 102,700 (221) | 0.85 | ±10 % | no |
| B0772 | .20 mi S of MD2 | Anne Arundel | 4 | 72,320 | 66,720 | 27,120 (290) | 0.41 | ±10 % | no |
| B1114 | .20 mi S of US1 | Baltimore | 9 | 180,500 | 166,500 | 147,000 (360) | 0.88 | ±10 % | no |
| B0774 | .20 mi S of IS97 | Anne Arundel | 4 | 108,800 | 100,400 | 78,690 (240) | 0.78 | ±10 % | no |
| B1113 | .40 mi N of US1 | Baltimore | 9 | 190,400 | 175,700 | 166,100 (294) | 0.95 | ±10 % | yes |
| B0776 | .20 mi N of MD648E | Anne Arundel | 7 | 128,900 | 118,900 | 129,800 (346) | 1.09 | ±10 % | yes |
| B1190 | .30 mi N of MD372 | Baltimore | 8 | 208,800 | 192,600 | 168,500 (337) | 0.87 | ±10 % | no |
| B0777 | .30 mi S of MD295 | Anne Arundel | 6 | 160,700 | 149,300 | 143,600 (278) | 0.96 | ±10 % | yes |
| B1213 | .20 mi N of MD144 | Baltimore | 8 | 194,200 | 179,200 | 157,100 (135) | 0.88 | ±10 % | no |
| B0778 | .20 mi N of MD295 | Anne Arundel | 6 | 114,400 | 105,500 | 100,700 (150) | 0.95 | ±10 % | yes |
| P0032 | 100ft north of Ingleside Ave | Baltimore | 8 | 181,200 | 167,200 | 163,400 (338) | 0.98 | ±10 % | yes |
| B0779 | 100ft S of BALTIMORE CO/L | Anne Arundel | 6 | 118,100 | 108,900 | 98,130 (210) | 0.90 | ±10 % | yes |
| B1111 | .50 mi S of IS70 | Baltimore | 6 | 185,400 | 168,800 | 168,400 (344) | 1.00 | ±10 % | yes |
| B1110 | .40 mi S of MD122 | Baltimore | 6 | 153,700 | 141,800 | 107,700 (350) | 0.76 | ±10 % | no |
| B1109 | .50 mi N of MD122 | Baltimore | 8 | 200,100 | 184,600 | 195,500 (437) | 1.06 | ±10 % | yes |
| P0078 | 1.03 Miles south of IS 795 | Baltimore | 6 | 185,800 | 171,400 | 178,200 (115) | 1.04 | ±10 % | yes |
| B1191 | .30 mi N of IS795 | Baltimore | 8 | 180,300 | 166,300 | 139,900 (190) | 0.84 | ±10 % | no |
| B1192 | .30 mi N of MD140 | Baltimore | 8 | 192,300 | 177,400 | 174,500 (439) | 0.98 | ±10 % | yes |
| B1193 | .10 mi N of MD129 | Baltimore | 8 | 181,200 | 167,200 | 156,400 (455) | 0.94 | ±10 % | yes |
| B1108 | .50 mi N of STEVENSON RD | Baltimore | 8 | 189,600 | 174,900 | 171,700 (408) | 0.98 | ±10 % | yes |
| B030040 | .50 mi N of GREENSPRING AVE | Baltimore | 7 | 172,500 | 159,200 | 170,700 (375) | 1.07 | ±10 % | yes |
| B1105 | .10 mi S of MD139 | Baltimore | 6 | 163,200 | 150,600 | 138,300 (187) | 0.92 | ±10 % | yes |
| B1104 | .50 mi S of MD45 | Baltimore | 6 | 164,200 | 151,500 | 150,600 (165) | 0.99 | ±10 % | yes |
| B1103 | .40 mi N of MD45 | Baltimore | 6 | 160,800 | 148,300 | 133,900 (276) | 0.90 | ±10 % | yes |
| P5044 | west of Providence Rd | Baltimore | 6 | 156,800 | 144,700 | 148,200 (357) | 1.02 | ±10 % | yes |
| P0054 | .41 mi north of Cromwell Bridge Rd | Baltimore | 6 | 149,000 | 137,400 | 154,200 (395) | 1.12 | ±10 % | no |
| B1100 | .20 mi N of MD542 | Baltimore | 6 | 153,500 | 141,600 | 144,700 (428) | 1.02 | ±10 % | yes |
| B1099 | .30 mi S of MD147 | Baltimore | 6 | 165,600 | 156,000 | 153,600 (312) | 0.98 | ±10 % | yes |
| B1194 | .40 mi N of MD147 | Baltimore | 6 | 169,800 | 160,700 | 127,100 (381) | 0.79 | ±10 % | no |
| P5041 | north of US 1 | Baltimore | 6 | 137,900 | 127,200 | 96,610 (359) | 0.76 | ±10 % | no |
| P0034 | .59 mi north of US 1 | Baltimore | 6 | 150,100 | 138,500 | 118,200 (436) | 0.85 | ±10 % | no |
| B1178 | .60 mi N of MD 7 | Baltimore | 6 | 118,100 | 109,000 | 92,420 (276) | 0.85 | ±10 % | no |
| B1196 | .10 mi S of MD7 | Baltimore | 6 | 111,000 | 102,400 | 71,640 (311) | 0.70 | ±10 % | no |
| B1097 | .30 mi N of US40 | Baltimore | 6 | 106,700 | 98,410 | 80,040 (308) | 0.81 | ±10 % | no |
| B1096 | 1.0 MILE south of MD 702 | Baltimore | 4 | 77,290 | 71,300 | 50,550 (120) | 0.71 | ±10 % | no |
| B1095 | .50 mi S of MD150 | Baltimore | 4 | 42,840 | 37,940 | 20,450 (84) | 0.54 | ±15 % | no |
| P0074 | 50ft south of Trappe Rd | Baltimore | 4 | 35,840 | 30,350 | 22,620 (88) | 0.75 | ±15 % | no |
| B1093 | .10 mi N of BEACHWOOD RD | Baltimore | 4 | 41,170 | 37,980 | 19,000 (102) | 0.50 | ±15 % | no |
| B1198 | .40 mi N of MD157 | Baltimore | 4 | 36,580 | 33,750 | 1,082 (32) | 0.03 | ±15 % | no |

## I-95

John F. Kennedy Memorial Highway and Fort McHenry Tunnel.

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| P0051 | .15 mi north of Howard County Line | Baltimore | 8 | 161,900 | 144,700 | 117,800 (262) | 0.81 | ±10 % | no |
| B2529 | .50 mi S of MD216 | Howard | 8 | 194,900 | 177,100 | 125,100 (105) | 0.71 | ±10 % | no |
| B240122 | .40 mi S of WASHINGTON BLVD | Baltimore City | 8 | 162,000 | 147,200 | 130,800 (180) | 0.89 | ±10 % | no |
| P0071 | .65 mi north of IS 195 | Baltimore | 8 | 162,000 | 146,200 | 119,300 (409) | 0.82 | ±10 % | no |
| B2530 | .50 mi N of MD216 | Howard | 8 | 208,900 | 183,100 | 137,800 (172) | 0.75 | ±10 % | no |
| B240123 | .30 mi N of WASHINGTON BLVD | Baltimore City | 8 | 158,500 | 144,000 | 125,400 (265) | 0.87 | ±10 % | no |
| B0983 | .30 mi S of BALTO CITY LINE | Baltimore | 8 | 212,300 | 190,100 | 141,400 (158) | 0.74 | ±10 % | no |
| B2449 | .50 mi S of MD24 | Harford | 9 | 152,800 | 138,900 | 52,250 (322) | 0.38 | ±10 % | no |
| B2429 | .50 mi N of MD24 | Harford | 6 | 121,000 | 110,000 | 63,950 (312) | 0.58 | ±10 % | no |
| B2531 | .70 mi S of MD175 | Howard | 8 | 191,700 | 174,200 | 131,800 (336) | 0.76 | ±10 % | no |
| T0007 | at Fort McHenry Tunnel | Baltimore City | 8 | 140,800 | 127,900 | 45,000 (426) | 0.35 | ±10 % | no |
| P0039 | .08 mi south of MD 103 | Howard | 8 | 191,900 | 174,400 | 138,300 (329) | 0.79 | ±10 % | no |
| B2440 | .50 mi N of MD543 | Harford | 6 | 101,000 | 91,820 | 56,210 (193) | 0.61 | ±10 % | no |
| B240124 | .30 mi S of MD150 | Baltimore City | 8 | 115,100 | 104,600 | 75,510 (377) | 0.72 | ±10 % | no |
| B2532 | .50 mi N of MD100 | Howard | 8 | 178,600 | 162,300 | 120,600 (265) | 0.74 | ±10 % | no |
| B240125 | .40 mi N of MD150 | Baltimore City | 7 | 116,900 | 106,300 | 73,740 (435) | 0.69 | ±10 % | no |
| B240072 | .30 mi N of US40 | Baltimore City | 9 | 106,100 | 93,550 | 40,530 (534) | 0.43 | ±10 % | no |
| B2430 | .60 mi N of MD22 | Harford | 6 | 80,280 | 64,710 | 39,030 (187) | 0.60 | ±10 % | no |
| B030064 | .10 mi S of KENWOOD AVE | Baltimore | 10 | 185,700 | 167,000 | 30,330 (121) | 0.18 | ±10 % | no |
| B0989 | .50 mi N of MD43 | Baltimore | 10 | 161,600 | 145,100 | 70,230 (465) | 0.48 | ±10 % | no |

## I-83

Jones Falls Expressway and Harrisburg Expressway.

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| B240001 | .10 mi N of FAYETTE ST | Baltimore City | 5 | 55,770 | 50,690 | 50,420 (206) | 0.99 | ±10 % | yes |
| P0076 | .04 mi north of Old Pimlico Rd | Baltimore | 7 | 87,680 | 85,810 | 78,640 (168) | 0.92 | ±10 % | yes |
| BC002 | .30 mi S of north AVE | Baltimore City | 6 | 101,400 | 92,130 | 93,400 (262) | 1.01 | ±10 % | yes |
| B240002 | .20 mi S of 28TH ST | Baltimore City | 6 | 94,700 | 86,070 | 115,800 (267) | 1.34 | ±10 % | no |
| B0975 | .20 mi N of RUXTON RD | Baltimore | 6 | 92,390 | 83,970 | 72,320 (288) | 0.86 | ±10 % | no |
| B030038 | .30 mi N of JOPPA RD | Baltimore | 10 | 227,500 | 218,300 | 206,200 (291) | 0.94 | ±10 % | yes |
| B240003 | .10 mi N of 41ST ST STRUC #3207 | Baltimore City | 6 | 128,700 | 126,400 | 109,200 (148) | 0.86 | ±10 % | no |
| P0052 | .64 mi north of IS 695 | Baltimore | 6 | 126,900 | 115,300 | 123,800 (155) | 1.07 | ±10 % | yes |
| B240004 | .50 mi S of NORTHERN PKWY | Baltimore City | 6 | 110,000 | 99,960 | 115,800 (229) | 1.16 | ±10 % | no |
| B1189 | .40 mi N of TIMONIUM RD | Baltimore | 6 | 119,800 | 108,900 | 103,700 (104) | 0.95 | ±10 % | yes |
| B0977 | .50 mi N of PADONIA RD | Baltimore | 6 | 104,500 | 94,960 | 85,800 (140) | 0.90 | ±10 % | yes |
| B1199 | .10 mi N of WARREN RD | Baltimore | 6 | 80,850 | 73,480 | 67,790 (114) | 0.92 | ±10 % | yes |
| P0027 | .50 mile south of Belfast Rd | Baltimore | 4 | 60,050 | 53,090 | 48,150 (235) | 0.91 | ±10 % | yes |
| P5036 | .1 mi north of BELFAST RD | Baltimore | 4 | 51,830 | 47,110 | 23,060 (93) | 0.49 | ±10 % | no |
| B0979 | .50 mi N of MD137 | Baltimore | 4 | 55,560 | 50,500 | 37,290 (68) | 0.74 | ±10 % | no |
| B1188 | .50 mi N of MIDDLETOWN RD | Baltimore | 4 | 47,680 | 38,190 | 27,640 (49) | 0.72 | ±15 % | no |
| B0980 | .50 mi N of MD45 | Baltimore | 4 | 45,190 | 37,440 | 24,680 (55) | 0.66 | ±15 % | no |

## I-97

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| B020015 | .10 mi N of MD450 | Anne Arundel | 4 | 94,650 | 86,020 | 59,680 (126) | 0.69 | ±10 % | no |
| B0641 | .10 mi S of MILLERSVILLE RD STRUC #020148002 | Anne Arundel | 4 | 107,400 | 97,650 | 71,360 (154) | 0.73 | ±10 % | no |
| B0804 | .10 mi N of STRUC#0214000 | Anne Arundel | 6 | 122,100 | 110,900 | 100,400 (100) | 0.91 | ±10 % | yes |
| B0839 | .30 mi N of MD3BU | Anne Arundel | 6 | 142,000 | 129,100 | 85,100 (252) | 0.66 | ±10 % | no |
| B0627 | .10 mi N of MD174 | Anne Arundel | 6 | 124,900 | 113,500 | 121,700 (194) | 1.07 | ±10 % | yes |
| B020059 | .60 mi N of MD100 | Anne Arundel | 6 | 143,400 | 130,300 | 106,900 (136) | 0.82 | ±10 % | no |
| B0628 | .60 mi N of MD176 | Anne Arundel | 6 | 99,270 | 90,220 | 95,370 (204) | 1.06 | ±10 % | yes |
| P5037 | .20 MILE south of IS 695 | Anne Arundel | 6 | 124,000 | 112,700 | 98,380 (254) | 0.87 | ±10 % | no |

## I-895

Harbor Tunnel Thruway.

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| B0834 | A-.20 mi N of IS695 | Anne Arundel | 2 | 25,720 | 24,910 | 28,020 (208) | 1.12 | ±15 % | yes |
| B0843 | B-.10 mi N of MD2 | Anne Arundel | 4 | 21,230 | 20,400 | 50,400 (264) | 2.47 | ±20 % | no |
| B1120 | .50 mi N of HOWARD CO/L | Baltimore | 4 | 15,380 | 14,900 | 5,941 (65) | 0.40 | ±20 % | no |
| B0787 | .10 mi S of BALTO CITY LINE | Anne Arundel | 4 | 61,390 | 55,790 | 82,220 (309) | 1.47 | ±10 % | no |
| B0835 | B-.10 mi N of MD695 | Anne Arundel | 4 | 4,770 | 4,620 | 26,310 (209) | 5.70 | ±50 % | no |
| B2581 | .10 mi S of BALTIMORE CO/L | Howard | 2 | 14,810 | 14,340 | 2,812 (78) | 0.20 | ±20 % | no |
| BC044 | .30 mi S of FRANKFURST AVE | Baltimore City | 4 | 72,610 | 65,990 | 90,090 (215) | 1.36 | ±10 % | no |
| T0004 | at Baltimore Harbor Tunnel | Baltimore City | 4 | 85,540 | 77,740 | 104,700 (386) | 1.35 | ±10 % | no |
| B1121 | .30 mi N of IS695 | Baltimore | 4 | 13,850 | 12,590 | 11,120 (148) | 0.88 | ±20 % | yes |
| B1174 | .20 mi N of MD295 | Baltimore | 4 | 41,080 | 37,330 | 18,330 (150) | 0.49 | ±15 % | no |
| BC050 | .20 mi S of ODONNELL ST | Baltimore City | 4 | 75,640 | 68,740 | 84,830 (284) | 1.23 | ±10 % | no |
| BC051 | .20 mi N of ODONNELL ST | Baltimore City | 4 | 66,660 | 60,580 | 63,950 (237) | 1.06 | ±10 % | yes |
| BC052 | .10 mi S of E. LOMBARD ST | Baltimore City | 4 | 67,170 | 61,050 | 60,600 (219) | 0.99 | ±10 % | yes |
| BC053 | .20 mi N of E. LOMBARD ST | Baltimore City | 4 | 68,360 | 62,130 | 58,170 (232) | 0.94 | ±10 % | yes |
| BC008 | .20 mi S of MORAVIA RD | Baltimore City | 4 | 70,600 | 64,160 | 54,130 (220) | 0.84 | ±10 % | no |
| B0984 | .10 mi N of MORAVIA PARK DR | Baltimore City | 6 | 84,880 | 77,140 | 43,370 (249) | 0.56 | ±10 % | no |

## I-70

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| B1534 | 1.0 mi E of MD27 | Carroll | 6 | 70,640 | 64,200 | 57,000 (333) | 0.89 | ±10 % | no |
| P0053 | 1.25 Miles west of IS 695 | Baltimore | 6 | 101,400 | 91,970 | 96,740 (302) | 1.05 | ±10 % | yes |
| B2522 | .40 mi W of MD97 | Howard | 6 | 85,190 | 75,180 | 65,890 (289) | 0.88 | ±10 % | no |
| P0046 | .85 mi west of MD 32 | Howard | 6 | 85,130 | 77,370 | 72,240 (257) | 0.93 | ±10 % | yes |
| B2524 | .40 mi E of MD32 | Howard | 6 | 87,870 | 78,780 | 75,650 (229) | 0.96 | ±10 % | yes |
| B2583 | .10 mi W of MARRIOTTSVILLE RD | Howard | 4 | 67,720 | 61,550 | 57,180 (269) | 0.93 | ±10 % | yes |
| B2525 | .50 mi W of US29 | Howard | 4 | 82,200 | 72,010 | 71,670 (200) | 1.00 | ±10 % | yes |

## I-195

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| B0808 | .70 mi S of MD295 | Anne Arundel | 5 | 62,070 | 56,410 | 39,540 (231) | 0.70 | ±10 % | no |
| B1071 | .40 mi N of US1 | Baltimore | 4 | 47,570 | 46,120 | 20,230 (361) | 0.44 | ±15 % | no |
| B1073 | .40 mi N of IS95 | Baltimore | 4 | 28,360 | 25,780 | 21,310 (58) | 0.83 | ±15 % | no |
| P0066 | .59 mi north of MD 295 | Anne Arundel | 4 | 26,290 | 23,900 | 31,560 (380) | 1.32 | ±15 % | no |

## I-395

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| BC055 | .10 mi N of ML KING BLVD | Baltimore City | 4 | 64,790 | 62,410 | 61,030 (244) | 0.98 | ±10 % | yes |

## I-595

John Hanson Highway.

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| P0024 | US 50/IS 595 - 1.34 Miles west of MD 424 | Anne Arundel | 6 | 84,370 | 76,680 | 57,970 (151) | 0.76 | ±10 % | no |
| B0810 | .50 mi E of MD424 | Anne Arundel | 6 | 99,780 | 93,200 | 54,010 (132) | 0.58 | ±10 % | no |
| B0840 | .40 mi E of IS97 | Anne Arundel | 6 | 144,000 | 130,900 | 36,010 (103) | 0.28 | ±10 % | no |
| B0841 | .25 mi W of MD450 | Anne Arundel | 6 | 131,800 | 119,800 | 54,650 (77) | 0.46 | ±10 % | no |
| B0644 | .40 mi W of MD2 | Anne Arundel | 6 | 126,500 | 114,900 | 62,000 (122) | 0.54 | ±10 % | no |
| B0645 | .50 mi E of MD2 | Anne Arundel | 6 | 135,400 | 123,100 | 92,140 (150) | 0.75 | ±10 % | no |

## I-795

Northwest Expressway.

| Station | Location | County | Lanes | Count, all vehicles | Count, passenger | Model, passenger (s.d.) | Model ÷ count | FHWA limit | Within |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|
| B030066 | .10 mi N of MT. WILSON LA | Baltimore | 6 | 125,200 | 120,300 | 97,990 (216) | 0.81 | ±10 % | no |
| B1171 | .60 mi N of MD940 | Baltimore | 4 | 71,920 | 65,360 | 76,240 (128) | 1.17 | ±10 % | no |
| B1173 | .50 mi S of MD140 | Baltimore | 4 | 57,330 | 53,690 | 64,160 (70) | 1.20 | ±10 % | no |

## Capital Beltway (I-495)

The Capital Beltway lies outside the study area: the model carries only the residents of the six counties and the workers commuting into them who use it, not the Washington region's own traffic. The share below is therefore the part of the counted traffic made up of modelled persons, not a test of the model. Stations matched to the two carriageways named Capital Beltway in the network; the I-95 part of the Beltway in Prince George's County is included.

| Station | Location | County | Lanes | Count, all vehicles | Model, passenger | Model ÷ count |
|---|---|---|---:|---:|---:|---:|
| P5043 | north of MD 190 | Montgomery | 10 | 235,211 | 47,754 | 0.20 |
| B2899 | .50 mi W of MD187 | Montgomery | 6 | 110,853 | 46,003 | 0.41 |
| B2900 | .30 mi E of MD187 | Montgomery | 5 | 117,003 | 52,517 | 0.45 |
| B2971 | .20 mi E of MD355 | Montgomery | 8 | 214,280 | 74,414 | 0.35 |
| B2901 | .80 mi W of MD97 | Montgomery | 8 | 213,520 | 98,401 | 0.46 |
| P5029 | 0.08 mi east of Sligo Creek Pkwy | Montgomery | 8 | 215,826 | 101,911 | 0.47 |
| B2902 | .20 mi E of US29 | Montgomery | 8 | 207,093 | 88,162 | 0.43 |
| P0041 | .82 mi west of MD 650 | Montgomery | 8 | 193,608 | 93,375 | 0.48 |
| B3289 | .10 mi W of MD212 | Prince George's | 10 | 222,541 | 108,731 | 0.49 |
| B3155 | .30 mi S of MD210 | Prince George's | 8 | 203,510 | 6,244 | 0.03 |
| B3154 | .40 mi S of MD414 | Prince George's | 8 | 178,331 | 39,798 | 0.22 |
| P0049 | 200ft south of Temple Hill Rd Overpass | Prince George's | 8 | 163,866 | 50,507 | 0.31 |
| B3152 | .40 mi N of MD5 | Prince George's | 8 | 201,451 | 60,310 | 0.30 |
| B3151 | .40 mi S of MD4 | Prince George's | 8 | 197,140 | 65,932 | 0.33 |
| B160133 | .50 mi N of MD4 | Prince George's | 8 | 210,111 | 80,315 | 0.38 |
| P0043 | 1.02 Miles south of MD 214 | Prince George's | 8 | 209,313 | 83,571 | 0.40 |
| S1999160246 | .50 mile north of MD 214 | Prince George's | 8 | 203,231 | 83,868 | 0.41 |
| B3149 | .40 mi S of MD202 | Prince George's | 10 | 206,370 | 81,575 | 0.40 |
| B3148 | .10 mi S of MD704 | Prince George's | 8 | 202,610 | 92,833 | 0.46 |
| B3147 | .60 mi N of IS595/US50 | Prince George's | 8 | 223,181 | 86,677 | 0.39 |
| P0055 | .05 mi north of Good Luck Rd | Prince George's | 8 | 196,525 | 102,250 | 0.52 |
| B3145 | .30 mi S of MD201 | Prince George's | 8 | 215,931 | 69,766 | 0.32 |
| B3144 | .30 mi N of MD201 | Prince George's | 8 | 195,050 | 71,762 | 0.37 |
| B3354 | .40 mi S of US1 | Prince George's | 8 | 183,111 | 72,290 | 0.39 |
| B3143 | .30 mi N of US1 | Prince George's | 8 | 191,660 | 73,078 | 0.38 |
| **All 25 stations** | | | | **4,911,326** | **1,832,044** | **0.37** |

The value at B3155 (south of MD 210, near the Woodrow Wilson Bridge interchange) suggests that the station was matched to a minor carriageway; treat it with caution.
