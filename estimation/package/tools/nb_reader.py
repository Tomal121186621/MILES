"""Reader's layer of the SILO notebooks and INSTRUCTIONS.pdf: plain-language summary ("Model at a glance"), term labels and
readings of the coefficients, glossary, section notes and hold-out text.  Numbers are read from the folder's files
(model/reference_estimates.csv, RUN.json, output/holdout_*.csv), never typed here.

Used at build time by build_notebooks.py / build_instructions.py and at run time by the notebooks (readings of your estimates)."""
import json, os
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LN2 = np.log(2.0)

# kind: plain | lninc (shift per unit ln income of `base`) | x (interaction: effect of `base` for a group) | size | g (size weight)
#       | asc (constant of an alternative against the reference) | alt (car ownership: one coefficient per number of cars)
T = lambda group, label, measures, kind="plain", base=None, who=None: dict(group=group, label=label, measures=measures, kind=kind, base=base, who=who)

SPEC = {
    "01_residential_puma": dict(
        title="Residential location: which PUMA a moving household chooses",
        answers="When a household moves, which area (PUMA) does it move to? The model compares all 97 PUMAs of the model area by "
                "market size, distance from the previous home, commute, crime, density and the population mix. It is the upper level "
                "of the two-level residential model; the dwelling level enters through its inclusive value.",
        deciders="Households that moved into their dwelling in the last 12 months, householder from another U.S. house",
        data="ACS PUMS 2014-2018 (5-year), DC, DE, MD, PA, VA, WV", unit="movers",
        choice="The PUMA of the new home", alts="The 97 PUMAs of the model area, all available (no sampling)",
        subject="the PUMA", traits="location", two_level="upper", example=("B_ln_dwelling_density", "B_ln_density_x_ln_income"),
        terms={
            "B_ln_market_size": T("Size", "ln market size", "ln(dwelling stock x fixed turnover rate of the PUMA)"),
            "B_cartime_20_60": T("Distance from the previous home", "Car time 20-60 min", "car minutes from the previous home between 20 and 60"),
            "B_cartime_over60": T("Distance from the previous home", "Car time over 60 min", "car minutes beyond 60"),
            "B_previous_migration_area": T("Staying near the origin", "Inside the previous migration area", "share of the origin area's dwellings in the PUMA"),
            "B_bordering_previous_area": T("Staying near the origin", "Bordering the previous migration area", "PUMA borders the origin area"),
            "B_same_state": T("Staying near the origin", "Same state", "PUMA in the state lived in a year ago"),
            "B_commute_sum_ln1p_time": T("Commute", "Commute", "sum over workers of ln(1 + minutes to the workplace area)"),
            "B_crime_x_children": T("PUMA attributes", "Crime index x children", "county crime index, households with children"),
            "B_ln_dwelling_density": T("PUMA attributes", "ln dwelling density", "ln dwellings per acre ($50k household, 2+ persons, oldest 35+)"),
            "B_own_race_share": T("PUMA attributes", "Own-race share", "share of the PUMA's households with the householder race category of the mover"),
            "B_ln_density_x_single": T("PUMA attributes", "ln density x single-person household", "density effect for one-person households", "x", "B_ln_dwelling_density", "one-person households"),
            "B_ln_density_x_oldest_under35": T("PUMA attributes", "ln density x oldest member under 35", "density effect for young households", "x", "B_ln_dwelling_density", "households whose oldest member is under 35"),
            "B_ln_density_x_ln_income": T("PUMA attributes", "ln density x ln income", "density effect per unit ln(income / $50k)", "lninc", "B_ln_dwelling_density"),
            "B_core_city_share": T("PUMA attributes", "Core-city share", "share of the PUMA's dwellings in DC or Baltimore City"),
        },
        glossary=["PUMA", "migration area", "inclusive value", "market size", "log-likelihood", "BIC", "hold-out", "robust s.e.", "VIF", "weight"]),
    "02_residential_dwelling": dict(
        title="Residential location: which dwelling a moving household chooses within the PUMA",
        answers="Within the chosen PUMA, which dwelling does a moving household take? The model compares the chosen dwelling with 29 "
                "other dwellings of the same PUMA by cost, size, age and structure type, with effects that change with income. It is "
                "the lower level of the two-level residential model.",
        deciders="Households that moved into their dwelling in the last 12 months", data="ACS PUMS 2014-2018 (5-year), DC, DE, MD, PA, VA, WV",
        unit="movers", choice="The dwelling moved into",
        alts="The chosen dwelling and 29 dwellings drawn at random from the same PUMA's dwellings of recent movers",
        subject="the dwelling", traits="location", two_level="lower", example=("ASC_MF2_4", "B_MF2_4_x_lninc"),
        terms={
            "B_cost_share_above30": T("Affordability", "Cost above 30 % of income", "max(0, 12 x monthly cost / income - 0.30)"),
            "B_cost_share_above30_x_lninc": T("Affordability", "Cost above 30 % x ln income", "shift per unit ln(income / $50k)", "lninc", "B_cost_share_above30"),
            "B_ln_cost": T("Quality", "ln monthly housing cost", "price signal of dwelling quality"),
            "B_ln_cost_x_lninc": T("Quality", "ln cost x ln income", "shift per unit ln(income / $50k)", "lninc", "B_ln_cost"),
            "B_bedroom_shortfall": T("Size and age", "Bedroom shortfall", "bedrooms below household size (at most 5)"),
            "B_bedroom_shortfall_x_lninc": T("Size and age", "Bedroom shortfall x ln income", "shift per unit ln(income / $50k)", "lninc", "B_bedroom_shortfall"),
            "B_bedroom_excess": T("Size and age", "Bedroom excess", "bedrooms above household size"),
            "B_bedroom_excess_x_lninc": T("Size and age", "Bedroom excess x ln income", "shift per unit ln(income / $50k)", "lninc", "B_bedroom_excess"),
            "B_built_last5yrs": T("Size and age", "Built in the last five years", "new dwelling"),
            "B_built_last5yrs_x_lninc": T("Size and age", "New dwelling x ln income", "shift per unit ln(income / $50k)", "lninc", "B_built_last5yrs"),
            "ASC_SFA": T("Structure type (vs single-family detached)", "Single-family attached", "constant", "asc"),
            "B_SFA_x_lninc": T("Structure type (vs single-family detached)", "Single-family attached x ln income", "shift per unit ln(income / $50k)", "lninc", "ASC_SFA"),
            "ASC_MF2_4": T("Structure type (vs single-family detached)", "Multifamily 2-4 units", "constant", "asc"),
            "B_MF2_4_x_lninc": T("Structure type (vs single-family detached)", "Multifamily 2-4 x ln income", "shift per unit ln(income / $50k)", "lninc", "ASC_MF2_4"),
            "ASC_MF5plus": T("Structure type (vs single-family detached)", "Multifamily 5+ units", "constant", "asc"),
            "B_MF5plus_x_lninc": T("Structure type (vs single-family detached)", "Multifamily 5+ x ln income", "shift per unit ln(income / $50k)", "lninc", "ASC_MF5plus"),
            "ASC_mobile_home": T("Structure type (vs single-family detached)", "Mobile home or other", "constant", "asc"),
            "B_mobile_home_x_lninc": T("Structure type (vs single-family detached)", "Mobile home x ln income", "shift per unit ln(income / $50k)", "lninc", "ASC_mobile_home"),
        },
        glossary=["PUMA", "sampled alternatives", "inclusive value", "log-likelihood", "BIC", "hold-out", "robust s.e.", "VIF"]),
    "04_car_ownership": dict(
        title="Car ownership: how many cars a household owns",
        answers="How many cars does a household own: none, one, two, or three or more? The model uses household size, workers, "
                "income, age, dwelling, density and the accessibility a car adds. Each number of cars has its own coefficients against "
                "owning no car.",
        deciders="Maryland households (not group quarters)", data="ACS PUMS 2014-2018 (5-year), Maryland", unit="households",
        choice="Number of cars", alts="0, 1, 2, 3 or more cars (all available; no car is the reference with utility 0)",
        subject="owning that number of cars", traits="direct", two_level=None, example=("B_workers_2cars", None),
        stems={
            "ASC": T("Constant", "Constant", "baseline preference against no car", "asc"),
            "B_workers": T("Household", "Workers", "number of workers", "alt"),
            "B_persons16_2": T("Household", "Persons aged 16+: 2", "against one person aged 16+", "alt"),
            "B_persons16_3": T("Household", "Persons aged 16+: 3", "against one", "alt"),
            "B_persons16_4plus": T("Household", "Persons aged 16+: 4 or more", "against one", "alt"),
            "B_children_under16": T("Household", "Children under 16", "number of children", "alt"),
            "B_single_person": T("Household", "Single-person household", "one person", "alt"),
            "B_age_oldest": T("Household", "Age of the oldest member", "(age - 45) / 10", "alt"),
            "B_age_oldest_sq": T("Household", "Age of the oldest member, squared", "((age - 45) / 10)^2", "alt"),
            "B_lninc_under25k": T("Income", "ln income, under $25k", "piece of ln income", "alt"),
            "B_lninc_25_50k": T("Income", "ln income, $25-50k", "piece of ln income", "alt"),
            "B_lninc_50_100k": T("Income", "ln income, $50-100k", "piece of ln income", "alt"),
            "B_lninc_above100k": T("Income", "ln income, above $100k", "piece of ln income", "alt"),
            "B_single_family_detached": T("Dwelling", "Single-family detached", "against attached and other", "alt"),
            "B_multifamily": T("Dwelling", "Multifamily", "against attached and other", "alt"),
            "B_bedrooms": T("Dwelling", "Bedrooms", "number of bedrooms", "alt"),
            "B_ln_density_puma": T("Location", "ln dwelling density of the PUMA", "per km2", "alt"),
            "B_acc_gain_car": T("Location", "Accessibility gain from a car", "non-work logsum with minus without a car", "alt"),
            "B_lninc_x_ln_density": T("Location", "ln income x ln density", "centred interaction", "alt"),
            "B_baltimore_city": T("Location", "Baltimore City", "home in Baltimore City", "alt"),
        },
        alt_suffix={"1car": "1 car", "2cars": "2 cars", "3pluscars": "3+ cars"},
        glossary=["PUMA", "reference alternative", "log-likelihood", "BIC", "hold-out", "robust s.e.", "VIF"]),
    "05_workplace_choice": dict(
        title="Workplace choice: where a worker works",
        answers="Which zone does a worker work in? The model compares the chosen workplace zone with 99 zones drawn at random by the "
                "number of jobs, car time from home, boundaries and the job mix, with time effects that differ by person.",
        deciders="Workers with a fixed usual workplace", data="Regional Travel Survey 2017/18 (Baltimore and Washington regions)", unit="workers",
        choice="The workplace zone", alts="The chosen zone and 99 zones drawn at random from the 1,587 zones with jobs (hold-out: all 1,587)",
        subject="the zone as workplace", traits="location", two_level=None, example=("B_time", "B_time_x_income_125kplus"),
        terms={
            "MU_size": T("Size", "Size coefficient mu", "ln of the zone's jobs", "size"),
            "B_time": T("Car time", "Car time (min)", "AM-peak car minutes home to zone"),
            "B_ln1p_time": T("Car time", "ln(1 + car time)", "flattens the time effect"),
            "B_time_x_woman": T("Car time x person", "Time x woman", "", "x", "B_time", "women"),
            "B_time_x_age_under30": T("Car time x person", "Time x age under 30", "", "x", "B_time", "workers under 30"),
            "B_time_x_age_55plus": T("Car time x person", "Time x age 55+", "", "x", "B_time", "workers 55 and older"),
            "B_time_x_income_under40k": T("Car time x person", "Time x income under $40k", "", "x", "B_time", "incomes under $40k"),
            "B_time_x_income_75_125k": T("Car time x person", "Time x income $75-125k", "", "x", "B_time", "incomes of $75-125k"),
            "B_time_x_income_125kplus": T("Car time x person", "Time x income $125k+", "", "x", "B_time", "incomes of $125k or more"),
            "B_time_x_licence": T("Car time x person", "Time x driving licence", "", "x", "B_time", "licence holders"),
            "B_time_x_hhsize": T("Car time x person", "Time x household size", "per person", "x", "B_time", "each extra household member"),
            "B_time_x_rural_home": T("Car time x person", "Time x rural home", "", "x", "B_time", "workers with a rural home zone"),
            "B_time_x_no_car": T("Car time x person", "Time x no car", "", "x", "B_time", "workers in households without a car"),
            "B_same_zone": T("Borders and the District", "Same zone", "workplace in the home zone"),
            "B_other_county": T("Borders and the District", "Other county", "workplace in another county"),
            "B_other_state": T("Borders and the District", "Other state", "workplace in another state"),
            "B_DC_workplace_home_outside_DC": T("Borders and the District", "DC workplace, home outside DC", "District workplace for non-residents"),
            "B_office_share_x_income_under40k": T("Job mix x person", "Office share x income under $40k", "office share of the zone's jobs"),
            "B_office_share_x_income_125kplus": T("Job mix x person", "Office share x income $125k+", "office share of the zone's jobs"),
            "B_retail_share_x_age_under30": T("Job mix x person", "Retail share x age under 30", "retail share of the zone's jobs"),
            "B_industrial_share_x_woman": T("Job mix x person", "Industrial share x woman", "industrial share of the zone's jobs"),
            "B_high_wage_share": T("Wage proxy", "High-wage share", "share of the zone's jobs with high wages"),
            "B_high_wage_share_x_income_under40k": T("Wage proxy", "High-wage share x income under $40k", "", "x", "B_high_wage_share", "incomes under $40k"),
            "B_high_wage_share_x_income_75_125k": T("Wage proxy", "High-wage share x income $75-125k", "", "x", "B_high_wage_share", "incomes of $75-125k"),
            "B_high_wage_share_x_income_125kplus": T("Wage proxy", "High-wage share x income $125k+", "", "x", "B_high_wage_share", "incomes of $125k or more"),
        },
        glossary=["zone", "sampled alternatives", "size term", "log-likelihood", "BIC", "hold-out", "robust s.e.", "VIF"]),
}
_SCHOOL_TERMS = {
    "MU_size": T("Size", "Size coefficient mu", "ln of the zone's weighted enrolment", "size"),
    "G_in_boundary_public": T("Size", "In-boundary public enrolment (log weight)", "against out-of-boundary public", "g"),
    "G_private": T("Size", "Private enrolment (log weight)", "against out-of-boundary public", "g"),
    "G_private_4yr": T("Size", "Private 4-year enrolment (log weight)", "against public 4-year", "g"),
    "G_2yr": T("Size", "2-year enrolment (log weight)", "against public 4-year", "g"),
    "B_time": T("Car time", "Car time (min)", "AM-peak car minutes home to school zone"),
    "B_ln1p_time": T("Car time", "ln(1 + car time)", "flattens the time effect"),
    "B_time_x_no_car": T("Car time", "Time x no car", "", "x", "B_time", "students of households without a car"),
    "B_time_x_income_125kplus": T("Car time", "Time x income $125k+", "", "x", "B_time", "incomes of $125k or more"),
    "B_same_zone": T("Boundaries", "Same zone", "school in the home zone"),
    "B_other_county": T("Boundaries", "Other county", "school in another county"),
    "B_other_state": T("Boundaries", "Other state", "school in another state"),
    "B_other_county_x_public_share": T("Boundaries", "Other county x public share", "public share of the zone's enrolment, other county"),
    "B_charter_or_magnet_share": T("School zone", "Charter-or-magnet share", "share of the zone's enrolment"),
    "B_quality_public": T("School zone", "Quality of the public part", "% proficient / 10, centred, public share"),
    "B_quality_x_income_under40k": T("School zone", "Quality x income under $40k", "", "x", "B_quality_public", "incomes under $40k"),
    "B_no_score_share": T("School zone", "Share of public enrolment without a score", "share"),
    "B_own_race_share": T("School zone", "Own-race share", "share of the zone's enrolment of the student's race category"),
}
for f, band, lab, n in [("06_school_location_K8", "K-8", "kindergarten to grade 8", "elementary and middle"), ("07_school_location_high_school", "high school", "grades 9-12", "high"),
                        ("08_school_location_college", "college", "2-year, 4-year and graduate", "post-secondary")]:
    SPEC[f] = dict(
        title=f"School location: which zone a {band} student attends",
        answers=f"Which zone does a {band} student ({lab}) go to school in? The model compares all zones with {n} enrolment by size, car "
                "time from home, boundaries and school attributes. Home and school are known only as survey zones or tracts, so both are "
                "spread over several model zones.",
        deciders=f"{band.capitalize()} students", data="Regional Travel Survey 2017/18 (Baltimore and Washington regions)", unit="students",
        choice="The school zone", alts=f"All zones with {n} enrolment (full choice set)",
        subject="the school zone", traits="location", two_level=None, example=("B_time", None),
        terms={k: v for k, v in _SCHOOL_TERMS.items()},
        glossary=["zone", "size term", "log-likelihood", "BIC", "hold-out", "robust s.e.", "VIF"])

