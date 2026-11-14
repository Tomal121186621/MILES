#!/usr/bin/env python3
"""Inputs of the school-assignment step of the chain (assign_schools.py), written to 2_silo/schoolchoice/apply/:
  school_choice_coefficients.csv  segment, parameter, kind (size / size_inter / utility / fixed), term, value: the full-set estimates of
                                  work/final_<seg>.json (school_final_model.py); the fixed K-8 logsum coefficient (1) as kind 'fixed'
  school_records.csv              one row per band record of input/schools_2016.csv: id, zone, band, component (pub / priv for K-12;
                                  pub4 / priv4 / cc for post-secondary by IPEDS HD2024 SECTOR 1 / 2-3 / 4-9), ipeds_sector, enrolment
                                  (= capacity, students enrolled in the band)
  school_sabs_inboundary.csv      home zone, band, school id, a = share of the zone's housing units inside the school's SABS 2015-16
                                  attendance boundary (attendance_boundaries.py)
  school_logsum_<seg>.npy         school-tour mode-choice logsum, car availability (3) x income group (4) x zone x zone (zone-id
                                  order), the arrays of the estimation (school_logsums.py); written for the segments whose model uses it
Usage: python3 landuse/schools/write_inputs.py"""
import os, sys, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import school_common as C   # noqa: E402
AP = f"{C.SC}/apply"; os.makedirs(AP, exist_ok=True)
rows = []
for seg in C.SEG:
    fj = json.load(open(f"{C.W}/final_{seg}.json"))
    for n, v in fj["coef_fullset"].items():
        kind = "size" if n.startswith(("mu_", "g_")) else "size_inter" if n.startswith("h_") else "utility"
        term = n[2:].replace("X", "*") if kind == "utility" else n[2:].replace("X", ":") if kind == "size_inter" else n
        rows.append(dict(segment=seg, parameter=n, kind=kind, term=term, value=v))
    for k, v in fj.get("fixed", {}).items(): rows.append(dict(segment=seg, parameter=f"b_{k}", kind="fixed", term=k, value=v))
pd.DataFrame(rows).to_csv(f"{AP}/school_choice_coefficients.csv", index=False)
sp = pd.read_parquet(f"{C.W}/school_points.parquet")
sp.rename(columns={"comp": "component", "capacity": "enrolment"})[["id", "zone", "band", "component", "ipeds_sector", "enrolment"]].to_csv(f"{AP}/school_records.csv", index=False)
pd.read_parquet(f"{C.W}/sabs_home_school.parquet")[["zone", "band", "school_id", "a"]].to_csv(f"{AP}/school_sabs_inboundary.csv", index=False)
L = np.load(f"{C.W}/logsum.npy", mmap_mode="r")
for seg in C.SEG:
    if any(r["term"].startswith("ls") for r in rows if r["segment"] == seg): np.save(f"{AP}/school_logsum_{seg}.npy", np.asarray(L[C.SEG.index(seg)]))
print(pd.DataFrame(rows).to_string(index=False)); print(os.listdir(AP))
