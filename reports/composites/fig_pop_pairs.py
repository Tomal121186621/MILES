#!/usr/bin/env python3
"""Generative quality of the CVAE on the held-out PUMS test split, every attribute and every pair of attributes.
Regenerates the validation population of population/cvae/steps/07_validate.py (150,000 households from the training split only,
seed 1, EMA weights of the 'full' run) and scores it against the test split with the SRMSE of population/cvae/vaelib/validate.py.
Pairs are formed at the person level (household attributes attached to every member), so household x person pairs are included;
household x household pairs use households.  Reference: the training split against the same test split (two samples of one population).
Outputs: WORKSPACE/data/pop_pairs_srmse.csv, WORKSPACE/5_reports/article/figures/fig_val_pop_quality.{pdf,png}:
  SRMSE of every pair of attributes: below the diagonal the synthetic population, above it the training split, both against the test split
  (single-attribute errors are in the CSV; the article shows the single attributes against the ACS in fig_val_stage1)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import sys, json, itertools, numpy as np, pandas as pd
V = f"{WORKSPACE}"; VAE = f"{VAE_HOME}"   # generator data (outputs/); the generator code is population/cvae
sys.path.insert(0, f"{MILES_HOME}/population/cvae"); sys.path.insert(0, f"{MILES_HOME}/reports")
import torch
from vaelib import config, crosswalks, validate as VV
from vaelib.model import CVAE, CVAEConfig
from vaelib.zones import ZoneSampler
from vaelib.generate import generate_population
import paperstyle as ps
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

PRE = f"{VAE}/outputs/01_preprocessed"; TR = f"{VAE}/outputs/03_training/full"
hh = pd.read_parquet(f"{PRE}/hh.parquet").reset_index(drop=True); pp = pd.read_parquet(f"{PRE}/pp.parquet")
p2i = json.load(open(f"{VAE}/outputs/02_targets/puma_to_idx.json")); sp = np.load(f"{TR}/split_idx.npz")
train_hh, test_hh = hh.loc[sp["train"]], hh.loc[sp["test"]]
train_pp, test_pp = pp[pp.SERIALNO.isin(set(train_hh.SERIALNO))], pp[pp.SERIALNO.isin(set(test_hh.SERIALNO))]
state = torch.load(f"{TR}/checkpoint_best.pt", map_location="cpu", weights_only=False)
model = CVAE(n_pumas=len(p2i), cfg=CVAEConfig(**state["model_cfg"])); model.load_state_dict(state["ema_state"])
gen_hh, gen_pp = generate_population(model, train_hh, train_pp, p2i, ZoneSampler(crosswalks.build_zone_table(), rng=np.random.default_rng(1)),
                                     n_total=150_000, seed=1, device="cpu")

HV = [("hhSizeVAE", config.N_HH_SIZES, 1)] + VV.HH_VARS; PV = VV.PP_VARS
LAB = {"hhSizeVAE": "HH size", "dwellingType": "HH dwelling type", "tenure": "HH tenure", "autos": "HH cars", "income_bin": "HH income",
       "age_bin": "P age", "gender": "P sex", "race": "P race", "occupation": "P occupation", "driversLicense": "P driving licence",
       "relationship": "P relationship", "nationality": "P nationality", "pincome_bin": "P income"}
if "hhSizeVAE" not in gen_hh.columns:
    gen_hh["hhSizeVAE"] = gen_hh["hhSize"].clip(upper=config.N_HH_SIZES) if "hhSize" in gen_hh.columns else gen_pp.groupby(gen_pp.columns[0]).size()
def person_frame(h, p, key_h, key_p):
    """Persons with the household attributes attached (household income renamed income_bin -> income_bin; person income -> pincome_bin)."""
    x = p.rename(columns={"income_bin": "pincome_bin"}).merge(h[[key_h] + [v for v, _, _ in HV]], left_on=key_p, right_on=key_h, how="inner")
    return x
key = next(c for c in ["hh_id", "SERIALNO", "hhid"] if c in gen_hh.columns and c in gen_pp.columns)
G = person_frame(gen_hh, gen_pp, key, key); T = person_frame(test_hh, test_pp, "SERIALNO", "SERIALNO"); R = person_frame(train_hh, train_pp, "SERIALNO", "SERIALNO")
PVr = [(("pincome_bin" if v == "income_bin" else v), n, b) for v, n, b in PV]
ALL = [(v, n, b, "h") for v, n, b in HV] + [(v, n, b, "p") for v, n, b in PVr]

def srm(a, b, level):
    """SRMSE of the joint of attributes a, b (and of a alone when b is None): synthetic and training split against the test split."""
    cols = [a] if b is None else [a, b]
    if level == "h":
        src = [(gen_hh, None), (train_hh, "WGTP_eff"), (test_hh, "WGTP_eff")]
    else:
        src = [(G, None), (R, "PWGTP_eff"), (T, "PWGTP_eff")]
    d = [VV._joint_dist(f, [(c[0], c[1], c[2]) for c in cols], None, (np.ones(len(f)) if w is None else f[w].to_numpy())) for f, w in src]
    return VV.srmse(d[2], d[0]), VV.srmse(d[2], d[1]), VV.tv(d[2], d[0]), VV.tv(d[2], d[1])

rows = []
for i, a in enumerate(ALL):
    s = srm(a[:3], None, a[3]); rows.append(dict(a=a[0], b="", synthetic=s[0], training=s[1], tv_synthetic=s[2], tv_training=s[3]))
    for b in ALL[i + 1:]:
        lev = "h" if a[3] == b[3] == "h" else "p"
        s = srm(a[:3], b[:3], lev); rows.append(dict(a=a[0], b=b[0], synthetic=s[0], training=s[1], tv_synthetic=s[2], tv_training=s[3]))
P = pd.DataFrame(rows); P.to_csv(f"{V}/data/pop_pairs_srmse.csv", index=False)
pr = P[P.b != ""]; print(f"pairs {len(pr)}: synthetic median {pr.synthetic.median():.3f} max {pr.synthetic.max():.3f}; training median {pr.training.median():.3f} max {pr.training.max():.3f}")
print(pr.sort_values("synthetic", ascending=False).head(8).round(3).to_string(index=False))

# ---- figure
names = [LAB[a[0]] for a in ALL]; n = len(ALL); M = np.full((n, n), np.nan)
for _, r in pr.iterrows():
    i, j = [a[0] for a in ALL].index(r.a), [a[0] for a in ALL].index(r.b)
    M[j, i] = r.synthetic; M[i, j] = r.training                                        # below diagonal: synthetic; above: training split
fig, a2 = ps.figure(height=4.9)
a2.grid(False); vmax = float(np.ceil(np.nanmax(M) * 20) / 20)
im = a2.imshow(M, cmap=ps.SEQ, vmin=0, vmax=vmax, aspect="equal")
for i in range(n):
    for j in range(n):
        if np.isfinite(M[i, j]): a2.text(j, i, f"{M[i, j]:.2f}".lstrip("0"), ha="center", va="center", fontsize=ps.MIN_FONT,
                                         color="white" if M[i, j] > 0.6 * vmax else ps.INK)
a2.plot([-0.5, n - 0.5], [-0.5, n - 0.5], color=ps.INK2, lw=0.6)
a2.set_xticks(range(n)); a2.set_xticklabels(names, rotation=45, ha="right", rotation_mode="anchor"); a2.set_yticks(range(n)); a2.set_yticklabels(names)
a2.tick_params(length=0)
a2.set_title("Below the diagonal: synthetic population; above: training split", loc="center", fontsize=ps.TICK, fontweight="normal", color=ps.INK2)
cb = fig.colorbar(im, ax=a2, fraction=0.035, pad=0.02); cb.set_label("SRMSE against held-out households (–)"); cb.outline.set_visible(False)
ps.finish(fig, f"{V}/5_reports/article/figures/fig_val_pop_quality")
