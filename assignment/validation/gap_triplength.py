# Like-for-like car trip length (straight line between tract internal points), model population vs RTS 2017/18 (2026-11-04).
# Usage: python3 assignment/validation/gap_triplength.py <population.xml.gz> <second population.xml.gz> <out.csv>   (results: WORKSPACE/4_matsim/validation/previews/gap/tract_l4l.csv)
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import gzip, re, sys, numpy as np, pandas as pd, geopandas as gpd
sys.path.insert(0, f"{MILES_HOME}/activity/survey")
from survey_population import tract_zone, geoid
V=f"{WORKSPACE}"; ROOT=f"{PROJECT_ROOT}"
CO={"24003","24005","24013","24025","24027","24510"}
B=[0,1,2,5,10,20,1e9]; LAB=["0-1","1-2","2-5","5-10","10-20","20+"]
TZ=tract_zone().set_index("geoid")[["x","y"]]       # tract internal point, EPSG:26918
TR=pd.concat([gpd.read_file(f"{V}/data/raw/tiger_tracts_2010/tl_2010_{s}_tract10/tl_2010_{s}_tract10.shp")[["GEOID10","geometry"]] for s in ["24","11","42","10","51","54"]]).to_crs(26918)
def grp(a,b):
    s={a,b}; return "work" if "work" in s else "school" if "education" in s else "shopping" if "shopping" in s else "other"
def model(path):
    o=[]; county=None; acts=[]; modes=[]
    for line in gzip.open(path,"rt"):
        if '<person ' in line: county=None; acts=[]; modes=[]
        elif 'name="homeCounty"' in line: county=re.search(r'>(\d+)<',line).group(1)
        elif '<activity' in line: m=re.search(r'type="(\w+)" x="([-\d.]+)" y="([-\d.]+)"',line); acts.append((m.group(1),float(m.group(2)),float(m.group(3))))
        elif '<leg ' in line: modes.append(re.search(r'mode="(\w+)"',line).group(1))
        elif '</person>' in line and county in CO:
            for i,m in enumerate(modes):
                if m=="car": o.append((grp(acts[i][0],acts[i+1][0]),acts[i][1],acts[i][2],acts[i+1][1],acts[i+1][2]))
    D=pd.DataFrame(o,columns=["g","ox","oy","dx","dy"])
    for e in "od":
        p=gpd.GeoDataFrame(geometry=gpd.points_from_xy(D[e+"x"],D[e+"y"]),crs=26985).to_crs(26918)
        j=gpd.sjoin(p,TR,how="left",predicate="within"); j=j[~j.index.duplicated()]
        D[e+"t"]=j.GEOID10.values
    D=D.dropna(subset=["ot","dt"])
    a=TZ.reindex(D.ot).values; b=TZ.reindex(D.dt).values
    D["km"]=np.hypot(a[:,0]-b[:,0],a[:,1]-b[:,1])/1e3; D["w"]=1.0; D["same"]=D.ot==D.dt
    return D.dropna(subset=["km"])
def survey():
    H=pd.read_csv(f"{ABIT_HOME}/input/rts/RTS_raw_flat_data.csv",low_memory=False,usecols=["tripid","household_id","home_state_county_fips","o_state_county_fips","d_state_county_fips"])
    S=pd.read_csv(f"{ABIT_HOME}/input/rts/rts_trips_clean.csv",low_memory=False,usecols=["tripid","travel_mode","distance","wttrdfin","o_activity","d_activity","o_tract_fips","d_tract_fips"]).merge(H,on="tripid")
    S=S[S.home_state_county_fips.astype(str).isin(CO)&S.travel_mode.isin([3,4])]
    ot=geoid(S.o_state_county_fips,S.o_tract_fips); dt=geoid(S.d_state_county_fips,S.d_tract_fips)
    a=TZ.reindex(ot).values; b=TZ.reindex(dt).values
    act=lambda c: c.map({2:"work",4:"education",5:"shopping"}).fillna("x")
    D=pd.DataFrame({"g":[grp(x,y) for x,y in zip(act(S.o_activity),act(S.d_activity))],"km":np.hypot(a[:,0]-b[:,0],a[:,1]-b[:,1])/1e3,"w":S.wttrdfin.values,"same":(ot==dt).values,"rep":S.distance.values*1.609})
    return D.dropna(subset=["km"])
def dist(D):
    s=D.w.groupby(pd.cut(D.km,B,labels=LAB,right=False),observed=False).sum(); return (100*s/s.sum()).round(1).tolist()+[round(np.average(D.km,weights=D.w),2),round(100*D.w[D.same].sum()/D.w.sum(),1)]
S=survey(); rows={("all","survey"):dist(S)}
Ms={tag:model(p) for tag,p in [("current",sys.argv[1]),("decay",sys.argv[2])]}
for tag,M in Ms.items(): rows[("all",tag)]=dist(M)
for g in ["work","school","shopping","other"]:
    rows[(g,"survey")]=dist(S[S.g==g])
    for tag,M in Ms.items(): rows[(g,tag)]=dist(M[M.g==g])
R=pd.DataFrame(rows,index=LAB+["mean km","same tract %"]).T
R["TVD"]=[round(0.5*sum(abs(R.loc[i,c]-R.loc[(i[0],"survey"),c]) for c in LAB),1) for i in R.index]
pd.set_option("display.width",250); pd.set_option("display.max_columns",20); print("Straight line between tract internal points, car-driver trips of six-county residents"); print(R)
R.to_csv(sys.argv[3])
