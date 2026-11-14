#!/usr/bin/env python3
"""Figures of the 2024 forecast test.  Visual system: composite.py.  Every panel comes from ONE model version: the model of
record with the estimated tour mode choice (temporal_2024 T24_MODEL=mc, runs mc_*), ten replications per setting.

    python3 reports/composites/fig_forecast.py [forecast s_t24_workplace s_t24_county_mode]

Article
  fig_forecast        2024 forecast validation, frozen model: (a) departure from home to work by hour against the ACS 2024,
                      (b)-(d) start-time distribution of shopping, other and return-home activities against the ATUS 2021-2024
                      Maryland weekday diaries (TASHA Fig. 6 form, KS in each panel), (e) travel time to work, (f) mode to work;
                      model on the observed 2024 population (mean and
                      90 % band of the replications) and on the forecast 2024 population of the land-use model
Supplementary Material
  fig_s_t24_workplace     workers employed in their home county or county group: model on the observed and the forecast
                          population against ACS 2024 and LODES 2022
  fig_s_t24_county_mode   commute mode share by Maryland county, model (observed 2024 population) against ACS 2024:
                          (a) car driver, (b) the other modes
Data: activity/lib/reporting_2024/report.py (run with T24_NO_OUTPUT=1: nothing is rewritten) and
activity/lib/mode_choice/mc_t24.py -> results/t24_commute_mode_county.csv (same mc runs).
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
os.environ["T24_MODEL"] = "mc"; os.environ["T24_NO_OUTPUT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import composite as K   # noqa: E402
ps = K.ps; V = K.V
sys.path.insert(0, f"{ORIOLE_HOME}/activity/lib/reporting_2024")
import numpy as np, pandas as pd   # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator   # noqa: E402
import report as R   # noqa: E402
import fig_abit_tasha as TS   # noqa: E402  (KS text and y-limit helpers of the TASHA-form figures)

KEY = "Maryland|workers"
MODES = ["Car, driver", "Car, passenger", "Bus", "Rail", "Walk", "Bicycle"]
MLAB = {"Car, driver": "Car driver", "Car, passenger": "Car passenger", "Bus": "Bus", "Rail": "Rail", "Walk": "Walk", "Bicycle": "Bicycle"}
SHORT = {"Allegany + Garrett + Washington": "Western Maryland", "Caroline + Dorchester + Kent + Queen Anne's + Talbot": "Upper and Mid Shore",
         "Somerset + Wicomico + Worcester": "Lower Shore", "Calvert + St. Mary's": "Calvert, St Mary's", "Baltimore": "Baltimore County"}
H_OBS_POP = "Model, observed 2024 population"; H_FC_POP = "Model, forecast 2024 population"


def start_panel(fig, ax, obs, metric, typ, key, xlabel):
    """TASHA Fig. 6 form: start-time distribution (share of the 24-h frequency by hour), observed steps, model on the observed 2024
    population (mean and 90 % band), model on the forecast population (light blue, dashed); Roorda's KS (observed population)."""
    x = np.arange(24); H = R.HOUR_ORDER
    m = 100 * R.hser(R.G["acs2024"], key, metric, typ).loc[H].fillna(0).values
    sd = 100 * R.hser(R.G["acs2024"], key, metric, typ, "std").loc[H].fillna(0).values
    f = 100 * R.hser(R.G["silo2024"], key, metric, typ).loc[H].fillna(0).values
    K.obs_steps(ax, obs); K.model_line(ax, x, f, color=K.LIGHT_MODEL, ls=(0, (4, 2)), zorder=3); K.model_line(ax, x, m, sd=sd)
    ax.set_xticks(np.arange(0, 24, 4)); ax.set_xticklabels([str(h) for h in H[::4]]); ax.set_xlim(-0.5, 23.5); ax.grid(axis="x", visible=False)
    ax.set_xlabel(xlabel)
    ax.set_ylim(0, max(obs.max(), (m + K.Z90 * sd).max(), f.max()) * 1.08); TS.nice(ax)
    nz = (m > 0) | (obs > 0); D, P, _ = R.C.ks_values(m[nz], obs[nz])
    TS.ks_box(fig, ax, D, P, [(x, obs), (x, m + K.Z90 * sd), (x, f)])
    return D, P


