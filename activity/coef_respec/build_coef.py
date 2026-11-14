#!/usr/bin/env python3
"""Generate ABIT-format coefficient/distribution files for Maryland from cleaned RTS + Tour-Based MITO.
See PROVENANCE.md for what is RTS-estimated vs assumed/transferred."""
import csv, json, math, statistics, os, collections
BASE=os.path.dirname(os.path.abspath(__file__))
RTS=os.path.join(BASE,"../../rts")
OUT=BASE
PURP6=["work","education","recreation","shopping","accompany","other"]
PURP6U=[p.upper() for p in PURP6]
def W(fn,header,rows):
    with open(os.path.join(OUT,fn),"w",newline="") as f:
        w=csv.writer(f); w.writerow(header); w.writerows(rows)

# ---------- read RTS ----------
tours=list(csv.DictReader(open(os.path.join(RTS,"rts_tours.csv"))))
pm={'HBW':'WORK','HBE':'EDUCATION','HBS':'SHOPPING','HBO':'OTHER','WBO':'OTHER'}
mn={'autoDriver':'CAR_DRIVER','autoPassenger':'CAR_PASSENGER','sr':'CAR_PASSENGER','bus':'BUS','train':'TRAIN','walk':'WALK','bike':'BIKE','other':'OTHER'}
persons=set(t['person_id'] for t in tours); NP=len(persons)
tour_by=collections.Counter(pm.get(t['purpose'],'OTHER') for t in tours)
# split HBO(OTHER) into recreation/accompany/other using trip d_activity codes
trips=list(csv.DictReader(open(os.path.join(RTS,"rts_trips_clean.csv"))))
dact=collections.Counter(int(r['d_activity']) for r in trips if r['d_activity'] not in ('','-9'))
# 10 social->RECREATION, 16 escort->ACCOMPANY, else OTHER (within non home/work/school/shop)
rec=dact.get(10,0)+dact.get(11,0); acc=dact.get(16,0); oth=sum(v for k,v in dact.items() if k in (18,17,12,13,14,15))
tot_disc=max(1,rec+acc+oth)
hbo=tour_by['OTHER']
rate={'WORK':tour_by['WORK']/NP,'EDUCATION':tour_by['EDUCATION']/NP,'SHOPPING':tour_by['SHOPPING']/NP,
      'RECREATION':hbo/NP*rec/tot_disc,'ACCOMPANY':hbo/NP*acc/tot_disc,'OTHER':hbo/NP*oth/tot_disc}
# mode share by purpose
ms=collections.defaultdict(collections.Counter)
for t in tours: ms[pm.get(t['purpose'],'OTHER')][mn.get(t['tour_mode'],'OTHER')]+=1
def share(P):
    tot=sum(ms[P].values()) or 1; return {m:ms[P][m]/tot for m in ['CAR_DRIVER','CAR_PASSENGER','TRAIN','TRAM_METRO','BUS','BIKE','WALK']}
# mode share by distance band
band=lambda d:0 if d<1 else 1 if d<3 else 2 if d<5 else 3 if d<10 else 4
mb=collections.defaultdict(collections.Counter)
for t in tours:
    try:d=float(t['dist_primary'])
    except:continue
    if d<0:continue
    mb[band(d)][mn.get(t['tour_mode'],'OTHER')]+=1
def bshare(b):
    tot=sum(mb[b].values()) or 1; return {m:mb[b][m]/tot for m in ['CAR_DRIVER','CAR_PASSENGER','TRAIN','TRAM_METRO','BUS','BIKE','WALK']}
# trip length (mi) by purpose  -> km
dp=collections.defaultdict(list)
for t in tours:
    try:d=float(t['dist_primary'])
    except:continue
    if d>0:dp[pm.get(t['purpose'],'OTHER')].append(d*1.60934)
