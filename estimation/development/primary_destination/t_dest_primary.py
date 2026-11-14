#!/usr/bin/env python3
"""Coefficient tables of the final primary-destination models (d_primary.py) in the layout of the article tables
est_dc_<P>_primary.tex (same labels), terms grouped.  Final model = rows step == "final" of <name>_coef.csv / <name>_fit.csv.
Writes est_dc_<P>_primary_new.tex in ESTIMATION_RESULTS/dest_primary and compiles a check document (check.tex) with tectonic.
    python3 estimation/development/primary_destination/t_dest_primary.py"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, subprocess
sys.dont_write_bytecode = True
import pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/dest_primary"; SBS = os.path.dirname(HERE)
sys.path.insert(0, f"{os.path.dirname(CODE)}/tables")
import t_new_tables as T                  # noqa: E402  (helpers: load, longtable, n_from_bic, f)

TE_WORK = f"{WORKSPACE}/3_abit/tasha_estimation/work"
PREAMBLE = f"{os.path.dirname(SBS)}/final_tables/estimation_tables_abit.tex"
MODELS = [("d_shop", "SHOPPING", "shopping"), ("d_rec", "RECREATION", "recreation"), ("d_acc", "ACCOMPANY", "accompanying"),
          ("d_oth", "OTHER", "other errands")]
COMP = {"pop": "population", "ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school enrolment"}
XLAB = {"inc0": "income $<$ \\$50k", "inc2": "income $\\geq$ \\$100k", "car0": "no car", "car1": "cars $<$ drivers",
        "kid": "person $<$ 18", "senior": "person 65+", "child": "household with children", "worker": "worker", "male": "male",
        "hh1": "one-person household", "am": "AM 6--9", "pm": "PM 15--19", "ev": "evening 19--6", "multi": "tour with at least one stop"}
KN = ["0", "1", "2", "5", "10", "20", "50"]
EST = ("Estimation: maximum likelihood on the full choice set, robust sandwich covariance, unweighted; estimation half of the Regional "
       "Travel Survey. Locations: the survey's traffic zones, spread over the model zones by housing units (home ends) or jobs "
       "(activity ends); the likelihood is averaged over the possible zones of the destination and of home (location mixture).")
DEFS = ("Distance: car distance from home (km), piecewise linear with the slope per km in each band; ln(distance) interactions with "
        "person, household, arrival-time and tour flags; central business district: at least 10,000 jobs per km$^2$; land-use mix: "
        "entropy of the job and population shares (0--1); car generalised time: car time plus cost over the household's value of "
        "time (min); logsum: mode-choice logsum from home.")


def groups():
    dist = [(f"d_{a}_{b}", ("distance 0--1\\,km (per km)" if a == "0" else f"distance {a}--{b}\\,km")) for a, b in zip(KN[:6], KN[1:])]
    dist += [("d_50_inf", "distance $>$ 50\\,km"), ("d", "distance (km)"), ("lnd", "ln(distance, km)"),
             ("cgt", "car generalised time (min)"), ("ls", "mode-choice logsum")]
    return [("Distance and impedance", dist),
            ("Same zone", [("intra", "intrazonal (destination = home zone)")]),
            ("Area", T.with_refs([("bc", "Baltimore City"), ("dcz", "Washington DC"), ("cbd", "central business district"), ("va", "Virginia"),
                                  ("othst", "Delaware, Pennsylvania, West Virginia")], [T.AREA_REF])),
            ("Land use", [("lnretden", "ln(1 + retail jobs per km$^2$)"), ("mix", "land-use mix (entropy)")]),
            ("Boundaries", [("xcounty", "outside the origin county"), ("xstate", "outside the origin state")]),
            ("Interactions with ln(distance)", T.with_refs([(f"lnd_{k}", f"ln(distance) $\\times$ {v}") for k, v in XLAB.items()],
                                                           T.std_refs("lnd_", "ln(distance)"))),
            ("Transit", [("ptav_car0", "bus within 120\\,min of home $\\times$ no car")]),
            ("Size", [(f"theta_{k}", f"$\\theta$ {v} (ln weight)") for k, v in COMP.items()] + [("mu_size", "$\\mu$, ln size")])]


def base_of(name):
    """base component of the size term: the one component of the five without a theta in the final model's step-1 search"""
    log = open(f"{HERE}/{name}.log").read().split("\n")
    sz = [l for l in log if "final specification:" in l][0]
    return sz.split("size base ")[1].split(",")[0]


def n_val(pur):
    r = pd.read_parquet(f"{TE_WORK}/dc_rec_validation_taz.parquet", columns=["purpose", "kind"])
    return int(((r.purpose == pur) & (r.kind == "primary")).sum())


def table(name, pur, word):
    c, r = T.load(HERE, name); N = T.n_from_bic(r)
    foot = [f"Observations: {N:,}; alternatives: 1,588 zones (full choice set); parameters: {int(r.K)}.",
            T.fitline(r, n_val(pur), "records"), EST,
            f"Size term $\\mu\\ln(1+S_j)$, $S_j=\\sum_c \\exp(\\theta_c)\\,x_{{jc}}$, with $\\theta = 0$ for the base component "
            f"({COMP[base_of(name)]}). " + DEFS]
    return T.longtable(f"Discretionary primary destination, {word} (multinomial logit over 1,588 zones).",
                       f"tab:est_dc_{pur}_primary", c, groups(), foot, name)


def main():
    files = []
    for name, pur, word in MODELS:
        if not os.path.exists(f"{HERE}/{name}_fit.csv"): print("missing", name); continue
        fn = f"est_dc_{pur}_primary_new.tex"; open(f"{HERE}/{fn}", "w").write(table(name, pur, word)); files.append(fn); print("wrote", fn)
    pre = open(PREAMBLE).read().split("\\begin{document}")[0]
    open(f"{HERE}/check.tex", "w").write(pre + "\\begin{document}\n" + "\n".join(f"\\input{{{x[:-4]}}}" for x in files) + "\n\\end{document}\n")
    subprocess.run(["tectonic", "--keep-logs", "check.tex"], cwd=HERE)
    lg = open(f"{HERE}/check.log").read()
    print("errors:", lg.count("\n!"), "undefined refs:", lg.count("undefined"), "overfull:", lg.count("Overfull"))


if __name__ == "__main__":
    main()
