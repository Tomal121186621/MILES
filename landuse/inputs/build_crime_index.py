#!/usr/bin/env python3
"""County crime index for the rebuilt SILO (input/crimeIndex.csv: FIPS, County, State, CrimeIndicator), one row per county
of input/zoneSystem.csv (COUNTYFIPS, 61 counties in MD, DC, DE, PA, VA, WV), from observed 2016 Uniform Crime Reporting data.

How the engine uses it (useCases/maryland): GeoDataReaderMstm.readCrimeData stores CrimeIndicator as the county crime rate and
derives an area-weighted region rate; HousingStrategyMstm uses crimeUtility = 1 - rate for a dwelling (weight theta 0-0.10 in
DwellingUtilityCalcMstm) and 1 - regionRate in the region utility (weight gamma 0.05-0.25, RegionUtilityCalcMstm).  The
indicator must therefore lie in [0, 1] with 1 = highest crime.  The original MSTM file (engine test scenario
crimeIndex_orig.csv) ranged 0.03-0.91 with 0.2024 for counties without data; its definition is not documented upstream.

Definition used here: index crime rate = (violent + property Part I offenses, arson excluded) per 100,000 residents in 2016
(denominator: Census PEP vintage-2020 estimate for 2016), divided by the highest county rate in the zone system (Baltimore
City), so CrimeIndicator = rate / max(rate) in [0, 1].

Sources (downloaded 2026-10-21 into WORKSPACE/data/raw/crime/, see data_sources.md and data/raw/manifest.csv):
  MD  Maryland Statistical Analysis Center, "Violent Crime & Property Crime by County: 1975 to Present" (compiled from the
      Maryland State Police / Governor's Office of Crime Prevention Crime in Maryland UCR), all 24 jurisdictions, 2016 rows.
  DC  FBI Crime in the United States 2016, Table 3 (by state), District of Columbia total.
  PA  Pennsylvania State Police UCR, Crime in Pennsylvania Annual Uniform Crime Report 2016, Table 2 (Part I offenses by county).
  VA  FBI CIUS 2016 Table 8 (county sheriffs / county police) + Table 6 (cities and towns), summed per county with the town->county
      assignment TOWN_TO_COUNTY below; Virginia State Police offenses (about 1-3 % of a county's total) are not in these tables.
  WV  FBI CIUS 2016 Tables 8 and 6 as for VA; WV reporting in 2016 is incomplete, so a county whose summed rate is below
      MIN_COVERAGE x the state rate, or that has no sheriff row, takes the state rate (flagged).
  DE  FBI CIUS 2016 Table 3 state rate, apportioned to the three counties by the ratio of the county to the state NIBRS serious
      (violent + serious property) offense rate per 1,000 from Crime in Delaware 2012-2016 (Delaware SAC), tables 1, 4, 7, 10.
  Fallback for any other county: the state rate from FBI CIUS 2016 Table 3 (flagged in data/crime_index_sources.csv).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import re, os, warnings
import pandas as pd, pypdf
warnings.filterwarnings("ignore")
ROOT = f"{WORKSPACE}"
RAW = f"{ROOT}/data/raw/crime"; INP = f"{ROOT}/2_silo/input"; DOWNLOADED = "2026-10-21"
MIN_COVERAGE = 1.0 / 3.0   # observed county rate below this fraction of its state rate = incomplete agency reporting -> state rate
URL = {"md": "https://opendata.maryland.gov/api/views/jwfa-fdxs/rows.csv?accessType=DOWNLOAD",
       "fbi3": "https://ucr.fbi.gov/crime-in-the-u.s/2016/crime-in-the-u.s.-2016/tables/table-3",
       "fbi6": "https://ucr.fbi.gov/crime-in-the-u.s/2016/crime-in-the-u.s.-2016/tables/table-6/table-6-state-cuts/<state>.xls",
       "fbi8": "https://ucr.fbi.gov/crime-in-the-u.s/2016/crime-in-the-u.s.-2016/tables/table-8/table-8-state-cuts/<state>.xls",
       "pa": "https://www.ucr.pa.gov/paucrspublic/Publication/Archived/21.2016AnnualReport.pdf",
       "de": "https://sac.delaware.gov/wp-content/uploads/sites/64/2017/04/Crime-in-Delaware-2012-2016.pdf"}

# ---- zone system counties and 2016 population (PEP vintage 2020) -------------------------------------------------------------
z = pd.read_csv(f"{INP}/zoneSystem.csv")
counties = z.groupby("COUNTYFIPS").agg(name=("JUR_NAME", "first"), state=("STFIPS", "first")).reset_index().rename(columns={"COUNTYFIPS": "FIPS"})
ST = {10: "DE", 11: "DC", 24: "MD", 42: "PA", 51: "VA", 54: "WV"}
counties["State"] = counties.state.map(ST)
counties["County"] = counties.name.str.replace(r", [A-Z]{2}$", "", regex=True)
pep = pd.read_csv(f"{ROOT}/data/raw/pep/co-est2020-alldata.csv", encoding="latin-1", usecols=["SUMLEV", "STATE", "COUNTY", "POPESTIMATE2016"])
pep = pep[pep.SUMLEV == 50]; pep["FIPS"] = pep.STATE * 1000 + pep.COUNTY
pop = pep.set_index("FIPS").POPESTIMATE2016.to_dict()
# MSTM combined Virginia jurisdictions (zone system FIPS -> component county/city FIPS)
COMBINED = {51919: [51059, 51600, 51610], 51942: [51153, 51683, 51685], 51951: [51069, 51840]}
for k, parts in COMBINED.items(): pop[k] = sum(pop[p] for p in parts)
counties["pop2016"] = counties.FIPS.map(pop)
assert counties.pop2016.notna().all(), counties[counties.pop2016.isna()]

def fbi(f):
    t = pd.read_html(f)[0]; t.columns = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in t.columns]
    return t
def num(s): return float(str(s).replace(",", ""))

# ---- state rates, FBI CIUS 2016 Table 3 (fallback and DE base) ------------------------------------------------------------------
t3 = fbi(f"{RAW}/fbi_cius2016_table-3.html")
t3["st"] = t3.State.str.replace(r"\d+$", "", regex=True).str.strip()
tot = t3[t3.Area.isin(["State Total", "Total"]) & t3["Unnamed: 2"].isna()].set_index("st")
state_rate = {}   # offenses per 100,000 (violent + property, FBI population)
for st, nm in {"DE": "DELAWARE", "DC": "DISTRICT OF COLUMBIA", "MD": "MARYLAND", "PA": "PENNSYLVANIA", "VA": "VIRGINIA", "WV": "WEST VIRGINIA"}.items():
    r = tot.loc[nm]; state_rate[st] = 1e5 * (num(r["Violent crime1"]) + num(r["Property crime"])) / num(r.Population)

rows = []   # FIPS, violent, property, source, method, note
def add(fips, viol, prop, source, method, note=""): rows.append(dict(FIPS=fips, violent=viol, property=prop, source=source, method=method, note=note))

# ---- Maryland: MSAC county table (GRAND TOTAL = 7 index offenses, arson not included) --------------------------------------------
md = pd.read_csv(f"{RAW}/md_violent_property_crime_by_county_1975_present.csv"); md = md[md.YEAR == 2016]
md_fips = {r.County: r.FIPS for r in counties[counties.State == "MD"].itertuples()}
for _, r in md.iterrows():
    add(md_fips[r["JURISDICTION"]], r["VIOLENT CRIME TOTAL"], r["PROPERTY CRIME TOTALS"], "MD MSAC/MSP UCR county table 2016 (opendata.maryland.gov jwfa-fdxs)",
        "observed", f"published rate {r['OVERALL CRIME RATE PER 100,000 PEOPLE']:.1f} per 100,000 on UCR population {r['POPULATION']}")
# ---- District of Columbia: FBI Table 3 total -------------------------------------------------------------------------------------
r = tot.loc["DISTRICT OF COLUMBIA"]; add(11001, num(r["Violent crime1"]), num(r["Property crime"]), "FBI CIUS 2016 Table 3, District of Columbia total", "observed")

# ---- Pennsylvania: PSP UCR annual report 2016, Table 2 (Part I offenses by county; property column includes arson) --------------
pa_txt = ""
for p in pypdf.PdfReader(f"{RAW}/pa_ucr_2016_annual_report.pdf").pages[290:300]:
    t = p.extract_text() or ""
    if "Part I Offenses Reported by County" in t: pa_txt += t + "\n"
pa_fips = {r.County.replace(" County", "").upper(): r.FIPS for r in counties[counties.State == "PA"].itertuples()}
pat = re.compile(r"^([A-Z]+) ([\d,]+) ([\d,.]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)\s*$", re.M)
for m in pat.finditer(pa_txt):
    if m.group(1) in pa_fips:
        viol, prop, arson = num(m.group(4)), num(m.group(5)), num(m.group(14))
        add(pa_fips[m.group(1)], viol, prop - arson, "PSP Crime in Pennsylvania 2016, Table 2 Part I offenses by county", "observed",
            f"published crime index {m.group(2)} incl. {int(arson)} arson, rate {m.group(3)} per 100,000")
assert len([r for r in rows if r["FIPS"] // 1000 == 42]) == 9

# ---- Virginia and West Virginia: FBI Table 8 (county agencies) + Table 6 (towns/cities inside the county) ------------------------
TOWN_TO_COUNTY = {  # FBI Table 6 city name -> zone-system county FIPS (VA independent cities map to their own or combined FIPS)
    51001: ["Chincoteague", "Onancock", "Onley", "Parksley"], 51043: ["Berryville"], 51061: ["Warrenton", "Remington"],
    51107: ["Leesburg", "Purcellville", "Middleburg"], 51131: ["Cape Charles", "Exmore"], 51193: ["Colonial Beach"],
    51510: ["Alexandria"], 51630: ["Fredericksburg"], 51919: ["Fairfax City", "Falls Church", "Herndon", "Vienna"],
    51942: ["Manassas", "Manassas Park", "Dumfries", "Haymarket", "Occoquan", "Quantico"], 51951: ["Winchester", "Middletown", "Stephens City"],
    54003: ["Martinsburg"], 54037: ["Charles Town", "Ranson", "Shepherdstown", "Harpers Ferry", "Bolivar"], 54057: ["Keyser", "Piedmont"],
    54065: ["Bath"], 54077: ["Kingwood", "Terra Alta"], 54023: ["Petersburg"], 54027: ["Romney"], 54093: ["Parsons", "Davis", "Thomas"]}
COUNTY_ROW = {51001: "Accomack", 51013: "Arlington County Police Department", 51043: "Clarke", 51061: "Fauquier", 51099: "King George",
              51107: "Loudoun", 51131: "Northampton", 51133: "Northumberland", 51177: "Spotsylvania", 51179: "Stafford", 51193: "Westmoreland",
              51919: "Fairfax County Police Department", 51942: "Prince William County Police Department", 51951: "Frederick",
              54003: "Berkeley", 54023: "Grant", 54027: "Hampshire", 54037: "Jefferson", 54057: "Mineral", 54065: "Morgan", 54077: "Preston", 54093: "Tucker"}
for st, f in (("VA", "virginia"), ("WV", "west-virginia")):
    t8 = fbi(f"{RAW}/fbi_cius2016_table-8_{f}.html").set_index("County"); t6 = fbi(f"{RAW}/fbi_cius2016_table-6_{f}.html")
    t6["City"] = t6.City.str.replace(r"\d+$", "", regex=True); t6 = t6.set_index("City")
    for c in counties[counties.State == st].itertuples():
        agencies, viol, prop = [], 0.0, 0.0
        main = COUNTY_ROW.get(c.FIPS)                       # independent cities (Alexandria, Fredericksburg) have no county row
        if main in t8.index:
            r = t8.loc[main]; viol += num(r["Violent crime"]); prop += num(r["Property crime"]); agencies.append(main)
        for town in TOWN_TO_COUNTY.get(c.FIPS, []):
            if town in t6.index:
                r = t6.loc[town]; viol += num(r["Violent crime"]); prop += 0 if pd.isna(r["Property crime"]) else num(r["Property crime"]); agencies.append(town)
        rate = 1e5 * (viol + prop) / c.pop2016
        if (main is not None and main not in t8.index) or not agencies or rate < MIN_COVERAGE * state_rate[st]:
            add(c.FIPS, None, None, f"FBI CIUS 2016 Table 3, {st} state rate", "state fallback",
                f"agency reporting incomplete: reporting agencies {agencies or 'none'} give {rate:.0f} per 100,000 vs state {state_rate[st]:.0f}")
        else:
            add(c.FIPS, viol, prop, f"FBI CIUS 2016 Tables 8+6, agencies: {'; '.join(agencies)}", "observed",
                "state police offenses not included" if st == "VA" else "")

# ---- Delaware: state rate (Table 3) apportioned by county NIBRS serious-offense rate (Crime in Delaware 2012-2016) ---------------
de_rate = {}
for p in pypdf.PdfReader(f"{RAW}/de_crime_in_delaware_2012_2016.pdf").pages[15:45]:
    t = p.extract_text() or ""
    m = re.search(r"Table (1|4|7|10): (Delaware Statewide|New Castle County|Kent County|Sussex County) Serious Crime Summary", t)
    if not m: continue
    part = t.split("per 1,000 People")[1]
    v = re.search(r"Violent Offenses\s+([\d. ]+)", part).group(1).split()[-1]
    s = re.search(r"Serious Property Offenses\s+([\d. ]+)", part).group(1).split()[-1]
    de_rate[m.group(2)] = float(v) + float(s)
assert len(de_rate) == 4, de_rate
for fips, nm in {10001: "Kent County", 10003: "New Castle County", 10005: "Sussex County"}.items():
    share = de_rate[nm] / de_rate["Delaware Statewide"]
    rows.append(dict(FIPS=fips, violent=None, property=None, rate=state_rate["DE"] * share, method="state rate apportioned",
                     source="FBI CIUS 2016 Table 3 DE state rate x county/state NIBRS serious-offense rate (Crime in Delaware 2012-2016, tables 1/4/7/10)",
                     note=f"NIBRS violent+serious property per 1,000 in 2016: county {de_rate[nm]:.2f}, state {de_rate['Delaware Statewide']:.2f}"))

# ---- assemble, fallback for anything left, scale ---------------------------------------------------------------------------------
d = counties.merge(pd.DataFrame(rows), on="FIPS", how="left")
missing = d.method.isna()
d.loc[missing, "method"] = "state fallback"; d.loc[missing, "source"] = "FBI CIUS 2016 Table 3 state rate"; d.loc[missing, "note"] = "no county data located"
obs = d.method == "observed"
d.loc[obs, "rate"] = 1e5 * (d.violent + d.property) / d.pop2016
fb = d.method == "state fallback"
d.loc[fb, "rate"] = d.loc[fb, "State"].map(state_rate)
d["index_offenses"] = (d.violent + d.property).round().astype("Int64")
RATE_MAX = d.rate.max(); d["CrimeIndicator"] = (d.rate / RATE_MAX).round(6)
assert d.CrimeIndicator.between(0, 1).all() and len(d) == 61 and d.CrimeIndicator.notna().all()
d["rate_per_100k"] = d.rate.round(1)

out = d[["FIPS", "County", "State", "CrimeIndicator"]].sort_values("FIPS")
p = f"{INP}/crimeIndex.csv"
if os.path.islink(p): os.remove(p)
out.to_csv(p, index=False, lineterminator="\n")
src = d[["FIPS", "County", "State", "pop2016", "index_offenses", "rate_per_100k", "CrimeIndicator", "method", "source", "note"]].sort_values("FIPS").copy()
src["year"] = 2016; src["downloaded"] = DOWNLOADED; src["scale"] = f"rate / {RATE_MAX:.1f} (Baltimore City)"
src.to_csv(f"{ROOT}/data/crime_index_sources.csv", index=False, lineterminator="\n")

print(f"crimeIndex.csv: {len(out)} counties; scale max rate {RATE_MAX:.1f} per 100,000 ({d.loc[d.rate.idxmax(), 'County']})")
print("state rates per 100,000 (FBI Table 3):", {k: round(v) for k, v in state_rate.items()})
print(d.groupby(["State", "method"]).size().to_string())
print(d[d.State == "MD"].sort_values("rate")[["County", "pop2016", "index_offenses", "rate_per_100k", "CrimeIndicator"]].to_string(index=False))
print(d[d.State != "MD"].sort_values(["State", "FIPS"])[["FIPS", "County", "State", "rate_per_100k", "CrimeIndicator", "method"]].to_string(index=False))
