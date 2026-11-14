#!/usr/bin/env python3
"""Biogeme data of a full-choice-set location model: one row per record, wide float32 parquet in parts.

    python3 build_biogeme_data.py            (project Python: numpy, pandas, pyarrow, torch; after build_estimation_tables.py)

Reads the estimation tables (input/data/<estimation|holdout>/records, candidates, configurations .parquet), the zone table and
skims of 00_shared_data, and writes input/data/<estimation|holdout>/biogeme_part<NN>.parquet (+ biogeme_meta.json).
The record x zone variables are computed with the project's own functions (copies in this folder: dc_common.skims,
dc_model.impedance / features), so they are the values the estimation used (the estimation stored them in float32 too).

Layout of one row (record n; c = anchor configuration 0..C-1, k = candidate destination zone 0..K-1, j = zone 0..1587):
  rec, purpose_id, n_cfg, n_cand                     record id, purpose index (pooled models), counts
  f_<flag>                                           chooser flags (0/1; hhsize: persons)
  w_<c>                                              configuration weight (0 for padding configurations)
  za_<c>, zb_<c>, cnty_a_<c>, st_a_<c>, cnty_b_<c>, st_b_<c>   anchor zones (index) and their county FIPS / state FIPS
  cz_<k>, b_<k>                                      candidate zone index and weight b (0 for padding slots)
  cand_<attr>_<k>                                    zone attributes of candidate k (attr: bc dcz cbd va othst lnretden mix
                                                     pop ret off oth stu cnty st)
  <var>_<c>_<j>                                      record x zone variable var of configuration c for zone j
  c<var>_<c>_<k>                                     the same variable for candidate zone k
Record x zone variables (VARS): imp = impedance (primary form: car km from anchor a, intrazonal 0.5 sqrt(area); stop / detour
form: max(0, d(a,j) + d(j,b) - d(a,b))), cgt = car generalised time (min) of the same legs, ls = mode-choice logsum (if used).
"""
import os, sys, json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import dc_common as C                   # noqa: E402  (copy: zones, skims)
import dc_model as M                    # noqa: E402  (copy: impedance, features, chooser)

# ------------------------------------------------------------------------------------------------ model configuration
PURPOSES = ["WORK"]                     # purpose_id = index in this list (pooled models: one table set per purpose)
TABLES = {"WORK": ""}                   # sub-folder of input/data/<half>/ holding the purpose's tables ("" = the folder itself)
FORM = "primary"                        # "primary" or "stop"
VARS = ["imp"]                          # record x zone variables used by the model ("imp" always; "cgt", "ls" if in the model)
PART = 1000                             # records per parquet part
LS_FUNC = None                          # function(rows, alts, purpose, sk) -> ls (n x 1588), for models with the logsum
HALVES = {"estimation": "estimation", "validation": "holdout"}
ZATTR = ["bc", "dcz", "cbd", "va", "othst", "lnretden", "mix", "pop", "ret", "off", "oth", "stu"]
FLAGS = ["inc0", "inc2", "car0", "car1", "child", "kid", "senior", "worker", "am", "pm", "ev", "nonauto", "worktour", "inbound",
         "multi", "male", "hh1", "hhsize"]


def flags(rec):
    """dc_model.chooser plus the flags the estimation scripts added (male, one-person household, household size)"""
    a = M.chooser(rec); a["male"] = rec.male.values.astype(float); a["hh1"] = (rec.hhsize.values == 1).astype(float)
    a["hhsize"] = rec.hhsize.values.astype(float)
    return {k: np.asarray(a[k], float) for k in FLAGS}


def record_vars(rows, purpose, sk):
    nz = len(C.zones()); alts = np.broadcast_to(np.arange(nz), (len(rows), nz))
    out = {"imp": M.impedance(rows, alts, sk)}
    if "cgt" in VARS: out["cgt"] = M.features(rows, alts, ["cgt"], sk, purpose)["cgt"]
    if "ls" in VARS: out["ls"] = LS_FUNC(rows, alts, purpose, sk)
    return {k: np.asarray(v, np.float32) for k, v in out.items()}


def load(half, purpose):
    d = f"{HERE}/../data/{HALVES[half]}/{TABLES[purpose]}".rstrip("/")
    return (pd.read_parquet(f"{d}/records.parquet"), pd.read_parquet(f"{d}/candidates.parquet"),
            pd.read_parquet(f"{d}/configurations.parquet"))


