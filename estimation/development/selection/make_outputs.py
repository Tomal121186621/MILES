#!/usr/bin/env python3
"""Article-format tables and engine coefficient files of the DAYMAP re-specification (2026-11-06).

    python3 estimation/development/selection/make_outputs.py      -> side_experiments/respec_2026-11/article_tables/est_dc_*_primary.tex, est_stop_*_stop.tex, est_loc_*.tex, est_subtour.tex,
                                    est_return.tex, est_mc_*.tex;  side_experiments/respec_2026-11/abit/*/..._respec.csv;  side_experiments/respec_2026-11/abit/summary_*.csv
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle
import numpy as np
import pandas as pd
from scipy.stats import norm
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/side_experiments/respec_2026-11/abit"   # results of the selection (data); CODE = this folder
V = f"{WORKSPACE}"; OUT = f"{os.path.dirname(HERE)}/article_tables"; A3 = f"{V}/3_abit"; EST = f"{V}/5_reports/article/sections/est"
os.makedirs(OUT, exist_ok=True)
DISC = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
PNAME = {"SHOPPING": "shopping", "RECREATION": "recreation", "ACCOMPANY": "accompanying", "OTHER": "other errands"}
STARS = "$^{***}$ $p<0.01$, $^{**}$ $p<0.05$, $^{*}$ $p<0.10$ (robust $t$)."


def m(x, d):
    s = f"{x:,.{d}f}"; return s.replace("-", "$-$", 1) if s.startswith("-") else s


def star(t):
    if not np.isfinite(t): return "$^{\\phantom{***}}$"
    a = abs(t); s = "***" if a >= norm.ppf(0.995) else "**" if a >= norm.ppf(0.975) else "*" if a >= norm.ppf(0.95) else ""
    return f"$^{{{s}}}$" if s == "***" else (f"$^{{{s}\\phantom{{{'*' * (3 - len(s))}}}}}$" if s else "$^{\\phantom{***}}$")


def pval(t):
    if not np.isfinite(t): return "--"
    p = 2 * norm.sf(abs(t)); return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def row(label, v, se, t):
    if not np.isfinite(se): return f"    {label} & {m(v, 4)}$^{{\\phantom{{***}}}}$ & -- & -- & -- \\\\"
    return f"    {label} & {m(v, 4)}{star(t)} & {se:.4f} & {m(t, 2)} & {pval(t)} \\\\"


HEAD = """{{\\footnotesize\\setlength{{\\tabcolsep}}{{4pt}}\\nolinenumbers
\\begin{{longtable}}{{@{{}}L{{{w}\\linewidth}}rrrr@{{}}}}
  \\caption{{{cap}}}
  \\label{{{lab}}}\\\\
  \\toprule
  Variable & Coefficient & Robust s.e. & Robust $t$ & $p$ \\\\
  \\midrule
  \\endfirsthead
  \\multicolumn{{5}}{{@{{}}l@{{}}}}{{\\footnotesize Table~\\thetable\\ (continued)}}\\\\[2pt]
  \\toprule
  Variable & Coefficient & Robust s.e. & Robust $t$ & $p$ \\\\
  \\midrule
  \\endhead
  \\midrule
  \\multicolumn{{5}}{{@{{}}r@{{}}}}{{\\emph{{continued on the next page}}}} \\\\
  \\endfoot
  \\bottomrule
  \\endlastfoot
"""
TAIL = "\\end{longtable}\n\\linenumbers}\n"


def note(x, p=False): return f"    \\multicolumn{{5}}{{@{{}}{'p' if p else 'L'}{{0.98\\linewidth}}}}{{{x}}} \\\\"


def sub(x): return f"    \\multicolumn{{5}}{{@{{}}l}}{{\\emph{{{x}}}}} \\\\"


# ================================================================================================ location models
FLAG = {"inc0": "income $<$ \\$50k", "inc2": "income $\\geq$ \\$100k", "car0": "no car", "car1": "cars $<$ drivers", "multi": "tour with at least one stop",
        "nonauto": "tour mode not car", "inbound": "inbound stop", "worker": "worker", "child": "household with children", "kid": "person $<$ 18",
        "senior": "person 65+", "worktour": "work or school tour", "am": "AM 6--9", "pm": "PM 15--19", "ev": "evening 19--6"}
FLAG_ORDER = ["inc0", "inc2", "car0", "car1", "multi", "nonauto", "inbound", "worker", "child", "kid", "senior", "worktour", "am", "pm", "ev"]
SIZE = {"pop": "residents", "ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school enrolment", "leis": "leisure jobs", "hlth": "health-care jobs"}
LOC_ORDER = (["d_0_1", "d_1_2", "d_2_5", "d_5_10", "d_10_20", "d_20_inf", "d_50_inf", "dt_0_1", "dt_1_2", "dt_2_5", "dt_5_10", "dt_10_20", "dt_20_inf", "cgt", "ls",
              "mu_size"] + [f"theta_{c}" for c in SIZE] + ["mix", "lnretden", "cbd", "rail", "lnstopden", "intra", "intra_a", "intra_b", "xcounty", "xstate", "bc", "dcz", "va", "othst"]
             + [f"lnd_{f}" for f in FLAG_ORDER] + [f"lndt_{f}" for f in FLAG_ORDER] + ["ptav_car0"])
LOC_BLOCK = lambda p: (2 if p.startswith(("d_", "dt_")) or p in ("cgt", "ls") else 3 if p == "mu_size" or p.startswith("theta_") else 4 if p in ("mix", "lnretden", "cbd", "rail", "lnstopden")
                       else 5 if p in ("intra", "intra_a", "intra_b", "xcounty", "xstate", "bc", "dcz", "va", "othst") else 6 if p.startswith(("lnd_", "lndt_")) else 7)
LOC_BLOCK_NAME = {2: "Impedance", 3: "Size term", 4: "Zone attributes", 5: "Boundaries and areas", 6: "Person and household $\\times$ impedance",
                  7: "Person and household $\\times$ zone attributes"}


def loc_label(p, stop):
    if p.startswith(("d_", "dt_")):
        _, lo, hi = p.split("_"); w = "detour" if stop else "distance"
        if p == "d_50_inf": return "distance $>$ 50\\,km (change of slope)"
        if hi == "inf": return f"{w} $>$ {lo}\\,km"
        return f"{w} {lo}--{hi}\\,km" + (" (per km)" if lo == "0" else "")
    if p == "cgt": return "car generalised time, detour (min)" if stop else "car generalised time (min)"
    if p == "ls": return "mode-choice logsum, detour" if stop else "mode-choice logsum"
    if p == "mu_size": return "$\\mu$, ln size"
    if p.startswith("theta_"): return f"$\\theta$ {SIZE[p[6:]]} (ln weight)"
    L = {"mix": "land-use mix (entropy)", "lnretden": "ln(1 + retail jobs per km$^2$)", "cbd": "central business district", "rail": "rail stop in the zone",
         "lnstopden": "ln(1 + transit stops per km$^2$)", "intra": "intrazonal (destination = anchor zone)", "intra_a": "in the zone of the previous location",
         "intra_b": "in the zone of the next anchor", "bc": "Baltimore City", "dcz": "Washington DC", "va": "Virginia", "othst": "Delaware, Pennsylvania, West Virginia",
         "ptav_car0": "no car $\\times$ transit path to the zone"}
    if p == "xcounty": return "outside the counties of both anchors" if stop else "outside the county of the anchor"
    if p == "xstate": return "outside the states of both anchors" if stop else "outside the state of the anchor"
    if p in L: return L[p]
    if p.startswith("lndt_"): return f"ln(1 + detour) $\\times$ {FLAG[p[5:]]}"
    if p.startswith("lnd_"): return f"ln(distance) $\\times$ {FLAG[p[4:]]}"
    return p


LOC_FILE = {**{f"{p}_primary": f"est_dc_{p}_primary" for p in DISC}, **{f"{p}_stop": f"est_stop_{p}_stop" for p in DISC},
            "WORK_wbwork": "est_loc_wbwork", "WORK_wbhome": "est_loc_wbhome", "WORK_wahb": "est_loc_wahb", "EDUCATION_nonstud": "est_loc_nonstud",
            "EDUCATION_daycare": "est_loc_daycare", "OTHER_wbs": "est_subtour"}
LOC_CAP = {"WORK_wbwork": "Work business of a worker with a usual workplace (anchors: home and workplace)", "WORK_wbhome": "Work business of other persons (from home)",
           "WORK_wahb": "Work trips of persons who usually work at home (from home)", "EDUCATION_nonstud": "School episodes of persons without a school record (from home)",
           "EDUCATION_daycare": "Daycare and pre-school episodes of children under 5 (from home)"}


def loc_final(seg):
    d = "destinations" if seg.split("_")[1] in ("primary", "stop") and seg.split("_")[0] in DISC else "other_locations"
    return pickle.load(open(f"{HERE}/{d}/work/final_{seg}.pkl", "rb"))


def base_drops(o):
    return [r["candidate"] for r in o["log"] if str(r.get("decision", "")).startswith("base term dropped")], \
           [r["candidate"] for r in o["log"] if str(r.get("decision", "")).startswith("base size component")]


def loc_table(seg):
    o = loc_final(seg); stop = seg.endswith("_stop") or seg == "WORK_wbwork"; t = o["table"].set_index("param")
    names = sorted(o["names"], key=lambda p: LOC_ORDER.index(p) if p in LOC_ORDER else 999)
    lines = []; blk = None
    for p in names:
        b = LOC_BLOCK(p)
        if b != blk: lines.append(sub(LOC_BLOCK_NAME[b])); blk = b
        r = t.loc[p]; lines.append(row(loc_label(p, stop), r.value, r.rob_se, r.rob_t))
    N, K, L, L0 = o["N"], o["K"], o["LL"], o["LL0"]
    mu = t.loc["mu_size"]; tmu = (mu.value - 1) / mu.rob_se
    h = o["holdout"]; c = o["current_holdout"]
    dropped, zero = base_drops(o)
    base_comp = o["spec"].base
    stat = [f"Observations: {N:,}; alternatives: 1,588 zones (full choice set); parameters: {K}.",
            f"LL(0) = {m(L0, 1)}; LL($\\hat\\beta$) = {m(L, 1)}; $\\rho^2$ = {1 - L / L0:.3f}; adjusted $\\rho^2$ = {1 - (L - K) / L0:.3f}; AIC = {m(2 * K - 2 * L, 1)}; BIC = {m(np.log(N) * K - 2 * L, 1)}."]
    ho = f"Hold-out half ({o['N_val']:,} records): LL = {m(h['LL_sum'], 1)} ({m(h['LL_obs'], 4)} per record); distance distribution KS = {h['KS']:.3f}; mean distance {h['km_pred']:.1f} against {h['km_obs']:.1f}\\,km observed."
    if c is not None:
        ho += f" Model it replaces, same records: LL = {m(c['LL_sum'], 1)} ({m(c['LL_obs'], 4)} per record), KS = {c['KS']:.3f}."
    stat.append(ho)
    spec = ("Specification: the base common to all location models (distance pieces and car generalised time; size term; land-use mix; same zone, county and state"
            " boundaries; ln distance by income and car ownership" + ("; tour context" if seg.split("_")[0] in DISC else "") + ") and the candidates that passed the"
            " selection rule (expected sign, robust $|t| \\geq 1.96$, lower BIC and higher hold-out log-likelihood).")
    if dropped: spec += " Base terms removed because the sign is opposite to the expected one with $|t| > 2$: " + "; ".join(loc_label(x, stop) for x in dropped) + "."
    if zero: spec += " Size components with an estimated weight of 0 (lower bound), removed: " + ", ".join(SIZE[x] for x in zero) + "."
    est = ("Estimation: maximum likelihood on the full choice set, PyTorch implementation, robust sandwich covariance, unweighted."
           + (" Locations: the survey's traffic zones, spread over the model zones by housing units (home ends) or jobs (activity ends); the likelihood is averaged over the possible zones of the destination and of the anchors (location mixture)."
              if seg.split("_")[0] in DISC and not seg.endswith("wbs") else " Destinations: the survey's census tract, matched to the model zones by the area of their overlap.")
           + f" Size term $\\mu\\ln(1+S_j)$ with the size weights $\\exp(\\theta)$ relative to the base component; $\\mu=1$ is {'rejected' if abs(tmu) > 1.96 else 'not rejected'} (Wald $t$ = {m(tmu, 2)}).")
    if seg.endswith("primary") and seg.split("_")[0] in DISC: dep = "Destinations located by the survey's traffic zones. Dependent variable: chosen zone of the main episode of a tour (estimation half of the Regional Travel Survey)."
    elif seg.endswith("stop"): dep = "Destinations located by the survey's traffic zones. Dependent variable: chosen zone of the stop; the impedance is the detour between the origin of the trip to the stop and the next anchor."
    elif seg == "OTHER_wbs": dep = "Same form and estimator as the main-activity models with the usual workplace as the anchor. Further stops of an outing use the stop model between the previous stop and the workplace."
    else: dep = "Estimation half of the Regional Travel Survey."
    var = f"Variables: defined in Table~\\ref{{tab:loc_vars}}{', with the usual workplace in place of home' if seg == 'OTHER_wbs' else ''}; base component of the size term: {SIZE[base_comp]}."
    foot = [note(x) for x in stat + [spec, est]] + [note(dep, True), note(var), note(STARS)]
    if seg.split("_")[0] in DISC and not seg.endswith("wbs"):
        cap = (f"Discretionary primary destination, {PNAME[seg.split('_')[0]]} (multinomial logit over 1,588 zones)." if seg.endswith("primary")
               else f"Stop location, {PNAME[seg.split('_')[0]]} (multinomial logit over 1,588 zones, sequential anchors).")
        lab = f"tab:est_dc_{seg}" if seg.endswith("primary") else f"tab:est_stop_{seg}"; w = "0.5" if seg.endswith("primary") else "0.48"
    elif seg == "OTHER_wbs":
        cap = "Outings from the workplace: destination of the first stop (multinomial logit over 1,588 zones; estimation half)."; lab = "tab:est_subtour_dest"; w = "0.48"
    else:
        cap = f"Location choice: {LOC_CAP[seg]} (multinomial logit over 1,588 zones)."; lab = f"tab:{LOC_FILE[seg].replace('est_loc_', 'est_loc_')}"; w = "0.48"
    return HEAD.format(w=w, cap=cap, lab=lab) + "\n" + "\n".join(lines) + "\n    \\midrule\n" + "\n".join(foot) + "\n" + TAIL


# ================================================================================================ tour formation
TOUR_LABEL = {"const": "Constant", "lncomm": "ln(1 + home--workplace distance, km)", "sp_0_4": "Work duration, 0--4\\,h (per h)", "sp_4_7": "Work duration, 4--7\\,h (per h)",
              "sp_7_inf": "Work duration above 7\\,h (per h)", "arr_early": "Arrival at work before 7:00", "arr_late": "Arrival at work at 10:00 or later",
              "sw": "Secondary work episode (arrival from 15:00)", "cbd_w": "Workplace zone with at least 10,000 jobs per km$^2$", "lnacc2": "ln(1 + retail and other jobs within 2\\,km of the workplace)",
              "lnretden_w": "Workplace zone: ln(1 + retail jobs per km$^2$)", "mix_w": "Workplace zone: land-use mix (entropy)", "rail_w": "Workplace zone: rail stop",
              "lnstopden_w": "Workplace zone: ln(1 + transit stops per km$^2$)", "lnkm": "ln(1 + distance workplace--first stop, km)", "tm_cd": "Arrived at work by car, as driver",
              "tm_cp": "Arrived at work by car, as passenger", "age_u30": "Age under 30", "age_55p": "Age 55 or over", "female": "Female", "inc_low": "Household income $<$ \\$50k",
              "inc_high": "Household income $\\geq$ \\$100k", "car0": "No car in the household", "carshort": "Fewer cars than licensed drivers", "kids": "Child under 16 in the household",
              "detour_km": "Detour via home (km)", "lndetour": "ln(1 + detour via home, km)", "dhome_km": "Distance from home (km)", "a_work": "Preceding episode: work",
              "a_school": "Preceding episode: school", "a_acc": "Preceding episode: accompanying", "a_shop": "Preceding episode: shopping", "a_joint": "Preceding episode: joint",
              "e_work": "Following episode: work", "e_school": "Following episode: school", "e_acc": "Following episode: accompanying", "e_shop": "Following episode: shopping",
              "e_joint": "Following episode: joint", "jj": "Both episodes joint", "jmand": "Joint episode next to a work or school episode", "nep3": "Three out-of-home episodes in the day",
              "nep4": "Four out-of-home episodes", "nep5": "Five or more out-of-home episodes", "am": "End of the preceding episode before 9:00", "pm": "End of the preceding episode 15--19",
              "ev": "End of the preceding episode after 19:00", "worker": "Person type: worker", "stud_k12": "Person type: K--12 student", "stud_ps": "Person type: post-secondary student",
              "retiree": "Person type: retiree", "toddler": "Person type: child under 5", "core_h": "Home zone core city", "rural_h": "Home zone rural"}
TOUR_BLOCK = lambda p: (1 if p == "const" else 2 if p in ("lncomm", "lnkm", "detour_km", "lndetour", "dhome_km") else
                        7 if p in ("age_u30", "age_55p", "female", "inc_low", "inc_high", "car0", "carshort", "kids", "worker", "stud_k12", "stud_ps", "retiree", "toddler") else 4)
TOUR_BLOCK_NAME = {1: "Constant", 2: "Impedance", 4: "Attributes of the episode and place", 7: "Person and household"}
TOUR_CAP = {"gen": ("Outings from the workplace: binary logit of at least one outing during a work episode at the usual workplace (estimation half).", "tab:est_subtour_gen"),
            "mode": ("Outings from the workplace: binary logit of walking against keeping the mode of the work tour (estimation half).", "tab:est_subtour_mode"),
            "rh": ("Return-home logit between consecutive out-of-home episodes (estimation half of the Regional Travel Survey).", "tab:est_return")}
TOUR_OBS = {"gen": "work episodes at the usual workplace", "mode": "outings", "rh": "pairs of consecutive out-of-home episodes"}


def tour_table(model):
    o = pickle.load(open(f"{HERE}/tour_formation/work/final_{model}.pkl", "rb")); t = o["table"].set_index("variable")
    names = sorted(o["cols"], key=lambda p: (TOUR_BLOCK(p), o["cols"].index(p)))
    lines = []; blk = None
    for p in names:
        b = TOUR_BLOCK(p)
        if b != blk: lines.append(sub(TOUR_BLOCK_NAME[b])); blk = b
        r = t.loc[p]; lines.append(row(TOUR_LABEL.get(p, p), r.value, r.rob_se, r.rob_t))
    N, K, L, Lc, L0 = o["N"], o["K"], o["LL"], o["LLc"], o["LL0"]
    dropped = [r["candidate"] for r in o["log"] if str(r.get("decision", "")).startswith("base term dropped")]
    st = [f"Observations: {N:,} {TOUR_OBS[model]}; alternatives: 2; parameters: {K}.",
          f"LL(0) = {m(L0, 1)}; LL(constants) = {m(Lc, 1)}; LL($\\hat\\beta$) = {m(L, 1)}; $\\rho^2$ = {1 - L / L0:.3f}; $\\rho^2$ against the constants = {1 - L / Lc:.3f}; AIC = {m(2 * K - 2 * L, 1)}; BIC = {m(np.log(N) * K - 2 * L, 1)}."
          f" Hold-out half ({o['N_val']:,}): LL = {m(o['holdout'], 1)} (model it replaces, {o['K_current']} parameters: {m(o['holdout_current'], 1)}; constant only {m(o['holdout_const'], 1)});"
          f" weighted share {o['weighted_share_val'][1]:.3f} predicted against {o['weighted_share_val'][0]:.3f} observed."]
    spec = ("Specification: a base common to the three tour-formation models (the same eight person and household terms in each) and the candidates that passed the"
            " selection rule (expected sign, robust $|t| \\geq 1.96$, lower BIC and higher hold-out log-likelihood).")
    if dropped: spec += " Base terms removed because the sign is opposite to the expected one with $|t| > 2$: " + "; ".join(TOUR_LABEL.get(x, x) for x in dropped) + "."
    est = "Estimation: maximum likelihood, robust (sandwich) standard errors, unweighted."
    if model == "gen": est += " An outing is a work episode at the usual workplace followed by one or more discretionary episodes and a return to the workplace."
    if model == "mode": est += " If the outing does not walk, its legs keep the mode of the work tour (the car stays at the workplace for a walking outing)."
    if model == "rh": est += " $y = 1$ if the person returned home between two consecutive out-of-home episodes; pairs inside an outing from the workplace are excluded."
    foot = [note(x) for x in st + [spec, est, "Variables: Table~\\ref{tab:tour_vars}.", STARS]]
    cap, lab = TOUR_CAP[model]
    return HEAD.format(w="0.48", cap=cap, lab=lab) + "\n" + "\n".join(lines) + "\n    \\midrule\n" + "\n".join(foot) + "\n" + TAIL


# ================================================================================================ mode choice
MODE = {"WK": "walk", "BK": "bicycle", "CP": "car passenger", "BUS": "bus", "TRAIN": "train", "CD": "car driver"}
MC_VAR = {"km": "Distance home--main activity (km, both ways)", "core_o": "Home zone core city", "rural_o": "Home zone rural", "core_d": "Main-activity zone core city",
          "rural_d": "Main-activity zone rural", "age": "Age (years)", "male": "Male", "lic": "Driving licence", "hhsize": "Household size", "autos": "Household cars",
          "short": "Fewer cars than licensed drivers$^{\\dagger}$", "joint": "Joint household tour$^{\\dagger}$", "acc": "Accompanying tour", "rec": "Recreation tour",
          "wash": "Home in the Washington region", "inc_hi": "Household income $\\geq$ \\$100k"}
MC_SPECIAL = {"gc": "Generalised cost (min), all motorised modes", "time": "Travel time (min): car, transit in-vehicle", "time_car": "Car travel time (min)",
              "time_pt": "Transit in-vehicle time (min)", "ovt": "Transit out-of-vehicle time (min)", "cost_inc": "Cost (\\$) / relative household income",
              "park": "Paid-parking share at the destination (car driver)", "stops_nonauto": "Stops on the tour (walk, bicycle, bus, train)",
              "lnden_nonmot": "ln density of the main-activity zone (walk, bicycle)", "mu_auto": "$\\mu$ auto", "mu_transit": "$\\mu$ transit", "mu_nonmot": "$\\mu$ non-motorised"}
MC_ORDER_VARS = ["km", "core_o", "rural_o", "core_d", "rural_d", "wash", "age", "male", "lic", "hhsize", "autos", "short", "joint", "acc", "rec", "inc_hi"]
MC_BLOCK_NAME = {1: "Constants (reference: car driver)", 2: "Impedance", 4: "Attributes of the alternatives", 5: "Areas", 7: "Person, household and tour", 8: "Nests"}
MC_CAP = {"work": "work tours", "school": "school tours", "shopping": "shopping tours", "other": "other (recreation, accompanying and other errands) tours"}


def mc_block(p):
    if p.startswith("ASC_"): return 1
    if p in ("gc", "time", "time_car", "time_pt", "ovt", "cost_inc") or p.startswith(("km_", "gc_")): return 2
    if p == "park": return 4
    if p.startswith(("core_", "rural_", "wash_")): return 5
    if p.startswith("mu_"): return 8
    return 7


def mc_key(p):
    alts = ["WK", "BK", "CP", "BUS", "TRAIN"]
    if p.startswith("ASC_"): return (1, 0, alts.index(p[4:]))
    if p in MC_SPECIAL: return (mc_block(p), list(MC_SPECIAL).index(p), 0)
    var, a = p.rsplit("_", 1)
    return (mc_block(p), 100 + MC_ORDER_VARS.index(var) if var in MC_ORDER_VARS else 999, alts.index(a) if a in alts else 9)


def mc_label(p):
    if p.startswith("ASC_"): return f"Constant: {MODE[p[4:]]}"
    if p in MC_SPECIAL: return MC_SPECIAL[p]
    var, a = p.rsplit("_", 1)
    if var == "gc": return f"Generalised cost (min), {MODE[a]}"
    return f"{MC_VAR.get(var, var)}: {MODE[a]}"


def mc_table(seg):
    o = pickle.load(open(f"{HERE}/mode_choice/work/final_{seg}.pkl", "rb")); t = o["table"].set_index("param")
    names = sorted(o["names"], key=mc_key); lines = []; blk = None
    for p in names:
        b = mc_block(p)
        if b != blk: lines.append(sub(MC_BLOCK_NAME[b])); blk = b
        r = t.loc[p]
        if p.startswith("mu_") and p in o["at_bound"]: lines.append(f"    {mc_label(p)} & 1.0000 (bound) & -- & -- & -- \\\\"); continue
        lines.append(row(mc_label(p), r.value, r.rob_se, r.rob_t))
    N, K, L, L0, Lc = o["N"], o["K"], o["LL"], o["LL0"], o["LLc"]; Ke = K - len([p for p in o["at_bound"] if p.startswith("mu_")])
    w = "Weighted pseudo-log-likelihood: " if o["weighted"] else ""
    st = [f"Observations: {N:,} tours; alternatives: 6; parameters: {Ke}{' (nest parameters at the bound of 1 not counted)' if Ke < K else ''}. {w}LL(0) = {m(L0, 1)}; LL(constants) = {m(Lc, 1)}; LL($\\hat\\beta$) = {m(L, 1)};"
          f" $\\rho^2$ = {1 - L / L0:.3f}; $\\bar\\rho^2$ = {1 - (L - Ke) / L0:.3f}; AIC = {m(2 * Ke - 2 * L, 1)}; BIC = {m(np.log(N) * Ke - 2 * L, 1)}."
          f" Hold-out half ({o['N_val']:,} tours{', its own weights' if o['weighted'] else ''}): {'weighted ' if o['weighted'] else ''}LL = {m(o['holdout'], 1)} (model it replaces, {o['K_current']} parameters: {m(o['holdout_current'], 1)})."]
    dropped = [r["candidate"] for r in o["log"] if str(r.get("decision", "")).startswith("base term dropped")]
    los = "gc" in o["names"]
    txt = ("Generalised cost $GC_m = T_m + 60\\,C_m / VOT_h$ (minutes), $VOT_h = 0.5 \\times$ household income / 2,080\\,h (USDOT guidance); round trip by period." if los else
           "Level of service: car time and transit in-vehicle time (min), transit out-of-vehicle time (walk access, egress and first wait, min), and money (\\$) divided by household income relative to \\$84,216; round trip by period.")
    txt += (" Maximum likelihood, PyTorch implementation (reproduces the Biogeme log-likelihoods of the earlier models to 0.01)."
            + (" Weighted exogenous sample maximum likelihood \\citep{ManskiLerman1977}: each tour is weighted by the ratio of the ACS 2015--2019 commute share of its mode in its home stratum to the sample share; standard errors from the sandwich $H^{-1}(\\sum_n w_n^2 g_n g_n^{\\top})H^{-1}$."
               if o["weighted"] else " No survey weights (exogenous sampling of households); robust (sandwich) standard errors.")
            + " Nests: auto (car driver, car passenger), transit (bus, train), non-motorised (walk, bicycle); $\\mu \\geq 1$ (1 = no nesting)."
            + " Specification: the base common to the four segments and the candidates that passed the selection rule (expected sign, robust $|t| \\geq 1.96$, lower BIC and higher hold-out log-likelihood)."
            + (" Base terms removed because the sign is opposite to the expected one with $|t| > 2$: " + "; ".join(mc_label(x) for x in dropped) + "." if dropped else "")
            + " $^{\\dagger}$\\,Estimation control, applied as 0 in \\abit{}, where the household stage generates joint travel and the car shortage explicitly.")
    nest = "nested logit"; cap = f"Tour mode choice, {MC_CAP[seg]} ({nest}, {'generic cost' if los else 'time, out-of-vehicle time and income-scaled cost'}, area type at both ends{', choice-based sample weights' if o['weighted'] else ''})."
    foot = [note(x) for x in st + [txt]] + [note("Dependent variable: main mode of the home-based tour (estimation half of the Regional Travel Survey).", True),
                                            note("Variables: Table~\\ref{tab:mc_vars}."), note(STARS)]
    return HEAD.format(w="0.47", cap=cap, lab=f"tab:est_mc_{seg}") + "\n" + "\n".join(lines) + "\n    \\midrule\n" + "\n".join(foot) + "\n" + TAIL


# ================================================================================================ engine files
def engine_dc():
    cur = pd.read_csv(f"{A3}/coef_tasha/dest_choice_mnl.csv"); rows = []; new_terms = set()
    known_lin = None
    for seg in [f"{p}_primary" for p in DISC] + [f"{p}_stop" for p in DISC] + ["WORK_wbwork", "WORK_wbhome", "WORK_wahb", "EDUCATION_nonstud", "EDUCATION_daycare", "OTHER_wbs"]:
        try: o = loc_final(seg)
        except FileNotFoundError: print("missing", seg); continue
        key = seg.replace("_stop", "_seq_stop") if seg.endswith("_stop") else ("WORK_wbwork_stop" if seg == "WORK_wbwork" else seg)
        v = dict(zip(o["names"], o["x"])); sp = o["spec"]
        rows.append(dict(segment=key, variable="mu_size", value=v["mu_size"])); rows.append(dict(segment=key, variable=f"size_{sp.base}", value=1.0))
        for c in sp.comps:
            rows.append(dict(segment=key, variable=f"size_{c}", value=float(np.exp(v[f"theta_{c}"]))))
            if c in ("leis", "hlth"): new_terms.add(f"size_{c}")
        for k in sp.lin:
            rows.append(dict(segment=key, variable=k, value=v[k]))
            if k in ("rail", "lnstopden"): new_terms.add(k)
    new = pd.DataFrame(rows)
    keep = cur[cur.segment.str.endswith("_stop") & ~cur.segment.str.endswith("_seq_stop") & ~cur.segment.eq("WORK_wbwork_stop")]   # non-sequential stop models: not re-specified, copied
    out = pd.concat([new, keep], ignore_index=True)
    out.to_csv(f"{HERE}/destinations/dest_choice_mnl_respec.csv", index=False)
    return sorted(new_terms)


def engine_tour():
    cur = pd.read_csv(f"{A3}/coef_tasha/tasha/tasha_subtour.csv")
    g = pickle.load(open(f"{HERE}/tour_formation/work/final_gen.pkl", "rb")); mo = pickle.load(open(f"{HERE}/tour_formation/work/final_mode.pkl", "rb"))
    rest = cur[~cur.key.str.startswith(("gen.", "mode."))]
    rows = [dict(key=f"gen.{c}", value=v) for c, v in zip(g["cols"], g["table"].value)] + [dict(key=f"mode.{c}", value=v) for c, v in zip(mo["cols"], mo["table"].value)]
    pd.concat([pd.DataFrame(rows), rest], ignore_index=True).to_csv(f"{HERE}/tour_formation/tasha_subtour_respec.csv", index=False)
    r = pickle.load(open(f"{HERE}/tour_formation/work/final_rh.pkl", "rb"))
    pd.DataFrame(dict(variable=r["cols"], value=r["table"].value.values)).to_csv(f"{HERE}/tour_formation/tasha_return_home_respec.csv", index=False)
    java_rh = {"const", "sl_0_05", "sl_05_1", "sl_1_2", "sl_2_4", "sl_4_inf", "lnslack", "detour_km", "lndetour", "dhome_km", "a_work", "a_school", "a_acc", "a_shop", "a_joint",
               "e_work", "e_school", "e_acc", "e_shop", "e_joint", "worker", "stud_k12", "stud_ps", "retiree", "toddler", "nep3", "nep4", "nep5", "am", "pm", "ev", "jj", "jmand"}
    java_gen = {"const", "sp_0_4", "sp_4_7", "sp_7_inf", "arr_early", "arr_late", "sw", "age_u30", "age_55p", "female", "inc_low", "inc_high", "car0", "carshort", "kids", "cbd_w", "lnretden_w", "lncomm", "lnacc2"}
    java_mode = {"const", "lnkm", "cbd_w", "lnretden_w", "tm_cd", "tm_cp"}
    return dict(rh=[c for c in r["cols"] if c not in java_rh], gen=[c for c in g["cols"] if c not in java_gen], mode=[c for c in mo["cols"] if c not in java_mode])


def engine_mc():
    rows = []; new = set()
    java = {"ASC", "gc", "km"} | {"age", "male", "lic", "hhsize", "autos", "core_o", "rural_o", "core_d", "rural_d", "joint", "short", "acc", "rec"}
    for seg in ["work", "school", "shopping", "other"]:
        o = pickle.load(open(f"{HERE}/mode_choice/work/final_{seg}.pkl", "rb"))
        for p, v in zip(o["names"], o["x"]):
            rows.append(dict(segment=seg, parameter=p, value=v))
            base = p if p in ("gc",) or p.startswith("mu_") else p.split("_")[0] if p.startswith("ASC_") else p.rsplit("_", 1)[0] if p.rsplit("_", 1)[-1] in MODE else p
            if not (p.startswith(("ASC_", "mu_", "gc", "km_")) or base in java): new.add(p)
    pd.DataFrame(rows).to_csv(f"{HERE}/mode_choice/tour_mode_choice_respec.csv", index=False)
    return sorted(new)


def main(what):
    if "loc" in what:
        files = {}
        for seg, fn in LOC_FILE.items():
            try: files.setdefault(fn, []).append(loc_table(seg))
            except FileNotFoundError: print("not yet", seg)
        for fn, parts in files.items():
            if fn == "est_subtour": continue
            open(f"{OUT}/{fn}.tex", "w").write("\n".join(parts)); print("wrote", fn)
        if "est_subtour" in files: what = what + ["subtour_dest"]; OTHER_WBS_TABLE[0] = files["est_subtour"][0]
    if "tour" in what:
        g, mo, rh = tour_table("gen"), tour_table("mode"), tour_table("rh")
        dest = OTHER_WBS_TABLE[0] or ""
        open(f"{OUT}/est_subtour.tex", "w").write(g + "\n" + dest + "\n" + mo); open(f"{OUT}/est_return.tex", "w").write(rh); print("wrote est_subtour, est_return")
    if "mc" in what:
        for s in ["work", "school", "shopping", "other"]:
            try: open(f"{OUT}/est_mc_{s}.tex", "w").write(mc_table(s)); print("wrote est_mc", s)
            except FileNotFoundError: print("not yet mc", s)
    if "engine" in what:
        print("new location terms needing the engine:", engine_dc()); print("tour terms the engine does not compute:", engine_tour()); print("mode terms the engine does not compute:", engine_mc())


OTHER_WBS_TABLE = [None]
if __name__ == "__main__":
    main(sys.argv[1:] or ["loc", "tour", "mc", "engine"])
