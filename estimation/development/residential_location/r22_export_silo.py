#!/usr/bin/env python3
"""Two-level residential location model, revised PUMA level (r22_final.py) for SILO (2026-11-19): export-ready engine files (suffix
_1119g, written to this folder) and the inputs of the Java unit check (r22_verify/).  Nothing of r14 / r19 / r20 / r22 is edited.

Engine files:
  resloc_dwelling_coef_1119g.csv  variable,value   the 18 dwelling-level coefficients (unchanged, = resloc_dwelling_coef_1118m.csv)
  resloc_puma_coef_1119g.csv      variable,value   the 14 PUMA-level coefficients of r22_coef.csv + IVd = 1.  New terms (U_p additions):
        lnddens_x_single   b x lnddens_p x [household size = 1]
        lnddens_x_young35  b x lnddens_p x [age of the oldest member < 35]
        lnddens_x_lninc    b x lnddens_p x ln(max(income, 5000) / 50000)   (2016 $)
        core_share         b x core_p,  core_p = sum_z Wn_zp [county of zone z is 11001 (DC) or 24510 (Baltimore City)]
                           (Wn_zp = w_attr_zp x current dwellings of z / sum over the PUMA's zones: the weights of the other PUMA
                           attributes; recomputed every year like lnddens)
  resloc_zone_core_1119g.csv      zone,core        1 for the zones of DC and Baltimore City (zoneSystem COUNTYFIPS 11001, 24510)
  resloc_puma_core_1119g.csv      puma7,core_share_2016   core_p with the 2016 dwellings (check only)
  The zone, migration-zone, zone-attribute, adjacency and turnover files are unchanged (_1118m).
Java check (r22_verify/): as r18_export_silo.py, for 300 movers of the estimation half: dwelling level (their 30 sampled alternatives)
and PUMA level (every PUMA; the 200 IV dwellings per PUMA as drawn; M = turnover x 2016 dwellings), with the 2016 zone inputs;
Python utilities X b + IVd; puma_hh.csv adds size, age of the oldest member (age_max) and income.
    python3 r22_export_silo.py              -> engine files + r22_verify/*
    python3 r22_export_silo.py check DIR    -> compares DIR/java_dwelling.csv, DIR/java_puma.csv -> r22_java_check_{dwelling,puma}.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
ARGS = list(sys.argv)
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import r22_city_bias as B     # noqa: E402  (r20 crosswalk, r19_final functions)
import r22_final as RF        # noqa: E402
F, R = B.F, B.R
from rc import MICRO, INP, ZONE_IDS   # noqa: E402
VD = f"{HERE}/r22_verify"; SUF = "1119g"
RENAME = {"lnddens_x_young": "lnddens_x_young35", "core": "core_share"}
RACES = ["white", "black", "hispanic", "other"]


def coefs():
    co = pd.read_csv(f"{HERE}/r20_coef.csv"); bdw = co[co.level == "dwelling"].set_index("param").coef.reindex(F.DWF)
    c22 = pd.read_csv(f"{HERE}/r22_coef.csv").set_index("param").coef
    names = list(c22.index)
    return bdw, c22, names


def write(path, df, notes):
    with open(path, "w") as f:
        for n in notes: f.write("# " + n + "\n")
        df.to_csv(f, index=False)
    print(f"wrote {os.path.basename(path)} ({len(df)} rows)")


class Rec:
    def __init__(self, rng): self.rng, self.draws = rng, []
    def choice(self, *a, **k):
        x = self.rng.choice(*a, **k); self.draws.append(np.array(x)); return x


def main():
    bdw, c22, names = coefs()
    d0 = pd.read_csv(f"{HERE}/resloc_dwelling_coef_1118m.csv"); assert np.allclose(d0.set_index("variable").value.reindex(F.DWF).values, bdw.values)
    pd.DataFrame({"variable": F.DWF, "value": bdw.values}).to_csv(f"{HERE}/resloc_dwelling_coef_{SUF}.csv", index=False)
    pc = pd.DataFrame({"variable": [RENAME.get(n, n) for n in names] + ["IVd"], "value": list(c22.values) + [1.0]})
    pc.to_csv(f"{HERE}/resloc_puma_coef_{SUF}.csv", index=False); print(pc.to_string(index=False))
    zs = pd.read_csv(f"{INP}/zoneSystem.csv").set_index("ZoneId").reindex(ZONE_IDS)
    write(f"{HERE}/resloc_zone_core_{SUF}.csv", pd.DataFrame({"zone": ZONE_IDS, "core": np.isin(zs.COUNTYFIPS.values, B.CORE).astype(int)}),
          ["core city zones of the PUMA term core_share (r22_final.py): 1 = zone in DC (11001) or Baltimore City (24510), zoneSystem COUNTYFIPS",
           "core_share_p = sum over the PUMA's zones of Wn_zp x core_z (Wn: w_attr x current dwellings, normalised per PUMA, as the other PUMA attributes)"])
    est, val, pool, G = F.setup(); A = B.puma_attrs(G)
    write(f"{HERE}/resloc_puma_core_{SUF}.csv", pd.DataFrame({"puma7": G[2], "core_share_2016": A["core"]}),
          ["core_share of every PUMA with the 2016 dwellings (estimation geography; check only)"])
    # ---- Java check
    os.makedirs(VD, exist_ok=True)
    h = est.sample(300, random_state=20261118).reset_index(drop=True); h["id"] = np.arange(len(h))
    R.RNG = np.random.default_rng(20261118); R.dw_X = F._full; alt, av = R.sample(h, pool); X = F.F17.dw_final(h, alt); V = X @ bdw.values
    rows = [(i, k, h.income.values[i], int(h.NP.values[i]), alt["cost"][i, k], int(alt["bed"][i, k]), alt["dtype"][i, k], int(bool(alt["new5"][i, k])), V[i, k])
            for i in range(len(h)) for k in range(R.J) if av[i, k]]
    pd.DataFrame(rows, columns=["id", "alt", "income", "size", "cost", "bedrooms", "type", "new5", "V_python"]).to_csv(f"{VD}/dwelling_in.csv", index=False)
    R.dw_X = F.F17.dw_final
    if "crime" not in R.UP: R.UP = R.UP + ["crime"]
    class Bb: pass
    mb = Bb(); mb.b = bdw.values
    R.RNG = Rec(np.random.default_rng(20261119)); X1, av1, C1, w1, n1 = R.upper_data(h, pool, mb, G); assert n1 == len(h)
    k = [R.UP.index(v) for v in F.UPF]; iv = R.UP.index("IVd"); jm = F.UPF.index("lnM"); pumas = G[2]
    Mp = F.MSIZES["stock_x_turnover"].reindex(pumas).values
    Z = X1[:, :, k].copy(); Z[:, :, jm] = np.log(np.maximum(Mp, 1.0))[None, :]
    d = dict(h=h, av=av1, lnddens=X1[:, :, R.UP.index("lnddens")])
    ex = B.combine(RF.NEW, d, A); Zx = np.concatenate([Z] + [ex[n][:, :, None] for n in ex], 2); xn = list(F.UPF) + list(ex)
    assert xn == names, (xn, names)
    U = Zx @ c22.values + X1[:, :, iv]; U = np.where(av1, U, np.nan)
    pd.DataFrame({"id": np.repeat(h.id.values, len(pumas)), "puma7": np.tile(pumas, len(h)), "V_python": U.ravel()}).to_csv(f"{VD}/puma_python.csv", index=False)
    des = {RENAME.get(n, n): Zx[:, :, i].ravel() for i, n in enumerate(xn)}; des["IVd"] = X1[:, :, iv].ravel()
    pd.DataFrame({"id": np.repeat(h.id.values, len(pumas)), "puma7": np.tile(pumas, len(h)), **des}).to_csv(f"{VD}/puma_design_python.csv", index=False)
    draws = R.RNG.draws; pr = []
    for j, p in enumerate(pumas):
        g = pool[pool.puma7 == p]
        if len(g) == 0: continue
        g = g.iloc[draws.pop(0)]
        pr.append(pd.DataFrame({"puma7": p, "cost": g.cost.values, "bedrooms": g.BDSP.values.astype(int), "type": g.dtype.values, "new5": (g.age_dd.values <= 5).astype(int)}))
    assert not draws
    pd.concat(pr).to_csv(f"{VD}/puma_pool.csv", index=False)
    pd.DataFrame({"puma7": pumas, "M": Mp, "core_share": A["core"]}).to_csv(f"{VD}/puma_M.csv", index=False)
    z = G[0]
    hh = pd.read_csv(f"{MICRO}/hh_2016.csv", usecols=["dwelling", "race"]); dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["id", "zone"])
    hh["zone"] = hh.dwelling.map(dd.set_index("id").zone); Sx = pd.crosstab(hh.zone, hh.race).reindex(index=ZONE_IDS, columns=RACES).fillna(0)
    pd.DataFrame({"zone": ZONE_IDS, "dwellings": z.dwellings.values, "jobs": z.jobs.values, "core": np.isin(zs.COUNTYFIPS.values, B.CORE).astype(int),
                  **{f"n_{r}": Sx[r].values for r in RACES}}).to_csv(f"{VD}/zone_inputs.csv", index=False)
    pd.DataFrame({"id": h.id, "income": h.income, "size": h.NP.astype(int), "age_max": h.age_max.astype(int), "mig7": h.mig7.astype(int),
                  "pow": h.pow7s.fillna("").astype(str).str.replace(";", "|"), "nocar": (h.VEH.fillna(0) <= 0).astype(int),
                  "child": (h.n_child > 0).astype(int), "race": h.head_race}).to_csv(f"{VD}/puma_hh.csv", index=False)
    print(f"Java check inputs in {VD}: {len(h)} movers, {len(rows)} dwelling alternatives, PUMA pool {sum(len(x) for x in pr)} dwellings")


def check(dj):
    p = pd.read_csv(f"{VD}/dwelling_in.csv"); j = pd.read_csv(f"{dj}/java_dwelling.csv"); m = p.merge(j, on=["id", "alt"]); assert len(m) == len(p)
    m["abs_diff"] = (m.V - m.V_python).abs(); m.to_csv(f"{HERE}/r22_java_check_dwelling.csv", index=False)
    print(f"dwelling level: {len(m)} utilities, max abs diff {m.abs_diff.max():.3g}")
    p = pd.read_csv(f"{VD}/puma_python.csv"); j = pd.read_csv(f"{dj}/java_puma.csv"); m = p.merge(j, on=["id", "puma7"], how="left")
    both = m.V_python.notna() & m.V.notna(); m["abs_diff"] = (m.V - m.V_python).abs(); m.to_csv(f"{HERE}/r22_java_check_puma.csv", index=False)
    print(f"PUMA level: {both.sum()} utilities in both, max abs diff {m.abs_diff[both].max():.3g}; only Python {(m.V_python.notna() & m.V.isna()).sum()}, only Java {(m.V_python.isna() & m.V.notna()).sum()}")


if __name__ == "__main__":
    if len(ARGS) > 2 and ARGS[1] == "check": check(ARGS[2])
    else: main()
