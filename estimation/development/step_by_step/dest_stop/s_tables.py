#!/usr/bin/env python3
"""Coefficient tables of the final stop-location models (s_shop, s_rec, s_acc, s_oth) in the layout of the article tables
est_stop_<P>_stop.tex (same \\label, grouped rows, article wording).  Helpers of ../tables_new/t_new_tables.py (imported).
Writes est_stop_<P>_stop_new.tex and the compile check check.tex in this folder.
    python3 s_tables.py"""
import os, sys
sys.dont_write_bytecode = True
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tables_new"))
import t_new_tables as T     # noqa: E402

PUR = {"s_shop": ("SHOPPING", "shopping"), "s_rec": ("RECREATION", "recreation"), "s_acc": ("ACCOMPANY", "accompanying"), "s_oth": ("OTHER", "other")}
KN = ["0", "1", "2", "5", "10", "20"]
XL = {"inc0": "income $<$ \\$50k", "inc2": "income $\\geq$ \\$100k", "car0": "no car", "car1": "cars $<$ drivers",
      "kid": "person $<$ 18", "senior": "person 65+", "male": "male", "hhsize": "household size (persons)", "child": "household with children",
      "worker": "worker", "nonauto": "tour mode not car", "worktour": "work or school tour", "inbound": "inbound stop",
      "am": "arrival AM 6--9", "pm": "arrival PM 15--19", "ev": "arrival evening 19--6"}
GROUPS = [
    ("Detour and impedance", [(f"dt_{a}_{b}", "detour 0--1\\,km (per km)" if a == "0" else f"detour {a}--{b}\\,km") for a, b in zip(KN[:5], KN[1:])]
     + [("dt_20_inf", "detour $>$ 20\\,km"), ("dt", "detour (km)"), ("lndt", "ln(1 + detour, km)"),
        ("ls", "mode-choice logsum, detour"), ("cgt", "car generalised time, detour (min)"),
        ("ptav_car0", "transit available from the previous location $\\times$ no car")]),
    ("Anchor zones", [("intra_a", "stop in the zone of the previous location"), ("intra_b", "stop in the zone of the next anchor")]),
    ("Area", T.with_refs([("bc", "Baltimore City"), ("dcz", "Washington DC"), ("cbd", "central business district"), ("va", "Virginia"),
                          ("othst", "Delaware, Pennsylvania, West Virginia")], [T.AREA_REF])),
    ("Land use", [("lnretden", "ln(1 + retail jobs per km$^2$)"), ("mix", "land-use mix (entropy)")]),
    ("Boundaries", [("xcounty", "outside the counties of both anchors"), ("xstate", "outside the states of both anchors")]),
    ("Interactions with ln(1 + detour)", T.with_refs([(f"lndt_{k}", f"ln(1 + detour) $\\times$ {v}") for k, v in XL.items()],
                                                    T.std_refs("lndt_", "ln(1 + detour)", "arrival "))),
    ("Size", [(f"theta_{k}", f"$\\theta$ {v} (ln weight)") for k, v in T.COMP.items()] + [("mu_size", "$\\mu$, ln size")])]
EST = ("Estimation: maximum likelihood on the full choice set, robust sandwich covariance, unweighted; estimation half of the Regional "
       "Travel Survey. Locations: the survey's traffic zones, spread over the model zones by housing units (home ends) or jobs (activity ends); "
       "the likelihood is averaged over the possible zones of the destination and of the anchors (location mixture).")


def table(name):
    P, word = PUR[name]
    c, r = T.load(HERE, name); n = pd.read_csv(f"{HERE}/{name}_n.csv").iloc[0]
    fit = pd.read_csv(f"{HERE}/{name}_fit.csv"); fin = fit[fit.step == "final"].iloc[0]
    sb = SIZEBASE[name]
    foot = [f"Observations: {int(n.N_estimation):,}; alternatives: 1,588 zones (full choice set); parameters: {int(fin.K)}.",
            T.fitline(fin, int(n.N_validation), "records"), EST,
            f"Size term $\\mu\\ln(1+S_j)$, $S_j=\\sum_c \\exp(\\theta_c)\\,x_{{jc}}$, with $\\theta = 0$ for the base component ({T.COMP[sb]}). "
            "Dependent variable: chosen zone of the stop. Detour: $d(a,j) + d(j,b) - d(a,b)$ by car (km) between the origin $a$ of the trip to "
            "the stop and the next anchor $b$ of the tour (the primary destination for an outbound stop, home for an inbound stop), piecewise "
            "linear with the slope per km in each band; interactions with person, household, tour and arrival-time flags; land-use mix: entropy "
            "of the job and population shares (0--1); logsum: mode-choice logsum of the detour; transit available: bus door-to-door time "
            "below 120 min."]
    return T.longtable(f"Stop location, {word} (multinomial logit over 1,588 zones, sequential anchors).", f"tab:est_stop_{P}_stop",
                       c, GROUPS, foot, name)


SIZEBASE = {}


def main():
    files = []
    for name, (P, _) in PUR.items():
        if not os.path.exists(f"{HERE}/{name}_fit.csv"): print("missing", name); continue
        log = open(f"{HERE}/{name}.log").read().split("final specification:")[-1]
        SIZEBASE[name] = log.split("size base ")[1].split(",")[0].strip()
        fn = f"est_stop_{P}_stop_new.tex"; open(f"{HERE}/{fn}", "w").write(table(name)); files.append(fn); print("wrote", fn)
    pre = open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "final_tables", "estimation_tables_abit.tex")).read()
    pre = pre[:pre.index("\\begin{document}")]
    open(f"{HERE}/check.tex", "w").write(pre + "\\begin{document}\n" + "\n".join(f"\\input{{{f[:-4]}}}" for f in files) + "\n\\end{document}\n")


if __name__ == "__main__":
    main()
