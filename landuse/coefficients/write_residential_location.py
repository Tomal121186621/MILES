#!/usr/bin/env python3
"""Engine input files of the re-specified residential location model (resloc.spec = respec), from the final estimates the article
tables read (estimation/development/residential_location: t_region_table.py -> r05 final step; t_zone_dwelling_tables.py -> r08 chosen zone form, r06 final
dwelling form).  New files only (never overwrites an existing file):
  2_silo/input/residential_county_coefficients.csv           parameter,estimate,robust_se   (county, step Ja; IV_A fixed at 1 listed explicitly)
  2_silo/input/residential_zone_dwelling_coefficients.csv         level,parameter,estimate,robust_se   (zone x structure type; dwelling)
  2_silo/input/residential_county_attributes.csv    region,state,school,crime,growth   (s06_region.region_frame + r05.add_growth)
  2_silo/input/residential_county_adjacency.csv     region_a,region_b   (r05.adjacency: county polygons touching within 50 m)
  data/accessibility_multimodal_respec_2016.csv       copy of accessibility_new/accessibility_2016_new_multimodal.csv (the file the
                                                      final zone model and county inclusive values were estimated with)
    python3 landuse/coefficients/write_residential_location.py   (COEF_ONLY=1: the two coefficient files only)"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, shutil
import numpy as np, pandas as pd
V = f"{WORKSPACE}"
SBS = f"{ESTIMATION_RESULTS}"; R = f"{SBS}/residential"; INP = f"{V}/2_silo/input"
sys.path.insert(0, f"{TERP_HOME}/landuse/lib/residential"); sys.path.insert(0, f"{TERP_HOME}/estimation/development/residential_location"); sys.argv = [sys.argv[0]]   # estimation code; R holds its results
import r05_region_sequence as R5   # noqa: E402  (adjacency, region frame, growth)


ONLY_COEF = os.environ.get("COEF_ONLY") == "1"   # 2026-11-10: rewrite the two coefficient files only, when their backup *_pre1110a exists


def new(path):
    if ONLY_COEF:
        assert os.path.exists(path.replace(".csv", "_pre1110a.csv")), f"no backup of {path}"; return path
    assert not os.path.exists(path), f"exists, not overwritten: {path}"
    return path


def main():
    F = pd.read_csv(f"{R}/r05_fit.csv"); s = F[F.final].iloc[0]
    c = pd.read_csv(f"{R}/r05_coef.csv"); c = c[c.step == s.step][["parameter", "estimate", "robust_se"]]
    fixed = [x for x in str(s.fixed_at_1).split(";") if x and x != "nan"]
    c = pd.concat([c, pd.DataFrame({"parameter": fixed, "estimate": 1.0, "robust_se": 0.0})])
    assert len(c) == int(s.K) + len(fixed)
    c.to_csv(new(f"{INP}/residential_county_coefficients.csv"), index=False)
    print("county step", s.step, "K", int(s.K), "fixed", fixed); print(c.to_string(index=False))
    zf = pd.read_csv(f"{R}/r08_fit.csv"); zm = zf[zf.chosen.fillna(False).astype(bool)].model.iloc[0]
    zc = pd.read_csv(f"{R}/r08_coef.csv"); zc = zc[zc.model == zm][["parameter", "estimate", "robust_se"]].assign(level="zone")
    df = pd.read_csv(f"{R}/r06_fit.csv"); dm = df[df.validation_LL.notna()].iloc[0].model
    dc = pd.read_csv(f"{R}/r06_coef.csv"); dc = dc[dc.model == dm][["parameter", "estimate", "robust_se"]].assign(level="dwelling")
    out = pd.concat([zc, dc])[["level", "parameter", "estimate", "robust_se"]]
    out.to_csv(new(f"{INP}/residential_zone_dwelling_coefficients.csv"), index=False)
    print("zone:", zm, len(zc), "| dwelling:", dm, len(dc))
    if ONLY_COEF: return
    # county attributes: state, school (mean achievement, not used by the respec model), crime, school learning growth
    z, Rg = R5.RG.region_frame()
    seda = pd.read_csv(f"{R5.RAW}/seda_county_pool_cs_4.1.csv"); seda = seda[seda.subgroup == "all"].set_index("sedacounty")
    def gr(f):
        q = seda.reindex(R5.RG.COMBINED.get(f, [f])).dropna(subset=["cs_mn_grd_eb"]); return np.average(q.cs_mn_grd_eb, weights=q.tot_asmts)
    z["growth"] = z.COUNTYFIPS.map({f: gr(f) for f in z.COUNTYFIPS.unique()})
    Rg["growth"] = z.groupby("region").apply(lambda x: np.average(x.growth, weights=x.dwellings + 1e-9))
    att = Rg.reset_index().rename(columns={"index": "region"})[["region", "state", "school", "crime", "growth"]]
    old = pd.read_csv(f"{INP}/resloc_region_attributes.csv").set_index("region")
    print("crime vs current attribute file, max abs diff", float((att.set_index("region").crime - old.crime).abs().max()),
          "| school", float((att.set_index("region").school - old.school).abs().max()))
    att.to_csv(new(f"{INP}/residential_county_attributes.csv"), index=False)
    regs = np.sort(z.region.unique()); A = R5.ADJ
    pairs = [(regs[i], regs[j]) for i in range(len(regs)) for j in range(i + 1, len(regs)) if A[i, j] > 0]
    pd.DataFrame(pairs, columns=["region_a", "region_b"]).to_csv(new(f"{INP}/residential_county_adjacency.csv"), index=False)
    print("adjacent county pairs", len(pairs))
    shutil.copyfile(f"{SBS}/accessibility_new/accessibility_2016_new_multimodal.csv", new(f"{V}/data/accessibility_multimodal_respec_2016.csv"))


if __name__ == "__main__":
    main()
