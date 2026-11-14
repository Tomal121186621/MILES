import csv,statistics,collections
OUT="input/maryland/output"; RTS="input/rts"
P6=["WORK","EDUCATION","SHOPPING","RECREATION","ACCOMPANY","OTHER"]
acts=list(csv.DictReader(open(f"{OUT}/activities.csv")))
persons=set(a['person_id'] for a in acts); NP_all=len(persons)
# travelers = persons with >=1 main-tour (matches RTS tour-file denominator)
travelers=set(a['person_id'] for a in acts if a['activity_type'] in ('MANDATORY','PRIMARY') and a['purpose'] not in ('HOME','SUBTOUR'))
NP=len(travelers)
main={'MANDATORY','PRIMARY'}; stopt={'ON_MANDATORY_TOUR','ON_DISCRETIONARY_TOUR'}
tours=collections.Counter();stops=collections.Counter();todh=collections.Counter()
for a in acts:
    p=a['purpose']
    if p in ('HOME','SUBTOUR'):continue
    if a['activity_type'] in main and p in P6:
        tours[p]+=1
        try:
            st=int(a['start_time_min'])
            if st>=0: todh[(st%1440)//60]+=1
        except:pass
    elif a['activity_type'] in stopt: stops[p]+=1
tot_tours=sum(tours.values());tot_stops=sum(stops.values())
legs=list(csv.DictReader(open(f"{OUT}/legs.csv")))
mbp=collections.defaultdict(collections.Counter);dbp=collections.defaultdict(list);alld=[]
for l in legs:
    try:d=float(l['distance_m'])/1609.34
    except:continue
    alld.append(d);np_=l['next_purpose']
    if l['previous_purpose']=='HOME' and np_ in P6:
        mbp[np_][l['mode']]+=1;dbp[np_].append(d)
rt=list(csv.DictReader(open(f"{RTS}/rts_tours.csv")))
pm={'HBW':'WORK','HBE':'EDUCATION','HBS':'SHOPPING','HBO':'OTHER','WBO':'OTHER'}
mn={'autoDriver':'CAR_DRIVER','autoPassenger':'CAR_PASSENGER','sr':'CAR_PASSENGER','bus':'BUS','train':'TRAIN','walk':'WALK','bike':'BIKE','other':'OTHER'}
RNP=len(set(t['person_id'] for t in rt))
rt_tours=collections.Counter(pm.get(t['purpose'],'OTHER') for t in rt)
rt_mode=collections.defaultdict(collections.Counter);rt_dist=collections.defaultdict(list);rt_all=[];rt_stops=[];rt_tod=collections.Counter()
for t in rt:
    P=pm.get(t['purpose'],'OTHER');rt_mode[P][mn.get(t['tour_mode'],'OTHER')]+=1
    try:
        d=float(t['dist_primary'])
        if d>0:rt_dist[P].append(d);rt_all.append(d)
    except:pass
    try:rt_stops.append(int(t['n_stops']))
    except:pass
    try:rt_tod[int(float(t['start_min'])//60)]+=1
    except:pass
rows=[]
def add(m,c,a,r):rows.append([m,c,round(a,4),round(r,4),round(a-r,4)])
add("tours_per_person","WORK",tours['WORK']/NP,rt_tours['WORK']/RNP)
add("tours_per_person","EDUCATION",tours['EDUCATION']/NP,rt_tours['EDUCATION']/RNP)
add("tours_per_person","SHOPPING",tours['SHOPPING']/NP,rt_tours['SHOPPING']/RNP)
add("tours_per_person","OTHER+REC+ACC",(tours['OTHER']+tours['RECREATION']+tours['ACCOMPANY'])/NP,rt_tours['OTHER']/RNP)
add("tours_per_person","TOTAL",tot_tours/NP,len(rt)/RNP)
am=collections.Counter()
for P in mbp:
    for m,c in mbp[P].items():am[m]+=c
tam=sum(am.values()) or 1
rm=collections.Counter()
for t in rt:rm[mn.get(t['tour_mode'],'OTHER')]+=1
trm=sum(rm.values()) or 1
for m in ['CAR_DRIVER','CAR_PASSENGER','TRAIN','BUS','WALK','BIKE']:
    add("modeshare_all",m,am[m]/tam,rm[m]/trm)
for P in ["WORK","EDUCATION","SHOPPING"]:
    ta=sum(mbp[P].values()) or 1;tr=sum(rt_mode[P].values()) or 1
    add("modeshare_CARdriver",P,mbp[P]['CAR_DRIVER']/ta,rt_mode[P]['CAR_DRIVER']/tr)
    add("modeshare_transit",P,(mbp[P]['BUS']+mbp[P]['TRAIN'])/ta,(rt_mode[P]['BUS']+rt_mode[P]['TRAIN'])/tr)
prim=[d for P in dbp for d in dbp[P]]
add("triplen_mi_median","ALL",statistics.median(prim),statistics.median(rt_all))
for P in ["WORK","EDUCATION","SHOPPING"]:
    if dbp[P] and rt_dist[P]:add("triplen_mi_median",P,statistics.median(dbp[P]),statistics.median(rt_dist[P]))
add("stops_per_tour","ALL",tot_stops/max(1,tot_tours),statistics.mean(rt_stops))
ttd=sum(todh.values()) or 1;trtd=sum(rt_tod.values()) or 1
add("tod_ampeak_7_9","share",(todh[7]+todh[8])/ttd,(rt_tod[7]+rt_tod[8])/trtd)
add("tod_pmpeak_16_18","share",(todh[16]+todh[17])/ttd,(rt_tod[16]+rt_tod[17])/trtd)
with open(f"{OUT}/validation_abit_vs_rts.csv","w",newline="") as f:
    w=csv.writer(f);w.writerow(["metric","category","abit","rts","diff"]);w.writerows(rows)
print(f"ABIT persons={NP} tours/person={tot_tours/NP:.3f} | RTS travelers={RNP} tours/person={len(rt)/RNP:.3f}")
print(f"{'metric':20}{'cat':16}{'ABIT':>9}{'RTS':>9}{'diff':>9}")
for r in rows:print(f"{r[0]:20}{r[1]:16}{r[2]:>9}{r[3]:>9}{r[4]:>9}")
