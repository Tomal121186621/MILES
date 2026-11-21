#!/usr/bin/env python3
"""Shared helpers of the hold-out maps (w12_holdout_map.py, l12_holdout_map.py; style of residential/r21_holdout_map.py).

  zone_to_puma()   zone -> PUMA shares: 2010 tract internal points (hu shares), zones without one by their centroid
                   (residential/r20_geo_puma_zone.csv); a zone's share is split over PUMAs by these shares
  aggregate(z, s)  zone-level shares (Series by zone id) -> PUMA and county (zoneSystem COUNTYFIPS) shares
  geometry()       PUMA polygons (2010 TIGER tracts dissolved by the Census 2010 tract-to-PUMA file), county polygons (zones by
                   zoneSystem county), both clipped to the model area (union of the zones, gaps <= 300 m closed, holes < 5 km2 filled);
                   county lines = county borders inside the model area
  draw(rows, ...)  rows of three panels: observed % / model % (one sequential scale per row) / model minus observed pp (diverging,
                   symmetric, grey at 0); legend under every panel; statistics under (b) and (c); footnote; paperstyle check;
                   PDF + PNG 200 dpi."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
V = WORKSPACE
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"   # HERE: results of this step (data); CODE: this folder
sys.path.insert(0, f"{MILES_HOME}/reports")   # reports/paperstyle.py
import paperstyle as PS   # noqa: E402
BALT = [24510, 24005, 24003, 24027, 24025, 24013]
BW = BALT + [11001, 24031, 24033, 24021, 24009, 24017, 51013, 51059, 51510, 51600, 51610, 51107, 51153]   # Baltimore-Washington


def bounds(counties, pad=3000):
    b = geometry()["zp"]; b = b[b.county.isin(counties)].total_bounds; return (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
MINUS = "−"
_G = {}


def zone_to_puma():
    pz = pd.read_csv(f"{HERE}/residential/r20_geo_puma_zone.csv"); tot = pz.groupby("zone").hu.transform("sum")
    pz["f"] = np.where(tot > 0, pz.hu / tot.where(tot > 0, 1), 1.0 / pz.groupby("zone").hu.transform("size"))
    return pz[["zone", "puma7", "f"]]


def zone_county():
    zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv"); return zs.set_index("ZoneId").COUNTYFIPS


def aggregate(obs, mod):
    """obs, mod: Series of percentages by zone id (sum 100) -> (PUMA table, county table) with observed_pct, model_pct, diff_pp"""
    pz = zone_to_puma(); z = pd.DataFrame({"observed_pct": obs, "model_pct": mod}).fillna(0.0)
    assert set(z.index) <= set(pz.zone), "zone without a PUMA"
    m = pz.merge(z, left_on="zone", right_index=True)
    P = m.assign(observed_pct=m.observed_pct * m.f, model_pct=m.model_pct * m.f).groupby("puma7")[["observed_pct", "model_pct"]].sum()
    P = P.reindex(np.sort(pz.puma7.unique())).fillna(0.0)
    C = z.groupby(z.index.map(zone_county())).sum(); C.index.name = "county"
    for T in (P, C): T["diff_pp"] = T.model_pct - T.observed_pct
    return P.reset_index(), C.reset_index()


def stats(T):
    return dict(r=float(np.corrcoef(T.observed_pct, T.model_pct)[0, 1]), mad=float(T.diff_pp.abs().mean()), n=len(T))


def geometry():
    if _G: return _G
    import geopandas as gpd
    from shapely.geometry import Polygon, MultiPolygon
    zp = gpd.read_file(f"{V}/2_silo/input/zones.shp")[["id", "geometry"]]; zp["county"] = zp.id.map(zone_county())
    area = zp.dissolve().geometry.iloc[0].buffer(0).buffer(300).buffer(-300)
    polys = area.geoms if area.geom_type == "MultiPolygon" else [area]
    area = MultiPolygon([Polygon(q.exterior, [r for r in q.interiors if Polygon(r).area > 5e6]) for q in polys]).buffer(0).simplify(150)
    tr = pd.concat([gpd.read_file(f"{V}/data/raw/tiger_tracts_2010/tl_2010_{st:02d}_tract10.zip")[["GEOID10", "geometry"]] for st in (10, 11, 24, 42, 51, 54)]).to_crs(zp.crs)
    tp = pd.read_csv(f"{V}/data/raw/resloc/2010_Census_Tract_to_2010_PUMA.txt", dtype=str); tp["geoid"] = tp.STATEFP + tp.COUNTYFP + tp.TRACTCE
    t2p = (tp.STATEFP.astype(int) * 100000 + tp.PUMA5CE.astype(int)).values; tr["puma7"] = tr.GEOID10.map(pd.Series(t2p, index=tp.geoid.values))
    pumas = zone_to_puma().puma7.unique()
    pu = tr[tr.puma7.isin(pumas)].dissolve("puma7"); pu["geometry"] = pu.geometry.buffer(0).simplify(150).intersection(area)
    tr["county"] = tr.GEOID10.str[:5].astype(int); cty = tr.dissolve("county"); cty["geometry"] = cty.geometry.buffer(0).simplify(150)
    cty = cty[cty.intersects(area)].copy()
    # county fills: zones dissolved by the zoneSystem county code (combined Virginia codes such as 51919 are not TIGER counties)
    cpoly = zp.dissolve("county")[["geometry"]]; cpoly["geometry"] = cpoly.geometry.buffer(200).buffer(-200).simplify(150).intersection(area)
    cpoly = cpoly[~cpoly.geometry.is_empty]
    lines = cty.copy(); lines["geometry"] = lines.geometry.boundary.intersection(area.buffer(-100)); lines = lines[~lines.geometry.is_empty]
    _G.update(pu=pu, cty=cpoly, lines=lines, area=area, balt=zp[zp.county.isin(BALT)].total_bounds, zp=zp)
    return _G


def nice_bins(vmax):
    for b in ([0, 0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3], [0, 0.25, 0.5, 1, 2, 3, 4, 6], [0, 0.5, 1, 2, 4, 6, 8, 12], [0, 1, 2, 4, 6, 8, 12, 16, 24]):
        if vmax <= b[-1] * 2:
            return b + [float(np.ceil(vmax))] if vmax > b[-1] else b
    return [0, 2, 5, 10, 15, 20, 30, float(np.ceil(vmax))]


def draw(rows, path, footnote, height=None):
    """rows: list of dict(table=DataFrame (puma7 or county index col + observed_pct, model_pct, diff_pp), level='puma'|'county',
    label=row title, extent='all'|'balt'|(x0, y0, x1, y1), box=None|(x0, y0, x1, y1) (rectangle on the map), stat_b=str, stat_c=str)"""
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, Normalize
    from matplotlib.patches import Rectangle
    G = geometry(); nr = len(rows)
    fig = PS.new_figure(height or min(PS.MAX_HEIGHT, 0.2 + 2.1 * nr))
    gs = fig.add_gridspec(2 * nr, 3, height_ratios=sum(([1.0, 0.07] for _ in rows), []))
    x0, y0, x1, y1 = G["area"].bounds; pad = 3000; bb = G["balt"]; zb = (bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad)
    for i, R in enumerate(rows):
        key = "puma7" if R["level"] == "puma" else "county"
        g = (G["pu"] if R["level"] == "puma" else G["cty"]).join(R["table"].set_index(key))
        bins = R.get("bins") or nice_bins(max(g.observed_pct.max(), g.model_pct.max())); norm = BoundaryNorm(bins, PS.SEQ.N)
        lim = float(np.ceil(np.abs(g.diff_pp).max() * 10) / 10); dnorm = Normalize(-lim, lim)
        ext = {"all": (x0, y0, x1, y1), "balt": zb}.get(R["extent"], R["extent"]) if isinstance(R["extent"], str) else R["extent"]
        lw = 0.25 if ext == (x0, y0, x1, y1) else 0.4
        cols = [("observed_pct", PS.SEQ, norm, "(a) Observed,\nhold-out " + R["who"] + " (%)"), ("model_pct", PS.SEQ, norm, "(b) Model,\nhold-out " + R["who"] + " (%)"),
                ("diff_pp", PS.DIV, dnorm, "(c) Model minus\nobserved (pp)")]
        for j, (col, cmap, nm, title) in enumerate(cols):
            ax = fig.add_subplot(gs[2 * i, j]); ax.set_axis_off(); ax.set_aspect("equal")
            g.plot(ax=ax, column=col, cmap=cmap, norm=nm, edgecolor="white", linewidth=lw)
            G["lines"].plot(ax=ax, color=PS.INK2, linewidth=lw)
            ax.set_xlim(ext[0], ext[2]); ax.set_ylim(ext[1], ext[3])
            if R.get("box") is not None:
                b = R["box"]; ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fill=False, edgecolor=PS.INK, lw=0.6))
            if i == 0: ax.set_title(title, fontsize=PS.FONT, loc="left")
            if j == 0 and R.get("label"):
                ax.text(-0.03, 0.5, R["label"], transform=ax.transAxes, rotation=90, ha="right", va="center", fontsize=PS.FONT, color=PS.INK)
            if j == 1 and R.get("stat_b"):
                ax.text(0.0, -0.02, R["stat_b"], transform=ax.transAxes, ha="left", va="top", fontsize=PS.TICK, color=PS.INK)
            if j == 2 and R.get("stat_c"):
                ax.text(0.0, -0.02, R["stat_c"].replace("-", MINUS), transform=ax.transAxes, ha="left", va="top", fontsize=PS.TICK, color=PS.INK)
            cax = fig.add_subplot(gs[2 * i + 1, j]); sm = plt.cm.ScalarMappable(norm=nm, cmap=cmap)
            cb = fig.colorbar(sm, cax=cax, orientation="horizontal"); cb.outline.set_linewidth(0.3); cb.ax.tick_params(labelsize=PS.TICK, length=2, width=0.4)
            if j < 2:
                lab = set(bins[::2]) | {bins[-1]}
                cb.set_ticks(bins); cb.set_ticklabels([f"{b:g}" if b in lab else "" for b in bins])
            else:
                t = np.round(np.linspace(-lim, lim, 5), 2); cb.set_ticks(t); cb.set_ticklabels([(f"{x:+g}" if x else "0").replace("-", MINUS) for x in t])
    fig.text(0.0, 0.0, footnote, ha="left", va="bottom", fontsize=PS.TICK, color=PS.INK2)
    fh = (footnote.count("\n") + 1) * 0.15 / fig.get_size_inches()[1]; fig.get_layout_engine().set(rect=(0, fh + 0.01, 1, 1 - fh - 0.01))
    PS.check(fig, os.path.basename(path))
    fig.savefig(path + ".pdf"); fig.savefig(path + ".png", dpi=200); plt.close(fig)
    print(f"wrote {path}.pdf / .png")