GLOSSARY = {
    "PUMA": "Public Use Microdata Area: a Census area of about 100,000 people, the smallest area of the ACS microdata.",
    "migration area": "The area a household lived in a year earlier, as the ACS records it: one PUMA or a group of PUMAs.",
    "inclusive value": "The expected value of the best dwelling in a PUMA: ln of the mean of exp(V) over 200 sampled dwellings. Its coefficient is held at 1.",
    "market size": "M = dwelling stock of the PUMA x fixed turnover rate (recent movers' dwellings / dwellings in 2016). It changes only with construction and demolition.",
    "sampled alternatives": "The chosen alternative and others drawn at random with equal probability; this gives the same estimates as the full set, with less precision.",
    "size term": "mu x ln(size of the zone): with mu = 1 the probability is proportional to the zone's jobs or enrolment.",
    "reference alternative": "The alternative whose utility is fixed at 0 (no car); the coefficients of the others are differences against it.",
    "zone": "A traffic analysis zone of the model (1,588 zones).",
    "MAST": "Maryland Activity Scheduling and Travel model: the activity-based model of the MILES platform, built on the ABIT code base (Activity-Based Incremental Transport model).",
    "log-likelihood": "Sum over decision makers of ln(probability of the observed choice). Closer to 0 is better.",
    "BIC": "Bayesian information criterion: -2 log-likelihood + K ln N. Lower is better; it penalises extra parameters.",
    "hold-out": "The 20 % (residential, cars) or half (survey models) of the records not used for estimation. It was also used in the specification search, so its fit is not a fully independent test.",
    "robust s.e.": "Standard error from the sandwich formula, valid when the model is not exactly right.",
    "VIF": "Variance inflation factor: how much the correlation with other variables inflates a coefficient's variance; 10 or more is high.",
    "weight": "Estimation weight of a mover: expected share of origin and destination inside the model area, divided by its mean.",
}

