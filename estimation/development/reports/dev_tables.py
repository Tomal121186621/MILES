#!/usr/bin/env python3
"""Model-development tables (article format): for each model, the nested sequence from the basic model, one block per step, with
K, log-likelihood, likelihood-ratio test against the current model, BIC and the decision; rejected blocks stay in the table with
the reason.  Selection on the estimation sample; the validation sample is reported once, for the final model.
Inputs: ESTIMATION_RESULTS/*/s07_fit.csv, r03_fit.csv, r04_fit.csv, m08_fit.csv, m08_coef.csv, d01_fit.csv; the specification searches
of 2_silo/resloc/tables and 3_abit/destination_choice/work/search_*.pkl.
Output: build/dev/dev_*.tex and model_development.pdf (in <workspace>/side_experiments/respec_2026-11/final_tables).
Usage: python3 estimation/development/reports/dev_tables.py"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, shutil, subprocess
import numpy as np, pandas as pd

HERE = f"{WORKSPACE}/side_experiments/respec_2026-11/final_tables"   # templates (.tex), build/ and PDFs (data)
SBS = ESTIMATION_RESULTS
V = f"{WORKSPACE}"; sys.path.insert(0, f"{MILES_HOME}/activity/lib/destination_choice")
B = os.path.join(HERE, "build"); OUT = os.path.join(B, "dev")


def n(x, d=1):
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{d}f}".replace("-", "$-$")


def lr(x, k):
    return "" if x is None or np.isnan(x) else f"{n(x)} ({int(k)})"


def table(label, caption, panels, notes):
    """panels: list of (title or None, rows); row = (step, description, K, LL, LR, df, BIC, decision)."""
    h = [r"{\footnotesize\setlength{\tabcolsep}{4pt}\nolinenumbers",
         r"\begin{longtable}{@{}lL{0.42\linewidth}rrrrl@{}}", f"  \\caption{{{caption}}}", f"  \\label{{{label}}}\\\\",
         r"  \toprule", r"  Step & Model & $K$ & LL & LR (df) & BIC & Decision \\", r"  \midrule", r"  \endfirsthead",
         r"  \multicolumn{7}{@{}l@{}}{\footnotesize Table~\thetable\ (continued)}\\[2pt]", r"  \toprule",
         r"  Step & Model & $K$ & LL & LR (df) & BIC & Decision \\", r"  \midrule", r"  \endhead", r"  \midrule",
         r"  \multicolumn{7}{@{}r@{}}{\emph{continued on the next page}} \\", r"  \endfoot", r"  \bottomrule", r"  \endlastfoot"]
    for i, (title, rows) in enumerate(panels):
        if title:
            if i: h.append(r"  \midrule")
            h.append(f"  \\multicolumn{{7}}{{@{{}}l}}{{\\emph{{{title}}}}} \\\\")
        for s, d, K, LL, L, df, bic, dec in rows:
            h.append(f"  {s} & {d} & {'' if K is None else int(K)} & {n(LL)} & {lr(L, df)} & {n(bic)} & {dec} \\\\")
    h.append(r"  \midrule")
    for t in notes: h.append(f"  \\multicolumn{{7}}{{@{{}}p{{0.98\\linewidth}}}}{{{t}}} \\\\")
    h += [r"\end{longtable}", r"\linenumbers}"]
    open(f"{OUT}/{label.split(':')[1]}.tex", "w").write("\n".join(h) + "\n")


def decision(r, sign_ok=True):
    if r.get("kept") in (True, "True"): return "kept"
    if not (r.get("p", 0) < 0.05): return "not kept: LR"
    if not sign_ok: return "not kept: sign"
    return "not kept: BIC"


RULE = ("A block is kept when the likelihood-ratio (LR) test against the current model is significant at 5\\,\\%, the BIC falls "
        "and the signs are the expected ones; LR and decision refer to the last kept model. Estimation sample only.")


# ---------------------------------------------------------------- car ownership
def cars():
    f = pd.read_csv(f"{SBS}/car_ownership/s07_fit.csv").to_dict("records")
    lab = {"M1": "Constants", "M2": "+ household composition (workers, non-working persons 16+, children, member 65+, single person)",
           "M3": "+ ln income", "M4": "+ dwelling (single-family detached, multifamily, bedrooms)", "M5": "+ ln dwelling density of the PUMA",
           "M6": "+ non-work accessibility gain from a car", "F1": "Income piecewise linear (bends at \\$25k, \\$50k, \\$100k)",
           "I1": "+ ln income $\\times$ ln density"}
    rows, final = [], None
    for r in f:
        if r["step"] == "final": final = r; continue
        if r["step"] in ("record", "final_householder"): continue
        if r["step"] == "F2":
            d = r["label"].split("age: ")[1].replace(" instead of member 65+", "")
            rows.append(("F2", f"Age form: {d} instead of member 65+", r["K"], r["LL"], np.nan, 0, r["BIC"], "chosen" if r.get("kept") in (True, "True") else "not chosen: BIC"))
            continue
        rows.append((r["step"], lab[r["step"]], r["K"], r["LL"], r.get("LR", np.nan), r.get("df", 0), r["BIC"], "kept" if r["step"] == "M1" else decision(r)))
    table("tab:dev_cars", "Car ownership: model development (multinomial logit, reference: no car).", [(None, rows)],
          [RULE, "Age forms are not nested and are compared by BIC: householder age linear, age and age squared, bands (under 30, 45--64, 65+; reference 30--44). The final model uses the age of the oldest household member.",
           f"Final model: $K$ = {final['K']}, LL = {n(final['LL'])}; hold-out sample (20\\,\\%) LL = {n(final['holdout_LL'])}."])


# ---------------------------------------------------------------- residential: dwelling, zone, region
OOT = pd.read_csv(f"{SBS}/residential/r09_oot.csv").set_index(["model", "version"]).LL


def dwelling():
    s = pd.read_csv(f"{V}/2_silo/resloc/tables/dwelling_specification_search.csv").to_dict("records")
    lab = ["Housing burden linear, price, bedrooms, structure type", "Burden piecewise linear (bends at 30\\,\\% and 50\\,\\%)",
           "+ structure type $\\times$ household (size, children, member 65+, ln income)", "+ burden $\\times$ children",
           "Step 3 with price, bedroom and new-dwelling terms by income group", "One above-50\\,\\% burden slope for incomes \\$75k+"]
    rows = []
    for i, r in enumerate(s):
        dec = "kept" if i in (0, 1, 2, 4, 5) else "not kept: BIC"
        L, df = (r["LR_vs_previous"], r["df"]) if i in (1, 2, 3, 4) else (np.nan, 0)
        if i == 5: dec = "kept (restriction)"; L, df = 2 * (s[4]["LL"] - r["LL"]), 1
        rows.append((str(i + 1), lab[i], r["K"], r["LL"], L, df, r["BIC"], dec))
    a = pd.read_csv(f"{SBS}/residential/r04_fit.csv").to_dict("records")
    alab = ["Age form: member 65+ $\\times$ structure type (step 6)", "Age form: age (linear) $\\times$ structure type",
            "Age form: age bands $\\times$ structure type"]
    for k, r in enumerate(a):
        rows.append(("7" + "abc"[k], alab[k], r["K"], r["LL"], np.nan, 0, r["BIC"], "chosen" if r["BIC"] == min(x["BIC"] for x in a) else "not chosen: BIC"))
    g = pd.read_csv(f"{SBS}/residential/r06_fit.csv").to_dict("records"); form = min(g[1:3], key=lambda x: x["BIC"])
    for k, r in enumerate(g[1:3]):
        lab = ("Income form: four income-group coefficients per term (step 7c)" if r["model"].startswith("Income-group")
               else "Income form: one coefficient per term plus term $\\times$ ln income")
        rows.append(("8" + "ab"[k], lab, r["K"], r["LL"], np.nan, 0, r["BIC"], "chosen" if r is form else "not chosen: BIC"))
    DROP = {"bur_lo_x_lninc": "cost share below 30\\,\\% $\\times$ ln income", "SFA_x_size": "single-family attached $\\times$ household size",
            "MH_x_size": "mobile home $\\times$ household size", "MH_x_child": "mobile home $\\times$ children"}
    prev = form
    for k, r in enumerate(g[3:]):
        lab = "Without " + DROP[r["model"].split("without ")[-1]]
        rows.append((str(9 + k), lab, r["K"], r["LL"], 2 * (prev["LL"] - r["LL"]), prev["K"] - r["K"], r["BIC"], "kept (restriction)" if r["BIC"] < prev["BIC"] else "not kept: BIC"))
        if r["BIC"] < prev["BIC"]: prev = r
    best = prev
    table("tab:dev_dwelling", "Residential location, dwelling part (dwelling within the PUMA): model development.", [(None, rows)],
          [RULE, "Step 5 replaces the price terms of step 3 (LR against step 3); step 6 is a restriction of step 5 (LR of the restriction).",
           "Lettered rows are alternative forms of the same terms, compared by BIC (non-nested). Age of the oldest member; bands: under 35, 50--64, 65+ (reference 35--49). Step 8 compares two forms of the income dependence of the cost-burden, ln cost, bedroom and new-dwelling terms (non-nested, BIC); ln income = ln(income / \\$50k). Steps 9 onward drop terms that are collinear with other terms and not significant (LR of the restriction).",
           f"Final model: $K$ = {best['K']}, LL = {n(best['LL'])}; validation sample LL = {n(best['validation_LL'])}. Out-of-time test (ACS PUMS movers 2019--2021, used once, same sampled choice sets): LL = {n(OOT[('dwelling', 'final')])} (model of record {n(OOT[('dwelling', 'model of record')])})."])


def zone():
    f = pd.read_csv(f"{SBS}/residential/r03_fit.csv").to_dict("records")
    rows, final = [], None
    for r in f:
        if r["step"] == "final": final = r; continue
        lab = "Size term (ln dwellings of the zone $\\times$ structure type)" if r["step"] == "Z0" else r["label"]
        lab = lab.replace("+ income similarity", "+ share of same-income households in the zone").replace(" x ", " $\\times$ ").replace("ln(1 + t)", "$\\ln(1+t)$").replace(": member 65+", ": member 65+").replace(": bands", ": bands (under 35, 50--64, 65+)")
        if r["step"] == "Z6":
            dec = "chosen" if r.get("kept") in (True, "True") else "not chosen: " + ("LR" if not r.get("p", 0) < 0.05 else "BIC")
        elif isinstance(r.get("decision"), str):   # 2026-11-10 land-use steps: decision recorded by r03 (sign rule included)
            dec = r["decision"]
        elif "not tested" in str(r["label"]):
            dec = "not tested"
        else:
            dec = "kept" if r["step"] == "Z0" else decision(r)
        import re as _re; _m = _re.match(r"(\d+)([a-z]*)$", r["step"][1:])
        stp = ("F" + _m.group(1)) if r["step"].startswith("B") else str(int(_m.group(1)) + 1) + _m.group(2)   # B<k>: final backward check
        if r["step"].startswith("B"):
            NM = {"accN_x_child": "non-work accessibility $\\times$ children", "accW_x_nocar": "work accessibility $\\times$ no car",
                  "lnddens_x_child": "dwelling density $\\times$ children", "lnretden": "retail density", "accN_x_age65": "non-work accessibility $\\times$ 65+"}
            _t = _re.search(r"without (.*) \(\|t\| ([0-9.]+)", r["label"])
            lab = "Final check: without " + ", ".join(NM.get(x.strip(), x.strip().replace("_", "\\_")) for x in _t.group(1).split(",")) + f" ($|t|$ = {_t.group(2)})"
        if r["step"] == "Z6": stp += "abc"[sum(1 for x in rows if x[0].startswith("7"))]
        rows.append((stp, lab, r["K"], r["LL"], r.get("LR", np.nan), r.get("df", 0), r["BIC"], dec))
    g = pd.read_csv(f"{SBS}/residential/r08_fit.csv").to_dict("records")
    for k, r in enumerate(g):
        lab = "Accessibility: car-based impedance (step 10)" if k == 0 else "Accessibility: multimodal impedance (mode-choice logsum)"
        rows.append(("11" + "ab"[k], lab, r["K"], r["LL"], np.nan, 0, r["BIC"], "chosen" if r.get("chosen") in (True, "True") else "not chosen: BIC"))
    fin8 = [r for r in g if r.get("chosen") in (True, "True")][0]
    if os.path.exists(f"{SBS}/residential/r12_fit.csv"):   # 2026-11-10: non-work accessibility split by purpose
        for k, r in enumerate(pd.read_csv(f"{SBS}/residential/r12_fit.csv").to_dict("records")):
            lab = ["Non-work accessibility pooled (step 11b)", "Non-work accessibility split: shopping + services/other", "Shopping accessibility only (for information)"][k]
            dec = "chosen" if r.get("chosen") in (True, "True") else ("not chosen: sign" if r.get("sign_ok") in (False, "False") else "not chosen: not an approved form" if k == 2 else "not chosen: BIC")
            rows.append(("12" + "abc"[k], lab, r["K"], r["LL"], np.nan, 0, r["BIC"], dec))
    table("tab:dev_zone", "Residential location, zone $\\times$ structure-type part (within the county): model development.", [(None, rows)],
          [RULE, "Lettered rows are alternatives, compared by BIC. Steps 7a--7c: age forms (age of the oldest member; linear form: (age $-$ 50)/10; bands: reference 35--49); the lowest BIC among those that pass the LR test is kept. Steps 11a--11b: the accessibility of the household's income group and car availability with car-based impedance, or with the mode-choice logsum (car, transit, walk, bike) as impedance. Steps 5a--5e: land use of the zone (ln dwellings per acre, ln(1 + jobs per acre), ln(1 + retail jobs per km$^2$), land-use mix, paid-parking share; expected signs $-$, $-$, none, $+$, $-$), each added in turn; step 8b: dwelling density $\\times$ no car ($+$) and $\\times$ children ($-$), one set. Steps 12a--12c: the pooled non-work accessibility against shopping and services/other accessibility (expected signs positive). Non-work accessibility is a base term and is kept as the main effect of its interactions; work accessibility is dropped (wrong sign, $t$ $-$2.5). Rows F1, F2, ...: final backward check of the non-base terms with $|t| < 1.96$ (multimodal form; LR of dropping the term).",
           "Sampled choice sets of 30 cells (uniform); households with a known age. Five-fold cross-validation of steps 11a and 11b on all households (estimate on four folds, full choice set on the fifth): multimodal accessibility fits better in every fold (log-likelihood difference " + "{:.1f} in total).".format(*[(lambda r: (r[r.form == "multimodal"].LL_test.sum() - r[r.form == "car-based"].LL_test.sum()))(pd.read_csv(f"{SBS}/residential/r10_cv.csv"))]),
           f"Final model: $K$ = {fin8['K']}, LL = {n(fin8['LL'])}; validation sample, full choice set: LL = {n(fin8['validation_LL_fullset'])}."])


def region():
    f = pd.read_csv(f"{SBS}/residential/r05_fit.csv").to_dict("records")
    lab = {"S0": "Car time to another county (under 20, 20--60, over 60\\,min)",
           "S1": "+ previous county, same state", "S2": "+ size: ln dwellings in the county",
           "S3": "Size: inclusive value of the zone $\\times$ structure-type part", "S4": "+ inclusive value of the dwelling part",
           "R": "Step 10a without crime (sign reversed after step 8, not significant)",
           "L": "Step 12 with the dwelling inclusive value fixed at 1",
           "Ja": "Step 14g + car time $\\times$ ln income",
           "Jb": "Step 14g + car time by income group",
           "I": "Step 15a with income-specific inclusive values, car time, previous county and commute",
           "C": "Step 11 with inclusive-value parameters fixed at 1 where the estimate exceeds 1",
           "A": "Step 9 + county constants (county-wide terms dropped)"}
    num = {"S2": "3a", "S3": "3b", "R": "12", "L": "13", "Ja": "15a", "Jb": "15b", "I": "16", "C": "17", "A": "18"}
    num.update({f"T{x}": f"14{x}" for x in "abcdefg"})
    rows = []
    for r in f:
        st = r["step"]; dec = clean_dec(r["decision"])
        if st in ("C", "A"): continue
        dec = "not kept: sign" if dec.startswith("not kept: sign") else dec
        dec = {"S2": "not chosen: BIC", "S3": "chosen"}.get(st, dec)
        rows.append((num[st] if st in num else (str(int(st[1:].rstrip("abc")) + (1 if int(st[1:].rstrip("abc")) < 2 else 0)) + "".join(c for c in st[1:] if c in "abc")), lab.get(st, r["model"]), r["K"], r["LL"], r.get("LR", np.nan), r.get("df", 0), r["BIC"], dec))
    fin = [r for r in f if r["final"]][0]
    table("tab:dev_region", "Residential location, county of moving households: model development.", [(None, rows)],
          [RULE, "Lettered rows are alternatives, compared by BIC among those that pass the rule. Steps 3a and 3b are alternative size measures (non-nested, compared by BIC); the inclusive value contains the number of dwellings and also how attractive they are. Step 12 drops a kept term whose sign reversed after later blocks and that is no longer significant (LR of dropping it). The inclusive-value parameters must lie between 0 and 1 for consistency with random utility maximisation. Step 13 fixes the dwelling inclusive value at its upper bound (LR of the restriction). Steps 14a--14g: forms of the car time to another county, compared by BIC among those in which the car-time effect does not rise with time (the under-20-min slope is positive in 14a, 14c, 14d and 14e). Steps 15a and 15b: car time to another county varying with household income (ln(income / \\$50k)), the inclusive values common to all incomes. Step 16 makes the inclusive values, car time, previous county and commute specific to the four income groups.",
           "Age: oldest member; linear form (age $-$ 50)/10, bands under 35, 50--64, 65+ (reference 35--49). Household size: persons $-$ 1 (at most 5). Previous county: share of the household's origin migration area (ACS) that lies in the county. Inclusive values from the zone and dwelling parts reported in this document. Expected signs: crime and crime $\\times$ children negative, school learning growth and its interaction with children positive.",
           f"Final model (step {num[fin['step']] if fin['step'] in num else int(fin['step'][1:]) + 1}): $K$ = {fin['K']}, LL = {n(fin['LL'])}; validation sample LL = {n(fin['val_LL_final'])}. Out-of-time test (ACS PUMS movers 2019--2021, used once): LL = {n(OOT[('county', 'final')])} (model of record {n(OOT[('county', 'model of record')])})."])


# ---------------------------------------------------------------- mode choice
def mode():
    f = pd.read_csv(f"{SBS}/mode_choice/m08_fit.csv"); c = pd.read_csv(f"{SBS}/mode_choice/m08_coef.csv")
    lab = {"M0": "Constants", "M1": "+ level of service", "M2": "+ person: age, male, driving licence",
           "M3": "+ household: size, cars, member under 18", "M4a": "+ home zone: core city, rural",
           "M4b": "+ main-activity zone: core city, rural", "M5": "+ tour: joint household tour, purpose, stops",
           "M6": "+ paid-parking share at the destination (car driver)", "M7": "+ out-of-vehicle time (bus, train)"}
    form = {"work": "generalised cost", "shopping": "time and cost", "other": "time and cost", "school": "time"}
    fname = {"GC": "generalised cost", "TC": "time and cost", "T": "time only"}
    title = {"work": "Work tours", "shopping": "Shopping tours", "other": "Other tours", "school": "School tours"}
    panels, finals = [], []
    for seg in ["work", "shopping", "other", "school"]:
        g = f[f.segment == seg].to_dict("records"); rows = []
        if seg == "school":
            g9 = pd.read_csv(f"{SBS}/mode_choice/m09_fit.csv").to_dict("records")
            sl = {"M0": ("0", "Constants"), "M1a": ("1a", "+ level of service: time (motorised modes)"), "M1b": ("1b", "+ level of service: round-trip distance on every mode"),
                  "M1c": ("1c", "+ level of service: time and distance on every mode"), "M2": ("2", lab["M2"]), "M3": ("3", lab["M3"]), "M4a": ("4a", lab["M4a"]),
                  "M4b": ("4b", lab["M4b"]), "M5": ("5", lab["M5"]), "M6": ("6", lab["M6"]), "M7": ("7", lab["M7"]),
                  "P": ("8", "Bus and train share the person and household coefficients"), "M4a'": ("9a", "+ home zone: core city, rural (one transit set)"),
                  "M4b'": ("9b", "+ main-activity zone: core city, rural (one transit set)")}
            for r in g9:
                if r["step"] == "final": finals.append((seg, r)); continue
                if r["step"] == "M8": rows.append(("10", "Nested logit: " + r["label"].split(": ")[1], r["K"], r["LL"], r.get("LR"), r.get("df", 0), r["BIC"], "not kept: BIC" if r["decision"] == "not kept" else r["decision"])); continue
                k, d = sl[r["step"]]; dec = clean_dec(r["decision"])
                if dec == "not kept": dec = "not kept: LR" if not r.get("p", 0) < 0.05 else "not kept: BIC"
                if r["step"] == "P": dec = "kept (restriction)" if dec.startswith("kept") else dec
                rows.append((k, d, r["K"], r["LL"], r.get("LR") if r["step"] != "P" else r.get("LR"), r.get("df", 0) if r["step"] != "P" else r.get("df", 0), r["BIC"], dec))
            panels.append((title[seg], rows)); continue
        for r in g:
            st = r["step"]
            if st == "final": finals.append((seg, r)); continue
            if st == "M8":
                k = c[(c.segment == seg) & (c.step == "M8")]
                nm = r["label"].split(": ")[1]
                mus = k[k.param.str.startswith("mu_")]
                if r.get("kept") in (True, "True"):
                    other = [x for x in g if x["step"] == "M8" and x is not r and x.get("kept") in (True, "True")]
                    dec = "kept" if not other or r["BIC"] <= min(x["BIC"] for x in other) else "not kept: BIC"
                elif not r.get("p", 0) < 0.05: dec = "not kept: LR"
                else: dec = "not kept: $\\mu$ at bound"
                rows.append(("8", f"Nested logit: {nm}", r["K"], r["LL"], r.get("LR"), r.get("df", 0), r["BIC"], dec)); continue
            if st == "H":
                mo = {"WK": "walk", "BK": "bike", "CP": "car passenger", "BUS": "bus", "TRAIN": "train"}[r["label"].split()[-1]]
                k = 9 + sum(1 for x in rows if x[1].startswith("Without household size"))
                rows.append((str(k), f"Without household size: {mo}", r["K"], r["LL"], r.get("LR"), r.get("df", 0), r["BIC"],
                             "kept (restriction)" if r.get("kept") in (True, "True") else "not kept: BIC")); continue
            if st == "F":
                f2 = r["label"].split()[2]
                dec = "not chosen: sign" if r.get("signs_ok") in (False, "False") else "not chosen: no cost term" if f2 == "T" else "not chosen: BIC"
                rows.append(("F", f"Level of service as {fname[f2]}", r["K"], r["LL"], np.nan, 0, r["BIC"], dec)); continue
            dec = "kept" if st == "M0" else decision(r, sign_ok=True)
            if st == "M7" and r.get("p", 1) < 0.05 and r["BIC"] < g[[x["step"] for x in g].index("M6")]["BIC"]: dec = "not kept: sign"
            if st == "M7":
                o = c[(c.segment == seg) & (c.step == "M7") & (c.param == "ovt")].coef
                if len(o) and o.iloc[0] > 0 and r.get("p", 1) < 0.05: dec = "not kept: sign" if dec != "not kept: BIC" else "not kept: BIC, sign"
            d = lab[st] + (f" ({form[seg]})" if st == "M1" else "")
            rows.append((st.replace("M", ""), d, r["K"], r["LL"], r.get("LR"), r.get("df", 0), r["BIC"], dec))
        panels.append((title[seg], rows))
    fin = "; ".join(f"{title[s].lower()}: $K$ = {r['K']}, LL = {n(r['LL'])}, validation LL = {n(r['holdout_LL'])}" for s, r in finals)
    table("tab:dev_mc", "Tour mode choice: model development.", panels,
          [RULE, "Person, household, location and tour variables enter every mode except car driver (reference). Steps 1--7: multinomial logit; step 8: nests auto (car driver, car passenger), transit (bus, train), non-motorised (walk, bike), or auto and transit only; nest parameters $\\mu \\ge 1$.",
           "School tours: level-of-service forms compared as steps 1a--1c (time is not significant); step 8 is a restriction (LR of the restriction); steps 9a--9b repeat the area-type blocks with one set of bus and train coefficients. Other tours: level of service (step F, final model): a form with a cost term is preferred when the cost coefficient is negative and significant; time only otherwise. Generalised cost: time + 60 $\\times$ cost / value of time (half the wage rate). Work tours weighted (WESML). Steps 9 onward drop household size on a mode where it is collinear with children and not significant (LR of the restriction). Driving licence: 0 for walk (normalisation; car driver requires a licence, so only the differences between the other modes are identified).",
           "Car availability follows the household car allocation, so the ``fewer cars than drivers'' term is not part of the model.",
           "Car-driver availability excludes tours during whose window (leaving home to returning home) all household cars are at some instant simultaneously in use by other members' recorded car-driver tours (a joint group counts once), the rule of the household car allocation.",
           f"Final models: {fin}."])


# ---------------------------------------------------------------- destination and stop location
def destinations():
    d1 = pd.read_csv(f"{SBS}/destination/d01_fit.csv")
    lab = {"S1": "Size term + distance (linear)", "S2": "Distance piecewise linear", "S3": "+ intrazonal", "S4": "+ area dummies",
           "S5": "+ retail density, land-use mix", "S6": "+ county and state boundary",
           "S7": "+ ln distance $\\times$ income, cars, children, age, worker", "S8": "+ ln distance $\\times$ time of day",
           "S9": "+ mode-choice logsum", "S9t": "+ car generalised time instead of the logsum", "S9b": "+ logsum and car generalised time",
           "S10": "+ transit availability (households without a car)", "F": "Backward elimination ($|t| < 1.96$)"}
    stoplab = dict(lab, S1="Size term + detour (linear)", S2="Detour piecewise linear", S3="+ stop in an anchor zone",
                   S7="+ ln(1 + detour) $\\times$ income, cars, children, age, worker, tour mode, tour purpose, direction")
    P = {"SHOPPING": "Shopping", "OTHER": "Other", "RECREATION": "Recreation", "ACCOMPANY": "Accompanying"}
    for kind in ["primary", "stop"]:
        panels = []
        for pur in P:
            seg = f"{pur}_{kind}"; o = pickle.load(open(f"{V}/3_abit/destination_choice/work/search_{seg}.pkl", "rb")); R = o["rows"]
            M = {r["model"]: r for r in R}; aic = {k: M[k]["AIC"] for k in ("S9", "S9t", "S9b") if k in M}; top = min(aic, key=aic.get)
            rows = []
            for r in R:
                m = r["model"]; L = r.get("LR", np.nan); df = r.get("LR_df", 0)
                if m in ("S9", "S9t", "S9b"): dec = "chosen (AIC)" if m == top else "not chosen: AIC"; L, df = np.nan, 0
                elif m == "S10": dec = "kept" if r.get("LR_p", 1) < 0.05 else "not kept: LR"
                elif m == "F": dec = "final"; L, df = np.nan, 0
                elif m == "S8" and kind == "stop": continue
                else: dec = "added" if m == "S1" or r.get("LR_p", 1) < 0.05 else "added (LR n.s.)"
                rows.append((m.replace("S", ""), (stoplab if kind == "stop" else lab)[m], r["K"], r["LL"], L, df, r["BIC"], dec))
            for x in d1[(d1.segment == seg) & d1.model.str.startswith("+")].to_dict("records"):
                v = "woman" if "female" in x["model"] else "household size"
                d = ("ln(1 + detour)" if kind == "stop" else "ln distance") + f" $\\times$ {v}"
                rows.append(("T", f"+ {d}", x["K"], x["LL"], x["LR"], 1, x["BIC"], "kept" if x["kept"] else ("not kept: LR" if x["p"] >= 0.05 else "not kept: BIC")))
            panels.append((P[pur] + (" tours, primary destination" if kind == "primary" else " stops"), rows))
        what = "primary destination of home-based tours" if kind == "primary" else "intermediate stops"
        table(f"tab:dev_{'dc' if kind == 'primary' else 'stop'}", f"Destination choice, {what}: model development.", panels,
              ["Steps 1--8 are added in turn (LR against the previous step); terms that are not significant are removed at the end by backward elimination (step F). Steps 9, 9t and 9b are not nested and are compared by AIC; the backward elimination drops terms with robust $|t| < 1.96$ (distance pieces and size term kept). Step T: tested on the final model (LR at 5\\,\\% and BIC).",
               "40 sampled alternatives (importance sampling) with the sampling correction; estimation sample."])



# ---------------------------------------------------------------- workplace, school location, other locations, outings, return home
FIX = {"- a\\_school": "- preceding episode: school", "- e\\_school": "- following episode: school", " x ": " $\\times$ ", "ln(1 + km)": "$\\ln(1+\\text{km})$"}


def clean_dec(d):
    """short decision labels for the revision rows (band sets, size bound, fixed pieces)"""
    d = str(d)
    if d.startswith("information only") or d.startswith("not dropped: joint LR"): return "kept (joint LR)"
    if d.startswith("whole band set kept"): return "kept: set completed (joint LR)"
    if d.startswith("dropped: whole band set"): return "dropped: set (joint LR)"
    if d.startswith("dropped: theta"): return "dropped: not identified"
    if d.startswith("mu <= 1 adopted"): return "kept (restriction)"
    if d.startswith("mu <= 1 not adopted"): return "not kept: BIC"
    if d == "not chosen: car time rises with time": return "not chosen: sign"
    if "excluded" in d: return "not used"
    return d


def seq_rows(path):
    """rows of a block sequence (columns step, label, K, LL, BIC, LR, df, p, decision); final and record rows returned apart"""
    f = pd.read_csv(path).to_dict("records"); rows, fin, rec = [], None, None
    for k, r in enumerate(f):
        st = str(r["step"])
        if st == "final": fin = r; continue
        if st == "record": rec = r; continue
        lab = str(r["label"])
        for a, b in (("\\", ""), ("$", "\\$"), ("&", "\\&"), ("%", "\\%"), ("_", "\\_")): lab = lab.replace(a, b)
        for a, b in FIX.items(): lab = lab.replace(a, b)
        lab = lab.replace("- no car (", "- the no-car term (")
        if lab.startswith("Final check: without "): lab = "- " + lab[len("Final check: without "):]
        lab = lab[0].upper() + lab[1:] if lab[0].isalpha() else lab
        if lab.startswith("- "): lab = "Without " + lab[2:]
        if k > 0 and not lab.startswith(("+", "Without")) and not st[-1:].isalpha():
            proper = lab.split()[0].rstrip(";,") in ("Baltimore", "Washington", "Virginia", "Delaware", "Pennsylvania", "West", "Maryland", "DC")
            lab = "+ " + (lab if proper else lab[0].lower() + lab[1:])
        dec = str(r.get("decision", ""))
        if dec.startswith("start of the revision") or "_pre" in str(r.get("step", "")): continue
        dec = clean_dec(dec)
        dec = {"base": "kept", "nan": "kept", "final": "kept"}.get(dec, dec)
        if dec.startswith("dropped"): dec = "dropped"
        st = st.replace("D", "R").replace("F", "R")
        rows.append((st, lab, r["K"], r["LL"], r.get("LR", np.nan), r.get("df", 0) if r.get("df") == r.get("df") else 0, r["BIC"], dec))
    return rows, fin, rec


def final_line(name, fin, rec):
    return (f"{name}: final $K$ = {int(fin['K'])}, LL = {n(fin['LL'])}, validation LL = {n(fin['validation_LL'])}"
            + (f" (current specification: $K$ = {int(rec['K'])}, validation LL = {n(rec['validation_LL'])})" if rec else ""))


def sequences(label, caption, models, notes):
    panels, fins = [], []
    for title, path in models:
        if not os.path.exists(path): continue
        rows, fin, rec = seq_rows(path); panels.append((title, rows))
        if fin: fins.append(final_line(title, fin, rec))
    if not panels: return False
    lead = ("Lettered rows are alternatives, compared by BIC among those that pass the rule. Rows R: a kept term whose sign reversed "
            "after later blocks and that is no longer significant is dropped (LR of dropping it). Estimation half only; the validation "
            "half is used once, for the final model and the current specification.")
    table(label, caption, panels, [RULE, lead] + notes + ["; ".join(fins) + "."])
    return True


def pooled_rows(path):
    """rows of a pooling sequence (primary_destination_pooled/dp_pooled.py, other_locations/lp_pooled.py): start, restriction blocks, revision rows"""
    f = pd.read_csv(path).to_dict("records"); rows = []
    LAB = {"S+R+O|mu_size": "(shopping, recreation, other)", " x ": " $\\times$ ", "Log distance": "ln(distance)", "log distance": "ln(distance)",
           "Re-enabled interactions, shared: ": "+ shared ", " (bound)": "", "accompany)": "accompanying)"}
    for r in f:
        st = str(r["step"])
        if st.startswith(("sep_", "current_", "final", "separate")) or st == "R0": continue
        lab = str(r["label"])
        for a, b in LAB.items(): lab = lab.replace(a, b)
        d = str(r["decision"])
        dec = ("start" if d.startswith("start") else "kept (reparametrisation)" if "reparametrisation" in d
               else "kept (restriction)" if d.startswith("chosen") else clean_dec(d))
        LR, df = (r.get("LR", np.nan), r.get("df", 0)) if r.get("df") == r.get("df") else (np.nan, 0)
        rows.append((st, lab, r["K"], r["LL"], LR, df, r["BIC"], dec))
    fin = [r for r in f if str(r["step"]) == "final"][0]
    return rows, fin


def others():
    A, L, W = f"{SBS}/activity", f"{SBS}/locations", f"{SBS}/workplace"
    made = []
    if sequences("tab:dev_work", "Workplace choice: model development.", [(None, f"{W}/w04_fit.csv")],
                 ["Chosen zone plus 99 zones sampled at random (no correction needed); validation on the full choice set. Each step starts from the estimates of the previous one and is solved to a gradient below 10$^{-4}$ where possible (Newton steps)."]):
        made.append("dev_work")
    if sequences("tab:dev_school", "School location choice by school level: model development.",
                 [("Kindergarten to grade 8", f"{L}/l07_school_k8_fit.csv"), ("High school", f"{L}/l07_school_hs_fit.csv"), ("College", f"{L}/l07_school_college_fit.csv")],
                 ["Full choice set (zones with enrolment of the level). The county and state lines are separate steps; they were one block in a first run of the kindergarten-to-grade-8 model."]):
        made.append("dev_school")
    if sequences("tab:dev_loc", "Other episode locations: model development.",
                 [("Daycare and pre-school of children under 5", f"{L}/l01_daycare_fit.csv"), ("School episodes of persons without a school record", f"{L}/l02_nonstud_fit.csv"),
                  ("Work trips of at-home workers", f"{L}/l03_wahb_fit.csv"), ("Work business from home", f"{L}/l04_wbhome_fit.csv"),
                  ("Work business of a worker with a usual workplace", f"{L}/l05_wbwork_fit.csv"), ("Outing destination from the workplace", f"{L}/l06_outing_dest_fit.csv")],
                 ["Multinomial logit over all 1,588 zones. A person or time-of-day flag enters only with at least 20 records on each side, a zone flag with at least 5 observed destinations."]):
        made.append("dev_loc")
    P, S = f"{SBS}/dest_primary", f"{SBS}/dest_stop"
    names = [("Shopping", "shop"), ("Recreation", "rec"), ("Accompanying", "acc"), ("Other", "oth")]
    if all(os.path.exists(f"{P}/d_{k}_fit.csv") for _, k in names):
        sequences("tab:dev_dc", "Primary destination of discretionary tours: model development.", [(t, f"{P}/d_{k}_fit.csv") for t, k in names],
                  ["Multinomial logit over all 1,588 zones. A person or time-of-day flag enters only with at least 20 records on each side, a zone flag with at least 5 observed destinations."])
    if all(os.path.exists(f"{S}/s_{k}_fit.csv") for _, k in names):
        sequences("tab:dev_stop", "Stop location: model development.", [(t, f"{S}/s_{k}_fit.csv") for t, k in names],
                  ["Multinomial logit over all 1,588 zones; impedance: detour between the previous location and the next anchor. Guards as for the primary destinations."])
    if os.path.exists(f"{SBS}/dest_pooled/dp_fit.csv"):
        rows, fin = pooled_rows(f"{SBS}/dest_pooled/dp_fit.csv")
        table("tab:dev_dc_pooled", "Primary destination of discretionary tours, pooled model of the four purposes: model development.", [(None, rows)],
              [RULE, "Start: the four separate models with a common specification, estimated jointly (LL = sum of the separate LLs). Each block restricts a group of coefficients to one value for all four purposes or for a subset (letters: all four; shopping and other; shopping, recreation and other), with purpose-specific scale; a restriction is kept when BIC falls, the shared estimates have the expected signs and none is at a bound. Rows R: the >50\\,km piece held at 0 (collinear with car time); joint LR tests of each complete band set; the size coefficient held at its bound of 1.",
               f"Final model: $K$ = {int(fin['K'])}, LL = {n(fin['LL'])}, BIC = {n(fin['BIC'])}; validation LL = {n(fin['validation_LL'])}."])
        made.append("dev_dc_pooled")
    if os.path.exists(f"{L}/lp_edu_fit.csv"):
        rows, fin = pooled_rows(f"{L}/lp_edu_fit.csv")
        table("tab:dev_loc_edu", "School episodes of persons without a school record and daycare, pooled model: model development.", [(None, rows)],
              [RULE, "Start: the two separate models with a common specification, estimated jointly. Each block restricts a group of coefficients to one value for both purposes, with a daycare-specific scale; rows BR: interactions that the daycare sample alone could not carry, tried on the pooled sample.",
               f"Final model: $K$ = {int(fin['K'])}, LL = {n(fin['LL'])}, BIC = {n(fin['BIC'])}; validation LL = {n(fin['validation_LL'])}."])
        made.append("dev_loc_edu")
    if sequences("tab:dev_act", "Outings from the workplace and return home: model development.",
                 [("Outing during a work episode (binary logit)", f"{A}/a01_outing_fit.csv"), ("Outing on foot or by the mode of the work tour (binary logit)", f"{A}/a02_outing_mode_fit.csv"),
                  ("Return home between consecutive out-of-home episodes (binary logit)", f"{A}/a03_return_fit.csv")], []):
        made.append("dev_act")
    return made


def main():
    os.makedirs(OUT, exist_ok=True)
    cars(); dwelling(); zone(); region(); mode(); destinations(); extra = others()
    doc = [l for l in open(f"{HERE}/estimation_tables_final.tex").read().split("\n")]
    pre = doc[:doc.index(r"\begin{document}") + 1]
    body = [r"\begin{center}{\Large\bfseries Model development tables}\end{center}"] + [f"\\input{{dev/{t}}}" for t in
            ["dev_region", "dev_zone", "dev_dwelling", "dev_cars"] + [t for t in ["dev_work", "dev_school"] if t in extra] + ["dev_mc", "dev_dc"] + [t for t in ["dev_dc_pooled"] if t in extra] + ["dev_stop"]
            + [t for t in ["dev_loc", "dev_loc_edu", "dev_act"] if t in extra]] + [r"\end{document}"]
    open(f"{B}/model_development.tex", "w").write("\n".join(pre + body) + "\n")
    for _ in range(2):
        r = subprocess.run(["tectonic", "-X", "compile", "-k", "--keep-logs", "model_development.tex"], cwd=B, capture_output=True, text=True)
        if r.returncode: print(r.stderr[-3000:]); raise SystemExit(1)
    shutil.copy(f"{B}/model_development.pdf", HERE); print("ok")


if __name__ == "__main__":
    main()
