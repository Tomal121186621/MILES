#!/usr/bin/env python3
"""(TAZ variant, 2026-10-28: coefficients of coef_tasha_taz/dest_choice_mnl.csv; merged distance pieces via dc_taz_engine;
results/java_utility_check_{os.environ.get('TAZ_COEF', 'coef_tasha_taz')}.csv.)  Check that MAST's Java utilities of the new location segments equal the estimation utilities (dc_model.utility).
    python3 check_java_utilities.py DEBUG_CSV HALF   (DEBUG_CSV: dest.mnl.debug.file of a survey-population run with
    dest.mnl.debug.segments = the new segments) -> results/java_utility_check_{os.environ.get('TAZ_COEF', 'coef_tasha_taz')}.csv"""
import sys, numpy as np, pandas as pd, torch
import te_common as T, dc_common as C, dc_model as M, prep_dc_data as PD
import dc_taz_engine  # noqa: F401  (merged distance pieces in dc_model.features)
f, half = sys.argv[1], sys.argv[2]
d = pd.read_csv(f, header=None, names=["seg", "pid", "za", "zb", "start", "mode", "inbound", "tp", "zj", "V"])
import os; coef = pd.read_csv(f"{C.A3}/{os.environ.get('TAZ_COEF', 'coef_tasha_taz')}/dest_choice_mnl.csv"); sk = C.skims(); m = C.id2idx(); z = C.zones()
pm = pd.read_csv(f"{C.A3}/survey_pop/{half}/persons_map.csv").set_index("id"); P = PD.people(half)
rows = []
d["mode"] = d["mode"].fillna("").astype(str); d["tp"] = d.tp.fillna("").astype(str)
for (seg, pid, za, zb, st, md, inb, tp), g in d.groupby(["seg", "pid", "za", "zb", "start", "mode", "inbound", "tp"], sort=False):
    sp = pm.person_id.get(pid)
    if pd.isna(sp) or sp not in P.index: continue
    c = coef[coef.segment == seg].set_index("variable").value; stop = seg.endswith("_stop")
    sizes = [k[5:] for k in c.index if k.startswith("size_")]; base = [k for k in sizes if c[f"size_{k}"] == 1.0][0]; comps = [k for k in sizes if k != base]
    lin = [k for k in c.index if k != "mu_size" and not k.startswith("size_")]
    tour = md != ""
    rec = pd.DataFrame({"person_id": [sp], "kind": ["stop" if stop else "primary"], "tod": [PD.tod_cls(np.array([st]))[0]],
                        "mode_auto": [1.0 if (not tour or md in ("CAR_DRIVER", "CAR_PASSENGER")) else 0.0], "tour_purpose": [tp if tour else ""],
                        "position": ["in" if (tour and str(inb).lower() == "true") else ""], "multi": [0.0], "home_idx": [int(m[za])], "anchor_b": [int(m[zb]) if zb >= 0 else -1]})
    rec = PD.chooser_cols(rec, P); rec["home_idx"] = int(m[za])
    spec = M.Spec("F", lin, base, comps); best = None
    for mv in ([0.0, 1.0] if "lnd_multi" in lin else [0.0]):   # the debug line does not carry the complexity flag: both values
        rec["multi"] = mv
        theta = torch.tensor([c[k] for k in lin] + [np.log(c[f"size_{k}"]) for k in comps] + [c["mu_size"]])
        alts = np.arange(len(z))[None, :]; D = M.Data(rec, alts, np.zeros((1, len(z))), np.zeros((1, len(z))), spec, seg.split("_")[0], sk)
        Vp = M.utility(theta, spec, D).detach().numpy()[0]
        j = m[g.zj.values]; dd = np.abs(Vp[j] - g.V.values)
        if best is None or dd.max() < best.max(): best = dd
    diff = best
    rows.append(dict(segment=seg, person=pid, anchor=za, anchor_b=zb, start=st, n=len(g), max_abs_diff=float(diff.max()), max_abs_V=float(np.abs(g.V.values).max())))
r = pd.DataFrame(rows); r.to_csv(f"{T.RES}/java_utility_check_{os.environ.get('TAZ_COEF', 'coef_tasha_taz')}.csv", index=False)
print(r.groupby("segment").agg(choices=("n", "size"), max_abs_diff=("max_abs_diff", "max"), max_abs_V=("max_abs_V", "max")).to_string())