def build(half):
    z = C.zones(); sk = C.skims(); nz = len(z); od = f"{HERE}/../data/{HALVES[half]}"
    for f in os.listdir(od):
        if f.startswith("biogeme_part"): os.remove(f"{od}/{f}")
    za = {a: z[a].values.astype(np.float32) for a in ZATTR}; za["cnty"] = z.countyfips.values.astype(np.float32); za["st"] = z.state.values.astype(np.float32)
    data = [(pi, p) + load(half, p) for pi, p in enumerate(PURPOSES)]
    Kc = max(int(cfg.groupby("rec").size().max()) for _, _, _, _, cfg in data)
    Kd = max(int(cand.groupby("rec").size().max()) for _, _, _, cand, _ in data)
    part = 0; N = 0
    for pi, p, rec, cand, cfg in data:
        for i0 in range(0, len(rec), PART):
            sub = rec.iloc[i0:i0 + PART].reset_index(drop=True); n = len(sub)
            pos = pd.Series(np.arange(n), index=sub.rec.values)
            c = cfg[cfg.rec.isin(sub.rec.values)].copy(); c["p"] = pos[c.rec.values].values
            c = c.sort_values(["p", "w"], ascending=[True, False]).reset_index(drop=True); c["k"] = c.groupby("p").cumcount()
            rows = sub.iloc[c.p.values].reset_index(drop=True).copy()
            rows["home_idx"] = c.home_idx.values.astype(int); rows["anchor_b"] = c.anchor_b.values.astype(int)
            RV = record_vars(rows, p, sk)
            slot = np.zeros((n, Kc), np.int64); have = np.zeros((n, Kc), bool)
            slot[c.p.values, c.k.values] = np.arange(len(c)); have[c.p.values, c.k.values] = True
            slot = np.where(have, slot, slot[:, :1])                                # padding configuration = copy of slot 0
            w = np.zeros((n, Kc)); w[c.p.values, c.k.values] = c.w.values
            cs = cand[cand.rec.isin(sub.rec.values)].copy(); cs["p"] = pos[cs.rec.values].values
            cs = cs.sort_values(["p", "b"], ascending=[True, False]).reset_index(drop=True); cs["k"] = cs.groupby("p").cumcount()
            cz = np.full((n, Kd), -1, np.int64); cb = np.zeros((n, Kd)); cz[cs.p.values, cs.k.values] = cs.zidx.values; cb[cs.p.values, cs.k.values] = cs.b.values
            assert (cz[:, 0] >= 0).all(), "record without a candidate zone"
            cz = np.where(cz >= 0, cz, cz[:, :1])                                   # padding candidate = slot 0 with b = 0
            cols = {"rec": sub.rec.values.astype(np.int64), "purpose_id": np.full(n, pi, np.int64),
                    "n_cfg": have.sum(1).astype(np.int64), "n_cand": (cb > 0).sum(1).astype(np.int64)}
            for k, v in flags(sub).items(): cols[f"f_{k}"] = v.astype(np.float32)
            a_idx = rows.home_idx.values; b_idx = rows.anchor_b.values
            for cc in range(Kc):
                s = slot[:, cc]; aa = a_idx[s]; bb = b_idx[s]
                cols[f"w_{cc}"] = w[:, cc]; cols[f"za_{cc}"] = aa.astype(np.float32); cols[f"zb_{cc}"] = bb.astype(np.float32)
                cols[f"cnty_a_{cc}"] = za["cnty"][aa]; cols[f"st_a_{cc}"] = za["st"][aa]
                cols[f"cnty_b_{cc}"] = np.where(bb >= 0, za["cnty"][np.maximum(bb, 0)], -1).astype(np.float32)
                cols[f"st_b_{cc}"] = np.where(bb >= 0, za["st"][np.maximum(bb, 0)], -1).astype(np.float32)
            for k in range(Kd):
                cols[f"cz_{k}"] = cz[:, k].astype(np.float32); cols[f"b_{k}"] = cb[:, k]
                for a, v in za.items(): cols[f"cand_{a}_{k}"] = v[cz[:, k]]
            for var, X in RV.items():
                for cc in range(Kc):
                    Xc = X[slot[:, cc]]
                    for k in range(Kd): cols[f"c{var}_{cc}_{k}"] = Xc[np.arange(n), cz[:, k]]
                    for j in range(nz): cols[f"{var}_{cc}_{j}"] = Xc[:, j]
            pd.DataFrame(cols).to_parquet(f"{od}/biogeme_part{part:02d}.parquet", index=False)
            part += 1; N += n
            print(f"  {half} {p}: records {i0}-{i0 + n - 1} -> part {part - 1}", flush=True)
    meta = dict(half=half, N=N, parts=part, n_cfg_max=Kc, n_cand_max=Kd, zones=nz, purposes=PURPOSES, form=FORM, vars=VARS)
    json.dump(meta, open(f"{od}/biogeme_meta.json", "w"), indent=1)
    print(half, meta, flush=True)


if __name__ == "__main__":
    for h in HALVES: build(h)
