# Usage: python3 gap_routes.py <matsim run dir> <out dir>   (results: previews/gap/; 2026-11-04)
"""Road-class mix of the executed car routes (seed 1, selected plans) of six-county residents, by straight-line trip distance,
and for a sample of short trips the shortest-distance path on the same network (what a distance-minimising driver would use)."""
import gzip, re, sys, numpy as np, pandas as pd, pickle, os
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
RUN=sys.argv[1]; OUT=sys.argv[2]
CO={"24003","24005","24013","24025","24027","24510"}
L=pd.read_csv(f"{RUN}/output_links.csv.gz",sep=";",usecols=["link","from_node","to_node","length","freespeed","modes","osm:way:highway"],dtype={"link":str,"from_node":str,"to_node":str})
L=L[L.modes.str.contains("car",na=False)].copy(); h=L["osm:way:highway"].fillna("other")
CLS={"motorway":"Freeway","trunk":"Freeway","motorway_link":"Ramp","trunk_link":"Ramp","primary":"Primary","primary_link":"Primary","secondary":"Secondary","secondary_link":"Secondary",
     "tertiary":"Tertiary","tertiary_link":"Tertiary"}
L["cls"]=h.map(CLS).fillna("Local/residential"); L=L.set_index("link")
ORDER=["Freeway","Ramp","Primary","Secondary","Tertiary","Local/residential"]
ln=L.length.to_dict(); cl=L.cls.to_dict()
rows=[]; county=None; inplan=False; acts=[]; routes=[]; sel=False
pat_act=re.compile(r'<activity type="(\w+)"[^>]*?x="([-\d.]+)" y="([-\d.]+)"')
for line in gzip.open(f"{RUN}/output_plans.xml.gz","rt"):
    if "<person " in line: county=None
    elif 'name="homeCounty"' in line: m=re.search(r'>(\d+)<',line); county=m.group(1) if m else None
    elif "<plan " in line: sel='selected="yes"' in line; acts=[]; legs=[]; mode=None
    elif sel and "<activity " in line:
        m=pat_act.search(line)
        if m: acts.append((float(m.group(2)),float(m.group(3)),m.group(1)))
    elif sel and "<leg " in line: mode=re.search(r'mode="(\w+)"',line).group(1); legs.append([mode,None,len(acts)])
    elif sel and '<route type="links"' in line and legs and legs[-1][0]=="car":
        legs[-1][1]=line.split(">",1)[1].split("<",1)[0].split()
    elif "</plan>" in line and sel and county in CO:
        for mode,r,i in legs:
            if mode!="car" or not r or i<1 or i>=len(acts): continue
            o=acts[i-1]; d=acts[i]; eu=np.hypot(d[0]-o[0],d[1]-o[1])
            km={c:0.0 for c in ORDER}
            for l in r[1:]:      # MATSim: start link not traversed
                km[cl.get(l,"Local/residential")]+=ln.get(l,0)
            rows.append(dict(eu=eu,o=r[0],d=r[-1],**km))
        sel=False
R=pd.DataFrame(rows); R["routed"]=R[ORDER].sum(1)
B=[0,1,2,5,10,20,1e9]; LAB=["0-1","1-2","2-5","5-10","10-20","20+"]
R["band"]=pd.cut(R.eu/1e3,B,labels=LAB,right=False)
G=R.groupby("band",observed=False)
T=pd.DataFrame({"car trips (10%)":G.size(),"mean straight km":G.eu.mean()/1e3,"mean route km":G.routed.mean()/1e3,"routed/straight":G.routed.sum()/G.eu.sum()})
for c in ORDER: T[c+" %"]=100*G[c].sum()/G.routed.sum()
tot=R[ORDER].sum(); T.loc["all"]=[len(R),R.eu.mean()/1e3,R.routed.mean()/1e3,R.routed.sum()/R.eu.sum()]+[100*tot[c]/tot.sum() for c in ORDER]
pd.set_option("display.width",250); pd.set_option("display.max_columns",20); print(T.round(2)); T.round(3).to_csv(f"{OUT}/route_mix_by_band.csv")
# shortest-distance and free-flow-time paths for a sample of short trips (straight line < 5 km)
nodes=pd.Index(pd.unique(pd.concat([L.from_node,L.to_node]))); fi=nodes.get_indexer(L.from_node); ti=nodes.get_indexer(L.to_node); n=len(nodes)
def graph(w):
    df=pd.DataFrame({"f":fi,"t":ti,"w":w}).groupby(["f","t"]).w.min().reset_index(); return csr_matrix((df.w.values,(df.f.values,df.t.values)),shape=(n,n))
Gd=graph(L.length.values); Gt=graph(L.length.values/L.freespeed.values)
S=R[(R.eu<5000)&(R.eu>200)].sample(1500,random_state=1)
lid=L.index; tonode=dict(zip(lid,ti)); fromnode=dict(zip(lid,fi))
res=[]
src=np.array([tonode[x] for x in S.o]); dst=np.array([fromnode[x] for x in S.d])
for name,Gx in [("shortest distance",Gd),("free-flow fastest",Gt)]:
    us=np.unique(src); dist,pred=dijkstra(Gx,indices=us,return_predecessors=True); row=dict(zip(us,range(len(us))))
    # class mix along the path: reconstruct node path -> links via (f,t) lookup
    ft={}; 
    for l,f,t,lg in zip(lid,fi,ti,L.length.values):
        k=(f,t)
        if k not in ft or lg<ft[k][1]: ft[k]=(l,lg)
    mix={c:0.0 for c in ORDER}; dsum=0; oksum=0; rsum=0
    for s,t,(_,r) in zip(src,dst,S.iterrows()):
        k=row[s]; 
        if not np.isfinite(dist[k,t]): continue
        v=t; path=[]
        while v!=s and v>=0: u=pred[k,v]; path.append(ft[(u,v)][0]); v=u
        for l in path: m=ft.get((fi[lid.get_loc(l)],ti[lid.get_loc(l)]))
        for l in path: mix[cl[l]]+=ln[l]; dsum+=ln[l]
        rsum+=r.routed; oksum+=1
    res.append(dict(path=name,trips=oksum,mean_km=dsum/oksum/1e3,km_ratio_to_executed=dsum/rsum,**{c+" %":100*mix[c]/dsum for c in ORDER}))
ex=S[ORDER].sum(); res.append(dict(path="executed (MATSim)",trips=len(S),mean_km=S.routed.mean()/1e3,km_ratio_to_executed=1.0,**{c+" %":100*ex[c]/ex.sum() for c in ORDER}))
P=pd.DataFrame(res).set_index("path"); P["mean_straight_km"]=S.eu.mean()/1e3; print("\nSample of 1,500 car trips with straight line 0.2-5 km"); print(P.round(2)); P.round(3).to_csv(f"{OUT}/route_mix_short_paths.csv")
