#!/usr/bin/env python3
"""Coefficient tables of the final models of the step-by-step work (activity, locations, school, workplace) in the layout of the
article tables (est_subtour.tex, est_return.tex, est_loc_*.tex, est_school.tex, est_jobchoice.tex), terms grouped, same labels.
Final model = rows step == "final" of <name>_coef.csv / <name>_fit.csv.  Writes <article file>_new.tex in ESTIMATION_RESULTS/tables_new.
    python3 estimation/development/tables/t_new_tables.py"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from scipy.stats import norm

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/tables_new"   # results of this step (data); CODE = this folder
SBS = os.path.dirname(HERE)
STAR_LINE = r"$^{***}$ $p<0.01$, $^{**}$ $p<0.05$, $^{*}$ $p<0.10$ (robust standard errors)."
COLS = r"Variable & Coefficient & Robust s.e. & $p$"
LOC_EST = ("Estimation: maximum likelihood on the full choice set, robust sandwich covariance, unweighted. Destinations: the survey's "
           "census tract, matched to the model zones by the area of their overlap.")


# ------------------------------------------------------------------------------------------------------------------ helpers
def f(x, d=4):
    return f"{x:,.{d}f}".replace("-", "$-$")


def g3(x):
    """three significant digits, as the article's school table"""
    d = 0 if x == 0 else max(0, 2 - int(np.floor(np.log10(abs(x)))))
    return f"{x:,.{d}f}".replace("-", "$-$")


def stars(p):
    return "$^{***}$" if p < 0.01 else "$^{**\\phantom{*}}$" if p < 0.05 else "$^{*\\phantom{**}}$" if p < 0.10 else "$^{\\phantom{***}}$"