SECTION = {
    1: "Where the records come from. Look for: the files and the record counts.",
    2: "From the raw records to the estimation sample. Look for: the records kept and dropped at each filter. With RUN_DATA_PREP the rebuilt tables must equal the shipped ones.",
    3: "The table the model reads. Look for: the columns used and what they mean (data dictionary).",
    4: "What the sample looks like. Look for: plausible shares and maps, and the chosen alternatives against the available ones.",
    5: "The utility functions, read from the model script; nothing is re-specified here.",
    6: "Correlation of the explanatory variables. Look for: |r| of 0.7 or more and VIF of 10 or more; these make single coefficients less precise.",
    7: "Log-likelihood at the article coefficients, without estimation. Look for: the two numbers should be equal (to rounding).",
    8: "Biogeme estimation, only with RUN_ESTIMATION. Look for: convergence and the run time.",
    9: "The estimates and what they mean. Look for: coefficients equal to the article within rounding, and the readings below.",
    10: "Fit on the hold-out records, which the estimation did not use. Look for: a log-likelihood per record close to that of the estimation sample, and the maps.",
}


# ------------------------------------------------------------------------------------------------ reading the files
def reference(folder):
    r = pd.read_csv(f"{ROOT}/SILO/{folder}/model/reference_estimates.csv")
    est = r[r.note.isna() & r.parameter.notna()][["parameter", "coefficient", "robust_se", "p"]].copy()
    est["p"] = pd.to_numeric(est.p.astype(str).str.replace("<", "", regex=False), errors="coerce") * np.where(est.p.astype(str).str.startswith("<"), 0.5, 1.0)
    stat = r[r.note.fillna("") == "model statistic"].set_index("parameter").coefficient
    return est, stat


