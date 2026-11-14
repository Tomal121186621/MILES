"""One figure style for every figure of the paper (Transportation Research Part A submission, elsarticle 1p, 11 pt).
Import and call `use()` before plotting; use the colour roles and legend labels below, never ad-hoc ones.

Rules (enforced by `finish()`, which refuses to save a figure that breaks them):
  - size: every figure is drawn at its printed size, exactly \\textwidth wide (390 pt = 5.396 in, elsarticle review
    layout of article/main.tex) and at most 0.88 \\textheight (6.68 in) high; the paper includes it with width=\\textwidth (no scaling)
  - text: one font (Helvetica/Arial); all text >= 8 pt, tick labels 7.5 pt, panel letters 9 pt bold; nothing smaller than 7.5 pt
  - no text overlaps other text (rotated labels are tested as rotated rectangles); no text or artist extends beyond the canvas
  - plain words: axis labels in words with units ("Model ÷ observed (–)", "Share of households (%)"); no acronyms or
    abbreviations inside a figure (data-source names and statistics go in the caption); no statistics boxes inside plots;
    category labels rotated 45 degrees at most
  - colour has one meaning everywhere: MODEL = blue, OBSERVED = dark grey; seed range light blue, tolerance band light grey;
    ratio classes RATIO_* for maps and ratio heatmaps; DIV for differences of shares (model minus observed)
  - legend labels from LEG (identical in every figure)
  - exported as PDF (vector) and PNG 300 dpi
"""
import matplotlib, numpy as np, os
matplotlib.use("Agg")              # file output only; interactive backends round the canvas to whole screen pixels (size check)
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.text import Text

# ---- page geometry of the compiled article (elsarticle [review,12pt]: \textwidth=390.0pt, \textheight=548.5pt; TeX pt = 1/72.27 in)
TEXTWIDTH_PT, TEXTHEIGHT_PT = 390.0, 548.5
WIDTH = TEXTWIDTH_PT / 72.27                   # 5.396 in: every figure is exactly this wide
MAX_HEIGHT = 0.88 * TEXTHEIGHT_PT / 72.27      # 6.68 in: a composite figure may fill a page, leaving room for its caption
SINGLE = DOUBLE = WIDTH                        # kept for older scripts: there is one width only
FONT, TICK, PANEL, MIN_FONT = 8.0, 7.5, 9.0, 7.5

# categorical palette (validated for colour-vision deficiency; adjacent-pair order), from the dataviz reference palette
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MODEL, OBSERVED, VARIANT, ACCENT = "#2a78d6", "#52514e", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SEQ = LinearSegmentedColormap.from_list("seq_blue", ["#eef4fc", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
DIV = LinearSegmentedColormap.from_list("div_blue_red", ["#104281", "#2a78d6", "#86b6ef", "#f0efec", "#f0a09f", "#e34948", "#9c1d1c"])
RATIO_BINS = [0, .5, .75, .9, 1.1, 1.25, 1.5, np.inf]; RATIO_COLORS = ["#104281", "#2a78d6", "#86b6ef", "#e8e7e1", "#f0a09f", "#e34948", "#9c1d1c"]
RATIO_LABELS = ["< 0.50", "0.50–0.75", "0.75–0.90", "Within ±10 %", "1.10–1.25", "1.25–1.50", "> 1.50"]
SEED_BAND = "#cfe1f8"      # seed / replication range, +-2 s.d. (light blue)
TOL_BAND = "#e8e7e1"       # tolerance band of the acceptance criterion (light grey)
NODATA = "white"           # map: no comparison available (drawn white, hatched)
PP_LIM = 10                # diverging heatmaps: model minus observed, percentage points, -10..+10 everywhere

# ---- legend labels: short and identical in every figure
LEG = dict(model="Model", observed="Observed", seed="Seed range (±2 s.d.)", tol="Tolerance band", outside="Outside tolerance",
           nodata="No comparison")
def tol_label(txt=None):
    """'Tolerance (±5 %)' when one figure uses one tolerance, else 'Tolerance band' (values in the caption)."""
    return f"Tolerance ({txt})" if txt else LEG["tol"]

# ---- plain-language axis labels used in several figures
RATIO_LABEL = "Model ÷ observed (–)"
PP_LABEL = "Difference, model − observed\n(percentage points)"


def use():
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"], "font.size": FONT,
                         "axes.labelsize": FONT, "axes.titlesize": PANEL, "legend.fontsize": FONT, "legend.title_fontsize": FONT,
                         "xtick.labelsize": TICK, "ytick.labelsize": TICK, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
                         "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.4,
                         "axes.axisbelow": True, "lines.linewidth": 1.4, "lines.markersize": 4, "legend.frameon": False,
                         "legend.handlelength": 1.6, "legend.columnspacing": 1.2, "legend.handletextpad": 0.5, "figure.dpi": 110,
                         "savefig.dpi": 300, "figure.constrained_layout.use": True, "figure.constrained_layout.h_pad": 0.04,
                         "figure.constrained_layout.w_pad": 0.04, "pdf.fonttype": 42, "axes.titlelocation": "left",
                         "axes.titleweight": "bold", "axes.titlepad": 5})


