#!/usr/bin/env python3
"""Maps of the count validation of the assignment (2026-11-12; popups and matched-link layer extended 2026-11-12e).

Interactive map (figures/validation_map.html, folium/Leaflet, one self-contained file; base-map tiles are loaded from the web):
  - every car link of the network, width and colour by the modelled daily volume (all vehicles, mean of the five runs); the two
    directions of a road are drawn as one line. Popup: link ids, OpenStreetMap name and highway type, length, lanes, capacity,
    free speed, modelled daily volume by direction (one value: the mean of the five runs), morning and evening peak-hour volumes, and the
    count stations on the segment with their observed passenger volume. Name, free speed and the peak-hour volumes are stored for the
    matched links, the motorway-to-tertiary roads and every segment with at least 1,000 vehicles per weekday (file size); minor
    streets below that carry the basic fields only.
  - the matched links of every count station as their own layer (amber); hovering over or clicking a station highlights its links
  - mainline count stations coloured by the passenger model/count ratio (diverging scale, grey around 1.0), a second layer by
    deviation class, ramp stations, stations whose matched link carries almost no model traffic, doubtful matches. Popup: observed
    (all vehicles, truck and bus shares, passenger) and simulated volumes (by direction and in total, mean of the five runs),
    ratios, deviation class, matching flags, directional split and the half of the station set.
  - continuous counters with the hourly GEH share and the shape of the profile, the seven screenlines, the county boundaries,
    the Key Bridge area
Static map (figures/validation_map.pdf and .png, article style): links by volume, mainline stations by ratio class, rings of
5, 10 and 20 km from downtown Baltimore, with a panel of the passenger ratio by ring.
Reads the outputs of validation_diagnostics.py (data/stations_diagnostics.csv, links_map.parquet, links_seed_stats.parquet,
stations_direction_volumes.csv, counters_direction_detail.csv, spatial_groups.csv), data/count_stations_split.csv and the
screenline geometry of screenlines.py.
Usage: python3 assignment/validation/validation_map.py   (env OUT, SCREEN_DATA)"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, json, re, numpy as np, pandas as pd, geopandas as gpd, shapely
from pyproj import Transformer
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"; ROOT = f"{PROJECT_ROOT}"   # H: validation data and outputs (workspace)
sys.path.insert(0, f"{MILES_HOME}/reports"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paperstyle as ps
import map_study_area as msa
WORK = f"{V}/5_reports/validation_pdfs/work/matsim_respec"
OUT = os.environ.get("OUT", H); DATA = f"{OUT}/data"; FIG = f"{OUT}/figures"; os.makedirs(FIG, exist_ok=True)
SD_DIR = os.environ.get("SCREEN_DATA", f"{WORK}/screenlines/data")
CRS = 26985; TF = Transformer.from_crs(CRS, 4326, always_xy=True); TB = Transformer.from_crs(4326, CRS, always_xy=True)
DOWNTOWN = (-76.6122, 39.2904); KEY_BRIDGE = (-76.5285, 39.2176)
VC = [(0, 1, "no modelled traffic"), (1, 1000, "1 to 1,000"), (1000, 5000, "1,000 to 5,000"), (5000, 20000, "5,000 to 20,000"), (20000, 50000, "20,000 to 50,000"), (50000, 1e12, "over 50,000")]
VCOL = ["#d9d8d2", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]; VWID = [0.6, 0.9, 1.5, 2.4, 3.4, 4.8]
HW = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "service", "other"]
HWLAB = {"motorway": "Motorway", "motorway_link": "Motorway ramp", "trunk": "Trunk road", "trunk_link": "Trunk-road ramp", "primary": "Primary road", "primary_link": "Primary ramp", "secondary": "Secondary road", "secondary_link": "Secondary ramp",
         "tertiary": "Tertiary road", "tertiary_link": "Tertiary ramp", "unclassified": "Unclassified road", "residential": "Residential street", "living_street": "Living street", "service": "Service road", "other": "Other"}
MAJOR = set(HW[:10]); DETAIL_VOL = 1000
CG = {h: (0 if h.startswith(("motorway", "trunk")) else 1 if h.startswith(("primary", "secondary")) else 2) for h in HW}      # class group of a link: freeway, arterial, collector-local
CGLAB = ["Links: freeways and their ramps", "Links: arterials (primary and secondary roads)", "Links: collectors and local streets (tertiary, residential, service)"]
FACLAB = {"freeway": "freeways", "arterial": "arterials", "collector": "collectors and local roads"}
MATCHED_STYLE = {"color": "#eda100", "weight": 5, "opacity": 0.75}


def vclass(v): return int(np.digitize(v, [1, 1000, 5000, 20000, 50000]))


def load():
    S = pd.read_csv(f"{DATA}/stations_diagnostics.csv", dtype={"LOCATION_ID": str, "link_NE": str, "link_SW": str}, low_memory=False)
    L = pd.read_parquet(f"{DATA}/links_map.parquet")
    D = pd.read_csv(f"{DATA}/counters_direction_detail.csv", dtype={"station": str, "mdot": str, "link": str})
    G = pd.read_csv(f"{DATA}/spatial_groups.csv")
    R = pd.read_parquet(f"{DATA}/links_seed_stats.parquet").set_index("link")
    SDV = pd.read_csv(f"{DATA}/stations_direction_volumes.csv", dtype={"LOCATION_ID": str, "link": str})
    SP = pd.read_csv(f"{V}/data/count_stations_split.csv", dtype={"LOCATION_ID": str}).drop_duplicates("LOCATION_ID").set_index("LOCATION_ID")["split"]
    return S, L, D, G, R, SDV, SP


def merged_lines(L):
    """One line per road segment: links that join the same two nodes (either direction) are merged; volumes summed, both ids kept."""
    L = L.copy(); L["key"] = np.where(L.f < L.t, L.f + "|" + L.t, L.t + "|" + L.f)
    L["vol_i"] = L.vol.round().astype(int).astype(str)
    if "freespeed" not in L: L["freespeed"] = np.nan
    g = L.groupby("key", sort=False)
    M = g.agg(ids=("link", ";".join), vols=("vol_i", ";".join), vol=("vol", "sum"), car=("car", "sum"), bus=("bus", "sum"), hw=("hw", "first"), name=("name", "first"), lanes=("lanes", "max"),
              capacity=("capacity", "max"), freespeed=("freespeed", "max"), length=("length", "first"), geometry=("geometry", "first"), stations=("stations", lambda s: ";".join(x for x in s.dropna() if x)))
    M["geom"] = shapely.from_wkt(M.geometry.values); M["hwcode"] = M.hw.fillna("other").map({h: i for i, h in enumerate(HW)}).fillna(len(HW) - 1).astype(int)
    M["vc"] = [vclass(v) for v in M.vol]
    return M.reset_index(drop=True)


def ratio_class(r):
    if not np.isfinite(r): return 7
    return int(np.digitize(r, ps.RATIO_BINS[1:-1]))


def coords_of(geom):
    xy = np.asarray(geom.coords); lon, lat = TF.transform(xy[:, 0], xy[:, 1]); return lat, lon


# ------------------------------------------------------------------------------------------------ interactive map
def interactive(S, L, D, M, R, SDV, SP):
    import folium
    from folium import FeatureGroup, GeoJson, GeoJsonTooltip
    m = folium.Map(location=[39.32, -76.62], zoom_start=10, tiles=None, prefer_canvas=True, control_scale=True)
    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", attr="Base map: Esri, HERE, Garmin, OpenStreetMap contributors",
                     name="Light base map", max_zoom=16).add_to(m)
    folium.TileLayer("openstreetmap", name="OpenStreetMap", show=False).add_to(m)
    o = (39.0, -77.0)
    def enc(lat, lon):
        c = np.round(np.column_stack([lat - o[0], lon - o[1]]).ravel() * 1e5).astype(int).tolist()
        if len(c) > 4:                         # drop nearly collinear vertices to keep the file small
            pts = np.column_stack([lat, lon]); keep = [0]
            for i in range(1, len(pts) - 1):
                a, b, p = pts[keep[-1]], pts[-1], pts[i]
                if abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / max(np.hypot(*(b - a)), 1e-9) > 3e-5: keep.append(i)
            keep.append(len(pts) - 1); c = np.round(np.column_stack([pts[keep, 0] - o[0], pts[keep, 1] - o[1]]).ravel() * 1e5).astype(int).tolist()
        return c
    # ---- links: compact arrays, drawn by a script after the page has loaded (one line per road segment, both directions)
    groups = [FeatureGroup(name=lab, show=True) for lab in CGLAB]
    for g in groups: g.add_to(m)
    fg_matched = FeatureGroup(name="Matched links of the count stations", show=True); fg_matched.add_to(m)
    fg_i695 = FeatureGroup(name="I-695 view: the Beltway and its stations only", show=False); fg_i695.add_to(m)
    try:        # mainline links of I-695 from the network audit (MDOT route of the link; ramps excluded)
        A = pd.read_parquet(f"{V}/data/network_audit_links.parquet", columns=["link", "hwy", "name", "mdot_route", "is_ramp"]).reset_index()
        i695_ids = set(A[(A.mdot_route == "IS 695") & A.hwy.isin(["motorway", "trunk"]) & ~A.is_ramp.fillna(False).astype(bool) & (A.name != "White Marsh Boulevard")]["link"].astype(str))
    except Exception as e: print("I-695 links:", e); i695_ids = set()
    matched_ids = set(S.link_NE.dropna()) | set(S.link_SW.dropna())
    detail = M.hw.isin(MAJOR) | (M.vol >= DETAIL_VOL) | M.ids.map(lambda s: any(x in matched_ids for x in s.split(";")))
    coords = []; attrs = []; segi = {}; i695_seg = []
    for i, r in enumerate(M.itertuples()):
        lat, lon = coords_of(r.geom); coords.append(enc(lat, lon))
        ids = r.ids.split(";"); a = [r.ids, int(round(r.vol)), int(r.hwcode), int(r.lanes), int(r.capacity), int(round(r.length)), r.vols, r.stations or ""]
        if any(k in i695_ids for k in ids): i695_seg.append(i)
        if detail.iloc[i]:
            rr = R.reindex(ids)
            a += [str(r.name) if isinstance(r.name, str) else "", int(round(r.freespeed * 3.6)) if np.isfinite(r.freespeed) else 0,
                  ";".join(f"{int(round(x.am_peak_vol))}@{int(x.am_peak_hour)}" for x in rr.itertuples()),
                  ";".join(f"{int(round(x.pm_peak_vol))}@{int(x.pm_peak_hour)}" for x in rr.itertuples())]
        attrs.append(a)
        for k in ids:
            if k in matched_ids: segi[k] = i
    # matched links, drawn one by one (direction-specific), with the stations they serve
    Li = L.set_index("link"); mld = []
    st_of_link = {}
    for r in S.itertuples():
        for k in (r.link_NE, r.link_SW):
            if isinstance(k, str): st_of_link.setdefault(k, []).append(r.LOCATION_ID)
    for k in sorted(matched_ids):
        if k not in Li.index: continue
        lat, lon = coords_of(shapely.from_wkt(Li.loc[k, "geometry"])); mld.append([k, enc(lat, lon), ";".join(st_of_link.get(k, []))])
    # station lookup for the link popups: id -> [road, class, observed all, observed passenger, model/count passenger, use]
    ST = {r.LOCATION_ID: [str(r.ROADNAME), str(r.cls), int(round(r.count_all)), int(round(r.count_pass)), round(float(r.ratio_pass), 2) if np.isfinite(r.ratio_pass) else None, str(r.use)] for r in S.itertuples()}
    LK = json.dumps(dict(o=list(o), c=coords, a=attrs, i695=i695_seg), separators=(",", ":")); MLD = json.dumps(mld, separators=(",", ":")); STJ = json.dumps(ST, separators=(",", ":")); SEGI = json.dumps(segi, separators=(",", ":"))
    # ---- stations: compact properties; popup table and hover highlight built by the script below
    S = S.copy(); S["rc"] = [ratio_class(r) for r in S.ratio_pass]; S["rc"] = np.where(S.near_zero.fillna(False), 7, S.rc)
    rcol = ps.RATIO_COLORS + ["#111111"]; rlab = ps.RATIO_LABELS + ["Model near zero"]
    dev = 100 * (S.model_all_mean - S.count_all).abs() / S.count_all
    S["dc"] = np.select([S.near_zero.fillna(False), dev <= S.fhwa_dev, S.ratio_all.between(0.75, 1.25), S.ratio_all < 0.75], [4, 0, 1, 2], 3)
    dcol = [ps.MODEL, "#86b6ef", ps.VARIANT, "#9c1d1c", "#111111"]; dlab = ["Within the FHWA desirable deviation", "Within 25 % of the count", "Outside, model below the count", "Outside, model above the count", "Model near zero"]
    S["geh_day"] = np.sqrt(2 * (S.model_all_mean / 24 - S.count_all / 24) ** 2 / np.maximum(S.model_all_mean / 24 + S.count_all / 24, 1e-9))
    dirv = {k: g for k, g in SDV.groupby("LOCATION_ID")}
    def feat(r, col, radius):
        g = dirv.get(r.LOCATION_ID); links = [] if g is None else [[x.dir, x.link, int(round(x["mean"]))] for _, x in g.sort_values("dir").iterrows()]
        yr = "counted in 2024" if r.counted24 else (f"estimate of the Administration, last count {2024 - int(r.count_age)}" if np.isfinite(r.count_age) else "estimate of the Administration")
        sp = f"north/east {r.NE_SPLIT:.0f} % / south/west {r.SW_SPLIT:.0f} %" if np.isfinite(r.NE_SPLIT) and np.isfinite(r.SW_SPLIT) else ""
        if r.use == "mainline": sp += " (two-way station, both links)" if len(links) == 2 else " (one-way count, link of the counted direction)" if len(links) == 1 else ""
        else: sp += " (ramp station, nearest ramp link)"
        p = dict(i=r.LOCATION_ID, r=str(r.ROADNAME), d=str(r.STATION_DESC) if isinstance(r.STATION_DESC, str) else "", c=str(r.county), k=str(r.cls), u=str(r.use), y=yr, sp=sp, n=int(r.NUM_LANES) if np.isfinite(r.NUM_LANES) else 0,
                 a=int(round(r.count_all)), t=round(100 * float(r.trk_sh), 1), b=round(100 * float(r.bus_sh), 1), p=int(round(r.count_pass)), mA=int(round(r.model_all_mean)),
                 mP=int(round(r.model_car_mean)), mB=int(round(r.model_bus_mean)) if np.isfinite(r.model_bus_mean) else 0, rA=round(float(r.ratio_all), 2), rP=round(float(r.ratio_pass), 2) if np.isfinite(r.ratio_pass) else None,
                 dv=dlab[int(r.dc)], fd=int(r.fhwa_dev), g=round(float(r.geh_day), 1), fl=str(r.match_flags) if isinstance(r.match_flags, str) else "", ct=str(r.match_category) if isinstance(r.match_category, str) else "",
                 tr=("doubtful" if r.doubtful else "weak" if r.weak else "accepted"), hf={"calibration_check": "check half", "held_out": "held-out half"}.get(SP.get(r.LOCATION_ID, ""), ""), L=links, col=col, radius=radius)
        return dict(type="Feature", geometry=dict(type="Point", coordinates=[round(r.lon, 6), round(r.lat, 6)]), properties=p)
    station_layers = []; default_station_layers = []
    def layer(d, name, colfun, radius=4.5, show=True, parent=None):
        fc = dict(type="FeatureCollection", features=[feat(r, colfun(r), radius) for r in d.itertuples()])
        gj = GeoJson(fc, name=name, show=show, marker=folium.CircleMarker(radius=radius, fill=True, fill_opacity=0.9, weight=0.6, color="#333333"),
                     style_function=lambda f: {"fillColor": f["properties"]["col"], "color": "#333333", "weight": 0.6, "fillOpacity": 0.9, "radius": f["properties"]["radius"]},
                     tooltip=GeoJsonTooltip(fields=["i", "r", "rP"], aliases=["Station", "Road", "Model/count, passenger"]))
        gj.add_to(parent if parent is not None else m); station_layers.append(gj)
        if show and parent is None: default_station_layers.append(gj)
        return gj
    ML = S[S.use == "mainline"]
    for fac in ["freeway", "arterial", "collector"]:
        layer(ML[ML.fac == fac], f"Stations on {FACLAB[fac]}: passenger model/count", lambda r: rcol[r.rc])
    for fac in ["freeway", "arterial", "collector"]:
        layer(ML[ML.fac == fac], f"Stations on {FACLAB[fac]}: deviation class", lambda r: dcol[r.dc], show=False)
    layer(S[S.use == "ramp"], "Ramp stations: passenger model/count", lambda r: rcol[r.rc], radius=3.5, show=False)
    gj_i695 = layer(ML[ML.cls == "Interstate: I-695"], "I-695 stations", lambda r: rcol[r.rc], radius=5.5, show=True, parent=fg_i695)   # inside the I-695 group, which is off by default
    layer(ML[ML.near_zero.fillna(False)], "Stations with almost no model traffic", lambda r: "#111111", radius=6, show=False)
    layer(ML[ML.doubtful.fillna(False)], "Doubtful station-to-link matches", lambda r: "#eda100", radius=6, show=False)
    js = f"""