def fig_forecast(A):
    fig = K.new(4.7); a, d1, d2, d3, b, c = K.grid(fig, 2, 3); H = R.HOUR_ORDER; ks = {}
    # (a) work: departure from home, ACS 2024; (b)-(d) start time of shopping, other, return home, ATUS 2021-2024 Maryland diaries
    ks["WORK"] = start_panel(fig, a, 100 * A["oh"].loc[H].fillna(0).values, "commute_dep_share", "WORK", KEY, "Departure from home (h)")
    a.set_ylabel("Share of commuters (%)")
    for ax, ty in [(d1, "SHOPPING"), (d2, "OTHER"), (d3, "HOME")]:
        ov = 100 * R.ohser(A["H_md24"], "Maryland|15+", "start_share", ty).fillna(0).loc[H].values
        ks[ty] = start_panel(fig, ax, ov, "start_share", ty, "Maryland|15+", "Activity start time (h)")
    for ax in (d1, d2, d3): ax.set_ylabel("Share of activities (%)")
    # (e) travel time
    TT = R.C.TT_LABELS; x = np.arange(len(TT))
    o = A["acsT"]; o = o[(o.vintage == "acs2024") & (o.area == "Maryland")].set_index("bin").share.reindex(TT).values
    get = lambda s, col="mean": R.G[s]["H"][(R.G[s]["H"].key == KEY) & (R.G[s]["H"].metric == "commute_tt_share")].set_index("type")[col].reindex(TT).values
    K.obs_steps(b, 100 * o); K.model_line(b, x, 100 * get("silo2024"), color=K.LIGHT_MODEL, ls=(0, (4, 2)), zorder=3)
    K.model_line(b, x, 100 * get("acs2024"), sd=np.nan_to_num(100 * get("acs2024", "std")))
    K.cat_axis(b, [t if i % 2 == 0 else "" for i, t in enumerate(TT)], rotate=True); b.set_xlabel("Travel time to work (min)"); b.set_ylim(0, 20); b.set_yticks([0, 5, 10, 15, 20])
    # (f) commute mode, log share axis (shares from 0.4 % to 85 %)
    x = np.arange(len(MODES))
    obs = 100 * A["am"].reindex(MODES).share.values
    mo = np.array([100 * R.sval(R.G["acs2024"], KEY, "commute_mode", m_) for m_ in MODES]); mf = np.array([100 * R.sval(R.G["silo2024"], KEY, "commute_mode", m_) for m_ in MODES])
    c.plot(x - 0.2, obs, "s", ms=K.MS - 0.4, color=K.OBSERVED, zorder=4); c.plot(x, mo, "o", ms=K.MS, color=K.MODEL, zorder=5)
    c.plot(x + 0.2, mf, "D", ms=K.MS - 0.6, color=K.LIGHT_MODEL, mec=K.MODEL, mew=0.4, zorder=4)
    K.cat_axis(c, [MLAB[m_] for m_ in MODES], rotate=True)
    c.set_yscale("log"); c.set_ylim(0.2, 100); c.yaxis.set_major_locator(FixedLocator([0.3, 1, 3, 10, 30, 100])); c.yaxis.set_minor_locator(NullLocator())
    c.set_yticklabels(["0.3", "1", "3", "10", "30", "100"]); c.set_ylabel("Share of commuters (%)")
    b.set_ylabel("Share of commuters (%)")
    K.title(a, "a", "Work: departure"); K.title(d1, "b", "Shopping"); K.title(d2, "c", "Other"); K.title(d3, "d", "Return home")
    K.title(b, "e", "Travel time to work"); K.title(c, "f", "Mode to work")
    K.legend(fig, [K.Line2D([], [], color=K.OBSERVED, lw=K.LW_OBS, marker="s", ms=K.MS - 0.4, label="Observed"),
                   K.Line2D([], [], color=K.MODEL, lw=K.LW_MODEL, marker="o", ms=K.MS, label=H_OBS_POP), K.h_band("Model, 90 % band of 10 replications"),
                   K.Line2D([], [], color=K.LIGHT_MODEL, lw=K.LW_MODEL, ls=(0, (4, 2)), marker="D", ms=K.MS - 0.6, mec=K.MODEL, mew=0.4, label=H_FC_POP)], ncol=2)
    print("KS start time, observed population (panels):", {k: (round(v[0], 3), round(v[1], 3)) for k, v in ks.items()})
    print("KS departure, report.py:", {k: (round(v[0], 3), round(v[1], 3)) for k, v in A["ks"].items() if not k.endswith("_tw")})
    print("modes obs/model/forecast:", dict(zip(MODES, zip(obs.round(1), mo.round(1), mf.round(1)))))
    return K.save(fig, "fig_forecast")


