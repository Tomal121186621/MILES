#!/usr/bin/env python3
"""collinearity_heatmaps.pdf: one model per page, heatmap of the variable correlations left, of the estimate correlations
(robust covariance) right, in the order of the chain (SILO, then DAYMAP).  Pooled models: the left panel holds the per-purpose
variable heatmaps (dp_pooled_var_corr.png, lp_edu_var_corr.png).  Images are downsampled to at most MAXPX pixels per side.
    python3 estimation/development/collinearity/c_heatmaps_pdf.py   ->  collinearity_heatmaps.pdf"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; MAXPX = 3000
Image.MAX_IMAGE_PIXELS = None
PAGES = [("county", "County"), ("zone", "Zone"), ("dwelling", "Dwelling"), ("cars", "Car ownership"), ("workplace", "Workplace"),
         ("school_k8", "School K-8"), ("school_hs", "School high school"), ("school_college", "School college"),
         ("mc_work", "Mode: work"), ("mc_school", "Mode: school"), ("mc_shopping", "Mode: shopping"), ("mc_other", "Mode: other"),
         ("mj_shopping", "Mode: joint shopping tours (group model)"), ("mj_other", "Mode: joint other tours (group model)"),
         ("dp_pooled", "Primary destination: pooled model of shopping, recreation, accompanying and other tours"),
         ("st_shop", "Stop: shopping"), ("st_rec", "Stop: recreation"), ("st_acc", "Stop: accompanying"), ("st_oth", "Stop: other"),
         ("lp_edu", "School of non-students and daycare: pooled model"),
         ("l03_wahb", "Work, home base"), ("l04_wbhome", "Work business from home"), ("l05_wbwork", "Work business from work"),
         ("l06_outing_dest", "Outing destination"),
         ("a01_outing", "Outing occurrence"), ("a02_outing_mode", "Outing mode"), ("a03_return", "Return home")]


def img(path, maxpx=MAXPX):
    im = Image.open(path).convert("RGB"); s = maxpx / max(im.size)
    if s < 1: im = im.resize((int(im.size[0] * s), int(im.size[1] * s)), Image.LANCZOS)
    return np.asarray(im)


def main():
    with PdfPages(f"{HERE}/collinearity_heatmaps.pdf") as pdf:
        for m, title in PAGES:
            fig, ax = plt.subplots(1, 2, figsize=(22, 11))
            for a, f, sub in zip(ax, (f"{m}_var_corr.png", f"{m}_est_corr.png"), ("Correlation of variables", "Correlation of estimates (robust)")):
                a.imshow(img(f"{HERE}/{f}", 6000 if m == "dp_pooled" else MAXPX)); a.axis("off"); a.set_title(sub, fontsize=13)
            fig.suptitle(title, fontsize=16); fig.tight_layout(rect=(0, 0, 1, 0.96)); pdf.savefig(fig, dpi=150); plt.close(fig)
            print(m, flush=True)


if __name__ == "__main__":
    main()