def figure(*args, height=None, **kw):
    """Figure at the printed width (\\textwidth) and the given height (inches): figure(h) or, as in the superseded stage
    scripts, figure(width, h) where the width is ignored (there is one width only)."""
    h = height if height is not None else (args[-1] if args else 0.68 * WIDTH)
    use(); return plt.subplots(figsize=(WIDTH, h), **kw)


def equality_line(ax, lo, hi, band=0.25):
    ax.plot([lo, hi], [lo, hi], color=INK2, lw=0.8, zorder=1)
    for f in (1 + band, 1 - band): ax.plot([lo, hi], [lo * f, hi * f], color=AXIS, lw=0.7, ls="--", zorder=1)


def new_figure(height):
    use(); return plt.figure(figsize=(WIDTH, height))


def ratio_color(r):
    return RATIO_COLORS[int(np.digitize(r, RATIO_BINS[1:-1]))]


def panel_label(ax, letter):
    """Panel letter (a), (b) ... as the left-aligned axes title (9 pt bold), above the top-left corner of the plot area."""
    ax.set_title(f"({letter})", loc="left", fontsize=PANEL, fontweight="bold", color=INK)


# ------------------------------------------------------------------------------------------------ verification
def _text_polygon(t, renderer):
    """Rotated rectangle of a text artist in display coordinates (the axis-aligned box of rotated text is too large)."""
    from shapely.geometry import box
    from shapely import affinity
    bb = t.get_window_extent(renderer)
    rot = t.get_rotation() % 180
    if rot in (0, 90) or bb.width == 0:
        return box(bb.x0, bb.y0, bb.x1, bb.y1)
    r0 = t.get_rotation(); t.set_rotation(0); b0 = t.get_window_extent(renderer); t.set_rotation(r0)
    cx, cy = (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2
    return affinity.rotate(box(cx - b0.width / 2, cy - b0.height / 2, cx + b0.width / 2, cy + b0.height / 2), r0, origin=(cx, cy))


def check(fig, name="figure", tol_px=0.6):
    """Raise RuntimeError if the figure breaks a paper rule: size, font < 7.5 pt, text overlapping text, a text label or legend
    drawn over data markers or bars, or any text or artist outside the canvas (cropping). Only text that is actually drawn is tested (tick labels outside the view are not drawn)."""
    errs = []
    w, h = fig.get_size_inches()
    if abs(w - WIDTH) > 1e-3: errs.append(f"width {w:.3f} in, must be \\textwidth = {WIDTH:.3f} in")
    if h > MAX_HEIGHT + 1e-3: errs.append(f"height {h:.2f} in > 0.88 \\textheight = {MAX_HEIGHT:.2f} in")
    fig.canvas.draw()                                   # layout pass
    drawn, orig = [], Text.draw
    def rec(self, renderer):
        orig(self, renderer)
        if self.get_visible() and self.get_text().strip() and self.get_alpha() != 0: drawn.append(self)
    Text.draw = rec
    try: fig.canvas.draw()
    finally: Text.draw = orig
    r = fig.canvas.get_renderer(); W, H = fig.bbox.width, fig.bbox.height; dpi = fig.dpi
    seen, items = set(), []
    for t in drawn:
        if id(t) in seen: continue
        seen.add(id(t))
        if t.get_fontsize() < MIN_FONT - 1e-6: errs.append(f"font {t.get_fontsize():.2f} pt < {MIN_FONT} pt: '{t.get_text()}'")
        bb = t.get_window_extent(r)
        if bb.x0 < -tol_px or bb.y0 < -tol_px or bb.x1 > W + tol_px or bb.y1 > H + tol_px:
            errs.append(f"text beyond the canvas (cropped): '{t.get_text()}'")
        items.append((t.get_text().replace("\n", " "), _text_polygon(t, r).buffer(-tol_px)))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            if not a.is_empty and not b.is_empty and a.intersects(b):
                errs.append(f"text overlap: '{items[i][0]}' and '{items[j][0]}'")
    # text or legend boxes drawn over data markers (labels with a white halo are placed over data on purpose and exempt)
    from matplotlib.collections import PathCollection
    for ax in fig.get_axes():
        pts = []
        for ln in ax.lines:
            if ln.get_visible() and ln.get_marker() not in (None, "None", "", " ") and len(ln.get_xydata()):
                pts.append(ax.transData.transform(ln.get_xydata()))
        for c in ax.collections:
            if isinstance(c, PathCollection) and c.get_visible() and len(c.get_offsets()):
                pts.append(c.get_offset_transform().transform(c.get_offsets()))
        from matplotlib.container import BarContainer
        bars = [b.get_window_extent(r) for cont in ax.containers if isinstance(cont, BarContainer) for b in cont.patches if b.get_height() != 0 and b.get_width() != 0]
        if not pts and not bars: continue
        P = np.vstack(pts) if pts else np.zeros((0, 2)); P = P[np.isfinite(P).all(1)]
        boxes = [(t.get_text(), t.get_window_extent(r)) for t in ax.texts if t.get_visible() and t.get_text().strip() and not t.get_path_effects()]
        leg = ax.get_legend()
        if leg is not None and leg.get_visible(): boxes.append(("legend: " + ", ".join(x.get_text() for x in leg.get_texts()), leg.get_window_extent(r)))
        for txt, bb in boxes:
            inside = (P[:, 0] > bb.x0 + 1) & (P[:, 0] < bb.x1 - 1) & (P[:, 1] > bb.y0 + 1) & (P[:, 1] < bb.y1 - 1)
            if inside.any(): errs.append(f"text over data markers: '{txt[:60]}'")
            if any(bb.x0 + 1 < q.x1 and q.x0 < bb.x1 - 1 and bb.y0 + 1 < q.y1 and q.y0 < bb.y1 - 1 for q in bars): errs.append(f"text over bars: '{txt[:60]}'")
    tb = fig.get_tightbbox(r)                           # inches; all artists, clipped artists clipped
    if tb.x0 < -tol_px / dpi or tb.y0 < -tol_px / dpi or tb.x1 > w + tol_px / dpi or tb.y1 > h + tol_px / dpi:
        errs.append(f"artists beyond the canvas (cropped): tight box {tb.x0:.3f},{tb.y0:.3f} – {tb.x1:.3f},{tb.y1:.3f} in, canvas {w:.3f} × {h:.3f} in")
    if errs:
        raise RuntimeError(f"{name}: " + "; ".join(dict.fromkeys(errs)))
    return len(items)


def finish(fig, path_without_ext, panel_labels=None):
    """Label panels (a), (b) ... (first axes in order), check the paper rules (see check()) and save PDF + PNG."""
    if panel_labels:
        for ax, lab in zip(fig.get_axes(), panel_labels): panel_label(ax, lab)
    n = check(fig, os.path.basename(path_without_ext))
    os.makedirs(os.path.dirname(path_without_ext), exist_ok=True)
    fig.savefig(path_without_ext + ".pdf"); fig.savefig(path_without_ext + ".png"); plt.close(fig)
    print(f"ok  {os.path.basename(path_without_ext)}: {WIDTH:.3f} × {fig.get_size_inches()[1]:.2f} in, {n} text items, no overlap, nothing cropped, no font < {MIN_FONT} pt")
    return path_without_ext + ".pdf"


# ---------------------------------------------------------------------------------------------------------------------------
# Systematic validation scheme (reports/figures_validation.py): ratios model/observed on a LINEAR axis with a reference
# line at 1 and the tolerance band in light grey (log axis only where ratios span more than a factor of 5); differences of
# shares as model minus observed in percentage points on DIV, always -PP_LIM..+PP_LIM; spatial ratios in the RATIO classes.

def ratio_axis(ax, band=None, center=1.0, orient="y", label=None, lo=None, hi=None, log=False):
    """Ratio axis: reference line at 1 (and dashed at `center` when it differs) and the tolerance band center*(1 +- band)."""
    span = ax.axhspan if orient == "y" else ax.axvspan; line = ax.axhline if orient == "y" else ax.axvline
    if band is not None: span(center * (1 - band), center * (1 + band), color=TOL_BAND, lw=0, zorder=0)
    line(1.0, color=INK2, lw=0.7, zorder=1)
    if center != 1.0: line(center, color=INK2, lw=0.8, ls=(0, (3, 2)), zorder=1)
    if log: (ax.set_yscale if orient == "y" else ax.set_xscale)("log")
    if label: (ax.set_ylabel if orient == "y" else ax.set_xlabel)(label)
    if lo is not None: (ax.set_ylim if orient == "y" else ax.set_xlim)(lo, hi)


def ratio_class_handles(include_nodata=True):
    from matplotlib.patches import Patch
    h = [Patch(facecolor=c, edgecolor=AXIS, lw=0.3, label=l) for c, l in zip(RATIO_COLORS, RATIO_LABELS)]
    if include_nodata: h.append(Patch(facecolor=NODATA, edgecolor=AXIS, hatch="//////", lw=0.4, label=LEG["nodata"]))
    return h


def choropleth(ax, gdf, values, edge=None):
    """gdf: GeoDataFrame indexed by unit id; values: Series ratio by the same id. Colours by the RATIO classes."""
    ax.set_aspect("equal", adjustable="datalim"); ax.set_axis_off()
    v = values.reindex(gdf.index); ok = np.isfinite(v.values)
    if ok.any(): gdf[ok].plot(ax=ax, color=[ratio_color(x) for x in v.values[ok]], edgecolor=edge or "white", linewidth=0.5)
    if (~ok).any(): gdf[~ok].plot(ax=ax, facecolor=NODATA, edgecolor=AXIS, hatch="//////", linewidth=0.3)
    ax.set_xlabel(""); ax.set_ylabel("")
    return v
