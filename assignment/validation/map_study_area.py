#!/usr/bin/env python3
"""Main-text map of the study area (2026-11-04): the six Baltimore-region counties, the major roads from OpenStreetMap (true way
geometries of motorway, trunk and primary roads, Maryland extract), the screenlines S1-S7 and the closed Key Bridge.  No count
stations, no minor roads.  Called by screenlines.py (draw); standalone it reads the screenline geometry written by screenlines.py.
Usage: python3 assignment/validation/map_study_area.py [screenlines_definition.geojson] [out_without_ext]"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, json, numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.geometry import shape, LineString
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"; ROOT = f"{PROJECT_ROOT}"   # H: validation data and outputs (workspace)
sys.path.insert(0, f"{TERP_HOME}/reports"); import paperstyle as ps   # noqa: E402
CRS = 26985
PBF = f"{ROOT}/inputs/osm/maryland-latest.osm.pbf"
ROADS = f"{H}/data/osm_major_roads.gpkg"
EXTENT = (365000, 492000, 104000, 235000)          # EPSG:26985
KEY_BRIDGE = (-76.5285, 39.2176)
SHORT = {1: "Baltimore City cordon", 2: "Patapsco River", 3: "Beltway cordon", 4: "Southern boundary (Patuxent)", 5: "Little Gunpowder Falls",
         6: "Carroll County line", 7: "Other regional boundary"}
STYLE = {"motorway": ("#4d4b46", 1.0), "trunk": ("#4d4b46", 1.0), "primary": ("#a7a49b", 0.45)}
WATER, LAND_OUT, LAND_IN = "#dfeaf3", "#efeee9", "white"


def osm_roads():
    """Motorway, trunk and primary ways (no links) of the OSM Maryland extract inside the map extent, cached as a GeoPackage."""
    if os.path.exists(ROADS): return gpd.read_file(ROADS)
    import osmium
    from pyproj import Transformer
    inv = Transformer.from_crs(CRS, 4326, always_xy=True)
    lon0, lat0 = inv.transform(EXTENT[0] - 5000, EXTENT[2] - 5000); lon1, lat1 = inv.transform(EXTENT[1] + 5000, EXTENT[3] + 5000)
    rows = []

    class W(osmium.SimpleHandler):
        def way(self, w):
            h = w.tags.get("highway")
            if h not in STYLE: return
            try: c = [(n.lon, n.lat) for n in w.nodes]
            except osmium.InvalidLocationError: return
            if len(c) < 2: return
            xs, ys = zip(*c)
            if max(xs) < lon0 or min(xs) > lon1 or max(ys) < lat0 or min(ys) > lat1: return
            rows.append((h, LineString(c)))
    W().apply_file(PBF, locations=True)
    g = gpd.GeoDataFrame({"hwy": [r[0] for r in rows]}, geometry=[r[1] for r in rows], crs=4326).to_crs(CRS)
    g["geometry"] = g.geometry.simplify(15); g.to_file(ROADS, driver="GPKG"); return g


def counties():
    """Six counties (BMR layer) and the surrounding counties (Census 2023 cartographic boundaries, 1:500k, shoreline-clipped), minus the six."""
    c6 = gpd.read_file(f"{MATSIM_HOME}/data/bmr_counties.gpkg").to_crs(CRS); c6["fips"] = c6.GEOID.astype(int)
    cb = gpd.read_file(f"{V}/data/raw/tiger_cb/cb_2023_us_county_500k.shp")
    nb = cb[cb.STATEFP.isin(["24", "42", "10", "11", "51", "34"])].to_crs(CRS)
    nb = nb[~nb.GEOID.astype(int).isin(c6.fips)].assign(fips=lambda d: d.GEOID.astype(int))[["fips", "geometry"]]
    nb["geometry"] = nb.geometry.difference(c6.geometry.union_all())
    return c6, nb


def _lines(geom):
    if geom.is_empty: return []
    out = []
    for g in getattr(geom, "geoms", [geom]):
        if g.geom_type in ("LineString", "LinearRing"): out.append(np.asarray(g.coords))
        elif g.geom_type in ("MultiLineString", "GeometryCollection"): out += _lines(g)
        elif g.geom_type == "Polygon": out.append(np.asarray(g.exterior.coords))
    return out


def draw(c6, nb, SLG, path):
    import matplotlib.patheffects as pe
    from matplotlib.lines import Line2D
    from matplotlib.collections import LineCollection
    from pyproj import Transformer
    R = osm_roads()
    halo = [pe.withStroke(linewidth=2.4, foreground="white")]
    kb = Transformer.from_crs(4326, CRS, always_xy=True).transform(*KEY_BRIDGE)
    fig = ps.new_figure(5.9); ax = fig.add_axes([0.0, 0.135, 1.0, 0.865]); ax.set_facecolor(WATER)
    nb.assign(geometry=nb.geometry.simplify(40)).plot(ax=ax, facecolor=LAND_OUT, edgecolor="#c9c7bf", lw=0.4, zorder=0)
    c6.assign(geometry=c6.geometry.simplify(40)).plot(ax=ax, facecolor=LAND_IN, edgecolor="none", zorder=0)
    for h in ["primary", "trunk", "motorway"]:
        col, lw = STYLE[h]; segs = [a for g in R[R.hwy == h].geometry for a in _lines(g)]
        ax.add_collection(LineCollection(segs, colors=col, linewidths=lw, zorder=2 if h == "primary" else 3, capstyle="round"))
    c6.boundary.plot(ax=ax, color=ps.INK, lw=0.6, zorder=4)
    cols = {k: ps.CAT[k] for k in range(1, 8)}
    for sid, g in SLG.items():
        for a in _lines(g): ax.plot(a[:, 0], a[:, 1], color=cols[sid], lw=2.0, zorder=6, solid_capstyle="round", alpha=0.95)
    ax.scatter([kb[0]], [kb[1]], marker="X", s=42, color=ps.INK, edgecolor="white", lw=0.6, zorder=9)
    x0, x1, y0, y1 = EXTENT; ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    for t, x, y in [("Carroll", 392000, 207000), ("Baltimore\nCounty", 430000, 211000), ("Harford", 458000, 213000), ("Howard", 400000, 177000),
                    ("Anne\nArundel", 438000, 140000), ("Baltimore\nCity", 433500, 181500)]:
        ax.text(x, y, t, ha="center", va="center", fontsize=ps.TICK if "City" in t else ps.FONT, color=ps.INK, fontweight="bold", path_effects=halo, zorder=10)
    for t, x, y in [("Pennsylvania", 410000, 231000), ("Frederick", 371500, 196000), ("Montgomery", 381000, 158000), ("Prince\nGeorge's", 410000, 128000),
                    ("Chesapeake\nBay", 452000, 124000)]:
        ax.text(x, y, t, ha="center", va="center", fontsize=ps.TICK, color=ps.MUTED, style="italic", path_effects=halo, zorder=10)
    slab = {1: (421500, 187500), 2: (402000, 191500), 3: (447500, 195500), 4: (393000, 168000), 5: (452000, 204500), 6: (418500, 216000), 7: (380500, 223000)}
    for sid, (x, y) in slab.items():
        ax.text(x, y, f"S{sid}", ha="center", va="center", fontsize=ps.FONT, color=cols[sid], fontweight="bold", path_effects=halo, zorder=11)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.grid(False); ax.set_xlabel(""); ax.set_ylabel("")
    for sp in ax.spines.values(): sp.set_visible(True); sp.set_color(ps.AXIS); sp.set_linewidth(0.6)
    xs, ys, km = 369000, 108000, 20      # scale bar and north arrow
    ax.plot([xs, xs + km * 1e3], [ys, ys], color=ps.INK, lw=1.2, solid_capstyle="butt")
    for xx in (xs, xs + km * 1e3): ax.plot([xx, xx], [ys - 600, ys + 600], color=ps.INK, lw=0.8)
    ax.text(xs + km * 5e2, ys + 1500, f"{km} km", ha="center", va="bottom", fontsize=ps.TICK, color=ps.INK)
    ax.annotate("", xy=(xs + km * 1.4e3, ys + 9000), xytext=(xs + km * 1.4e3, ys + 1000), arrowprops=dict(arrowstyle="-|>", color=ps.INK, lw=1.0))
    ax.text(xs + km * 1.4e3, ys + 9800, "N", ha="center", va="bottom", fontsize=ps.FONT, color=ps.INK, fontweight="bold")
    ax.text(x1 - 1500, y0 + 1500, "Roads: © OpenStreetMap contributors", ha="right", va="bottom", fontsize=ps.TICK, color=ps.MUTED, path_effects=halo, zorder=12)
    hs = [Line2D([], [], color=cols[k], lw=2.0, label=f"S{k} {SHORT[k]}") for k in SHORT]
    hs += [Line2D([], [], color=STYLE["motorway"][0], lw=1.0, label="Motorway, trunk road"), Line2D([], [], color=STYLE["primary"][0], lw=0.8, label="Primary road"),
           Line2D([], [], marker="X", ls="", color=ps.INK, ms=5, label="Key Bridge (closed 2024)")]
    fig.legend(handles=hs, loc="lower center", bbox_to_anchor=(0.5, 0.0), fontsize=ps.TICK, frameon=False, ncol=3)
    return ps.finish(fig, path)


def main():
    gj = sys.argv[1] if len(sys.argv) > 1 else f"{H}/previews/seed1_final/data/screenlines_definition.geojson"
    out = sys.argv[2] if len(sys.argv) > 2 else f"{V}/5_reports/article/figures/fig_net_study_area"
    F = json.load(open(gj))["features"]
    SLG = {f["properties"]["sl"]: shape(f["geometry"]) for f in F if f["properties"]["kind"] == "screenline"}
    c6, nb = counties(); draw(c6, nb, SLG, out)


if __name__ == "__main__":
    main()