window.addEventListener('load', function() {{
  var LK = {LK}; var MLD = {MLD}; var ST = {STJ}; var SEGI = {SEGI}; var map = {m.get_name()}; var G = [{', '.join(g.get_name() for g in groups)}];
  var FGM = {fg_matched.get_name()}; var FGI = {fg_i695.get_name()}; var SL = [{', '.join(g.get_name() for g in station_layers)}]; var SLD = [{', '.join(g.get_name() for g in default_station_layers)}]; var GJI = {gj_i695.get_name()};
  var CG = {json.dumps([CG[h] for h in HW])};
  var COL = {json.dumps(VCOL)}; var W = {json.dumps(VWID)}; var HW = {json.dumps([HWLAB[h] for h in HW])}; var MS = {json.dumps(MATCHED_STYLE)};
  function fmt(x) {{ return Math.round(x).toLocaleString(); }}
  function dec(c) {{ var pts = []; for (var j = 0; j < c.length; j += 2) pts.push([LK.o[0] + c[j] / 1e5, LK.o[1] + c[j + 1] / 1e5]); return pts; }}
  function cls(v) {{ return v < 1 ? 0 : v < 1000 ? 1 : v < 5000 ? 2 : v < 20000 ? 3 : v < 50000 ? 4 : 5; }}
  function row(k, v) {{ return '<tr><td style="padding:1px 10px 1px 0;color:#444;vertical-align:top">' + k + '</td><td style="text-align:right;white-space:nowrap">' + v + '</td></tr>'; }}
  function linkPopup(i, focus) {{
    var a = LK.a[i]; var ids = a[0].split(';'), vs = a[6].split(';'); var det = a.length > 8;
    var am = det ? a[10].split(';') : [], pm = det ? a[11].split(';') : [];
    var h = '<div style="font:12px Helvetica,Arial,sans-serif;max-width:430px"><b>Road segment' + (det && a[8] ? ': ' + a[8] : '') + '</b> (' + HW[a[2]] + ')' +
            '<table style="border-collapse:collapse;margin-top:4px;font-size:12px">' +
            row('Length / lanes per direction', a[5] + ' m / ' + a[3]) + row('Capacity per direction', fmt(a[4]) + ' veh/h') + (det ? row('Free speed', a[9] + ' km/h') : '') +
            row('<b>Modelled weekday volume, all vehicles, both directions</b>', '<b>' + fmt(a[1]) + '</b>');
    for (var q = 0; q < ids.length; q++) {{
      var lab = '&nbsp;&nbsp;link ' + ids[q] + (focus === ids[q] ? ' (this link)' : '');
      h += row(lab, fmt(vs[q]));
      if (det) {{ var a1 = am[q].split('@'), p1 = pm[q].split('@'); h += row('&nbsp;&nbsp;&nbsp;&nbsp;peak hour: morning / evening', fmt(a1[0]) + ' veh/h at ' + a1[1] + ':00 / ' + fmt(p1[0]) + ' veh/h at ' + p1[1] + ':00'); }}
    }}
    if (!det) h += row('<span style="color:#666">Name, free speed and peak hours are kept for matched links, main roads and segments above 1,000 vehicles</span>', '');
    if (a[7]) {{ a[7].split(';').forEach(function(s) {{ var t = ST[s]; if (t) h += row('Count station ' + s + ' (' + t[0] + ', ' + t[5] + ')', 'observed passenger ' + fmt(t[3]) + ', all vehicles ' + fmt(t[2]) + (t[4] !== null ? ', model ÷ count ' + t[4].toFixed(2) : '')); }}); }}
    return h + '</table></div>';
  }}
  for (var i = 0; i < LK.c.length; i++) {{ var a = LK.a[i], k = cls(a[1]); L.polyline(dec(LK.c[i]), {{color: COL[k], weight: W[k], opacity: 0.9, i: i}}).addTo(G[CG[a[2]]]); }}
  LK.i695.forEach(function(i) {{ var a = LK.a[i], k = cls(a[1]); L.polyline(dec(LK.c[i]), {{color: COL[k], weight: Math.max(W[k], 3), opacity: 0.95, i: i}}).addTo(FGI); }});
  G.concat([FGI]).forEach(function(g) {{ g.on('click', function(e) {{ if (e.layer.options.i === undefined) return; L.popup({{maxWidth: 460}}).setLatLng(e.latlng).setContent(linkPopup(e.layer.options.i, null)).openOn(map); }}); }});
  function i695View() {{ G.forEach(function(g) {{ map.removeLayer(g); }}); SL.forEach(function(g) {{ if (g !== GJI && map.hasLayer(g)) map.removeLayer(g); }});
    map.addLayer(FGI); map.addLayer(FGM); map.fitBounds(FGI.getBounds().pad(0.05)); }}
  function allView() {{ map.removeLayer(FGI); G.forEach(function(g) {{ map.addLayer(g); }}); SLD.forEach(function(g) {{ map.addLayer(g); }}); map.setView([39.32, -76.62], 10); }}
  document.getElementById('btn-i695').onclick = i695View; document.getElementById('btn-all').onclick = allView;
  var MLK = {{}};
  MLD.forEach(function(d) {{ var pl = L.polyline(dec(d[1]), Object.assign({{lid: d[0], sts: d[2]}}, MS)); pl.addTo(FGM); MLK[d[0]] = pl; }});
  FGM.on('click', function(e) {{ var id = e.layer.options.lid; var i = SEGI[id]; var h = (i !== undefined) ? linkPopup(i, id) : '<b>Link ' + id + '</b>';
    h += '<div style="font:12px Helvetica,Arial;margin-top:4px">Matched to station(s) ' + e.layer.options.sts.split(';').join(', ') + '</div>';
    L.popup({{maxWidth: 460}}).setLatLng(e.latlng).setContent(h).openOn(map); }});
  function stationPopup(p) {{
    var h = '<div style="font:12px Helvetica,Arial,sans-serif;max-width:440px"><b>Station ' + p.i + '</b> · ' + p.r + (p.d ? '<br><span style="color:#555">' + p.d + '</span>' : '') +
            '<br>' + p.k + ' · ' + p.c + ' · ' + (p.u === 'ramp' ? 'ramp station' : 'mainline station') + ' · ' + p.y + (p.n ? ' · ' + p.n + ' lanes' : '') +
            '<br>Directions: ' + p.sp + '<table style="border-collapse:collapse;margin-top:5px;font-size:12px">' +
            '<tr><td colspan=2 style="padding-top:3px"><b>Observed (weekday)</b></td></tr>' +
            row('&nbsp;&nbsp;All vehicles (AAWDT)', fmt(p.a)) + row('&nbsp;&nbsp;Truck share / bus share', p.t.toFixed(1) + ' % / ' + p.b.toFixed(1) + ' %') + row('&nbsp;&nbsp;Passenger vehicles (count less trucks and buses)', fmt(p.p)) +
            '<tr><td colspan=2 style="padding-top:5px"><b>Simulated on the matched link(s), weekday</b></td></tr>';
    p.L.forEach(function(l) {{ h += row('&nbsp;&nbsp;' + (l[0] === 'NE' ? 'North- or eastbound' : 'South- or westbound') + ', link ' + l[1], fmt(l[2])); }});
    h += row('&nbsp;&nbsp;<b>Total, all vehicles</b>', '<b>' + fmt(p.mA) + '</b>') + row('&nbsp;&nbsp;of which buses', fmt(p.mB)) + row('&nbsp;&nbsp;Passenger vehicles (cars)', fmt(p.mP)) +
         '<tr><td colspan=2 style="padding-top:5px"><b>Comparison</b></td></tr>' +
         row('&nbsp;&nbsp;Model ÷ count, all vehicles', p.rA.toFixed(2)) + row('&nbsp;&nbsp;Model ÷ count, passenger', p.rP === null ? '–' : p.rP.toFixed(2)) +
         row('&nbsp;&nbsp;Deviation class', p.dv + ' (desirable ±' + p.fd + ' %)') + row('&nbsp;&nbsp;GEH on the mean hourly flow (daily ÷ 24)', p.g.toFixed(1)) +
         '<tr><td colspan=2 style="padding-top:5px"><b>Matching</b></td></tr>' +
         row('&nbsp;&nbsp;Audit tier', p.tr) + row('&nbsp;&nbsp;Matcher flags / category', (p.fl || 'none') + (p.ct ? ' / ' + p.ct : '')) + row('&nbsp;&nbsp;Station set', p.hf || '–') +
         '</table><div style="color:#666;margin-top:3px">While this station is selected its matched link(s) blink on the map, with arrows in the direction of travel and a label with id, direction and simulated volume.</div></div>';
    return h;
  }}
  // ---- selected station: its matched links blink, carry direction arrows and a label with id, direction and simulated volume
  var HL = {{timer: null, links: [], station: null, arrows: L.layerGroup().addTo(map)}};
  var HOT = {{color: '#e34948', weight: 10, opacity: 1}}, HOT2 = {{color: '#fff200', weight: 12, opacity: 1}};
  function arrowIcon(angle) {{ return L.divIcon({{className: 'lk-arrow', html: '<svg width="20" height="20" viewBox="0 0 20 20" style="transform:rotate(' + angle + 'deg)"><path d="M3 10 L17 10 M11 4 L17 10 L11 16" stroke="#111" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M3 10 L17 10 M11 4 L17 10 L11 16" stroke="#fff" stroke-width="1.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>', iconSize: [20, 20], iconAnchor: [10, 10]}}); }}
  function addArrows(pl) {{
    var pts = pl.getLatLngs(); var segs = [], total = 0;
    for (var i = 0; i < pts.length - 1; i++) {{ var d = map.distance(pts[i], pts[i + 1]); segs.push(d); total += d; }}
    var fr = total > 600 ? [0.2, 0.5, 0.8] : total > 150 ? [0.3, 0.7] : [0.5];
    fr.forEach(function(f) {{ var target = f * total, acc = 0;
      for (var i = 0; i < segs.length; i++) {{
        if (acc + segs[i] >= target || i === segs.length - 1) {{
          var t = segs[i] > 0 ? Math.max(0, Math.min(1, (target - acc) / segs[i])) : 0; var a = pts[i], b = pts[i + 1];
          var pos = L.latLng(a.lat + t * (b.lat - a.lat), a.lng + t * (b.lng - a.lng)); var pa = map.latLngToLayerPoint(a), pb = map.latLngToLayerPoint(b);
          L.marker(pos, {{icon: arrowIcon(Math.atan2(pb.y - pa.y, pb.x - pa.x) * 180 / Math.PI), interactive: false, keyboard: false}}).addTo(HL.arrows); break; }}
        acc += segs[i]; }} }});
  }}
  function clearHL() {{ if (HL.timer) {{ clearInterval(HL.timer); HL.timer = null; }} HL.links.forEach(function(pl) {{ pl.setStyle(MS); pl.unbindTooltip(); }}); HL.links = []; HL.station = null; HL.arrows.clearLayers(); }}
  function startHL(p) {{
    clearHL(); if (!map.hasLayer(FGM)) map.addLayer(FGM); HL.station = p.i;
    p.L.forEach(function(l) {{ var pl = MLK[l[1]]; if (!pl) return; HL.links.push(pl); pl.bringToFront();
      pl.bindTooltip('link ' + l[1] + ' · ' + (l[0] === 'NE' ? 'north- or eastbound (NE)' : 'south- or westbound (SW)') + ' · ' + fmt(l[2]) + ' veh/weekday', {{permanent: true, direction: l[0] === 'NE' ? 'top' : 'bottom', className: 'lk-label', offset: [0, l[0] === 'NE' ? -8 : 8]}}).openTooltip();
      addArrows(pl); }});
    var on = false, n = 0;
    HL.timer = setInterval(function() {{ on = !on; HL.links.forEach(function(pl) {{ pl.setStyle(on ? HOT : HOT2); }});
      if (++n >= 15) {{ clearInterval(HL.timer); HL.timer = null; HL.links.forEach(function(pl) {{ pl.setStyle(HOT); }}); }} }}, 400);
    HL.links.forEach(function(pl) {{ pl.setStyle(HOT); }});
  }}
  function hover(p, on) {{ p.L.forEach(function(l) {{ var pl = MLK[l[1]]; if (pl && HL.links.indexOf(pl) < 0) {{ pl.setStyle(on ? HOT : MS); if (on) pl.bringToFront(); }} }}); }}
  SL.forEach(function(g) {{ g.eachLayer(function(l) {{ var p = l.feature.properties;
    l.bindPopup(function() {{ return stationPopup(p); }}, {{maxWidth: 480}});
    l.on('mouseover', function() {{ hover(p, true); }}); l.on('mouseout', function() {{ hover(p, false); }});
    l.on('popupopen', function() {{ startHL(p); }}); l.on('popupclose', function() {{ if (HL.station === p.i) clearHL(); }}); }}); }});
  window.__val = {{SL: SL, map: map, startHL: startHL, MLK: MLK, i695View: i695View, allView: allView, G: G, FGI: FGI, GJI: GJI}};
  SL.forEach(function(g) {{ if (map.hasLayer(g)) g.bringToFront(); }});
  map.on('overlayadd', function(e) {{ SL.forEach(function(g) {{ if (map.hasLayer(g)) g.bringToFront(); }}); }});
}});
"""
    m.get_root().html.add_child(folium.Element("<style>.lk-label{font:11px Helvetica,Arial,sans-serif;background:#fffbe6;border:1px solid #333;padding:2px 5px;border-radius:3px;white-space:nowrap}.lk-arrow{background:none;border:none}</style>"))
    m.get_root().html.add_child(folium.Element(f"<script>{js}</script>"))
    # ---- continuous counters
    try:
        STA = pd.read_csv(f"{V}/data/raw/tmas_2024/MD_2024 (TMAS).STA", sep="|", dtype=str).drop_duplicates("station_id").set_index("station_id")
        fg = FeatureGroup(name="Continuous counters (hourly GEH)", show=True)
        for st, d in D.groupby("station"):
            lat = float(STA.loc[st, "latitude"]) / 1e6; lon = -float(STA.loc[st, "longitude"]) / 1e6
            g5 = d.geh5_day.mean(); col = ps.MODEL if g5 >= 0.5 else "#86b6ef" if g5 >= 0.3 else ps.VARIANT if g5 >= 0.15 else "#9c1d1c"
            rows = ""
            for _, r in d.iterrows():
                rows += (f"<tr><td>{r['direction']}</td><td>{r['link']}</td><td>{r['count_day']:,.0f}</td><td>{r['model_day']:,.0f}</td><td>{r['ratio_day']:.2f}</td><td>{r['profile_corr']:.2f}</td><td>{100*r['geh5_day']:.0f} %</td>"
                         f"<td>{100*r['geh5_Morning peak']:.0f} / {100*r['geh5_Midday']:.0f} / {100*r['geh5_Evening peak']:.0f} / {100*r['geh5_Night']:.0f}</td><td>{r['verdict']}</td></tr>")
            html = (f"<b>Continuous counter {st[2:].lstrip('0')}, {d.road.iloc[0]}</b> ({d.cls.iloc[0]}; passenger vehicles, 2024 weekdays)<table style='font-size:11px;border-spacing:4px'>"
                    "<tr><th>Direction</th><th>Link</th><th>Count/day</th><th>Model/day</th><th>Ratio</th><th>Profile corr.</th><th>GEH&lt;5, day</th><th>GEH&lt;5 AM / midday / PM / night (%)</th><th>Verdict</th></tr>" + rows + "</table>")
            icon = folium.DivIcon(html=f"<div style='width:13px;height:13px;background:{col};border:1.5px solid #111;transform:rotate(45deg);box-shadow:0 0 2px #fff'></div>", icon_size=(13, 13), icon_anchor=(7, 7))
            folium.Marker(location=[lat, lon], icon=icon, popup=folium.Popup(html, max_width=640), tooltip=f"Counter {st[2:].lstrip('0')}, {d.road.iloc[0]}").add_to(fg)
        fg.add_to(m)
    except Exception as e: print("counters layer:", e)
    # ---- screenlines
    try:
        from shapely.geometry import shape
        F = [f for f in json.load(open(f"{SD_DIR}/screenlines_definition.geojson"))["features"] if f["properties"].get("kind") == "screenline"]
        SLG = gpd.GeoDataFrame([f["properties"] for f in F], geometry=[shapely.geometry.LineString(shape(f["geometry"]).coords) if f["geometry"]["type"] == "LinearRing" else shape(f["geometry"]) for f in F], crs=CRS).to_crs(4326)
        T = pd.read_csv(f"{SD_DIR}/screenline_table.csv"); T = T[T.section == "all"].set_index("sl")
        fg = FeatureGroup(name="Screenlines", show=True)
        for r in SLG.itertuples():
            t = T.loc[int(r.sl)]; col = ps.CAT[int(r.sl)]
            html = f"<b>S{int(r.sl)} {r.name}</b><br>Counted crossings: {int(t.counted)} of {int(t.crossings)}<br>Count {t.count_all:,.0f}, model {t.model_all:,.0f} vehicles per weekday<br>Model/count: {t.ratio_all:.2f} (all vehicles), {t.ratio_pass:.2f} (passenger)"
            folium.GeoJson(shapely.geometry.mapping(r.geometry), style_function=lambda f, c=col: {"color": c, "weight": 4, "opacity": 0.85}, tooltip=f"S{int(r.sl)} {r.name}", popup=folium.Popup(html, max_width=320)).add_to(fg)
        fg.add_to(m)
    except Exception as e: print("screenlines layer:", e)
    # ---- counties and the Key Bridge area
    c6 = gpd.read_file(f"{MATSIM_HOME}/data/bmr_counties.gpkg").to_crs(CRS); c6["geometry"] = c6.geometry.simplify(60); c6 = c6.to_crs(4326)
    folium.GeoJson(json.loads(c6[["NAME", "geometry"]].to_json()), name="County boundaries", style_function=lambda f: {"color": "#333333", "weight": 1.6, "fill": False, "dashArray": "6 4"}, tooltip=GeoJsonTooltip(fields=["NAME"], labels=False)).add_to(m)
    near = ML[ML.key_bridge_km <= 5]
    fg = FeatureGroup(name="Key Bridge area (closed since March 2024)", show=True)
    folium.Circle(location=[KEY_BRIDGE[1], KEY_BRIDGE[0]], radius=5000, color="#9c1d1c", weight=1.5, fill=True, fill_opacity=0.06, dash_array="4 4",
                  popup=folium.Popup(f"<b>Key Bridge area</b> (5 km around the bridge). The bridge is closed in the 2024 network. {len(near)} mainline stations lie in this circle; {int(near.counted24.sum())} were counted in 2024, "
                                     f"the others carry estimates grown from counts made before the closure and do not show the diverted traffic. Model/count of the {len(near)} stations: {near.model_all_mean.sum()/near.count_all.sum():.2f} (all vehicles), "
                                     f"{near[near.counted24].model_all_mean.sum()/max(near[near.counted24].count_all.sum(),1):.2f} at the stations counted in 2024.", max_width=360)).add_to(fg)
    folium.Marker(location=[KEY_BRIDGE[1], KEY_BRIDGE[0]], icon=folium.Icon(color="darkred", icon="remove", prefix="glyphicon"), tooltip="Francis Scott Key Bridge (closed)").add_to(fg)
    fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    # ---- title and legend
    sw = lambda c, w=14, h=4: f"<span style='display:inline-block;width:{w}px;height:{h}px;background:{c};vertical-align:middle;margin-right:6px'></span>"
    dot = lambda c: f"<span style='display:inline-block;width:10px;height:10px;border-radius:5px;background:{c};border:1px solid #333;vertical-align:middle;margin-right:6px'></span>"
    n_ml = len(ML); n_rp = int((S.use == "ramp").sum()); r_all = ML.model_all_mean.sum() / ML.count_all.sum(); r_pass = ML.model_car_mean.sum() / ML.count_pass.sum()
    legend = f"""