def s_workplace(A):
    sh, order = A["sh"], A["order"]; lab = {u: SHORT.get(l, l) for u, l in A["lab"].items()}
    fig = K.new(3.4); ax = fig.add_subplot(1, 1, 1); y = K.rows_axis(ax, [lab.get(u, str(u)) for u in order])
    for col, mk, off, kw in [("ACS 2024", "s", 0.27, dict(color=K.OBSERVED)), ("LODES 2022", "^", 0.09, dict(color="white", mec=K.OBSERVED, mew=0.9)),
                             ("model", "o", -0.09, dict(color=K.MODEL)), ("model_silo", "D", -0.27, dict(color=K.LIGHT_MODEL, mec=K.MODEL, mew=0.4))]:
        if col in sh: ax.plot(100 * sh[col].reindex(order).values, y + off, mk, ls="", ms=K.MS - (0.6 if mk == "D" else 0), zorder=4, **kw)
    ax.set_xlim(0, 100); ax.set_xticks([0, 20, 40, 60, 80, 100]); ax.set_xlabel("Workers employed in their home county or county group (%)")
    K.legend(fig, [K.h_obs_dot("Observed, ACS 2024"), K.Line2D([], [], marker="^", ls="", ms=K.MS, color="white", mec=K.OBSERVED, mew=0.9, label="Observed, LODES 2022"),
                   K.h_model_dot(H_OBS_POP), K.Line2D([], [], marker="D", ls="", ms=K.MS - 0.6, color=K.LIGHT_MODEL, mec=K.MODEL, mew=0.4, label=H_FC_POP)], ncol=2)
    return K.save(fig, "fig_s_t24_workplace")


def s_county_mode():
    r = pd.read_csv(f"{V}/3_abit/mode_choice/results/t24_commute_mode_county.csv")
    fig = K.new(2.9); a, b = K.grid(fig, 1, 2)
    for ax, modes, lo, hi in [(a, ["Car, driver"], 40, 100), (b, MODES[1:], 0, 25)]:
        ax.plot([lo, hi], [lo, hi], color=ps.INK2, lw=0.7, zorder=1)
        for i, m_ in enumerate(modes):
            d = r[r["mode"] == m_]; col = K.MODEL if m_ == "Car, driver" else ps.CAT[i + 1]
            ax.scatter(100 * d.acs, 100 * d.model, s=12, color=col, lw=0, zorder=3)
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("Observed share, ACS 2024 (%)"); ax.set_ylabel("Model share (%)")
    K.title(a, "a", "Car driver"); K.title(b, "b", "Other modes")
    K.legend(fig, [K.Line2D([], [], marker="o", ls="", ms=K.MS, color=K.MODEL if m_ == "Car, driver" else ps.CAT[i], label=MLAB[m_]) for i, m_ in enumerate(MODES)]
             + [K.Line2D([], [], color=ps.INK2, lw=0.7, label="Equality")], ncol=4)
    return K.save(fig, "fig_s_t24_county_mode")


if __name__ == "__main__":
    w = sys.argv[1:] or ["forecast", "s_t24_workplace", "s_t24_county_mode"]
    A = R.main() if {"forecast", "s_t24_workplace"} & set(w) else None
    print("model version: T24_MODEL =", R.C.MODEL, "| replications:", {k: R.G[k]["n"] for k in R.G})
    if "forecast" in w: print(fig_forecast(A))
    if "s_t24_workplace" in w: print(s_workplace(A))
    if "s_t24_county_mode" in w: print(s_county_mode())
