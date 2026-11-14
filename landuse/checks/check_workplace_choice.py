#!/usr/bin/env python3
"""Unit check of the engine's re-specified workplace choice (job.choice.model = respec) with the engine's own verification hook
(JobDataManagerImpl.verifyRts, -Dsilo.jobchoice.verify): for 300 workers of the estimation half the engine computes
V_j = mu ln S_j + rtsUtility over all 1,587 zones with jobs (S_j from the estimation job counts), against the estimation utility of
wdc.py (centred interactions, w04 final).  The engine reads its own zones file (state, county, region), car skim, rural flag and
accessibility file; the job-mix shares and hiearn are taken from a temporary attribute file with the estimation values
(silo.jobchoice.verify.fileShares), because in a run they are recomputed each year from the SILO job list (difference reported
separately).  Runs SILO up to the first prepareYear (data loading, ~3 min, 20 GB).
    python3 landuse/checks/check_workplace_choice.py <dir without spaces>   ->  c03_workplace_check.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, subprocess, shutil, re
import numpy as np, pandas as pd
V = f"{WORKSPACE}"; S = f"{V}/2_silo"; RUN = f"{S}/run"
HERE = f"{V}/side_experiments/respec_2026-11/engine_check"; W = f"{ESTIMATION_RESULTS}/workplace"   # outputs (workspace); W: estimation results
sys.path.insert(0, f"{ORIOLE_HOME}/estimation/development/workplace_choice"); import wdc   # noqa: E402
TMP = f"{RUN}/verify_respec"; NAME = "verify_respec_wp"
# files of the verification hook: a directory without spaces (run_silo.sh splits SILO_JAVA_OPTS on spaces)
VF = sys.argv[1] if len(sys.argv) > 1 else "/tmp"


def main():
    os.makedirs(TMP, exist_ok=True)
    zs = pd.read_csv(f"{S}/input/zoneSystem.csv").sort_values("ZoneId"); ZID = zs.ZoneId.values
    D = wdc.D
    pd.DataFrame({"zone": ZID, **{k: D[f"z_{k}"] for k in ["hiearn", "off_sh", "ret_sh", "ind_sh"]}, "rural": D["z_rural"]}).to_csv(f"{TMP}/zone_attrs_est.csv", index=False)
    pd.DataFrame({"zone": ZID[wdc.AZ], **{k: wdc.JOBS[wdc.AZ, i] for i, k in enumerate(["RET", "OFF", "IND", "OTH"])}}).to_csv(f"{VF}/zone_jobs.csv", index=False)
    P = wdc.persons(True); rng = np.random.default_rng(20261109); idx = np.sort(rng.choice(len(P["g"]), 300, replace=False))
    Q = {k: v[idx] for k, v in P.items()}
    pd.DataFrame({"test_id": idx, "home_zone": ZID[Q["hidx"]], "female": Q["female"], "age": Q["age"].astype(int), "car_segment": Q["car_seg"],
                  "income_group": Q["g"], "driving_licence": Q["lic"], "hh_size_capped_8": np.minimum(Q["hhsize"], 8), "kids": Q["kids"],
                  "workers": Q["workers"]}).to_csv(f"{VF}/workers.csv", index=False)
    # estimation utility over all zones with jobs
    c = pd.read_csv(f"{W}/w04_coef.csv"); c = c[c.step == "final"].drop_duplicates("param", keep="last").set_index("param").coef
    terms = [k for k in c.index if k not in ("mu", "g_OFF", "g_IND", "g_OTH")]
    A = np.broadcast_to(wdc.AZ, (len(idx), len(wdc.AZ)))
    U = sum(c[k] * wdc.feat(k, Q["hidx"], A, Q) for k in terms)
    lw = np.array([0, c.g_OFF, c.g_IND, c.g_OTH]); Sz = wdc.JOBS[wdc.AZ] @ np.exp(lw); U = U + c.mu * np.log(Sz)[None, :]
    py = pd.DataFrame({"test_id": np.repeat(idx, len(wdc.AZ)), "zone": np.tile(ZID[wdc.AZ], len(idx)), "V_py": U.ravel()})
    # engine run up to the verification
    out = f"{VF}/engine_V.csv"
    if not os.path.exists(out):
        subprocess.run(["python3", f"{ORIOLE_HOME}/landuse/run/write_properties.py", NAME, "2016", "2017", "-1", "1", "respec"], check=True, capture_output=True)
        p = f"{RUN}/{NAME}.properties"; t = open(p).read()
        t = re.sub(r"^job.choice.zone.attributes.file\s*=.*$", "job.choice.zone.attributes.file = ../verify_respec/zone_attrs_est.csv", t, flags=re.M)
        open(p, "w").write(t)
        env = dict(os.environ, ORIOLE_WORKSPACE=WORKSPACE, SILO_JAVA_OPTS=f"-Dsilo.jobchoice.verify={VF}/workers.csv;{VF}/zone_jobs.csv;{out} -Dsilo.jobchoice.verify.fileShares=true")
        rc = subprocess.run(["bash", f"{ORIOLE_HOME}/landuse/run/run_silo.sh", p, "20g"], env=env).returncode
        print("engine exit", rc, flush=True)
    j = pd.read_csv(out); m = py.merge(j, on=["test_id", "zone"]); assert len(m) == len(py) == len(j), (len(m), len(py), len(j))
    d = (m.V_py - m.V).abs()
    lp = m.assign(lp_py=m.V_py - m.groupby("test_id").V_py.transform(lambda x: np.log(np.exp(x - x.max()).sum()) + x.max()))
    res = [dict(part="workplace utilities (all zones with jobs)", n=len(m), max_abs_diff=float(d.max()),
                max_abs_diff_lnprob=float((lp.lp_py - lp.ln_prob).abs().max()))]
    # the estimation data hold the car time in float32 (w01_data.py); the engine reads the skim in double: same check with the
    # skim read in double precision
    sk = pd.read_csv(f"{S}/input/skims/auto_peak_time.csv.gz"); zi = pd.Series(np.arange(len(ZID)), index=ZID); T64 = np.full((len(ZID), len(ZID)), np.nan)
    T64[zi[sk.FROM].values, zi[sk.TO].values] = sk.VALUE.values; wdc.TT = T64
    U2 = sum(c[k] * wdc.feat(k, Q["hidx"], A, Q) for k in terms) + c.mu * np.log(Sz)[None, :]
    m2 = pd.DataFrame({"test_id": np.repeat(idx, len(wdc.AZ)), "zone": np.tile(ZID[wdc.AZ], len(idx)), "V_py": U2.ravel()}).merge(j, on=["test_id", "zone"])
    res.append(dict(part="workplace utilities, estimation utility with the skim in double precision", n=len(m2), max_abs_diff=float((m2.V_py - m2.V).abs().max())))
    # shares in a run: recomputed from the SILO 2016 job list (engine attribute file) instead of the estimation's
    a = pd.read_csv(f"{S}/input/workplace_choice_zone_attributes.csv").set_index("zone").reindex(ZID)
    dv = (c["z_off_sh*g1"] * (a.off_sh.values - D["z_off_sh"])[None, :] * (Q["g"] == 1)[:, None]
          + c["z_off_sh*g4"] * (a.off_sh.values - D["z_off_sh"])[None, :] * (Q["g"] == 4)[:, None]
          + c["z_ret_sh*young"] * (a.ret_sh.values - D["z_ret_sh"])[None, :] * (Q["age"] < 30)[:, None]
          + c["z_ind_sh*female"] * (a.ind_sh.values - D["z_ind_sh"])[None, :] * Q["female"][:, None])
    res.append(dict(part="job-mix shares from the SILO 2016 job list instead of the estimation file (utility difference)", n=dv.size,
                    max_abs_diff=float(np.abs(dv).max()), mean_abs_diff=float(np.abs(dv).mean())))
    print(pd.DataFrame(res).to_string(index=False))
    pd.DataFrame(res).to_csv(f"{HERE}/c03_workplace_check.csv", index=False)


if __name__ == "__main__":
    main()