def term(folder, p):
    S = SPEC[folder]
    if "stems" in S:
        for suf in S["alt_suffix"]:
            if p.endswith("_" + suf):
                return S["stems"].get(p[: -len(suf) - 1]), suf
        return None, None
    return S["terms"].get(p), None


def sizes(folder):
    R = json.load(open(f"{ROOT}/SILO/{folder}/RUN.json")); est, stat = reference(folder)
    ck = R.get("check") or {}
    n = ck.get("N") or stat.get("N")
    h = stat.get("validation N", stat.get("hold-out N"))
    return n, h, ck


def run_minutes(folder):
    R = json.load(open(f"{ROOT}/SILO/{folder}/RUN.json"))
    m = [s.get("minutes") for s in R.get("steps", []) if "--check" in s.get("command", "") or "evaluate" in s.get("command", "")]
    est = [s.get("minutes") for s in R.get("steps", []) if "estimate_" in s.get("command", "") and "--" not in s.get("command", "").split("estimate_")[1]]
    return m, est


# ------------------------------------------------------------------------------------------------ text (markdown)
def fmt(x, d=3):
    return f"{x:+.{d}f}".replace("-", "−")


def glance_md(folder):
    S = SPEC[folder]; est, stat = reference(folder); n, h, ck = sizes(folder); b = dict(zip(est.parameter, est.coefficient))
    L = ["## Model at a glance", "",
         f"**1. Who decides.** {S['deciders']}. Data: {S['data']}. Estimation sample: {int(n):,} {S['unit']}" + (f"; hold-out: {int(h):,}." if h == h and h is not None else "."), "",
         f"**2. What is chosen (dependent variable).** {S['choice']}. Alternatives: {S['alts']}.", "",
         "**3. Explanatory variables** (signs of the article estimates, `model/reference_estimates.csv`):", ""]
    if "stems" in S:
        suf = list(S["alt_suffix"])
        L += ["| Group | Variable | What it measures | " + " | ".join(S["alt_suffix"].values()) + " |", "|---|---|---|" + "---|" * len(suf)]
        for stem, t in S["stems"].items():
            v = [b.get(f"{stem}_{s}") for s in suf]
            L.append(f"| {t['group']} | {t['label']} | {t['measures']} | " + " | ".join("0 (fixed)" if x is None else ("+" if x > 0 else "−") for x in v) + " |")
    else:
        L += ["| Group | Variable | What it measures | Sign |", "|---|---|---|---|"]
        for p, t in S["terms"].items():
            if p not in b: continue
            sg = "+" if b[p] > 0 else "−"
            if t["kind"] == "lninc": sg += " (shift per unit ln income)"
            if t["kind"] == "x": sg += f" (shift for {t['who']})"
            L.append(f"| {t['group']} | {t['label']} | {t['measures'] or t['label']} | {sg} |")
    L += ["", "**4. How household traits enter.** " + (
        "Household traits (income, size, age, cars, children) are the same for every alternative, so on their own they cannot change "
        "which alternative is chosen. They enter only as interactions with attributes of the alternatives (for example density x "
        "single-person household, car time x income)." if S["traits"] == "location" else
        "Household traits enter directly, with one coefficient per number of cars; no car is the reference with utility 0, so each "
        "coefficient is a difference against owning no car."), ""]
    if S.get("two_level"):
        L += ["**5. How the two levels connect.** The PUMA level contains the inclusive value of the dwelling level (ln of the mean of "
              "exp(V) over 200 sampled dwellings of the PUMA) with coefficient 1, and ln M as a separate term, M = dwelling stock x fixed "
              "turnover rate of the PUMA. With the coefficient at 1 the two levels are one logit over all dwellings of the area.", ""]
    L += ["**%d. How to read a coefficient.** A positive coefficient makes the alternative more likely, a negative one less likely. "
          "exp(coefficient) is the factor by which the odds change for one unit more of the variable." % (6 if S.get("two_level") else 5)]
    m, x = S["example"]
    if x and m in b and x in b:
        t = term(folder, m)[0]
        L.append(f" Income enters as ln(income / $50k), so a main coefficient is that of a $50k household and the x ln income term shifts it: "
                 f"{t['label']} is {fmt(b[m] - LN2 * b[x], 2)} at $25k, {fmt(b[m], 2)} at $50k and {fmt(b[m] + LN2 * b[x], 2)} at $100k.")
    elif m in b:
        t = term(folder, m)[0]
        L.append(f" Example: {t['label'] if t else m} = {fmt(b[m], 3)}, odds factor exp({b[m]:.3f}) = {np.exp(b[m]):.3f} per unit.")
    return "\n".join(L)