<div style="position: fixed; bottom: 18px; left: 12px; z-index: 9999; background: rgba(255,255,255,0.94); padding: 10px 12px; border: 1px solid #999; border-radius: 4px; font: 12px Helvetica, Arial, sans-serif; max-width: 330px; line-height: 1.45">
<div style="font-size:14px;font-weight:bold;margin-bottom:4px">Traffic assignment against the 2024 counts, Baltimore region</div>
<div style="color:#444;margin-bottom:6px">Residents' weekday traffic of our model (every simulated volume on this map is the mean of five runs) on every network link, and the {n_ml:,} mainline count stations ({n_rp:,} ramp stations in a separate layer). Model/count over all mainline stations: {r_all:.2f} all vehicles, {r_pass:.2f} passenger vehicles. Click a link or a station for its observed and simulated traffic; hovering over a station highlights its matched links.</div>
<div style="margin-bottom:6px"><button id="btn-i695" style="font:12px Helvetica,Arial;padding:3px 8px;cursor:pointer">I-695 view</button> <button id="btn-all" style="font:12px Helvetica,Arial;padding:3px 8px;cursor:pointer">All roads</button>
<span style="color:#444"> — the layer list (top right) switches freeways, arterials and collectors/local streets on and off, links and stations alike</span></div>
<div style="font-weight:bold">Modelled volume (vehicles per weekday, both directions)</div>
{''.join(f"<div>{sw(VCOL[i], 18, max(2, int(VWID[i]*1.3)))}{lab}</div>" for i, (_, _, lab) in enumerate(VC))}
<div>{sw(MATCHED_STYLE['color'], 18, 5)}Matched link of a count station (red when selected)</div>
<div style="font-weight:bold;margin-top:6px">Station: model ÷ count, passenger vehicles</div>
{''.join(f"<div>{dot(rcol[i])}{rlab[i]}</div>" for i in range(len(rlab)))}
<div style="margin-top:6px"><span style='display:inline-block;width:10px;height:10px;background:{ps.MODEL};border:1px solid #333;transform:rotate(45deg);margin-right:8px'></span>Continuous counter (colour: share of hours with GEH below 5: blue over 50 %, light blue 30–50 %, orange 15–30 %, red below 15 %)</div>
<div>{sw('#333333', 18, 2)}County boundary &nbsp; {sw(ps.CAT[1], 18, 4)} Screenline</div>
</div>"""
    m.get_root().html.add_child(folium.Element(legend))
    m.get_root().html.add_child(folium.Element("<title>Traffic assignment against the 2024 counts, Baltimore region</title>"))
    out = f"{FIG}/validation_map.html"; m.save(out)
    mb = os.path.getsize(out) / 1e6; print(f"{out}: {mb:.1f} MB, {len(M):,} road segments ({int(detail.sum()):,} with name, free speed and peak hours), {len(mld):,} matched links, {len(i695_seg):,} I-695 segments, {n_ml:,} mainline stations")
    return out


# ------------------------------------------------------------------------------------------------ static map
def static(S, M, G):
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Circle
    from matplotlib.collections import LineCollection
    halo = [pe.withStroke(linewidth=2.4, foreground="white")]
    c6, nb = msa.counties(); x0, x1, y0, y1 = msa.EXTENT
    fig = ps.new_figure(6.55); ax = fig.add_axes([0.0, 0.30, 1.0, 0.655]); ax.set_facecolor(msa.WATER)
    nb.assign(geometry=nb.geometry.simplify(40)).plot(ax=ax, facecolor=msa.LAND_OUT, edgecolor="#c9c7bf", lw=0.4, zorder=0)
    c6.assign(geometry=c6.geometry.simplify(40)).plot(ax=ax, facecolor=msa.LAND_IN, edgecolor="none", zorder=0)
    # links by volume class (links below 500 vehicles per weekday are not drawn), rasterised to keep the PDF small
    widths = [0, 0.25, 0.45, 0.85, 1.4, 2.1]
    for k in range(1, 6):
        d = M[(M.vc == k) & (M.vol >= 500)]
        if not len(d): continue
        segs = [np.asarray(g.coords) for g in d.geom]
        ax.add_collection(LineCollection(segs, colors=VCOL[k], linewidths=widths[k], zorder=1 + k, capstyle="round", rasterized=True))
    c6.boundary.plot(ax=ax, color=ps.INK, lw=0.6, zorder=8)
    # rings
    dx, dy = TB.transform(*DOWNTOWN)
    for rk in (5, 10, 20): ax.add_patch(Circle((dx, dy), rk * 1e3, fill=False, edgecolor=ps.INK2, lw=0.7, ls=(0, (3, 2)), zorder=9))
    for rk, t in [(5, "5 km"), (10, "10 km"), (20, "20 km")]: ax.text(dx + rk * 1e3 * 0.707 + 300, dy + rk * 1e3 * 0.707 + 300, t, fontsize=ps.TICK, color=ps.INK2, path_effects=halo, zorder=12)
    # stations
    ML = S[S.use == "mainline"].copy(); ML["rc"] = [ratio_class(r) for r in ML.ratio_pass]
    order = [3, 2, 4, 1, 5, 0, 6]      # near 1.0 first, extremes on top
    for k in order:
        d = ML[(ML.rc == k) & ~ML.near_zero.fillna(False)]
        ax.scatter(d.x, d.y, s=5, color=ps.RATIO_COLORS[k], lw=0, zorder=10 + (0 if k == 3 else 1))
    z = ML[ML.near_zero.fillna(False)]; ax.scatter(z.x, z.y, s=9, marker="x", color="#111111", lw=0.6, zorder=12)
    kb = TB.transform(*KEY_BRIDGE); ax.scatter([kb[0]], [kb[1]], marker="X", s=36, color=ps.INK, edgecolor="white", lw=0.6, zorder=13)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.grid(False); ax.set_xlabel(""); ax.set_ylabel("")
    for sp in ax.spines.values(): sp.set_visible(True); sp.set_color(ps.AXIS); sp.set_linewidth(0.6)
    for t, xx, yy in [("Carroll", 388000, 212000), ("Baltimore\nCounty", 427000, 216000), ("Harford", 462000, 216000), ("Howard", 396000, 170000), ("Anne\nArundel", 441000, 136000)]:
        ax.text(xx, yy, t, ha="center", va="center", fontsize=ps.FONT, color=ps.INK, fontweight="bold", path_effects=halo, zorder=14)
    for t, xx, yy in [("Pennsylvania", 410000, 231500), ("Chesapeake\nBay", 455000, 122000), ("Baltimore City", 424500, 173500)]:
        ax.text(xx, yy, t, ha="center", va="center", fontsize=ps.TICK, color=ps.INK if "City" in t else ps.MUTED, style="normal" if "City" in t else "italic", fontweight="bold" if "City" in t else "normal", path_effects=halo, zorder=14)
    xs, ys, km = 369000, 108000, 20
    ax.plot([xs, xs + km * 1e3], [ys, ys], color=ps.INK, lw=1.2, solid_capstyle="butt", zorder=15)
    for xx in (xs, xs + km * 1e3): ax.plot([xx, xx], [ys - 600, ys + 600], color=ps.INK, lw=0.8, zorder=15)
    ax.text(xs + km * 5e2, ys + 1500, f"{km} km", ha="center", va="bottom", fontsize=ps.TICK, color=ps.INK, path_effects=halo, zorder=15)
    ax.annotate("", xy=(xs + km * 1.4e3, ys + 9000), xytext=(xs + km * 1.4e3, ys + 1000), arrowprops=dict(arrowstyle="-|>", color=ps.INK, lw=1.0), zorder=15)
    ax.text(xs + km * 1.4e3, ys + 9800, "N", ha="center", va="bottom", fontsize=ps.FONT, color=ps.INK, fontweight="bold", path_effects=halo, zorder=15)
    ax.text(x1 - 1500, y0 + 1500, "Roads: © OpenStreetMap contributors", ha="right", va="bottom", fontsize=ps.TICK, color=ps.MUTED, path_effects=halo, zorder=15)
    # panel (b): passenger ratio by ring
    ax2 = fig.add_axes([0.105, 0.095, 0.27, 0.15])
    Rg = G[(G.dimension == "Ring") & G.fac.isna()].reset_index(drop=True); xx = np.arange(len(Rg))
    ax2.bar(xx, Rg.ratio_pass, 0.6, color=[ps.ratio_color(v) for v in Rg.ratio_pass], edgecolor=ps.INK2, lw=0.4)
    ax2.axhline(1, color=ps.OBSERVED, lw=0.8); ax2.set_xticks(xx); ax2.set_xticklabels([f"{g.replace(' km', '').replace('over ', '> ')}\n({int(n)})" for g, n in zip(Rg.group, Rg.n)], fontsize=ps.TICK)
    ax2.set_ylim(0, 1.15); ax2.set_yticks([0, 0.5, 1.0]); ax2.set_ylabel("Model ÷ count,\npassenger (–)"); ax2.set_xlabel("Distance from downtown (km)\nand number of stations")
    # legend
    hv = [Line2D([], [], color=VCOL[k], lw=max(widths[k] * 2, 0.8), label=VC[k][2]) for k in range(1, 6)]
    hr = [Line2D([], [], marker="o", ls="", color=ps.RATIO_COLORS[k], ms=4, label=ps.RATIO_LABELS[k]) for k in range(7)] + [Line2D([], [], marker="x", ls="", color="#111111", ms=4, mew=0.8, label="Model near zero")]
    ho = [Line2D([], [], color=ps.INK2, lw=0.7, ls=(0, (3, 2)), label="5, 10, 20 km from downtown"), Line2D([], [], marker="X", ls="", color=ps.INK, ms=5, label="Key Bridge (closed 2024)")]
    l1 = fig.legend(handles=hv, title="Modelled volume\n(vehicles per weekday, both directions)", loc="lower left", bbox_to_anchor=(0.42, 0.14), fontsize=ps.TICK, title_fontsize=ps.TICK, frameon=False, ncol=1, handlelength=2.2)
    l2 = fig.legend(handles=hr, title="Station: model ÷ count\n(passenger vehicles)", loc="lower left", bbox_to_anchor=(0.72, 0.04), fontsize=ps.TICK, title_fontsize=ps.TICK, frameon=False, ncol=1)
    l3 = fig.legend(handles=ho, loc="lower left", bbox_to_anchor=(0.42, 0.03), fontsize=ps.TICK, frameon=False, ncol=1)
    for l in (l1, l2, l3): l._legend_box.align = "left"
    ps.finish(fig, f"{FIG}/validation_map", panel_labels="ab")


def main():
    S, L, D, G, R, SDV, SP = load(); M = merged_lines(L); print(f"{len(L):,} car links -> {len(M):,} road segments")
    static(S, M, G)
    interactive(S, L, D, M, R, SDV, SP)


if __name__ == "__main__": main()
