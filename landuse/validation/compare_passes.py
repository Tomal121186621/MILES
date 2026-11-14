#!/usr/bin/env python3
"""Out-of-sample tables before / after the stage-2 completion of 2026-10-23 (estimated residential location model with move-or-not
on the estimated utilities, job consistency and job totals, employment by age x sex, roommate households, construction kept in its
region), seed means of the five-seed runs 2016-2024:
  before = data/silo_validation_oos_mean_pass3.parquet (the 2026-10-22 runs, re-validated with the current validate_silo.py)
  after  = data/silo_validation_oos_mean.parquet
Prints Markdown tables for REPORT.md and writes data/silo_oos_before_after.csv.  Usage: compare_passes.py [before_suffix]"""
import sys
import numpy as np, pandas as pd
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"; sfx = sys.argv[1] if len(sys.argv) > 1 else "_pass3"
B = pd.read_parquet(f"{V}/data/silo_validation_oos_mean{sfx}.parquet"); A = pd.read_parquet(f"{V}/data/silo_validation_oos_mean.parquet")
for R in (A, B): R["tbl"] = R.table.str.replace(r" \[(PUMS|LODES|ACS|ACS flows)[^\]]*\]", "", regex=True); R["geo"] = R.geo.astype(str)
out = []; md = lambda g: g.geo.str.match(r"^24\d{3}$"); YRS = range(2021, 2025)
def val(R, sec, y, tbl, geo, b=None, col="model"):
    d = R[(R.section == sec) & (R.year == y) & (R.tbl == tbl) & (R.geo == geo)]
    if b is not None: d = d[d["bin"].astype(str) == str(b)]
    return d[col].mean() if len(d) else np.nan
print("### County population (24 Maryland counties), within ±2 % / ±5 % of the PEP growth path\n\n| year | before ±2 % | before ±5 % | after ±2 % | after ±5 % | after: counties outside ±2 % (ratio) |\n|---|---|---|---|---|---|")
for y in YRS:
    r = []
    for R in (B, A):
        d = R[(R.section == "A totals") & (R.year == y) & md(R)]; r += [(abs(d.ratio - 1) <= .02).sum(), (abs(d.ratio - 1) <= .05).sum()]
    bad = d[abs(d.ratio - 1) > .02].sort_values("ratio")
    print(f"| {y} | {r[0]}/24 | {r[1]}/24 | {r[2]}/24 | {r[3]}/24 | " + (", ".join(f"{g} ({x:.3f})" for g, x in zip(bad.geo, bad.ratio)) or "none") + " |")
    out.append(dict(table="county totals", year=y, before_2=r[0], before_5=r[1], after_2=r[2], after_5=r[3]))
print("\n### Composition, Maryland county × bin cells within ±5 pp of the ACS\n\n| attribute | 2021 before | 2021 after | 2024 before | 2024 after |\n|---|---|---|---|---|")
for t in A[A.section == "B composition"].tbl.unique():
    v = []
    for y in (2021, 2024):
        for R in (B, A):
            d = R[(R.section == "B composition") & (R.year == y) & (R.tbl == t) & md(R)]; v.append((d.diff_pp.abs() <= 5).mean())
    print(f"| {t} | {v[0]:.0%} | {v[1]:.0%} | {v[2]:.0%} | {v[3]:.0%} |"); out.append(dict(table="composition " + t, b2021=v[0], a2021=v[1], b2024=v[2], a2024=v[3]))
ev = [("births per woman 15-50", "births per woman 15-50"), ("deaths share of persons (engine events; observed: Maryland)", "deaths per person"),
      ("new marriages share of adults", "marriages per adult"), ("divorces share of married", "divorces per married"),
      ("persons who moved share (persons aged 1+)", "persons who moved, aged 1+")]
print("\n### Events, Maryland, model (before → after) and observed\n\n| event | " + " | ".join(str(y) for y in YRS) + " |\n|---|---|---|---|---|")
for t, lab in ev:
    cells = []
    for y in YRS:
        a = A[(A.section == "C events") & (A.year == y) & (A.table == t)]; b = B[(B.section == "C events") & (B.year == y) & (B.table == t)]
        cells.append(f"{b.model.mean():.4f} → {a.model.mean():.4f} ({a.observed.mean():.4f})"); out.append(dict(table="event " + lab, year=y, before=b.model.mean(), after=a.model.mean(), observed=a.observed.mean()))
    print(f"| {lab} | " + " | ".join(cells) + " |")
t = "persons who moved share (persons aged 1+)"
print("\n### Persons who moved within the year (aged 1+), Maryland, by year\n\n| year | before | after | ACS |\n|---|---|---|---|")
for y in range(2017, 2025):
    a = A[(A.section == "C events") & (A.year == y) & (A.table == t)]; b = B[(B.section == "C events") & (B.year == y) & (B.table == t)]
    print(f"| {y} | {b.model.mean():.1%} | {a.model.mean():.1%} | {a.observed.mean():.1%} |"); out.append(dict(table="moves by year", year=y, before=b.model.mean(), after=a.model.mean(), observed=a.observed.mean()))
