"""One visual system for every data figure of the article and its Supplementary Material (5_reports/composites/fig_*.py).

Standard (after the validation figures of Roorda, Miller & Habib 2008, TR-A 42:360-375):
  - one kind of comparison per figure, at most six panels in a regular grid of equal panels, shared axes where meaningful;
  - colours: OBSERVED dark grey, MODEL blue, and one accent (OUTSIDE, orange) for a value outside the tolerance band;
    a second model (former model, forecast population, chain test) is light blue and dashed; the model's 90 % band over
    the replications is a light-blue fill; the tolerance band a light-grey fill (palette checked with the dataviz
    validator: blue/grey/orange pass the colour-vision-deficiency separation; the grey is a deliberate neutral);
  - chart forms: distributions as an observed step histogram (grey) and a model line with its band; categories as dot
    plots (observed square, model circle); ratios and differences as dot plots against a reference line and a band;
  - text: sans 8 pt labels, 7.5 pt ticks, 9 pt bold panel titles "(a) Heading" at the top left of every panel;
  - one legend per figure, above the panels (outside the data area);
  - exactly \\textwidth wide, drawn at print size, checked by paperstyle.finish() (no text < 7.5 pt, no overlap, no cropping).
Output: 5_reports/figures/<name>.pdf/png, copied to 5_reports/article/figures/<name>.pdf.
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, shutil, sys
import numpy as np
V = f"{WORKSPACE}"
sys.path.insert(0, f"{TERP_HOME}/reports")
import paperstyle as ps   # noqa: E402
from matplotlib.lines import Line2D   # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
OUT = f"{V}/5_reports/figures"; ART = f"{V}/5_reports/article/figures"
LIGHT_MODEL = "#86b6ef"          # second model (former model, forecast population, chain test)
OUTSIDE = "#eb6834"              # accent: outside the tolerance band
MODEL, OBSERVED = ps.MODEL, ps.OBSERVED
BAND_ALPHA = 1.0
LW_MODEL, LW_OBS, MS = 1.4, 1.2, 4.0
LETTERS = "abcdefghijklmnopqrstuvwxyz"
Z90 = 1.645                      # 90 % band of the replications from their standard deviation (normal approximation)


def new(height):
    """Figure at \\textwidth x height (inches), constrained layout."""
    return ps.new_figure(height)


def grid(fig, nrows, ncols, **kw):
    """Regular grid of equal panels; returns the axes in reading order."""
    axs = fig.subplots(nrows, ncols, squeeze=False, **kw)
    return list(axs.ravel())


def title(ax, letter, text=None):
    """Panel title '(a) Heading', 9 pt bold, at the top left of the panel."""
    ax.set_title(f"({letter})" + (f" {text}" if text else ""), loc="left", fontsize=ps.PANEL, fontweight="bold", color=ps.INK, pad=4)


def titles(axes, texts=None):
    for i, ax in enumerate(axes): title(ax, LETTERS[i], texts[i] if texts else None)


def legend(fig, handles, ncol=None, **kw):
    """The one legend of the figure, centred above the panels."""
    return fig.legend(handles=handles, loc="outside upper center", ncol=ncol or len(handles), frameon=False, **kw)


# ---- legend handles (identical labels in every figure)
def h_model(label="Model"): return Line2D([], [], color=MODEL, lw=LW_MODEL, label=label)
def h_model_dot(label="Model"): return Line2D([], [], color=MODEL, marker="o", ms=MS, ls="", label=label)
def h_obs(label="Observed"): return Line2D([], [], color=OBSERVED, lw=LW_OBS, label=label)
def h_obs_dot(label="Observed"): return Line2D([], [], color=OBSERVED, marker="s", ms=MS - 0.4, ls="", label=label)
def h_variant(label): return Line2D([], [], color=LIGHT_MODEL, lw=LW_MODEL, ls=(0, (4, 2)), label=label)
def h_variant_dot(label): return Line2D([], [], color=LIGHT_MODEL, marker="D", ms=MS - 0.6, ls="", label=label)
def h_band(label="Model, 90 % band of replications"): return Patch(facecolor=ps.SEED_BAND, lw=0, label=label)
def h_tol(label="Tolerance band"): return Patch(facecolor=ps.TOL_BAND, lw=0, label=label)
def h_out(label="Outside tolerance"): return Line2D([], [], color=OUTSIDE, marker="o", ms=MS, ls="", label=label)
def h_err(label="Model, ±2 s.d. of seeds"): return Line2D([], [], color=MODEL, marker="|", ms=7, mew=0.9, ls="", label=label)


# ---- marks
def obs_steps(ax, values, x0=0):
    """Observed distribution as a step histogram over categorical bins centred at x0, x0+1, ..."""
    v = np.asarray(values, float); e = np.arange(len(v) + 1) - 0.5 + x0
    ax.stairs(v, e, color=OBSERVED, lw=LW_OBS, zorder=3, baseline=None)


def model_line(ax, x, m, sd=None, lo=None, hi=None, color=MODEL, ls="-", zorder=4):
    """Model as a line; its 90 % band over the replications from sd (mean +- 1.645 sd) or from explicit lo/hi."""
    x = np.asarray(x, float); m = np.asarray(m, float)
    if sd is not None: lo, hi = m - Z90 * np.asarray(sd, float), m + Z90 * np.asarray(sd, float)
    if lo is not None: ax.fill_between(x, np.clip(lo, 0, None), hi, color=ps.SEED_BAND, lw=0, zorder=2)
    ax.plot(x, m, color=color, lw=LW_MODEL, ls=ls, zorder=zorder)


def dots(ax, v, y, ok=None, err=None, s=14, zorder=4):
    """Model dots; values outside the tolerance (ok False) in the accent colour; optional +-err bars."""
    v = np.asarray(v, float); y = np.asarray(y, float); ok = np.ones(len(v), bool) if ok is None else np.asarray(ok, bool)
    if err is not None: ax.errorbar(v, y, xerr=err, fmt="none", ecolor=MODEL, elinewidth=0.7, zorder=zorder - 1)
    ax.scatter(v[ok], y[ok], s=s, color=MODEL, lw=0, zorder=zorder)
    ax.scatter(v[~ok], y[~ok], s=s, color=OUTSIDE, lw=0, zorder=zorder + 1)


def ratio_band(ax, band, center=1.0, orient="x"):
    """Tolerance band center*(1 +- band) in light grey, reference line at 1 (and dashed at center when it differs)."""
    span = ax.axvspan if orient == "x" else ax.axhspan; line = ax.axvline if orient == "x" else ax.axhline
    span(center * (1 - band), center * (1 + band), color=ps.TOL_BAND, lw=0, zorder=0)
    line(1.0, color=ps.INK2, lw=0.7, zorder=1)
    if center != 1.0: line(center, color=ps.INK2, lw=0.8, ls=(0, (3, 2)), zorder=1)


def rows_axis(ax, labels, show=True):
    """Categorical y axis, first label at the top."""
    n = len(labels); ax.set_ylim(-0.6, n - 0.4); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0)
    ax.set_yticks(range(n)); ax.set_yticklabels(list(labels)[::-1] if show else [""] * n)
    return np.arange(n)[::-1]


def cat_axis(ax, labels, rotate=False, show=True):
    n = len(labels); ax.set_xticks(range(n)); ax.set_xlim(-0.6, n - 0.4); ax.grid(axis="x", visible=False)
    if not show: ax.tick_params(labelbottom=False); return
    if rotate: ax.set_xticklabels(labels, rotation=45, ha="right", rotation_mode="anchor")
    else: ax.set_xticklabels(labels)


def save(fig, name):
    """Check the paper rules and save; copy the PDF to the article."""
    p = ps.finish(fig, f"{OUT}/{name}")
    os.makedirs(ART, exist_ok=True); shutil.copy(p, f"{ART}/{name}.pdf")
    return p


# ---- kept for older scripts
def heading(ax, txt):
    ax.set_title(txt, loc="center", fontsize=ps.FONT, fontweight="normal", color=ps.INK2)


def letters(axes):
    for ax, l in zip(axes, LETTERS): ps.panel_label(ax, l)
