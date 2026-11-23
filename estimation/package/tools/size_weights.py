#!/usr/bin/env python3
"""Size weights of the DAYMAP destination models (2026-11-16): model/size_weights.csv and a "## Size weights" section in
model/README.md of every folder with THETA parameters.
S_j = base_j + sum_k exp(THETA_k) x_kj: THETA < 0 means one unit of component k attracts less than one unit of the base, not
a negative effect (exp(THETA) > 0 always). The p-value of THETA tests exp(THETA) = 1 (same weight as the base), not "no effect".
Share of S: the component's contribution to the size term summed over all 1,588 zones (2016 zone data of the estimation).
Obsolete for folders 01-10 since 2026-11-17: their models have one attraction variable, beta ln(1 + x), and no THETA; folders
whose reference_estimates.csv has no THETA rows are skipped (no size_weights.csv, README not touched).
Usage: python3 tools/size_weights.py   (from manual_estimation/)"""
import os, re, sys
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "ABIT")
sys.path.insert(0, os.path.join(A, "03_stop_recreation", "input", "code"))
import dc_common as C

NAME = {"pop": "population", "ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school pupils"}
KEYS = [("population", "pop"), ("retail", "ret"), ("office", "off"), ("other_jobs", "oth"), ("school", "stu")]
# folder: base component per purpose (key "" when the model has one purpose)
BASE = {"01_primary_destination_pooled": {"SHOPPING": "ret", "RECREATION": "ret", "ACCOMPANY": "ret", "OTHER": "ret"},
        "03_stop_recreation": {"": "ret"}, "04_stop_accompanying": {"": "stu"}, "05_stop_other": {"": "ret"},
        "06_outing_first_stop_destination": {"": "ret"}, "07_work_business_usual_workplace": {"": "ret"},
        "08_work_business_other_persons": {"": "ret"}, "09_work_trips_home_workers": {"": "off"},
        "10_school_daycare_without_record_pooled": {"nonstudent_school": "stu", "daycare": "ret"}}
PURPOSE_LABEL = {"SHOPPING": "shopping", "RECREATION": "recreation", "ACCOMPANY": "accompanying", "OTHER": "other",
                 "nonstudent_school": "non-student school", "daycare": "daycare"}


def comp(p):
    return next(k for s, k in KEYS if s in p.lower())


def purpose(p, bases):
    if list(bases) == [""]: return ""
    return next(g for g in bases if (p.endswith("_" + g) if g.isupper() else f"_{g}_" in p))


def table(folder, T):
    r = pd.read_csv(os.path.join(A, folder, "model", "reference_estimates.csv"))
    r = r[r.parameter.str.startswith("THETA")]; rows = []
    for g, b in BASE[folder].items():
        d = r[[purpose(p, BASE[folder]) == g for p in r.parameter]]
        th = {comp(p): (p, x.coefficient, x.robust_se, x.p_value) for p, (_, x) in zip(d.parameter, d.iterrows())}
        part = {b: T[b]}; part.update({k: np.exp(v[1]) * T[k] for k, v in th.items()}); tot = sum(part.values())
        rows.append(dict(purpose=PURPOSE_LABEL.get(g, ""), component=NAME[b] + " (base)", parameter="", theta=0.0, robust_se=np.nan,
                         p_theta_eq_0=np.nan, weight=1.0, weight_lo95=np.nan, weight_hi95=np.nan, units_per_base_unit=1.0,
                         share_of_size_pct=100 * part[b] / tot))
        for k, (p, t, se, pv) in th.items():
            rows.append(dict(purpose=PURPOSE_LABEL.get(g, ""), component=NAME[k], parameter=p, theta=t, robust_se=se, p_theta_eq_0=pv,
                             weight=np.exp(t), weight_lo95=np.exp(t - 1.96 * se), weight_hi95=np.exp(t + 1.96 * se),
                             units_per_base_unit=np.exp(-t), share_of_size_pct=100 * part[k] / tot))
    return pd.DataFrame(rows)


def fmt_w(w):
    return f"{w:.4f}" if w < 0.01 else f"{w:.3f}" if w < 10 else f"{w:.1f}"


def section(D):
    multi = D.purpose.ne("").any()
    s = ["## Size weights", "",
         "S_j = base_j + Σ_k exp(THETA_k) x_kj. exp(THETA) is always positive, so every component adds to the attraction of a zone; "
         "THETA < 0 only means that one unit of the component (one resident, one office job) attracts less than one unit of the base. "
         "The p-value of THETA tests exp(THETA) = 1 (the same weight per unit as the base), not whether the component matters. "
         "Share of S: contribution of each component to the size term summed over all 1,588 zones (2016 zone data of the estimation). "
         "Values in `size_weights.csv`.", "",
         ("| Purpose " if multi else "") + "| Component | THETA | exp(THETA) (95 % CI) | Units per base unit | Share of S (%) |",
         ("|---" if multi else "") + "|---|---|---|---|---|"]
    for _, x in D.iterrows():
        if np.isnan(x.robust_se): th, w, u = "0 (base)", "1", "1"
        else:
            th = f"{x.theta:.3f} (p {x.p_theta_eq_0:.3g})"
            w = f"{fmt_w(x.weight)} ({fmt_w(x.weight_lo95)}–{fmt_w(x.weight_hi95)})"
            u = f"{x.units_per_base_unit:,.1f}" if x.units_per_base_unit >= 0.1 else f"{x.units_per_base_unit:.3f}"
        s.append((f"| {x.purpose} " if multi else "") + f"| {x.component} | {th} | {w} | {u} | {x.share_of_size_pct:.1f} |")
    return "\n".join(s) + "\n"


def main():
    z = C.zones(); T = {k: float(z[k].sum()) for k in NAME}
    for folder in BASE:
        m = os.path.join(A, folder, "model")
        if not pd.read_csv(os.path.join(m, "reference_estimates.csv")).parameter.str.startswith("THETA").any():
            print(f"{folder}: no THETA, skipped"); continue
        D = table(folder, T)
        D.to_csv(os.path.join(m, "size_weights.csv"), index=False, float_format="%.6g")
        f = os.path.join(m, "README.md"); txt = open(f).read()
        txt = re.sub(r"\n## Size weights\n.*?(?=\n## |\Z)", "", txt, flags=re.S).rstrip("\n") + "\n\n" + section(D)
        open(f, "w").write(txt); print(f"{folder}: {len(D)} rows")


if __name__ == "__main__": main()