def answers_md(folder, R):
    S = SPEC[folder]; n, h, ck = sizes(folder)
    m, est = run_minutes(folder)
    rows = [("Choice", S["choice"]), ("Alternatives", S["alts"]), ("Decision makers", S["deciders"]), ("Data", S["data"]),
            ("Estimation sample", f"{int(n):,} {S['unit']}")]
    if h == h and h is not None: rows.append(("Hold-out sample", f"{int(h):,} {S['unit']}"))
    note = []
    ss = f"{ROOT}/SILO/02_residential_dwelling/output/sample_size_coef.csv"
    if folder in ("01_residential_puma", "02_residential_dwelling") and os.path.exists(ss):
        c = pd.read_csv(ss); mx = c[c.case != "J30"].diff_in_se.abs().max()
        if folder == "02_residential_dwelling":
            note = ["", "**Why 29 other dwellings.** A PUMA has thousands of dwellings, and the ACS sample holds only some of them, so the model compares the "
                    "chosen dwelling with 29 others drawn uniformly at random from the same pool: the PUMA's dwellings of households that moved in within "
                    "12 months, the pool the chosen one comes from. Uniform random draws give unbiased estimates (McFadden 1978); only precision is lost. "
                    f"Re-estimating with a second draw of 30, and with 60 and 100 alternatives, changes no coefficient by more than {mx:.2f} robust "
                    "standard errors, so 30 are enough. In SILO a moving household chooses among 30 vacant dwellings drawn at random in the chosen PUMA (all of them if fewer)."]
        else:
            note = ["", "**The 200 dwellings of the inclusive value.** The value of a PUMA's dwellings to a household is the log of the mean of exp(V) over 200 "
                    "dwellings drawn at random from the PUMA's dwellings of recent movers (a sample of the thousands there). Redrawing them with the "
                    f"sampled-alternatives check moves no coefficient by more than {mx:.2f} robust standard errors. In SILO the 200 are drawn from the PUMA's vacant dwellings."]
    return "\n".join([f"# {S['title']}", "", "## What this model answers", "", S["answers"]] + note + ["",
                      "| | |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows])


def how_to_run_md(folder, cfg):
    m, est = run_minutes(folder)
    chk = next((x for x in m if isinstance(x, (int, float))), None)
    return "\n".join(["## How to run", "",
                      "- Kernel: *Python (biogeme)* (`~/.venvs/biogeme`, Biogeme 3.3); the data rebuild also needs `python3` with geopandas. Then *Run All*.",
                      "- `RUN_DATA_PREP`: rebuild the estimation tables in a scratch folder and compare them with the shipped ones.",
                      "- `RUN_CHECK`: log-likelihood at the article coefficients, no estimation" + (f" (about {chk:g} min)." if chk else "."),
                      "- `RUN_ESTIMATION`: run the Biogeme estimation (off by default; the results in `output/` are read instead)" +
                      (" — several hours for this model." if cfg.get("heavy") else "."),
                      "- `RUN_HOLDOUT`: log-likelihood of the hold-out records.",
                      "- Figures of the hold-out check are read from `output/holdout_*` (copied there by the notebook builder)."])


def glossary_md(folder):
    return "\n".join(["## Glossary", ""] + [f"- **{k}**: {GLOSSARY[k]}" for k in SPEC[folder]["glossary"]])


# ------------------------------------------------------------------------------------------------ run time: readings of the estimates
def readings(folder, est):
    """est: DataFrame parameter, coefficient, p (your estimates or the article's).  Returns a table of plain readings."""
    S = SPEC[folder]; b = dict(zip(est.parameter, est.coefficient)); pv = dict(zip(est.parameter, est.p)); out = []
    ns = lambda p: "" if pd.isna(pv.get(p)) or pv[p] < 0.05 else " Not significant at 5 %."
    if "stems" in S:
        for stem, t in S["stems"].items():
            vals = [(lab, b.get(f"{stem}_{s}")) for s, lab in S["alt_suffix"].items()]
            txt = ", ".join(f"{lab} {fmt(v)}" if v is not None else f"{lab} 0 (fixed)" for lab, v in vals)
            vv = [v for _, v in vals if v is not None]
            if stem == "ASC": r = "baseline utility of each number of cars against none, at zero values of the variables"
            elif all(v > 0 for v in vv): r = "raises the chance of owning cars rather than none" + (", more so for more cars" if vv == sorted(vv) else "")
            elif all(v < 0 for v in vv): r = "lowers the chance of owning cars rather than none" + (", more so for more cars" if vv == sorted(vv, reverse=True) else "")
            else: r = "mixed: compare the numbers of cars"
            out.append(dict(variable=t["label"], coefficients=txt, reading=r + "."))
        return pd.DataFrame(out)
    for p, t in S["terms"].items():
        if p not in b: continue
        c = b[p]
        if t["kind"] == "size":
            r = f"jobs or enrolment of the zone: twice the size makes it {2 ** c:.2f} times as likely" + (" (less than proportional)" if c < 1 else "")
        elif t["kind"] == "g":
            r = f"one student place of this kind counts as {np.exp(c):.2f} places of the reference kind"
        elif t["kind"] == "lninc" and t["base"] in b:
            m = b[t["base"]]; bl = S["terms"][t["base"]]["label"]
            r = f"{bl}: {fmt(m - LN2 * c, 2)} at $25k, {fmt(m, 2)} at $50k, {fmt(m + LN2 * c, 2)} at $100k income"
        elif t["kind"] == "x" and t["base"] in b:
            m = b[t["base"]]; bl = S["terms"][t["base"]]["label"]
            r = f"{bl} is {fmt(m + c)} for {t['who']} instead of {fmt(m)}"
        elif t["kind"] == "asc":
            r = f"against single-family detached, at $50k: odds x {np.exp(c):.2f}"
        else:
            r = (f"higher value → {S['subject']} {'more' if c > 0 else 'less'} likely; odds x {np.exp(c):.3g} per unit"
                 + (f" ({t['measures']})" if t["measures"] else ""))
        out.append(dict(variable=t["label"], coefficient=fmt(c, 4), reading=r + "." + ns(p)))
    return pd.DataFrame(out)


def groups(folder, params):
    return [(term(folder, p)[0] or {}).get("group", "other") for p in params]


def labels(folder, params):
    out = []
    for p in params:
        t, suf = term(folder, p)
        out.append(p if t is None else t["label"] + (f" ({SPEC[folder]['alt_suffix'][suf]})" if suf else ""))
    return out


# ------------------------------------------------------------------------------------------------ hold-out text from the CSVs
def county_names(path):
    zs = pd.read_csv(path); n = zs.drop_duplicates("COUNTYFIPS").set_index("COUNTYFIPS").JUR_NAME.astype(str)
    fix = {11001: "Washington DC", 24510: "Baltimore City", 51919: "Fairfax"}
    return {c: fix.get(c, v.split(",")[0].split("/")[0].replace(" County", "").strip()) for c, v in n.items()}


def holdout_md(folder, out_dir, zs_path):
    """4-6 plain lines under the hold-out map, numbers from output/holdout_*.csv."""
    nm = county_names(zs_path); f = lambda x: f"{x:+.1f}".replace("-", "−")
    P = pd.read_csv(f"{out_dir}/holdout_puma.csv"); C = pd.read_csv(f"{out_dir}/holdout_county.csv")
    if "band" in C:
        band = {"06_school_location_K8": "k8", "07_school_location_high_school": "hs", "08_school_location_college": "college"}[folder]
        P, C = P[P.band == band], C[C.band == band]
    rp, rc = np.corrcoef(P.observed_pct, P.model_pct)[0, 1], np.corrcoef(C.observed_pct, C.model_pct)[0, 1]
    top = C.reindex(C.diff_pp.abs().sort_values(ascending=False).index).head(3)
    what = {"05_workplace_choice": "hold-out workers by workplace PUMA", "01_residential_puma": "hold-out movers by PUMA (upper row: Baltimore\u2013Washington, lower row: Baltimore City and County)"}.get(folder, "hold-out students by school PUMA (the rows are the three school bands; high school is mapped by county)")
    L = [f"How to read it: (a) observed share of {what}; (b) the model share (sum of predicted probabilities), same scale; "
         "(c) model minus observed in percentage points: red = model too high, blue = too low.",
         f"Correlation of the shares: {rp:.2f} by PUMA, {rc:.2f} by county; mean absolute difference {P.diff_pp.abs().mean():.2f} pp by PUMA, "
         f"{C.diff_pp.abs().mean():.2f} pp by county.",
         "Largest county differences: " + ", ".join(f"{nm.get(c, c)} {f(d)} pp" for c, d in zip(top.county, top.diff_pp)) + "."]
    if folder == "08_school_location_college":
        L.append("College is the weakest band: few students per PUMA and enrolment concentrated on a few campuses, so single campuses "
                 "dominate the differences.")
    L.append(f"The hold-out {'sample' if folder == '01_residential_puma' else 'half'} was also used in the specification search, so this is not a fully independent test.")
    return "\n\n".join(L)


# ------------------------------------------------------------------------------------------------ effects by income / group (delta method)
INC = [25000, 50000, 100000, 150000]
_li = lambda i: np.log(i / 50000.0)
_D = lambda m, x: [("Affordability and quality" if m in ("B_cost_share_above30", "B_ln_cost") else "Size and age" if m.startswith(("B_bed", "B_built")) else "Structure type"), m, x]
EFFECTS = {
    "02_residential_dwelling": dict(kind="income", rows=[
        ("Affordability and quality", "Cost above 30 % of income", {"B_cost_share_above30": 1, "B_cost_share_above30_x_lninc": _li}),
        ("Affordability and quality", "ln monthly housing cost", {"B_ln_cost": 1, "B_ln_cost_x_lninc": _li}),
        ("Size and age", "Bedroom shortfall", {"B_bedroom_shortfall": 1, "B_bedroom_shortfall_x_lninc": _li}),
        ("Size and age", "Bedroom excess", {"B_bedroom_excess": 1, "B_bedroom_excess_x_lninc": _li}),
        ("Size and age", "Built in the last five years", {"B_built_last5yrs": 1, "B_built_last5yrs_x_lninc": _li}),
        ("Structure type", "Single-family attached", {"ASC_SFA": 1, "B_SFA_x_lninc": _li}),
        ("Structure type", "Multifamily 2-4 units", {"ASC_MF2_4": 1, "B_MF2_4_x_lninc": _li}),
        ("Structure type", "Multifamily 5+ units", {"ASC_MF5plus": 1, "B_MF5plus_x_lninc": _li}),
        ("Structure type", "Mobile home or other", {"ASC_mobile_home": 1, "B_mobile_home_x_lninc": _li})]),
    "01_residential_puma": dict(kind="income", rows=[
        ("ln dwelling density", "Two or more persons, oldest 35+", {"B_ln_dwelling_density": 1, "B_ln_density_x_ln_income": _li}),
        ("ln dwelling density", "Single person, 35+", {"B_ln_dwelling_density": 1, "B_ln_density_x_single": 1, "B_ln_density_x_ln_income": _li}),
        ("ln dwelling density", "Two or more persons, oldest under 35", {"B_ln_dwelling_density": 1, "B_ln_density_x_oldest_under35": 1, "B_ln_density_x_ln_income": _li}),
        ("ln dwelling density", "Single person under 35", {"B_ln_dwelling_density": 1, "B_ln_density_x_single": 1, "B_ln_density_x_oldest_under35": 1, "B_ln_density_x_ln_income": _li})]),
    "05_workplace_choice": dict(kind="group", cols=["< $40k", "$40-75k", "$75-125k", "$125k+"], rows=[
        ("Car time", "Car time (per min)", {"B_time": 1, "B_time_x_income_under40k": [1, 0, 0, 0], "B_time_x_income_75_125k": [0, 0, 1, 0], "B_time_x_income_125kplus": [0, 0, 0, 1]}),
        ("Wage proxy", "High-wage share", {"B_high_wage_share": 1, "B_high_wage_share_x_income_under40k": [1, 0, 0, 0], "B_high_wage_share_x_income_75_125k": [0, 0, 1, 0], "B_high_wage_share_x_income_125kplus": [0, 0, 0, 1]})]),
    "06_school_location_K8": dict(kind="group", cols=["< $40k", "$40k or more"], rows=[
        ("School zone", "Quality of the public part", {"B_quality_public": 1, "B_quality_x_income_under40k": [1, 0]})]),
    "08_school_location_college": dict(kind="group", cols=["< $125k", "$125k or more"], rows=[
        ("Car time", "Car time (min)", {"B_time": 1, "B_time_x_income_125kplus": [0, 1]})]),
}


def _w(f, j, col):
    if callable(f): return float(f(col))
    if isinstance(f, list): return float(f[j])
    return float(f)


def effects(folder, b, V=None, cols=None):
    """b: dict parameter -> coefficient; V: DataFrame robust covariance (index/columns parameter names) or None.
    Returns long table: block, feature, column, value, se, p."""
    E = EFFECTS[folder]; cols = cols or (INC if E["kind"] == "income" else E["cols"]); out = []
    from scipy.stats import norm
    for blk, lab, terms in E["rows"]:
        if not all(p in b for p in terms): continue
        for j, col in enumerate(cols):
            w = {p: _w(f, j, col) for p, f in terms.items()}
            v = sum(w[p] * b[p] for p in w); se = np.nan
            if V is not None:
                ps = list(w); g = np.array([w[p] for p in ps]); se = float(np.sqrt(g @ V.loc[ps, ps].values @ g))
            out.append(dict(block=blk, feature=lab, column=col, value=v, se=se, p=2 * norm.sf(abs(v / se)) if se == se and se > 0 else np.nan))
    return pd.DataFrame(out)


def effects_table(folder, b, V=None):
    """wide table: value with stars (article thresholds) and (s.e.)"""
    t = effects(folder, b, V); E = EFFECTS[folder]
    if t.empty: return t
    st = lambda p: "" if p != p else "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
    t["cell"] = [f"{v:+.3f}{st(p)}" + (f" ({s:.3f})" if s == s else "") for v, s, p in zip(t.value, t.se, t.p)]
    t["column"] = [f"${c // 1000:.0f}k" if isinstance(c, (int, np.integer)) else c for c in t.column]
    w = t.pivot_table(index=["block", "feature"], columns="column", values="cell", aggfunc="first", sort=False)
    order = [f"${c // 1000}k" for c in INC] if E["kind"] == "income" else E["cols"]
    return w[[c for c in order if c in w.columns]]


HOW_INCOME = {"02_residential_dwelling": "How to read it: above zero the feature makes a dwelling more attractive (structure types: than a detached house), "
                                         "below zero less; where the band crosses zero the effect is not significant at that income.",
              "01_residential_puma": "How to read it: below zero denser PUMAs are less attractive for that household type, above zero more; "
                                     "where a band crosses zero the effect is not significant at that income."}


# ================================================================================================ MAST (MAST folders)
_RTS = "Regional Travel Survey 2017/18 (Baltimore and Washington regions), estimation half"
_Z = "the 1,588 zones of the model (full choice set)"
_L = lambda what, who, unit, by="distance, attraction, area and land use, with distance effects that differ by person", traits=None: dict(
    kind="location", answers=f"Where does {what} go? The model compares {_Z} by {by}.", deciders=who, choice=f"The zone of {what}",
    alts=_Z.capitalize(), unit=unit, traits=traits)
_M = lambda tours, alts, unit="tours": dict(kind="mode", answers=f"Which mode does a person use for {tours}? The model compares the available modes by time, cost or distance and by person and household traits; car driver is the reference.",
                                            deciders=f"Persons on {tours}", choice="The tour mode", alts=alts, unit=unit)
_M6 = "car driver, walk, bike, car passenger, bus, train (as available)"
ABIT_SPEC = {
    "01_primary_destination_pooled": _L("the main stop of a shopping, recreation, accompanying or other tour", "Persons on discretionary tours", "tours"),
    "02_stop_shopping": _L("a shopping stop on a tour", "Persons making a shopping stop", "stops",
                           "detour, attraction, area and land use, with detour effects that differ by household and tour mode"),
    "03_stop_recreation": _L("a recreation stop on a tour", "Persons making a recreation stop", "stops",
                             "detour, attraction, area and land use, with detour effects that differ by tour mode and by the direction of the stop",
                             "No person or household traits enter; the tour mode and the direction of the stop (inbound) enter as interactions with log detour."),
    "04_stop_accompanying": _L("an accompanying stop on a tour", "Persons making an accompanying stop", "stops",
                               "detour, attraction, area and land use, with detour effects that differ by household cars and tour mode"),
    "05_stop_other": _L("an other-errand stop on a tour", "Persons making an other-errand stop", "stops",
                        "detour, attraction, area and land use, with a detour effect that differs by tour mode",
                        "No person or household traits enter; the tour mode enters as an interaction with log detour."),
    "06_outing_first_stop_destination": _L("the first stop of an outing from the workplace", "Workers making an outing", "outings",
                                           "distance from the workplace, car generalised time, retail jobs and the county boundary",
                                           "No person or household traits enter; the household income enters only through the value of time in the car generalised time."),
    "07_work_business_usual_workplace": _L("a work-business episode of a worker with a usual workplace", "Workers with a usual workplace", "episodes",
                                           "detour, car generalised time, office jobs, area and land use, with detour effects that differ by household cars and time of day"),
    "08_work_business_other_persons": _L("a work-business episode of a person without a usual workplace", "Other persons with work business", "episodes",
                                         "distance, office jobs and region, with distance effects that differ by income and by worker status"),
    "09_work_trips_home_workers": _L("a work trip of a person who works at home", "At-home workers", "episodes",
                                     "distance, office jobs and the county boundary", "No person or household traits enter this model."),
    "10_school_daycare_without_record_pooled": _L("a school episode without a school record, or daycare", "Students without a school record; children under 5", "episodes",
                                                  "distance, car generalised time, school enrolment, area and land use",
                                                  "No person or household traits enter this model."),
    "11_outing_generation": dict(kind="binary", answers="Does a worker leave the workplace for an outing during a work episode? The model uses work duration, arrival time and the workplace area.",
                                 deciders="Workers at their usual workplace", choice="Outing or not", alts="At least one outing; no outing (utility 0)", unit="work episodes"),
    "12_outing_mode": dict(kind="binary", answers="Is an outing from the workplace walked, or made with the mode of the work tour? The model uses distance, the workplace area and the work tour's mode.",
                           deciders="Workers on an outing", choice="Walk or the work tour's mode", alts="Walk; the work tour's mode (utility 0)", unit="outings"),
    "13_return_home": dict(kind="binary", answers="Does a person go home between two out-of-home episodes, or go on directly? The model uses the detour via home, the episode types, the person and the time of day.",
                           deciders="Persons between two out-of-home episodes", choice="Return home or not", alts="Return home; go on directly (utility 0)", unit="episode pairs"),
    "14_tour_mode_work": _M("work tours", _M6), "15_tour_mode_school": _M("school tours", _M6), "16_tour_mode_shopping": _M("shopping tours", _M6),
    "17_tour_mode_other": _M("recreation, accompanying and other tours", _M6), "18_tour_mode_joint_shopping": _M("joint shopping tours", "car driver, walk, bike, car passenger, bus"),
    "19_tour_mode_joint_other": _M("joint recreation and other tours", _M6),
    "20_transit_leg_mode": dict(kind="mode", answers="On a tour whose main mode is transit, which mode is each leg? The model compares transit, walk, car passenger, car driver and bike by leg position, distance and the person.",
                                deciders="Persons on transit tours", choice="The mode of a leg", alts="transit, walk, car passenger, car driver, bike (as available)", unit="legs"),
}
ABIT_GLOSS = {"location": ["zone", "log-likelihood", "hold-out", "robust s.e.", "VIF"], "mode": ["reference alternative", "log-likelihood", "hold-out", "robust s.e.", "VIF"],
              "binary": ["reference alternative", "log-likelihood", "hold-out", "robust s.e.", "VIF"]}
GLOSSARY["reference alternative"] = "The alternative whose utility is fixed at 0; the coefficients of the others are differences against it."


def abit_glance_md(folder, coef_rows, n_est=None):
    S = ABIT_SPEC[folder]
    L = ["## Model at a glance", "", f"**1. Who decides.** {S['deciders']}. Data: {_RTS}" + (f"; {int(n_est):,} {S['unit']}." if n_est else "."), "",
         f"**2. What is chosen (dependent variable).** {S['choice']}. Alternatives: {S['alts']}.", "",
         "**3. Explanatory variables** (signs of the article estimates; terms specific to an alternative or purpose are listed per series):", "",
         "| Group | Variable | Sign |", "|---|---|---|"]
    for (g, l), t in coef_rows.groupby(["group", "label"], sort=False):
        sg = ", ".join((f"{s}: " if s else "") + ("+" if c > 0 else "−") for s, c in zip(t.series, t.coef))
        L.append(f"| {g} | {l} | {sg} |")
    L += ["", "**4. How person and household traits enter.** " + (S["traits"] if S.get("traits") else
        "Traits are the same for every zone, so they enter only as interactions with zone attributes (mostly log distance x person group)."
        if S["kind"] == "location" else "Traits enter with one coefficient per alternative, against the reference alternative whose utility is 0."), "",
        "**5. How to read a coefficient.** Positive makes the alternative more likely, negative less likely; exp(coefficient) is the factor by which the odds change for one unit more."]
    return "\n".join(L)


# one-line reasons for a specification choice, shown under "What this model answers"
ABIT_NOTE = {
    "12_outing_mode": "The fewer-cars-than-drivers term is not included: it is not significant (likelihood-ratio test p = 0.34) and BIC is lower without it.",
    "13_return_home": "The fewer-cars-than-drivers term is kept: it is significant (likelihood-ratio test p = 0.007), and with it the model gives a return-home share of 27.9 % for households with fewer cars than drivers on the hold-out half, against 28.8 % observed (weighted).",
    "20_transit_leg_mode": "The fewer-cars-than-drivers term is kept: the car allocation runs before the leg choice but covers only part of the effect, and the term stays significant under the free-car rule (car driver only when a household car is free over the tour window).",
}


def abit_answers_md(folder, R):
    S = ABIT_SPEC[folder]
    return "\n".join([f"# {R.get('model', folder)}", "", "A model of MAST (Maryland Activity Scheduling and Travel model), the activity-based model of the MILES platform, built on the ABIT code base.", "", "## What this model answers", "", S["answers"], ""] + ([ABIT_NOTE[folder], ""] if folder in ABIT_NOTE else []) + [
                      "| | |", "|---|---|", f"| Choice | {S['choice']} |", f"| Alternatives | {S['alts']} |", f"| Decision makers | {S['deciders']} |", f"| Data | {_RTS} |"])


def abit_glossary_md(folder):
    return "\n".join(["## Glossary", ""] + [f"- **{k}**: {GLOSSARY[k]}" for k in ["MAST"] + ABIT_GLOSS[ABIT_SPEC[folder]["kind"]]])


def abit_readings(rows):
    out = []
    for r in rows.itertuples():
        out.append(dict(variable=r.label + (f" ({r.series})" if r.series else ""), coefficient=f"{r.coef:+.4f}".replace("-", "−"),
                        reading=("more likely" if r.coef > 0 else "less likely") + f" for one unit more; odds x {np.exp(r.coef):.3g}" +
                                ("" if abs(r.coef) > 1.96 * r.se else " (not significant at 5 %)")))
    return pd.DataFrame(out)


def how_to_run_md_abit(folder, chk_min, heavy):
    return "\n".join(["## How to run", "",
                      "- Kernel: *Python (biogeme)* (`~/.venvs/biogeme`, Biogeme 3.3). Then *Run All*.",
                      "- `RUN_DATA_PREP`: rebuild the records and tables in a scratch copy and compare them with the shipped ones.",
                      "- `RUN_CHECK`: log-likelihood at the reference coefficients, no estimation" + (f" (about {chk_min:.0f} min)." if chk_min and chk_min > 1 else "."),
                      "- `RUN_ESTIMATION`: run the Biogeme estimation (off by default).",
                      "- `RUN_HOLDOUT`: log-likelihood of the hold-out half" + (" (as long as the check; off by default)." if heavy else ".")])
