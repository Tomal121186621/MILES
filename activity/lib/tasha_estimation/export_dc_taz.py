#!/usr/bin/env python3
"""Export of the TAZ re-specified destination models into NEW coefficient sets (2026-10-28).

    python3 activity/lib/tasha_estimation/export_dc_taz.py [taz2]  -> 3_abit/coef_tasha_taz/ (copy of coef_tasha), 3_abit/coef_tasha_cal_taz/ (copy of coef_tasha_cal)

Only the destination rows of dest_choice_mnl.csv change: the segments <PURPOSE>_primary (results/dest_choice_primary_cx_tazr.csv)
and <PURPOSE>_seq_stop (results/dest_choice_stop_seq_tazr.csv) of the four discretionary purposes are replaced.  Everything else
is the model-of-record copy, including the pooled-anchor <PURPOSE>_stop segments (used only to relocate joint stops), the
work / education location segments and the calibration files.  coef_tasha and coef_tasha_cal are not touched.  Each variable
name is checked against the parsing rules of MarylandDestinationChoice.loadMnl (an unknown name stops an ABIT run).
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import json, os, shutil, sys, hashlib
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; A3 = os.path.dirname(HERE); RES = f"{HERE}/results"
SETS = {f"{A3}/coef_tasha": f"{A3}/coef_tasha_taz", f"{A3}/coef_tasha_cal": f"{A3}/coef_tasha_cal_taz"}
SIZE = ["pop", "ret", "off", "oth", "stu"]
FLAGS = ["inc0", "inc2", "car0", "car1", "child", "kid", "senior", "worker", "am", "pm", "ev", "nonauto", "worktour", "inbound", "multi"]
ZVARS = ["bc", "dcz", "va", "othst", "cbd", "lnretden", "mix"]
OTHER = {"ctime", "cgt", "ls", "intra", "intra_a", "intra_b", "xcounty", "xstate", "ptav_car0", "ptav"}


def parses(seg, v):
    """the rules of MarylandDestinationChoice.loadMnl (lines 421-453)."""
    stop = seg.split("_")[-1].lower() == "stop"; pre = "dt" if stop else "d"
    if v == "mu_size": return True
    if v.startswith("size_"): return v[5:] in SIZE
    if v.startswith(pre + "_") and v[len(pre) + 1].isdigit():
        p = v.split("_"); float(p[1]); p[2] == "inf" or float(p[2]); return len(p) == 3
    if v in (pre, "lndt" if stop else "lnd"): return True
    if v.startswith(("lndt" if stop else "lnd") + "_"): return v[v.index("_") + 1:] in FLAGS
    return v in OTHER or v in ZVARS


def main(suffix="tazr", sets=SETS):
    new = pd.concat([pd.read_csv(f"{RES}/dest_choice_primary_cx_{suffix}.csv"), pd.read_csv(f"{RES}/dest_choice_stop_seq_{suffix}.csv")], ignore_index=True)
    bad = [(s, v) for s, v in zip(new.segment, new.variable) if not parses(s, v)]
    if bad: raise SystemExit(f"names ABIT would not parse: {bad}")
    for src, dst in sets.items():
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        f = f"{dst}/dest_choice_mnl.csv"; m = pd.read_csv(f)
        out = pd.concat([m[~m.segment.isin(new.segment.unique())], new], ignore_index=True); out.to_csv(f, index=False)
        assert all(parses(s, v) for s, v in zip(out.segment, out.variable))
        st = dict(source=src, replaced_segments=sorted(new.segment.unique()), rows_before=len(m), rows_after=len(out),
                  sha_primary=hashlib.sha256(open(f"{RES}/dest_choice_primary_cx_{suffix}.csv", "rb").read()).hexdigest(),
                  sha_stop=hashlib.sha256(open(f"{RES}/dest_choice_stop_seq_{suffix}.csv", "rb").read()).hexdigest(),
                  note=f"TAZ locations (prep_dc_taz.py); rows: results/*_{suffix}.csv (taz: re-estimate with the record specification; tazr: collinearity re-specification); other files = copy of the source set")
        json.dump(st, open(f"{dst}/TAZ_STATE.json", "w"), indent=1)
        print(dst, st["rows_before"], "->", st["rows_after"], "rows;", ", ".join(st["replaced_segments"]))


if __name__ == "__main__":
    # python3 activity/lib/tasha_estimation/export_dc_taz.py            -> coef_tasha_taz, coef_tasha_cal_taz (re-specified rows, *_tazr)
    # python3 activity/lib/tasha_estimation/export_dc_taz.py taz2       -> coef_tasha_taz2 (behavioural only; TAZ re-estimate with the specification of record, *_taz)
    if len(sys.argv) > 1 and sys.argv[1] == "taz2": main("taz", {f"{A3}/coef_tasha": f"{A3}/coef_tasha_taz2"})
    else: main()