def pval(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def coef_row(lab, b, se):
    """Variable & coefficient with stars & robust s.e. & p"""
    p = 2 * norm.sf(abs(b / se))
    return f"    {lab} & {f(b)}{stars(p)} & {se:.4f} & {pval(p)} \\\\"


def ref_row(lab, ncol=3):
    return f"    {lab} & \\multicolumn{{{ncol}}}{{c}}{{reference}} \\\\"


class Ref:
    """Reference band of a band set. bands: [(parameter or None, band label)] in natural order. Shown when any member of the set is
    in the model; the label names every band without a parameter in the model, so a band merged into the reference is visible."""
    def __init__(self, fmt, bands):
        self.fmt, self.bands = fmt, bands

    def present(self, idx):
        return any(p in idx for p, _ in self.bands if p)

    def label(self, idx):
        return self.fmt.format(", ".join(b for p, b in self.bands if not p or p not in idx))


def with_refs(terms, refs):
    """insert each reference band (Ref, None) before the first term of its set"""
    out = list(terms)
    for r in refs:
        mem = [p for p, _ in r.bands if p]; i = next((k for k, (v, _) in enumerate(out) if v in mem), None)
        if i is not None: out.insert(i, (r, None))
    return out


def inc3(pre, fmt, lo="inc0", hi="inc2"):
    return Ref(fmt, [(f"{pre}{lo}", "income $<$ \\$50k"), (None, "income \\$50--100k"), (f"{pre}{hi}", "income $\\geq$ \\$100k")])


def car3(pre, fmt, no="car0", short="car1"):
    return Ref(fmt, [(f"{pre}{no}", "no car"), (f"{pre}{short}", "cars $<$ drivers"), (None, "cars $\\geq$ drivers")])


def age3(pre, fmt):
    return Ref(fmt, [(f"{pre}kid", "person $<$ 18"), (None, "person 18--64"), (f"{pre}senior", "person 65+")])


def tod4(pre, fmt, word=""):
    return Ref(fmt, [(f"{pre}am", f"{word}AM 6--9"), (None, f"{word}midday 9--15"), (f"{pre}pm", f"{word}PM 15--19"), (f"{pre}ev", f"{word}evening 19--6")])


def inc4(fmt, key):
    """reference band of the four SILO income groups; key(g) gives the parameter of group g (g1, g3, g4)"""
    return Ref(fmt, [(key("g1"), "income $<$\\$40k"), (None, "income \\$40--75k"), (key("g3"), "income \\$75--125k"), (key("g4"), "income \\$125k+")])


AREA_REF = Ref("{}", [("bc", "Baltimore City"), (None, "rest of Maryland"), ("dcz", "Washington DC"), ("va", "Virginia"),
                      ("othst", "Delaware, Pennsylvania, West Virginia")])


def std_refs(pre, ix, word=""):
    """reference bands of the income, car, age and time-of-day interaction sets of the location models"""
    fm = f"{ix} $\\times$ {{}}"
    return [inc3(pre, fm), car3(pre, fm), age3(pre, fm), tod4(pre, fm, word)]


def n_from_bic(r):
    return int(round(np.exp((r.BIC + 2 * r.LL) / r.K)))


def load(path, name):
    """final-model coefficients and fit row; falls back to the last kept step if the coef file has no 'final' rows"""
    fit = pd.read_csv(f"{path}/{name}_fit.csv"); coef = pd.read_csv(f"{path}/{name}_coef.csv")
    fr = fit[fit.step == "final"]
    if fr.empty: return None, None
    fr = fr.iloc[0]; c = coef[coef.step == "final"]
    if c.empty:
        kept = fit[fit.decision.isin(["kept", "chosen", "base", "dropped: sign reversed, not significant"])]
        st = kept.step.iloc[-1]; c = coef[coef.step == st]; print(f"{name}: no 'final' coefficient rows, using step {st}")
    c = c.drop_duplicates("param", keep="last").set_index("param")
    if "se" not in c or c.se.isna().any(): c["se"] = c.coef / c.t
    assert len(c) == int(fr.K), (name, len(c), fr.K)
    return c, fr


def select(c, groups, name):
    """keep the groups / terms present in the final model; every parameter exactly once"""
    out, seen = [], []
    for g, terms in groups:
        t = [(v, lab) for v, lab in terms if (v.present(c.index) if isinstance(v, Ref) else v in c.index)]
        if any(not isinstance(v, Ref) for v, _ in t): out.append((g, t)); seen += [v for v, _ in t if not isinstance(v, Ref)]
    assert len(seen) == len(set(seen)), (name, "duplicate")
    assert set(seen) == set(c.index), (name, "unlabelled", set(c.index) - set(seen))
    return out


def longtable(caption, label, c, groups, foot, name):
    groups = select(c, groups, name); rows = []; n = 0
    for g, terms in groups:
        rows.append(f"    \\multicolumn{{4}}{{@{{}}l}}{{\\emph{{{g}}}}} \\\\")
        for v, lab in terms:
            if isinstance(v, Ref): rows.append(ref_row(v.label(c.index))); continue
            rows.append(coef_row(lab, c.coef[v], c.se[v])); n += 1
    assert n == len(c)
    return wrap(caption, label, rows, foot)


def wrap(caption, label, rows, foot, ncol=4, colspec=r"@{}L{0.55\linewidth}rrr@{}", cols=COLS):
    """longtable around the body rows; foot lines as full-width notes, star line last"""
    head = rf"""{{\footnotesize\setlength{{\tabcolsep}}{{4pt}}\nolinenumbers
\begin{{longtable}}{{{colspec}}}
  \caption{{{caption}}}
  \label{{{label}}}\\
  \toprule
  {cols} \\
  \midrule
  \endfirsthead
  \multicolumn{{{ncol}}}{{@{{}}l@{{}}}}{{\footnotesize Table~\thetable\ (continued)}}\\[2pt]
  \toprule
  {cols} \\
  \midrule
  \endhead
  \midrule
  \multicolumn{{{ncol}}}{{@{{}}r@{{}}}}{{\emph{{continued on the next page}}}} \\
  \endfoot
  \bottomrule
  \endlastfoot
"""
    tail = [r"    \midrule"] + [f"    \\multicolumn{{{ncol}}}{{@{{}}L{{0.98\\linewidth}}}}{{{x}}} \\\\" for x in foot + [STAR_LINE]] + \
           [r"\end{longtable}", r"\linenumbers}"]
    return head + "\n".join(rows) + "\n" + "\n".join(tail) + "\n"


def fitline(r, nval, unit):
    return (f"LL($\\hat\\beta$) = {f(r.LL, 1)}; BIC = {f(r.BIC, 1)}. Validation half ({nval:,} {unit}): LL = {f(r.validation_LL, 1)}.")


def write(fn, parts):
    open(f"{HERE}/{fn}", "w").write("\n".join(parts)); print("wrote", fn)


# ------------------------------------------------------------------------------------------------------------------ activity
HH = [("inc_low", "Household income below \\$50k"), ("inc_high", "Household income \\$100k or more"),
      ("car0", "No car in the household"), ("carshort", "Fewer cars than drivers in the household"),
      ("kids", "Child under 16 in the household")]
HH = with_refs(HH, [Ref("Household income {}", [("inc_low", "below \\$50k"), (None, "\\$50--100k"), ("inc_high", "\\$100k or more")]),
                    Ref("Cars in the household: {}", [("car0", "none"), ("carshort", "fewer than drivers"), (None, "at least as many as drivers")])])
PERSON = with_refs([("age_u30", "Age under 30"), ("age_55p", "Age 55 or over"), ("age10", "Age (per 10 years)"), ("female", "Female"),
                    ("lic", "Driving licence")], [Ref("Age {}", [("age_u30", "under 30"), (None, "30--54"), ("age_55p", "55 or over")])])
A01 = [("Constant", [("const", "Constant")]),
       ("Work episode", [("sp_0_4", "Work duration, 0--4\\,h (per h)"), ("sp_4_7", "Work duration, 4--7\\,h (per h)"),
                         ("sp_7_inf", "Work duration above 7\\,h (per h)"), ("dur_h", "Work duration (h)"), ("lndur", "ln work duration (h)"),
                         ("sw", "Secondary work episode (arrival from 15:00)")]),
       ("Time of day", with_refs([("arr_early", "Arrival at work before 7:00"), ("arr_late", "Arrival at work from 10:00")],
                                 [Ref("Arrival at work {}", [("arr_early", "before 7:00"), (None, "7:00--10:00"), ("arr_late", "from 10:00")])])),
       ("Workplace and commute", [("cbd_w", "Workplace zone with at least 10,000 jobs per km$^2$"),
                                  ("lnacc2", "ln(1 + retail and other jobs within 2\\,km of the workplace)"),
                                  ("lncomm", "ln(1 + home--workplace distance, km)"), ("km_comm", "Home--workplace distance (km)")]),
       ("Person", PERSON), ("Household", HH)]
A02 = [("Constant", [("const", "Constant (walk)")]),
       ("Outing", with_refs([("lnkm", "ln(1 + distance workplace--first stop, km)"), ("km", "Distance workplace--first stop (km)"),
                             ("tm_cd", "Arrived at work by car, as driver"), ("tm_cp", "Arrived at work by car, as passenger"),
                             ("multi", "More than one stop on the outing"), ("midday", "Departure from the workplace 11:00--14:00")],
                            [Ref("Arrived at work by {}", [("tm_cd", "car, as driver"), ("tm_cp", "car, as passenger"), (None, "other modes")])])),
       ("Workplace zone", [("cbd_w", "Workplace zone with at least 10,000 jobs per km$^2$"),
                           ("lnretden_w", "ln(1 + retail jobs per km$^2$) of the workplace zone")]),
       ("Person", PERSON), ("Household", HH)]
EP = {"work": "work", "school": "school", "acc": "accompanying", "shop": "shopping", "joint": "joint"}
A03 = [("Constant", [("const", "Constant")]),
       ("Detour and distance", [("detour_km", "Detour via home (km)"), ("lndetour", "ln(1 + detour via home, km)"),
                                ("dhome_km", "Distance from home (km)")]),
       ("Episodes", with_refs([(f"a_{k}", f"Preceding episode: {v}") for k, v in EP.items()] + [(f"e_{k}", f"Following episode: {v}") for k, v in EP.items()],
                              [Ref(f"{w} episode: {{}}", [(f"{x}_{k}", v) for k, v in EP.items()] + [(None, "other individual discretionary")])
                               for x, w in (("a", "Preceding"), ("e", "Following"))])),
       ("Joint episodes", [("jj", "Both episodes joint"), ("jmand", "Joint episode next to a work or school episode")]),
       ("Person", with_refs([("worker", "Person type: worker"), ("stud_k12", "Person type: K--12 student"), ("stud_ps", "Person type: post-secondary student"),
                             ("retiree", "Person type: retiree"), ("toddler", "Person type: child under 5"), ("female", "Female"), ("lic", "Driving licence")],
                            [Ref("Person type: {}", [(None, "non-worker"), ("worker", "worker"), ("stud_k12", "K--12 student"), ("stud_ps", "post-secondary student"),
                                                     ("retiree", "retiree"), ("toddler", "child under 5")])])),
       ("Household", [("hhsize", "Household size (persons)")] + HH),
       ("Day pattern", with_refs([("nep3", "Three out-of-home episodes in the day"), ("nep4", "Four out-of-home episodes"),
                                  ("nep5", "Five or more out-of-home episodes"), ("nep", "Number of out-of-home episodes in the day")],
                                 [Ref("Out-of-home episodes in the day: {}", [(None, "two"), ("nep3", "three"), ("nep4", "four"), ("nep5", "five or more")])])),
       ("Time of day", with_refs([("am", "End of the preceding episode before 9:00"), ("pm", "End of the preceding episode 15--19"),
                                  ("ev", "End of the preceding episode after 19:00")],
                                 [Ref("End of the preceding episode {}", [("am", "before 9:00"), (None, "9:00--15:00"), ("pm", "15--19"), ("ev", "after 19:00")])]))]


# ------------------------------------------------------------------------------------------------------------------ locations
COMP = {"pop": "population", "ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school pupils"}
XLAB = {"inc0": "income $<$ \\$50k", "inc2": "income $\\geq$ \\$100k", "car0": "no car", "car1": "cars $<$ drivers",
        "kid": "person $<$ 18", "senior": "person 65+", "child": "household with children", "worker": "worker",
        "am": "AM 6--9", "pm": "PM 15--19", "ev": "evening 19--6"}
KN = ["0", "1", "2", "5", "10", "20", "50"]


def loc_groups(anchor="home", stop=False):
    if stop:
        dist = [(f"dt_{a}_{b}", ("detour 0--1\\,km (per km)" if a == "0" else f"detour {a}--{b}\\,km"))
                for a, b in zip(KN[:5], KN[1:6])] + [("dt_20_inf", "detour $>$ 20\\,km"), ("dt", "detour (km)"), ("lndt", "ln(1 + detour, km)"),
                                                      ("cgt", "car generalised time, detour (min)"), ("ls", "mode-choice logsum")]
        same = [("intra_a", "stop in the home zone"), ("intra_b", "stop in the workplace zone")]
        bnd = [("xcounty", "outside the counties of both anchors"), ("xstate", "outside the states of both anchors")]
        inter = [(f"lndt_{k}", f"ln(1 + detour) $\\times$ {v}") for k, v in XLAB.items()]
        inter = with_refs(inter, std_refs("lndt_", "ln(1 + detour)"))
        dh = "Detour and impedance"
    else:
        dist = [(f"d_{a}_{b}", ("distance 0--1\\,km (per km)" if a == "0" else f"distance {a}--{b}\\,km"))
                for a, b in zip(KN[:6], KN[1:])] + [("d_50_inf", "distance $>$ 50\\,km"), ("d", "distance (km)"), ("lnd", "ln(distance, km)"),
                                                     ("cgt", "car generalised time (min)"), ("ls", "mode-choice logsum")]
        same = [("intra", f"intrazonal (destination = {anchor} zone)")]
        o = "origin" if anchor == "home" else anchor
        bnd = [("xcounty", f"outside the {o} county"), ("xstate", f"outside the {o} state")]
        inter = [(f"lnd_{k}", f"ln(distance) $\\times$ {v}") for k, v in XLAB.items()]
        inter = with_refs(inter, std_refs("lnd_", "ln(distance)"))
        dh = "Distance and impedance"
    area = [("bc", "Baltimore City"), ("dcz", "Washington DC"), ("cbd", "central business district ($\\geq$ 10,000 jobs per km$^2$)"),
            ("va", "Virginia"), ("othst", "Delaware, Pennsylvania, West Virginia")]
    area = with_refs(area, [AREA_REF])
    land = [("lnretden", "ln(1 + retail jobs per km$^2$)"), ("mix", "land-use mix (entropy)")]
    size = [(f"theta_{k}", f"$\\theta$ {v} (ln weight)") for k, v in COMP.items()] + [("mu_size", "$\\mu$, ln size")]
    return [(dh, dist), ("Same zone", same), ("Area", area), ("Land use", land), ("Boundaries", bnd),
            ("Interactions with ln(distance)" if not stop else "Interactions with ln(1 + detour)", inter), ("Size", size)]


BASE = {"l01_daycare": "ret", "l02_nonstud": "stu", "l03_wahb": "off", "l04_wbhome": "ret", "l05_wbwork": "ret", "l06_outing_dest": "ret"}
LOCVAL = {"l01_daycare": 282, "l02_nonstud": 557, "l03_wahb": 427, "l04_wbhome": 1348, "l05_wbwork": 1529, "l06_outing_dest": 1155}


def size_def(name):
    return (f"Size term $\\mu\\ln(1+S_j)$, $S_j=\\sum_c \\exp(\\theta_c)\\,x_{{jc}}$, with $\\theta = 0$ for the base component "
            f"({COMP[BASE[name]]}).")


def loc_table(name, caption, label, anchor="home", stop=False, defs=""):
    c, r = load(f"{SBS}/locations", name); N = n_from_bic(r)
    foot = [f"Observations: {N:,}; alternatives: 1,588 zones (full choice set); parameters: {int(r.K)}.",
            fitline(r, LOCVAL[name], "records"), LOC_EST + " Estimation half of the Regional Travel Survey.",
            size_def(name) + " " + defs]
    return longtable(caption, label, c, loc_groups(anchor, stop), foot, name)


DIST_DEF = ("Distance: car distance from the {a} (km), piecewise linear with the slope per km in each band; ln(distance) interactions "
            "with person, household and arrival-time flags; land-use mix: entropy of the job and population shares (0--1).")


# ------------------------------------------------------------------------------------------------------------------ school
SCH = [("Size", [("mu_size", "size coefficient $\\mu$"), ("g_pub_in", "in-boundary public enrolment, log weight"),
                 ("g_priv", "private enrolment, log weight"), ("h_privXg1", "private enrolment $\\times$ income $<$\\$40k"),
                 ("h_privXg3", "private enrolment $\\times$ income \\$75--125k"), ("h_privXg4", "private enrolment $\\times$ income \\$125k+"),
                 ("g_priv4", "private 4-year enrolment, log weight"), ("h_priv4Xg1", "private 4-year enrolment $\\times$ income $<$\\$40k"),
                 ("h_priv4Xg4", "private 4-year enrolment $\\times$ income \\$125k+"), ("g_cc", "2-year enrolment, log weight"),
                 ("h_ccXa25", "2-year enrolment $\\times$ age 25+"), ("h_ccXg1", "2-year enrolment $\\times$ income $<$\\$40k"),
                 ("h_ccXg4", "2-year enrolment $\\times$ income \\$125k+")]),
       ("Car time", [("b_t", "car time (min)"), ("b_lt", "$\\ln(1+\\text{time})$"), ("b_ls", "school-tour logsum")]),
       ("Boundaries", [("b_intra", "same zone"), ("b_ccpub", "other county $\\times$ public share"), ("b_cc", "other county"),
                       ("b_cs", "other state")]),
       ("Interactions with car time", [("b_tXagec", "time $\\times$ age (centred)"), ("b_tXfemale", "time $\\times$ female"),
                                       ("b_tXg1", "time $\\times$ income $<$\\$40k"), ("b_tXg4", "time $\\times$ income \\$125k+"),
                                       ("b_tXcar0", "time $\\times$ no car"), ("b_tXcarlow", "time $\\times$ fewer cars than drivers")])]
SCH = [(g, with_refs(t, [inc4("private enrolment $\\times$ {}", lambda s: f"h_privX{s}"), inc4("private 4-year enrolment $\\times$ {}", lambda s: f"h_priv4X{s}"),
                         inc4("2-year enrolment $\\times$ {}", lambda s: f"h_ccX{s}"), inc4("time $\\times$ {}", lambda s: f"b_tX{s}"),
                         Ref("time $\\times$ {}", [("b_tXcar0", "no car"), ("b_tXcarlow", "fewer cars than drivers"), (None, "at least as many cars as drivers")])]))
       for g, t in SCH]


def wide_cells(cs, keys, v):
    """two rows per parameter for a wide table: coefficient with stars; robust s.e. in brackets and p (small)"""
    top, bot = [], []
    for k in keys:
        c = cs[k]
        if v in c.index:
            b, se = c.coef[v], c.se[v]; p = 2 * norm.sf(abs(b / se))
            top.append(f"{f(b)}{stars(p)}"); bot.append(f"{{\\scriptsize ({se:.4f}) {pval(p)}}}")
        else: top.append(""); bot.append("")
    return top, bot


BANDS = [("k8", "K--8", 1144, 1534), ("hs", "High school", 719, 667), ("college", "College", 141, 686)]


def school():
    cs, rs = {}, {}
    for b, *_ in BANDS: cs[b], rs[b] = load(f"{SBS}/locations", f"l07_school_{b}")
    allp = set().union(*[set(c.index) for c in cs.values()]); seen, rows = [], []
    for g, terms in SCH:
        t = [(v, lab) for v, lab in terms if (v.present(allp) if isinstance(v, Ref) else v in allp)]
        if not t: continue
        rows.append(f"\\multicolumn{{4}}{{@{{}}l}}{{\\emph{{{g}}}}} \\\\")
        for v, lab in t:
            if isinstance(v, Ref):
                rows.append(f"\\quad {v.label(allp)} & " + " & ".join("reference" if v.present(cs[b].index) else "" for b, *_ in BANDS) + " \\\\")
                continue
            top, bot = wide_cells(cs, [b for b, *_ in BANDS], v)
            rows += [f"\\quad {lab} & " + " & ".join(top) + " \\\\", " & " + " & ".join(bot) + " \\\\"]; seen.append(v)
    assert len(seen) == len(set(seen)) and set(seen) == allp, allp - set(seen)
    for b, *_ in BANDS: assert set(cs[b].index) <= set(seen)
    R = [rs[b] for b, *_ in BANDS]
    foot = [r"\midrule",
            "Students $N$; parameters $K$ & " + " & ".join(f"{n_from_bic(r):,}; {int(r.K)}" for r in R) + r" \\",
            "Alternatives (zones with enrolment) & " + " & ".join(f"{a:,}" for _, _, a, _ in BANDS) + r" \\",
            "Log-likelihood, full set & " + " & ".join(f(r.LL, 1) for r in R) + r" \\",
            "BIC & " + " & ".join(f(r.BIC, 1) for r in R) + r" \\",
            "Validation students & " + " & ".join(f"{v:,}" for *_, v in BANDS) + r" \\",
            "Validation log-likelihood & " + " & ".join(f(r.validation_LL, 1) for r in R) + r" \\",
            "Validation log-likelihood per student & " + " & ".join(f(r.validation_LL / v, 3) for r, (*_, v) in zip(R, BANDS)) + r" \\",
            r"\midrule",
            r"\multicolumn{4}{@{}L{0.98\linewidth}}{Choice set: all zones with enrolment of the student's band. Below each coefficient: robust s.e. in brackets and $p$. "
            r"Dependent variable: school zone of students with a school record (estimation half of the Regional Travel Survey 2017/18); "
            r"validation half on the full choice set. Empty: not in the model.} \\",
            r"\multicolumn{4}{@{}L{0.98\linewidth}}{Size term $\mu\ln S_j$ with the public enrolment of the band as reference (college: public "
            r"4-year); log weights of the other enrolment types relative to it. Car time: peak car time from the home zone (min). Public share: "
            r"share of public enrolment in the zone's enrolment of the band.} \\",
            r"\multicolumn{4}{@{}L{0.98\linewidth}}{" + STAR_LINE + r"} \\"]
    head = r"""{\footnotesize\setlength{\tabcolsep}{3pt}\nolinenumbers
\begin{longtable}{@{}L{0.37\linewidth}rrr@{}}
  \caption{School location choice: multinomial logit estimates by school band.}
  \label{tab:est_school}\\
  \toprule
  Parameter & K--8 & High school & College \\ \midrule
  \endfirsthead
  \multicolumn{4}{@{}l@{}}{\footnotesize Table~\thetable\ (continued)}\\[2pt]
  \toprule
  Parameter & K--8 & High school & College \\ \midrule
  \endhead
  \midrule
  \multicolumn{4}{@{}r@{}}{\emph{continued on the next page}} \\
  \endfoot
  \bottomrule
  \endlastfoot
"""
    write("est_school_new.tex", [head + "\n".join(rows + foot) + "\n\\end{longtable}\n\\linenumbers}\n"])


# ------------------------------------------------------------------------------------------------------------------ workplace
INC = {"g1": "income $<$\\$40k", "g3": "income \\$75--125k", "g4": "income \\$125k+"}

JT = {"OFF": "office", "IND": "industrial", "OTH": "other"}
WP = [("Size", [("mu", "size coefficient $\\mu$")] + [(f"g_{k}", f"{v} jobs, log weight") for k, v in JT.items()]
       + [(f"d_{k}_{s}", f"{v} jobs log weight $\\times$ {INC[s]}") for k, v in JT.items() for s in INC]),
      ("Car time", [("t", "time (min)"), ("lt", "$\\ln(1+\\text{time})$")]),
      ("Car time $\\times$ person", [("t*female", "time $\\times$ woman"), ("t*young", "time $\\times$ age $<30$"), ("t*old", "time $\\times$ age 55+")]
       + [(f"t*{k}", f"time $\\times$ {v}") for k, v in INC.items()]
       + [("t*lic", "time $\\times$ driving licence"), ("t*hhs", "time $\\times$ household size"), ("t*kids", "time $\\times$ children in the household"),
          ("t*w2", "time $\\times$ two or more workers"), ("t*rurh", "time $\\times$ rural home zone")]),
      ("Mode-choice logsum", [("ls", "logsum")]),
      ("Borders and the District", [("intra", "same zone"), ("cc", "other county"), ("cs", "other state"),
                                    ("cs*g4", "other state $\\times$ income \\$125k+"), ("cs*hva", "other state $\\times$ Virginia home"),
                                    ("dcw", "DC workplace, home outside DC")]),
      ("Accessibility of the workplace", [("accw", "non-work accessibility (logsum) of the workplace zone")]),
      ("Workplace regions", [("reg_bc", "Baltimore City"), ("reg_mopg", "Montgomery and Prince George's"),
                                                       ("reg_dcr", "District of Columbia"), ("reg_nvc", "Arlington and Alexandria"),
                                                       ("reg_nvo", "other Northern Virginia"), ("reg_mdo", "rest of Maryland"), ("reg_oth", "other states")]),
      ("Job mix $\\times$ person", [("z_off_sh*g1", "office share $\\times$ income $<$\\$40k"), ("z_off_sh*g4", "office share $\\times$ income \\$125k+"),
                                    ("z_ret_sh*young", "retail share $\\times$ age $<30$"), ("z_ind_sh*female", "industrial share $\\times$ woman")]),
      ("Wage proxy", [("z_hiearn", "high-wage share")] + [(f"z_hiearn*{k}", f"high-wage share $\\times$ {v}") for k, v in INC.items()])]


WP = [(g, with_refs(t, [inc4(f"{v} jobs log weight $\\times$ {{}}", lambda s, k=k: f"d_{k}_{s}") for k, v in JT.items()]
                     + [inc4("time $\\times$ {}", lambda s: f"t*{s}"), inc4("office share $\\times$ {}", lambda s: f"z_off_sh*{s}"),
                        inc4("high-wage share $\\times$ {}", lambda s: f"z_hiearn*{s}"),
                        Ref("time $\\times$ age {}", [("t*young", "$<30$"), (None, "30--54"), ("t*old", "55+")]),
                        Ref("{}", [(None, "Baltimore suburbs"), ("reg_bc", "Baltimore City"), ("reg_mopg", "Montgomery and Prince George's"),
                                   ("reg_nvc", "Arlington and Alexandria"), ("reg_nvo", "other Northern Virginia"),
                                   ("reg_mdo", "rest of Maryland"), ("reg_oth", "other states")])]))
      for g, t in WP]


def workplace():
    if not os.path.exists(f"{SBS}/workplace/w04_fit.csv"): print("workplace: no w04_fit.csv yet"); return False
    c, r = load(f"{SBS}/workplace", "w04")
    if c is None: print("workplace: no final row yet"); return False
    cen = [v for v in c.index if v.endswith("_c")]; c = c.rename(index=lambda v: v[:-2] if v.endswith("_c") else v)
    N = n_from_bic(r)
    foot = [f"Observations: {N:,} workers; alternatives: chosen zone + 99 zones sampled uniformly from the 1,587 zones with jobs "
            f"(no correction needed); parameters: {int(r.K)}.",
            f"LL($\\hat\\beta$) = {f(r.LL, 1)}; BIC = {f(r.BIC, 1)}. Validation half (9,749 workers, all 1,587 zones): LL = {f(r.validation_LL, 1)}"
            + (f" ({f(r.validation_LL_per_worker, 4)} per worker)." if "validation_LL_per_worker" in r and pd.notna(r.validation_LL_per_worker) else "."),
            "Estimation: maximum likelihood with analytic gradient; robust (sandwich) standard errors. Dependent variable: zone of the usual "
            "workplace of workers with a fixed workplace outside their home (estimation half of the Regional Travel Survey 2017/18).",
            "Size term $\\mu\\ln S_j$, $S_j$ = retail jobs + $\\sum_c \\exp(g_c)$ jobs of type $c$ (office, industrial, other); income groups: "
            "reference \\$40--75k. Car time: peak car time home--workplace (min). Shares: job shares of the workplace zone; high-wage share: share of "
            "high-earning jobs."
            + (" Person variables in the time interactions are centred at their estimation-half means, so the time coefficient is the effect for the mean worker." if cen else "")
            + (" Washington DC workplaces: area effect in the DC workplace term (home outside DC)." if "dcw" in c.index and "reg_dcr" not in c.index else "")]
    at = [v for v in c.index if v.startswith(("g_", "d_")) and abs(abs(c.coef[v]) - 10) < 1e-6]
    if at: foot[-1] += " Log-weight shifts are bounded to $[-10, 10]$; " + ", ".join(dict(WP[0][1])[v] for v in at) + " at the bound."
    write("est_jobchoice_new.tex", [longtable("Workplace choice: multinomial logit over the zones with jobs.", "tab:est_jobchoice", c, WP, foot, "w04")])
    return True


def loc_edu_pooled():
    """pooled school episodes of non-students + daycare (other_locations/lp_pooled.py edu): one column per purpose, shared terms span both"""
    C = pd.read_csv(f"{SBS}/locations/lp_edu_coef.csv"); c = C[C.step == "final"]; F = pd.read_csv(f"{SBS}/locations/lp_edu_fit.csv")
    r = F[F.step == "final"].iloc[0]; sep = F[F.step == "separate_total"].iloc[0]
    P = [("l02_nonstud", "Non-student school"), ("l01_daycare", "Daycare")]
    val = {(x.purpose, x.param): (x.coef, x.se) for x in c.itertuples()}; idx = set(c.param)
    def cell(b, se):
        pv = 2 * norm.sf(abs(b / se)); return f"{f(b)}{stars(pv)}", f"{{\\scriptsize ({se:.4f}) {pval(pv)}}}"
    rows, used = [], set()
    for g, terms in loc_groups("home"):
        body = []
        for v, lab in terms:
            if isinstance(v, Ref):
                if v.present(idx): body.append(f"    {v.label(idx)} & \\multicolumn{{2}}{{c}}{{reference}} \\\\")
                continue
            if v == "mu_size":
                body.append(f"    {lab} & \\multicolumn{{2}}{{c}}{{1 (bound, both purposes)}} \\\\"); continue
            if ("N+D", v) in val:
                a, b = cell(*val[("N+D", v)]); used.add(v)
                body += [f"    {lab} & \\multicolumn{{2}}{{c}}{{{a} (shared)}} \\\\", f"     & \\multicolumn{{2}}{{c}}{{{b}}} \\\\"]; continue
            cs = [cell(*val[(k, v)]) if (k, v) in val else ("--", "") for k, _ in P]
            if all(a == "--" for a, _ in cs): continue
            used.add(v); body += [f"    {lab} & " + " & ".join(a for a, _ in cs) + " \\\\", "     & " + " & ".join(b for _, b in cs) + " \\\\"]
        if body: rows += [f"    \\multicolumn{{3}}{{@{{}}l}}{{\\emph{{{g}}}}} \\\\"] + body
    assert idx - {"scale"} <= used, ("unlabelled", idx - used)
    b, se = val[("l01_daycare", "scale")]; t1 = (b - 1) / se; pv = 2 * norm.sf(abs(t1))
    rows += ["    \\multicolumn{3}{@{}l}{\\emph{Scale}} \\\\", f"    scale ($p$ against 1) & 1 (normalised) & {f(b)}{stars(pv)} \\\\",
             f"     &  & {{\\scriptsize ({se:.4f}) {pval(pv)}}} \\\\"]
    foot = [f"Observations (estimation half): non-student school {int(r.N_l02_nonstud):,}, daycare {int(r.N_l01_daycare):,} episodes; alternatives: "
            f"1,588 zones (full choice set); parameters: {int(r.K)} (separate models of the two purposes: {int(sep.K)}). "
            f"LL($\\hat\\beta$) = {f(r.LL, 1)}; BIC = {f(r.BIC, 1)}.",
            f"Validation half, LL: non-student school {f(r.validation_LL_l02_nonstud, 1)} ({int(r.Nv_l02_nonstud):,} records), daycare "
            f"{f(r.validation_LL_l01_daycare, 1)} ({int(r.Nv_l01_daycare):,} records); separate models together: {f(sep.validation_LL, 1)}.",
            "Utility of zone $j$ for purpose $p$: $U_{pj} = \\mu_p V_{pj}$, $\\mu = 1$ for non-student school; a coefficient marked "
            "\\emph{shared} takes the same value in $V_p$ of both purposes. --: not in the model of this purpose.",
            LOC_EST + " Estimation half of the Regional Travel Survey.",
            "Size term $\\mu\\ln(1+S_j)$, $S_j=\\sum_c \\exp(\\theta_c)\\,x_{jc}$, with $\\theta = 0$ for the base component (school pupils for "
            "non-student school, retail jobs for daycare). Distance: car distance from home (km); land-use mix: entropy of the job and "
            "population shares (0--1).",
            "Coefficient with stars; below it the robust standard error in brackets and $p$. " + STAR_LINE.split(" (")[0] + "."]
    return wrap("Location choice: school episodes of persons without a school record and daycare or pre-school episodes of children "
                "under 5, pooled model with purpose-specific scale (from home; multinomial logit over 1,588 zones).", "tab:est_loc_edu", rows, foot,
                ncol=3, colspec=r"@{}L{0.46\linewidth}cc@{}", cols="Variable & Non-student school & Daycare")


# ------------------------------------------------------------------------------------------------------------------ main
def main():
    A = f"{SBS}/activity"
    c1, r1 = load(A, "a01_outing"); c2, r2 = load(A, "a02_outing_mode"); c3, r3 = load(A, "a03_return")
    t1 = longtable("Outings from the workplace: binary logit of at least one outing during a work episode at the usual workplace (estimation half).",
                   "tab:est_subtour_gen", c1, A01,
                   [f"Observations: {n_from_bic(r1):,} work episodes at the usual workplace; alternatives: 2; parameters: {int(r1.K)}.",
                    fitline(r1, 8561, "episodes"),
                    "Estimation: Biogeme, robust standard errors. An outing is a work episode at the usual workplace followed by one or more "
                    "discretionary episodes and a return to the workplace.",
                    "Work duration: piecewise linear in hours with bends at 4\\,h and 7\\,h; secondary work episode: arrival at work from 15:00."], "a01")
    t6 = loc_table("l06_outing_dest", "Outings from the workplace: destination of the first stop (multinomial logit over 1,588 zones; estimation half).",
                   "tab:est_subtour_dest", anchor="workplace",
                   defs="Same form and estimator as the other location models with the usual workplace as the anchor: distance from the workplace (km), "
                        "piecewise linear with the slope per km in each band.")
    t2 = longtable("Outings from the workplace: binary logit of walking against keeping the mode of the work tour (estimation half).",
                   "tab:est_subtour_mode", c2, A02,
                   [f"Observations: {n_from_bic(r2):,} outings; alternatives: walk or the mode of the work tour; parameters: {int(r2.K)}.",
                    fitline(r2, 1153, "outings"),
                    "Estimation: Biogeme, robust standard errors. If the outing does not walk, its legs keep the mode of the work tour (the car "
                    "stays at the workplace for a walking outing).",
                    "Mode of the work tour: reference other modes; distance: car distance between the workplace and the first stop."], "a02")
    write("est_subtour_new.tex", [t1, t6, t2])
    write("est_return_new.tex", [longtable("Return-home logit between consecutive out-of-home episodes (estimation half of the Regional Travel Survey).",
                                           "tab:est_return", c3, A03,
                                           [f"Observations: {n_from_bic(r3):,} pairs of consecutive out-of-home episodes; alternatives: 2; parameters: {int(r3.K)}.",
                                            fitline(r3, 28327, "pairs"),
                                            "Estimation: maximum likelihood (robust sandwich covariance). $y = 1$ if the person returned home between two "
                                            "consecutive out-of-home episodes; pairs inside an outing from the workplace and pairs of two work episodes are excluded.",
                                            "Income bands: household income."], "a03")])
    dd = DIST_DEF.format(a="home")
    write("est_loc_edu_new.tex", [loc_edu_pooled()])
    write("est_loc_daycare_new.tex", [loc_table("l01_daycare", "Location choice: Daycare and pre-school episodes of children under 5 (from home) (multinomial logit over 1,588 zones).",
                                                "tab:est_loc_daycare", defs="Distance: car distance from home (km); land-use mix: entropy of the job and population shares (0--1).")])
    write("est_loc_nonstud_new.tex", [loc_table("l02_nonstud", "Location choice: School episodes of persons without a school record (from home) (multinomial logit over 1,588 zones).",
                                                "tab:est_loc_nonstud", defs="Distance: car distance from home (km); land-use mix: entropy of the job and population shares (0--1).")])
    write("est_loc_wahb_new.tex", [loc_table("l03_wahb", "Location choice: Work trips of at-home workers (from home) (multinomial logit over 1,588 zones).",
                                             "tab:est_loc_wahb", defs="Distance: car distance from home (km).")])
    write("est_loc_wbhome_new.tex", [loc_table("l04_wbhome", "Location choice: Work business of other persons (from home) (multinomial logit over 1,588 zones).",
                                               "tab:est_loc_wbhome", defs=dd)])
    write("est_loc_wbwork_new.tex", [loc_table("l05_wbwork", "Location choice: Work business of a worker with a usual workplace (anchors: home and workplace) (multinomial logit over 1,588 zones).",
                                               "tab:est_loc_wbwork", stop=True,
                                               defs="Detour: $d(h,j) + d(j,w) - d(h,w)$ by car between home $h$ and the usual workplace $w$ (km), piecewise "
                                                    "linear with the slope per km in each band; interactions with household and arrival-time flags; land-use mix: "
                                                    "entropy of the job and population shares (0--1); logsum: mode-choice logsum of the stop.")])
    school()
    workplace()


if __name__ == "__main__":
    main()