distkm={P:(statistics.mean(dp[P]) if dp[P] else 5.0) for P in ['WORK','EDUCATION','SHOPPING','OTHER']}
distkm['RECREATION']=distkm['OTHER']; distkm['ACCOMPANY']=distkm['SHOPPING']
# start hour distribution by purpose (min-of-day)
sh=collections.defaultdict(collections.Counter)
for t in tours:
    try:h=int(float(t['start_min'])//15*15)
    except:continue
    sh[pm.get(t['purpose'],'OTHER')][h]+=1
# duration: primary_dep-primary_arr by purpose
dur=collections.defaultdict(list)
for t in tours:
    try:
        a=float(t['primary_arr']);d=float(t['primary_dep']);du=d-a
        if 0<du<1440:dur[pm.get(t['purpose'],'OTHER')].append(du)
    except:pass
# stops per tour by purpose
stops={P:statistics.mean([int(t['n_stops']) for t in tours if pm.get(t['purpose'],'OTHER')==P]) for P in tour_by}

# ---------- Phase-A ABIT-format files ----------
# Munich activity-gen files: all region/muni/econ/demog coefs=0; intercepts RTS-calibrated (zero-inflation logit)
mand_vars=["(Intercept)","calibration","hh.urban","hh.regionType_71","hh.regionType_72","hh.regionType_73","hh.regionType_74","hh.regionType_75","hh.regionType_76","hh.regionType_77","hh.municipalityType_51","hh.municipalityType_52","hh.municipalityType_53","hh.municipalityType_54","hh.municipalityType_55","hh.econStatus_1","hh.econStatus_2","hh.econStatus_3","hh.notEmployed","hh.size_2","hh.size_3","hh.size_4","hh.size_5","hh.children_1","hh.children_2","hh.children_3","hh.adults_1","hh.adults_2","hh.adults_3","hh.adults_4","hh.adults_per_child_0","hh.adults_per_child_1","hh.adults_per_child_2","p.age","p.age_gr_1","p.age_gr_2","p.age_gr_3","p.age_gr_4","p.age_gr_5","p.age_gr_6","p.age_gr_fine_1","p.age_gr_fine_2","p.age_gr_fine_3","p.age_gr_fine_5","p.age_gr_fine_6","p.age_gr_fine_7","p.occupationStatus_Student","p.occupationStatus_Halftime","p.occupationStatus_Employed","p.occupationStatus_Unemployed","p.female","p.driversLicense","p.ownBicycle","hh.cars_1","hh.cars_2","hh.cars_3","p.t_mand_habmode_car","p.t_mand_habmode_cycle","p.t_mand_habmode_PT","p.t_mand_habmode_walk","num_days_edu","num_days_work"]
def logit(p): p=min(max(p,1e-4),1-1e-4); return math.log(p/(1-p))
# zero model: prob of ZERO tours of purpose (per person) ; intercept = logit(P(zero))
def zero_intercept(P): return round(logit(1-min(0.99,rate[P])),4)
rows=[]
for v in mand_vars:
    r=[v]
    for P in ["WORK","EDUCATION"]:
        r.append(zero_intercept(P) if v=="(Intercept)" else 0.0)
    rows.append(r)
W("actgen.mand.zero.csv",["variable","work","education"],rows)
count_vars=["(Intercept)","1|2","2|3","3|4","4|5","5|6","6|7","calibration","calibration_1|2","calibration_2|3","calibration_3|4","calibration_4|5","calibration_5|6","calibration_6|7","theta"]+mand_vars[2:]
# ordered logit thresholds: mostly 1/day -> set 1|2 low so P(>=1 given not zero)~high
rows=[]
for v in count_vars:
    r=[v]
    for P in ["WORK","EDUCATION"]:
        val=0.0
        if v=="1|2": val=-2.0
        elif v in ("2|3","3|4","4|5","5|6","6|7"): val=2.0+["2|3","3|4","4|5","5|6","6|7"].index(v)
        elif v=="theta": val=1.0
        r.append(val)
    rows.append(r)
W("actgen.mand.count.csv",["variable","work","education"],rows)
# accompany zero + count (negbin)
rows=[[v,(zero_intercept("ACCOMPANY") if v=="(Intercept)" else 0.0)] for v in mand_vars]
W("actgen.acrr.zero.csv",["variable","accompany"],rows)
acc_count_vars=["(Intercept)","calibration","theta"]+mand_vars[2:]
rows=[[v,(round(math.log(max(0.05,rate["ACCOMPANY"])),4) if v=="(Intercept)" else (1.0 if v=="theta" else 0.0))] for v in acc_count_vars]
W("actgen.acrr.count.csv",["variable","accompany"],rows)
# shopping/recreation/other negbin count
rows=[]
for v in acc_count_vars:
    r=[v]
    for P in ["shopping","recreation","other"]:
        val=0.0
        if v=="(Intercept)": val=round(math.log(max(0.05,rate[P.upper()])),4)
        elif v=="theta": val=1.0
        r.append(val)
    rows.append(r)
W("actgen.shreot.count.csv",["variable","shopping","recreation","other"],rows)
# subtour work/education (RTS work-based subtours ~ WBO share)
wbo=sum(1 for t in tours if t['purpose']=='WBO'); wtours=sum(1 for t in tours if t['purpose']=='HBW')
sub_asc=round(logit(max(0.01,wbo/max(1,wtours))),4)
W("actgen.subtour.work.csv",["variable","yes"],[[v,(sub_asc if v=="ASC" else 0.0)] for v in ["ASC","actDuration_6_24","actStart_8_12","actEnd_12_24","isTourOnFriday","isTourOnWeekend","isOccupation_halftime","isOccupation_student","calibration"]])
W("actgen.subtour.education.csv",["variable","yes"],[[v,(-3.0 if v=="ASC" else 0.0)] for v in ["ASC","actStart_7_12","actEnd_12_24","isAge<16","calibration"]])
# split onto mandatory / discretionary (stop split) -> use RTS stop-on-mandatory propensity
splitm_vars=["(Intercept)","hh.econStatus_1","hh.econStatus_2","hh.econStatus_3","hh.notEmployed","hh.size_2","hh.size_3","hh.size_4","hh.size_5","hh.children_1","hh.children_2","hh.children_3","hh.adults_1","hh.adults_2","hh.adults_3","hh.adults_4","hh.adults_per_child_0","hh.adults_per_child_1","hh.adults_per_child_2","p.age_gr_1","p.age_gr_2","p.age_gr_3","p.age_gr_4","p.age_gr_5","p.age_gr_6","p.occupationStatus_Student","p.occupationStatus_Employed","p.occupationStatus_Halftime","p.occupationStatus_Unemployed","p.female","p.driversLicense","p.ownBicycle","hh.cars_1","hh.cars_2","hh.cars_3","p.t_mand_habmode_PT","p.t_mand_habmode_car","p.t_mand_habmode_cycle","p.t_mand_habmode_walk","act.purpose_accompany","act.purpose_shop","act.purpose_other","act.purpose_recreation","calibration"]
W("act.split.type.onto.mandatory.csv",["variable","discAllActSplit"],[[v,(0.0 if v!="(Intercept)" else 0.0)] for v in splitm_vars])
disc_cols=["accompany_on_accompany","shop_on_accompany","shop_on_shop","other_on_accompany","other_on_shop","other_on_other","recreation_on_accompany","recreation_on_shop","recreation_on_other","recreation_on_recreation"]
splitd_vars=["(Intercept)","p.acts_accompany_disc","p.acts_accompany_main","p.acts_shop_disc","p.acts_shop_main","p.acts_other_disc","p.acts_other_main","p.acts_recreation_disc","calibration"]
W("act.split.type.onto.discretionary.csv",["variable"]+disc_cols,[[v]+[0.0]*len(disc_cols) for v in splitd_vars])

# destination choice main/stop (ALPHA/BETA) ; BETA = -decay per km from RTS mean dist
def beta_for(P): return round(-1.0/max(1.5,distkm.get(P.upper(),5.0)),4)  # exp decay scale ~ mean dist
rows=[]
for v in ["ALPHA","ALPHA_calibration","BETA","BETA_calibration"]:
    r=[v]
    for P in PURP6:
        if v=="ALPHA":r.append(1.0)
        elif v=="ALPHA_calibration":r.append(1.0)
        elif v=="BETA":r.append(beta_for(P))
        else:r.append(1.0)
    rows.append(r)
W("destination.choice.main.act.csv",["variable"]+PURP6,rows)
rows=[]
for v in ["ALPHA","ALPHA_calibration","BETA","BETA_calibration"]:
    r=[v]+[ (1.0 if v in("ALPHA","ALPHA_calibration","BETA_calibration") else beta_for(P)) for P in PURP6U]
    rows.append(r)
W("destination.choice.stop.act.csv",["variable"]+PURP6U,rows)
# attractors: weight by purpose
attr_types=["hh.total","jj.total","jj.retail","jj.office","jj.other","students"]
attr_w={"work":{"jj.total":1.0},"education":{"students":1.0,"hh.total":0.1},"recreation":{"hh.total":0.6,"jj.other":0.4},
        "shopping":{"jj.retail":1.0},"accompany":{"hh.total":0.7,"students":0.3},"other":{"jj.total":0.5,"hh.total":0.5}}
rows=[[a]+[attr_w[P].get(a,0.0) for P in PURP6] for a in attr_types]
W("destination.choice.attractors.csv",["variable"]+PURP6,rows)
# subtour destination (calibration row; BETA hardcoded in java)
W("subtour.destination.output.csv",["variable"]+PURP6,[["calibration"]+[0.0]*6,["ALPHA"]+[1.0]*6,["BETA"]+[beta_for(p) for p in PURP6]])

# TOD start.time.distributions (week-min). Single representative weekday=Tuesday (day idx1 -> offset 1440)
DAYOFF=1440
rows=[]
for P in PURP6U:
    src="OTHER" if P in ("RECREATION","ACCOMPANY") else P
    tot=sum(sh[src].values()) or 1
    for minute in range(0,1440,15):
        pr=sh[src].get(minute,0)/tot
        if pr>0: rows.append([DAYOFF+minute,P,round(pr,6)])
W("start.time.distributions.csv",["time_week_min","purpose","start_time_prob"],rows)
# duration.distributions
rows=[]
for P in PURP6U:
    src="OTHER" if P in ("RECREATION","ACCOMPANY") else P
    dl=dur.get(src,[60]); 
    hist=collections.Counter(min(1425,int(x//15*15)) for x in dl); tot=sum(hist.values()) or 1
    for dm,ct in sorted(hist.items()):
        rows.append([dm,P,0,24,round(ct/tot,6)])
W("duration.distributions.csv",["duration_min","purpose","start_from_h","start_to_h","duration_prob"],rows)
# subtour time
W("start.time.subtour.csv",["min","startTimeProbability"],[[m,round(1/48,6)] for m in range(600,1200,15)])
W("act.duration.subtour.csv",["min","actDurationProbability"],[[m,round(1/8,6)] for m in [15,30,45,60,75,90,105,120]])
# day of week mandatory (single weekday: Tue prob 1 for weekdays split, weekend ~0) 4 econ x 7 day x 2 purpose
rows=[]
for P in ["WORK","EDUCATION"]:
    for e in range(1,5):
        for d,pr in [("MONDAY",0.2),("TUESDAY",0.2),("WEDNESDAY",0.2),("THURSDAY",0.2),("FRIDAY",0.2),("SATURDAY",0.0),("SUNDAY",0.0)]:
            rows.append([P,e,d,pr])
W("day.of.week.distribution.mandatory.acts.csv",["purpose","econStatus","dayOfWeek","probabilities"],rows)

# tour mode nested logit files (ASC from RTS purpose shares; gc small)
modes=["TRAIN","TRAM_METRO","BUS","CAR_DRIVER","CAR_PASSENGER","BIKE","WALK"]
mode_vars=["INTERCEPT","gc","nestingCoefficient","p.female","p.age_gr_1","p.age_gr_2","p.age_gr_45","p.age_gr_6","p.mobilityRestricted","hh.size","hh.children","hh.regionType_12","hh.regionType_34","hh.regionType_56","hh.urban","tour.purpose_education","tour.stops2orMore","p.mainCommuteMode_occupied_carD","p.mainCommuteMode_occupied_carP","p.mainCommuteMode_occupied_cycle","p.mainCommuteMode_occupied_PT","p.mainCommuteMode_occupied_walk","num_days_edu","num_days_work","num_days_mand","vot_less_or_equal_income_4","vot_income_5_to_10","vot_income_greater_10"]
days=["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
def calib_rows_mand():
    out=[]
    for base in ["work","education"]:
        for reg in ["muc","nonMuc"]:
            for d in days: out.append(f"calibration_{base}_{d}_{reg}")
    return out
def calib_rows_disc():
    out=[]
    for reg in ["muc","nonMuc"]:
        for d in days: out.append(f"calibration_{d}_{reg}")
    return out
def asc(P,m):
    s=share(P); import math as _m
    p=max(1e-3,s.get(m,1e-3)); ref=max(1e-3,s.get("CAR_DRIVER",0.5))
    return round(_m.log(p/ref),4)
def write_mode(fn,P):
    vlist=mode_vars+(calib_rows_mand() if P in("WORK","EDUCATION") else calib_rows_disc())
    rows=[]
    for v in vlist:
        r=[v]
        for m in modes:
            if v=="INTERCEPT": r.append(asc(P,m))
            elif v=="gc": r.append(-0.03)
            elif v=="nestingCoefficient": r.append(1.0)
            else: r.append(0.0)
        rows.append(r)
    W(fn,["variable"]+modes,rows)
write_mode("mandatoryMode_nestedLogit.csv","WORK")
write_mode("accompanyMode_nestedLogit.csv","ACCOMPANY")
write_mode("shoppingMode_nestedLogit.csv","SHOPPING")
write_mode("recreationMode_nestedLogit.csv","RECREATION")
write_mode("otherMode_nestedLogit.csv","OTHER")
# habitual mode minimal (single-day inactive)
W("habitual.mode.coef.csv",["variable","car_driver","car_passenger","pt","bike","walk"],[["INTERCEPT",0.0,0.0,0.0,0.0,0.0]])
# subtour mode
W("mode.choice.subtour.csv",["variable","switchToWalk"],[[v,0.0] for v in ["log(distanceKm+1)","isOccupation_Employed","isOccupation_Halftime","isTourMainMode_CarD","isTourPurpose_Education","calibration"]])
# tod_dummy regenerated from RTS single-day (for SimpleTimeAssignment fallback)
rows=[]
for P in PURP6U:
    src="OTHER" if P in ("RECREATION","ACCOMPANY") else P
    tot=sum(sh[src].values()) or 1
    for minute in range(0,1440,15):
        rows.append([minute,P,round(sh[src].get(minute,0)/tot,6)])
W("tod_rts.csv",["time","purpose","probability"],rows)

# ---------- rts_params.json for compact Maryland runtime models ----------
params={
 "tours_per_person_per_day":{P:round(rate[P],4) for P in ["WORK","EDUCATION","SHOPPING","RECREATION","ACCOMPANY","OTHER"]},
 "mode_share_by_band_mi":{str(b):bshare(b) for b in range(5)},
 "mode_share_by_purpose":{P:share(P) for P in ["WORK","EDUCATION","SHOPPING","RECREATION","ACCOMPANY","OTHER"] if P in ms or P in ("RECREATION","ACCOMPANY")},
 "dist_mean_km_by_purpose":{P:round(distkm.get(P,5.0),3) for P in ["WORK","EDUCATION","SHOPPING","RECREATION","ACCOMPANY","OTHER"]},
 "start_hour_share_by_purpose":{P:{str(h):round(c/ (sum(sh[('OTHER' if P in ('RECREATION','ACCOMPANY') else P)].values()) or 1),5) for h,c in sh[('OTHER' if P in ('RECREATION','ACCOMPANY') else P)].items()} for P in ["WORK","EDUCATION","SHOPPING","RECREATION","ACCOMPANY","OTHER"]},
 "duration_min_mean_by_purpose":{P:round(statistics.mean(dur.get(('OTHER' if P in ('RECREATION','ACCOMPANY') else P),[60])),1) for P in ["WORK","EDUCATION","SHOPPING","RECREATION","ACCOMPANY","OTHER"]},
 "stops_per_tour_by_purpose":{P:round(stops.get(P,0.3),3) for P in tour_by},
}
# fill recreation/accompany mode share from OTHER/SHOPPING
params["mode_share_by_purpose"]["RECREATION"]=share("OTHER")
params["mode_share_by_purpose"]["ACCOMPANY"]=share("OTHER")
json.dump(params,open(os.path.join(OUT,"rts_params.json"),"w"),indent=1)
print("Generated",len([f for f in os.listdir(OUT) if f.endswith('.csv')]),"csv files + rts_params.json")
print("tours/person/day:",params["tours_per_person_per_day"])
print("dist_km:",params["dist_mean_km_by_purpose"])