for R, nm in ((B, "before"), (A, "after")):
    d = R[(R.section == "D2 construction") & R.year.between(2021, 2024) & md(R)]
    print(f"\nnew dwellings 2020-23 vs units permitted 2020-23 ({nm}): {d.model.sum():.0f} / {d.observed.sum():.0f} = {d.model.sum() / d.observed.sum():.3f}; counties within ±25 %: {((d.groupby('geo').model.sum() / d.groupby('geo')['observed'].sum()).sub(1).abs() <= .25).sum()}/24")
    out.append(dict(table="construction 2021-24 rows", which=nm, model=d.model.sum(), observed=d.observed.sum()))
SW = [("income class (2016 $)", "B composition", ["<25k", "25-50k", "50-75k", "75-100k", "100-150k", "≥150k"]), ("household size", "B composition", ["1", "2", "3", "4", "5+"]),
      ("workers per household", "B2 statewide", None)]
for t, sec, labs in SW:
    bins = list(dict.fromkeys(A[(A.tbl == t) & (A.geo == "24")]["bin"].astype(str)))
    if labs is None: labs = bins
    print(f"\n### Statewide {t}, Maryland households (model before / after / ACS)\n\n| bin | " + " | ".join(str(y) for y in (2016, 2020, 2024)) + " |\n|---|---|---|---|")
    for i, b_ in enumerate(bins):
        cells = []
        for y in (2016, 2020, 2024):
            b, a, o = val(B, sec, y, t, "24", b_), val(A, sec, y, t, "24", b_), val(A, sec, y, t, "24", b_, "observed")
            cells.append(f"{b:.1%} / {a:.1%} / {o:.1%}"); out.append(dict(table=t, bin=labs[i], year=y, before=b, after=a, observed=o))
        print(f"| {labs[i]} | " + " | ".join(cells) + " |")
t = "employed share by age and sex"; bins = list(dict.fromkeys(A[(A.tbl == t)]["bin"].astype(str)))
print(f"\n### Employed share by age and sex, Maryland (model before / after / ACS)\n\n| cell | 2020 | 2024 |\n|---|---|---|")
for b_ in bins:
    cells = []
    for y in (2020, 2024):
        b, a, o = val(B, "B2 statewide", y, t, "24", b_), val(A, "B2 statewide", y, t, "24", b_), val(A, "B2 statewide", y, t, "24", b_, "observed"); cells.append(f"{b:.1%} / {a:.1%} / {o:.1%}")
        out.append(dict(table=t, bin=b_, year=y, before=b, after=a, observed=o))
    print(f"| {b_} | " + " | ".join(cells) + " |")
for y in (2020, 2024):
    b, a, o = (val(R_, "B composition", y, "employed (16+)", "24", 1, c) for R_, c in ((B, "model"), (A, "model"), (A, "observed")))
    print(f"employed share of persons 16+, {y}: before {b:.1%}, after {a:.1%}, ACS {o:.1%}"); out.append(dict(table="employed 16+", year=y, before=b, after=a, observed=o))
ROWS = [("B2 statewide", "persons 18-34 in non-family households living with others", "24", "share", "{:.1%}"),
        ("D jobs", "vacant share of jobs vs JOLTS openings rate (Maryland)", "all regions", "share", "{:.1%}"),
        ("E commute", "share of Maryland-resident jobs in Maryland located in the home county", "24", "share", "{:.1%}"),
        ("E commute", "travel time to work, mean (model: car peak skim; ACS: JWMNP all modes)", "24", "min", "{:.1f}"),
        ("E commute", "travel time to work, median (model: car peak skim; ACS: JWMNP all modes)", "24", "min", "{:.1f}"),
        ("E commute", "share of Maryland-resident workers employed in Maryland", "24", "share", "{:.1%}"),
        ("F flows", "moving households staying in their region", "all regions", "share", "{:.1%}"),
        ("F flows", "Maryland movers moving to another state", "24", "share", "{:.1%}"),
        ("F flows", "correlation of region-to-region mover flows with the ACS flows 2016-20 (all pairs)", "all regions", "r", "{:.3f}"),
        ("F flows", "correlation of region-to-region mover flows with the ACS flows 2016-20 (between regions)", "all regions", "r", "{:.3f}")]
for R in (A, B):
    R["tbl"] = R.tbl.str.replace(r" \(model: car peak skim; ACS \d+: JWMNP all modes\)", " (model: car peak skim; ACS: JWMNP all modes)", regex=True)
print("\n### Households, jobs, commutes and mover flows by year (model before → after; observed)\n\n| quantity | " + " | ".join(str(y) for y in range(2017, 2025)) + " |\n|---|" + "---|" * 8)
for sec, t, geo, b_, f in ROWS:
    cells = []
    for y in range(2017, 2025):
        b, a, o = val(B, sec, y, t, geo, b_), val(A, sec, y, t, geo, b_), val(A, sec, y, t, geo, b_, "observed")
        cells.append(f"{f.format(b)} → {f.format(a)} ({f.format(o) if np.isfinite(o) else '–'})".replace("nan%", "–").replace("nan", "–")); out.append(dict(table=t, year=y, before=b, after=a, observed=o))
    print(f"| {t} | " + " | ".join(cells) + " |")
pd.DataFrame(out).to_csv(f"{V}/data/silo_oos_before_after.csv", index=False)
