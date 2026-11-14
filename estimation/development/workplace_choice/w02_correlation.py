#!/usr/bin/env python3
"""Workplace choice, step 2: correlations of the candidate attributes of the alternatives as they appear in the choice sets
(estimation workers x 100 sampled zones), and their VIF. Outputs: corr_heatmap.png, corr.csv, vif.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import wdc

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/workplace"   # results of this step (data); CODE = this folder
VARS = {"t": "Car time (min)", "lt": "ln(1 + car time)", "ls": "Mode-choice logsum", "intra": "Same zone", "cc": "Other county",
        "cs": "Other state", "dcw": "DC workplace, home elsewhere", "lnjobs": "ln jobs (size)", "z_off_sh": "Office share",
        "z_ret_sh": "Retail share", "z_ind_sh": "Industrial share", "z_hiearn": "High-wage share", "z_lnden": "ln job density",
        "z_rural": "Rural workplace", "accw": "Accessibility of the workplace"}


def main():
    m = wdc.Model([k for k in VARS if k != "lnjobs"])
    X = m.X.reshape(-1, m.X.shape[2]); lj = np.log(np.maximum(m.Nj.sum(2), 1)).reshape(-1, 1)
    X = np.column_stack([X[:, :7], lj, X[:, 7:]]); names = list(VARS)
    R = np.corrcoef(X, rowvar=False)
    pd.DataFrame(R, index=names, columns=names).round(3).to_csv(f"{HERE}/corr.csv")
    vif = np.diag(np.linalg.inv(R)); pd.DataFrame({"variable": names, "VIF": vif.round(2)}).to_csv(f"{HERE}/vif.csv", index=False)
    labels = list(VARS.values()); n = len(labels)
    cmap = LinearSegmentedColormap.from_list("div", ["#2166ac", "#d9d9d9", "#b2182b"])
    fig, ax = plt.subplots(figsize=(10, 8.6)); mask = np.triu(np.ones_like(R, bool), 1)
    im = ax.imshow(np.ma.masked_where(mask, R), cmap=cmap, vmin=-1, vmax=1)
    for i in range(n):
        for j in range(i):
            ax.text(j, i, f"{R[i, j]:.2f}".replace("-0.", "−0.").replace("0.", "."), ha="center", va="center", fontsize=7,
                    color="white" if abs(R[i, j]) > 0.6 else "#222222")
    ax.set_xticks(range(n)); ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=8); ax.set_yticks(range(n)); ax.set_yticklabels(labels, fontsize=8)
    for s in ax.spines.values(): s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.6); cb.set_label("Correlation", fontsize=8); cb.ax.tick_params(labelsize=7)
    ax.set_title("Workplace choice: correlations of the attributes of the alternatives\n9,707 workers x 100 zones of their choice sets", fontsize=10)
    fig.tight_layout(); fig.savefig(f"{HERE}/corr_heatmap.png", dpi=200)
    print("pairs |r| >= 0.6:"); [print(f"  {labels[i]} / {labels[j]}: {R[i, j]:+.2f}") for i in range(n) for j in range(i) if abs(R[i, j]) >= 0.6]
    print(pd.read_csv(f"{HERE}/vif.csv").to_string(index=False))


if __name__ == "__main__":
    main()
