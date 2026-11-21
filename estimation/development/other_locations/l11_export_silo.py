#!/usr/bin/env python3
"""Export of the final school location choice models (l10_school.py, 2026-11-18) to SILO (Java class SchoolChoiceMd) and the
Python side of the Java verification.  Nothing of l09/l10 is edited; l10_school is imported for its zone variables (QZ) and the
extended design (Design3).

Writes NEW files to 2_silo/input/ (lines starting with '#' document the columns; the Java reader skips them):
  school_location_coefficients_k8.csv / _hs.csv / _college.csv   parameter,value: l10_school_<seg>_final_coef.csv (size weights held at 0
                                                           written as g_<comp> = 0)
  school_location_records.csv     id,zone,band,component,capacity: every band record of input/schools_2016.csv with its size component
                                     (2_silo/schoolchoice/apply/school_records.csv, sc_01_data.py)
  school_location_inboundary.csv  home_zone,band,school_id,school_zone,a: SABS in-boundary share (schoolchoice/work/sabs_home_school.parquet)
  school_location_zone_attributes.csv   band,zone,cm,qpub,qnone,n_race,n_white,n_black,n_hisp,n_other,sh_white,sh_black,sh_hisp,sh_other
Verification (python3 l11_export_silo.py verify): for a sample of estimation rows (student x possible home zone) of each segment
writes l11_verify_<seg>_rows.csv (input of the Java check) and l11_verify_<seg>_py.csv (row,zone,V of the estimation code: mu ln S +
X b, full choice set), runs SchoolChoiceMd.main and writes l11_java_check_<seg>.csv (row,zone,V_py,V_java,diff,rel).
    python3 l11_export_silo.py            -> export only
    python3 l11_export_silo.py verify <classpath>"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, subprocess
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/locations"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import l10_school as L10   # noqa: E402  (module level: QZ and the Design3 hook; no estimation is run)
X9 = L10.X9; G = X9.G; S = X9.S; SC = X9.SC
INP = f"{SC.S}/input"; SEGS = {"k8": "k8", "hs": "hs", "col": "college"}
RC = ["white", "black", "hisp", "other"]


def header(f, lines):
    with open(f, "w") as fh:
        for l in lines: fh.write("# " + l + "\n")


def write(df, f, lines):
    header(f, lines); df.to_csv(f, mode="a", index=False)


def export():
    for seg, b in SEGS.items():
        c = pd.read_csv(f"{HERE}/l10_school_{b}_final_coef.csv")
        write(c, f"{INP}/school_location_coefficients_{b}.csv", [
            f"School location choice, segment {b}: final model of side_experiments/respec_2026-11/step_by_step/locations/l10_school.py",
            "(copy of l10_school_%s_final_coef.csv). V_hj = mu_size ln S_hj + sum b_x x_hj; S_hj = sum_c exp(g_c) N_c,hj" % b,
            "components K-12: pub_out (reference, weight 1), pub_in (SABS in-boundary public enrolment), priv; college: pub4 (reference), priv4, cc",
            "b_ names: t car peak min, lt ln(1+t), intra same zone, cc other county, cs other state, ccpub other county x public share,",
            "X car0 no car in household, X g1 / g4 household income < $40k / >= $125k (2016 $), cm charter-or-magnet share, qpub quality of",
            "the public part (centred), qnone public share without a score, own own-race share of the zone's enrolment of the band.",
            "g_ = 0 rows: size weights held at 0 in estimation."])
    sch = pd.read_csv(f"{INP}/schools_2016.csv", usecols=["id", "zone", "band", "capacity", "sector"])
    rec = pd.read_csv(f"{SC.SC}/apply/school_records.csv").set_index("id")
    sch["component"] = sch.id.map(rec.component)
    miss = sch.component.isna(); sch.loc[miss, "component"] = sch.sector[miss].map({"public": "pub", "private": "priv", "postsec": "cc"})
    print(f"records {len(sch)}, component from the sector (not in school_records.csv): {int(miss.sum())}")
    write(sch[["id", "zone", "band", "component", "capacity"]], f"{INP}/school_location_records.csv", [
        "School records of input/schools_2016.csv with the size component of the school location choice (2_silo/schoolchoice/sc_01_data.py,",
        "apply/school_records.csv). id = SILO school id, zone, band (elementary/middle/high/postsec), component pub/priv (K-12, CCD/PSS) or",
        "pub4/priv4/cc (college, IPEDS sector 1 / 2-3 / 4-9), capacity = enrolment of the band (the size N_s; records with capacity 0 not chosen)."])
    A = pd.read_parquet(f"{SC.W}/sabs_home_school.parquet").rename(columns={"zone": "home_zone"})
    write(A[["home_zone", "band", "school_id", "school_zone", "a"]], f"{INP}/school_location_inboundary.csv", [
        "SABS attendance-boundary shares (2_silo/schoolchoice/sc_00_sabs.py, work/sabs_home_school.parquet): a = share of the home zone's",
        "housing units inside the boundary of public school record school_id (band). In-boundary enrolment pub_in_hj = min(sum_s a_hs N_s, pub_j)",
        "over the public records s of the band in zone j (sc_03_engine.ain). Home zones not listed: pub_in = 0."])
    ZA = X9.ZA; rows = []
    for b in ["elementary", "middle", "high", "postsec"]:
        tot = sum(SC.size()[b].values()) if b in SC.size() else np.zeros(X9.NZ)
        zs = np.flatnonzero((X9.zarr(b, "n") > 0) | (tot > 0))
        d = pd.DataFrame({"band": b, "zone": SC.zones().zone.values[zs], "cm": X9.ZV[b]["cm"][zs],
                          "qpub": L10.QZ[b]["qpub"][zs] if b in L10.QZ else 0.0, "qnone": L10.QZ[b]["qnone"][zs] if b in L10.QZ else 0.0,
                          "n_race": X9.zarr(b, "n_race")[zs]})
        for k, c in enumerate(RC): d[f"n_{c}"] = X9.zarr(b, f"n_{c}")[zs]
        for k, c in enumerate(RC): d[f"sh_{c}"] = X9.ZV[b]["own"][k][zs]
        rows.append(d)
    Z = pd.concat(rows, ignore_index=True)
    write(Z, f"{INP}/school_location_zone_attributes.csv", [
        "Fixed zone inputs of the school location choice by band (l09_school_data.py -> l09_zone_attr.parquet; l10_school.py QZ):",
        "cm = charter-or-magnet share of the zone's band enrolment (min(charter + magnet, 1)); qpub = (enrolment of the band in Maryland public",
        "schools with a score / band enrolment n) x ((enrolment-weighted mean %% proficient of those schools) / 10 - %.2f), 0 without a score;" % X9.QMEAN,
        "qnone = max(public enrolment - enrolment with a score, 0) / n.  n_race, n_<race>: 2016 enrolment by race (CCD/IPEDS; reference only),",
        "sh_<race> = n_<race> / n_race = the own-race shares of the estimation (used by the Java verification only; in SILO the own-race share",
        "is recomputed every year from the students assigned in SILO).  Races: white, black, hisp(anic), other (SILO Race enum order)."])
    print(f"zone attributes {len(Z)} rows")


def model(seg):
    b = SEGS[seg]; f = pd.read_csv(f"{HERE}/l10_school_{b}_fit.csv"); r = f[f.step == "final"].iloc[0]
    spec = r.spec.split(); gfix = tuple(str(r.gfix).split(",")) if isinstance(r.gfix, str) else ()
    D = X9.Design2(seg, "estimation"); t, si, sabs = S.split(spec); M = X9.Model2(D, t, si, sabs, None, gfix)
    c = pd.read_csv(f"{HERE}/l10_school_{b}_final_coef.csv").set_index("parameter").value.to_dict(); th = M.at(c)
    mu = th[0]; g = th[1:1 + M.ng]; bb = th[1 + M.ng:1 + M.ng + M.K]
    lw = np.zeros((len(D.comps), D.R))
    for j, k in enumerate(M.gidx): lw[k] += g[j]
    WN = np.exp(lw)[:, :, None] * D.NK; lnS = np.log(WN.sum(0) + 1e-12)
    V = mu * lnS + D.corr + (np.tensordot(bb, M.Xs, axes=1) if M.K else 0.0)
    return D, np.where(D.av, V, -np.inf)


def verify(cp):
    zid = SC.zones().zone.values; java = os.path.join(subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip(), "bin", "java")
    for seg, b in SEGS.items():
        D, V = model(seg); rng = np.random.default_rng(20261118); rows = np.sort(rng.choice(D.R, size=min(300, D.R), replace=False))
        P = D.P; rec = D.rec[rows]
        R = pd.DataFrame({"row": rows, "home_zone": zid[D.h[rows]], "band": D.band[rec], "car0": P.car0.values[rec], "g": P.g.values[rec],
                          "race": P.race.values[rec]})
        R.to_csv(f"{HERE}/l11_verify_{seg}_rows.csv", index=False)
        ii, jj = np.nonzero(np.isfinite(V[rows]))
        py = pd.DataFrame({"row": rows[ii], "zone": zid[D.A[rows[ii], jj]], "V_py": V[rows][ii, jj].astype(float)})
        py.to_csv(f"{HERE}/l11_verify_{seg}_py.csv", index=False)
        out = f"{HERE}/l11_verify_{seg}_java.csv"
        cmd = [java, "-Xmx4g", "-cp", cp, "de.tum.bgu.msm.data.school.SchoolChoiceMd", b, f"{INP}/school_location_coefficients_{b}.csv",
               f"{INP}/school_location_records.csv", f"{INP}/school_location_inboundary.csv", f"{INP}/school_location_zone_attributes.csv",
               f"{INP}/zoneSystem.csv", f"{INP}/skims/auto_peak_time.csv.gz", f"{HERE}/l11_verify_{seg}_rows.csv", out]
        subprocess.run(cmd, check=True)
        jv = pd.read_csv(out); m = py.merge(jv.rename(columns={"V": "V_java"}), on=["row", "zone"], how="outer", indicator=True)
        m["diff"] = m.V_java - m.V_py; m["rel"] = m["diff"].abs() / np.maximum(1.0, m.V_py.abs())
        m.to_csv(f"{HERE}/l11_java_check_{seg}.csv", index=False)
        print(f"{seg}: {len(rows)} rows, {len(py)} available (row, zone) pairs; only python {int((m._merge == 'left_only').sum())}, only java "
              f"{int((m._merge == 'right_only').sum())}; max |diff| {m['diff'].abs().max():.3g}, max rel {m.rel.max():.3g}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify": verify(sys.argv[2])
    else: export()
