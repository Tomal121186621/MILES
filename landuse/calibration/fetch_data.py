#!/usr/bin/env python3
"""Download the public observed datasets listed in ../data_sources.md into WORKSPACE/data/raw/<dataset>/.
Files are never edited; a manifest (manifest.csv: file, url, bytes, sha256, downloaded) records every download.
Re-running skips files already present.  Usage: python3 landuse/calibration/fetch_data.py [dataset ...]   (default: all)"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, csv, hashlib, time, urllib.request
ROOT = f"{WORKSPACE}/data/raw"
MD_COUNTIES = ["24003", "24005", "24013", "24025", "24027", "24510", "24001", "24009", "24011", "24015", "24017", "24019", "24021", "24023",
               "24029", "24031", "24033", "24035", "24037", "24039", "24041", "24043", "24045", "24047", "11001", "10001", "10003", "10005"]
SETS = {
    "pep": [("co-est2020-alldata.csv", "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/counties/totals/co-est2020-alldata.csv"),
            ("co-est2024-alldata.csv", "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv"),
            ("co-est2025-alldata.csv", "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv"),
            ("cc-est2024-alldata-24.csv", "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/asrh/cc-est2024-alldata-24.csv"),
            ("cc-est2020-alldata-24.csv", "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/counties/asrh/cc-est2020-alldata-24.csv"),
            ("CO-EST2024-HU.xlsx", "https://www2.census.gov/programs-surveys/popest/tables/2020-2024/housing/totals/CO-EST2024-HU.xlsx")],
    "bps": [(f"co{y}a.txt", f"https://www2.census.gov/econ/bps/County/co{y}a.txt") for y in range(2016, 2025)],
    "lodes_wac": [(f"md_wac_S000_JT00_{y}.csv.gz", f"https://lehd.ces.census.gov/data/lodes/LODES8/md/wac/md_wac_S000_JT00_{y}.csv.gz") for y in range(2016, 2024)]
                 + [("md_xwalk.csv.gz", "https://lehd.ces.census.gov/data/lodes/LODES8/md/md_xwalk.csv.gz")],
    "lodes_od": [(f"md_od_{k}_JT00_{y}.csv.gz", f"https://lehd.ces.census.gov/data/lodes/LODES8/md/od/md_od_{k}_JT00_{y}.csv.gz") for y in range(2016, 2024) for k in ("main", "aux")],
    "qcew": [(f"qcew_{y}_{c}.csv", f"https://data.bls.gov/cew/data/api/{y}/a/area/{c}.csv") for y in range(2016, 2025) for c in MD_COUNTIES],
    "fhfa": [("hpi_master.csv", "https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv")],
}
def fetch(name, url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0: return "present"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research download)"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            os.replace(dest + ".part", dest); return "downloaded"
        except Exception as e:
            err = e; time.sleep(3)
    return f"FAILED {err}"
sets = sys.argv[1:] or list(SETS); man = f"{ROOT}/manifest.csv"; os.makedirs(ROOT, exist_ok=True)
rows = list(csv.DictReader(open(man))) if os.path.exists(man) else []
done = {r["file"] for r in rows}
for s in sets:
    d = f"{ROOT}/{s}"; os.makedirs(d, exist_ok=True); n_ok = n_fail = 0
    for name, url in SETS[s]:
        dest = f"{d}/{name}"; st = fetch(name, url, dest)
        if st.startswith("FAILED"): n_fail += 1; print(f"  {s}/{name}: {st}"); continue
        n_ok += 1
        if f"{s}/{name}" not in done:
            h = hashlib.sha256(open(dest, "rb").read()).hexdigest()[:16]
            rows.append(dict(file=f"{s}/{name}", url=url, bytes=os.path.getsize(dest), sha256=h, downloaded=time.strftime("%Y-%m-%d")))
    print(f"{s}: {n_ok} files ok, {n_fail} failed")
with open(man, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["file", "url", "bytes", "sha256", "downloaded"]); w.writeheader(); w.writerows(rows)
