#!/usr/bin/env python3
"""Car ownership, step 2: correlation check of all candidate variables (estimation sample, household weights).
Outputs: corr_heatmap.png, corr.csv, vif.csv.   Usage: python3 estimation/development/car_ownership/s02_correlation.py"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
VARS = {"cars": "Cars (outcome)", "hhsize": "Household size", "adults16": "Persons 16+", "workers": "Workers",
        "nonworking_adults": "Non-working persons 16+", "children": "Children under 16", "any_65plus": "Member 65+",
        "single_person": "Single person", "ln_income": "ln income", "sfd": "Single-family detached", "sfa": "Single-family attached",
        "multifamily": "Multifamily", "bedrooms": "Bedrooms", "acc_car": "Accessibility by car", "acc_nocar": "Accessibility without car",
        "acc_gain": "Accessibility gain from a car", "ln_density": "ln dwelling density (PUMA)", "balt_city": "Baltimore City"}


def wcorr(X, w):
    w = w / w.sum(); m = (X * w[:, None]).sum(0); Z = X - m
    C = (Z * w[:, None]).T @ Z; s = np.sqrt(np.diag(C)); return C / np.outer(s, s)


def main():
    d = pd.read_parquet(f"{HERE}/hh.parquet"); d = d[d.half == "estimation"]
    d["adults16"] = d.adults16.clip(upper=8); d["children"] = d.children.clip(upper=6)
    d["nonworking_adults"] = d.nonworking_adults.clip(upper=6)
    X = d[list(VARS)].values.astype(float); R = wcorr(X, d.w.values.astype(float))
    pd.DataFrame(R, index=list(VARS), columns=list(VARS)).round(3).to_csv(f"{HERE}/corr.csv")
    # variance inflation factors of the explanatory variables (outcome excluded)
    E = R[1:, 1:]; vif = np.diag(np.linalg.inv(E))
    pd.DataFrame({"variable": list(VARS)[1:], "VIF": vif.round(2)}).to_csv(f"{HERE}/vif.csv", index=False)
    labels = list(VARS.values()); n = len(labels)
    cmap = LinearSegmentedColormap.from_list("div", ["#2166ac", "#d9d9d9", "#b2182b"])
    fig, ax = plt.subplots(figsize=(10.5, 9))
    mask = np.triu(np.ones_like(R, bool), 1)
    im = ax.imshow(np.ma.masked_where(mask, R), cmap=cmap, vmin=-1, vmax=1)
    for i in range(n):
        for j in range(i + 1):
            ax.text(j, i, f"{R[i, j]:.2f}".replace("-0.", "−0.").replace("0.", ".") if i != j else "",
                    ha="center", va="center", fontsize=7, color="white" if abs(R[i, j]) > 0.6 else "#222222")
    ax.set_xticks(range(n)); ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=8)
    ax.set_yticks(range(n)); ax.set_yticklabels(labels, fontsize=8)
    for s in ax.spines.values(): s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.6); cb.set_label("Correlation (weighted)", fontsize=8); cb.ax.tick_params(labelsize=7)
    ax.set_title("Car ownership: correlations of the candidate variables\nACS PUMS 2014–2018 Maryland households, estimation sample (91,348)", fontsize=10)
    fig.tight_layout(); fig.savefig(f"{HERE}/corr_heatmap.png", dpi=200)
    pairs = [(labels[i], labels[j], R[i, j]) for i in range(1, n) for j in range(1, i) if abs(R[i, j]) >= 0.6]
    print("pairs |r| >= 0.6:"); [print(f"  {a} / {b}: {r:+.2f}") for a, b, r in sorted(pairs, key=lambda x: -abs(x[2]))]
    print("correlation with cars:"); [print(f"  {labels[i]}: {R[i, 0]:+.2f}") for i in np.argsort(-np.abs(R[1:, 0])) + 1]
    print(pd.read_csv(f"{HERE}/vif.csv").to_string(index=False))


if __name__ == "__main__":
    main()
