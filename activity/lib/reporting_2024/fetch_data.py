#!/usr/bin/env python3
"""Downloads for the 2024 temporal validation of DAYMAP (3_abit/temporal_2024).  Files go to Validation_2026/data/raw/<source>/
and are never edited; every download is logged with URL, date, size and the full SHA-256 in data/raw/<source>/SOURCES.csv and
appended to data/raw/manifest.csv (16-character hash there, as in the rest of the manifest).  Files already present are kept.

    python3 activity/lib/reporting_2024/fetch_data.py [source ...]      sources: pums_2024_1yr atus lodes_od lodes_wac pums_docs geo   (default: all)

www.bls.gov answers 403 to scripted clients; the ATUS files are fetched with the request headers of a desktop browser.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import csv, hashlib, os, subprocess, sys, time

RAW = f"{WORKSPACE}/data/raw"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
HDR = ["-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "-H", "Accept-Language: en-US,en;q=0.9",
       "-H", "Accept-Encoding: gzip, deflate, br", "-H", "Sec-Fetch-Dest: document", "-H", "Sec-Fetch-Mode: navigate",
       "-H", "Sec-Fetch-Site: same-origin", "-H", "Upgrade-Insecure-Requests: 1"]
PUMS1 = "https://www2.census.gov/programs-surveys/acs/data/pums/2024/1-Year"
ATUS = "https://www.bls.gov/tus/datafiles"
LODES = "https://lehd.ces.census.gov/data/lodes/LODES8"
OTHER = ["dc", "va", "pa", "de", "wv"]
SETS = {
    "pums_2024_1yr": [(f"csv_{k}{s}.zip", f"{PUMS1}/csv_{k}{s}.zip") for s in ["md"] for k in "ph"]
                     + [(f"csv_p{s}.zip", f"{PUMS1}/csv_p{s}.zip") for s in ["dc", "de", "pa", "va", "wv"]],   # county telework input of the zone system
    "pums_2019_5yr_de": [("csv_pde.zip", "https://www2.census.gov/programs-surveys/acs/data/pums/2019/5-Year/csv_pde.zip")],   # the copy in inputs/ is empty
    "pums_docs": [("PUMS_Data_Dictionary_2024.csv", "https://www2.census.gov/programs-surveys/acs/tech_docs/pums/data_dict/PUMS_Data_Dictionary_2024.csv"),
                  ("ACSPUMS2024CodeLists.xls", "https://www2.census.gov/programs-surveys/acs/tech_docs/pums/code_lists/ACSPUMS2024CodeLists.xls"),
                  ("ACSPUMS2020_2024CodeLists.xlsx", "https://www2.census.gov/programs-surveys/acs/tech_docs/pums/code_lists/ACSPUMS2020_2024CodeLists.xlsx"),
                  ("2024ACS_PUMS_User_Guide.pdf", "https://www2.census.gov/programs-surveys/acs/tech_docs/pums/2024ACS_PUMS_User_Guide.pdf")],
    "atus": [(f"{f}-0324.zip", f"{ATUS}/{f}-0324.zip") for f in ["atusresp", "atusact", "atuscps", "atusrost", "atussum"]]
            + [("lexiconnoex0324.pdf", "https://www.bls.gov/tus/lexicons/lexiconnoex0324.pdf"),
               ("atusintcodebk0324.pdf", "https://www.bls.gov/tus/dictionaries/atusintcodebk0324.pdf")],
    "lodes_od": [(f"{s}_od_aux_JT00_2022.csv.gz", f"{LODES}/{s}/od/{s}_od_aux_JT00_2022.csv.gz") for s in OTHER],
    "lodes_wac": [(f"{s}_wac_S000_JT00_2022.csv.gz", f"{LODES}/{s}/wac/{s}_wac_S000_JT00_2022.csv.gz") for s in OTHER]
                 + [(f"{s}_xwalk.csv.gz", f"{LODES}/{s}/{s}_xwalk.csv.gz") for s in OTHER],
    "geo": [("2020_Census_Tract_to_2020_PUMA.txt", "https://www2.census.gov/geo/docs/maps-data/data/rel2020/2020_Census_Tract_to_2020_PUMA.txt")],
}


def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0: return "present"
    cmd = ["curl", "-sSfL", "--retry", "3", "-A", UA] + (HDR + ["--compressed"] if "bls.gov" in url else []) + ["-o", dest + ".part", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        if os.path.exists(dest + ".part"): os.remove(dest + ".part")
        return f"FAILED {r.stderr.strip()[:200]}"
    os.replace(dest + ".part", dest); return "downloaded"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


if __name__ == "__main__":
    man = f"{RAW}/manifest.csv"; mrows = list(csv.DictReader(open(man))); mdone = {r["file"] for r in mrows}
    for s in (sys.argv[1:] or list(SETS)):
        d = f"{RAW}/{s}"; os.makedirs(d, exist_ok=True); log = f"{d}/SOURCES.csv"
        lrows = list(csv.DictReader(open(log))) if os.path.exists(log) else []; ldone = {r["file"] for r in lrows}
        for name, url in SETS[s]:
            dest = f"{d}/{name}"; st = fetch(url, dest); print(f"{s}/{name}: {st}", flush=True)
            if st.startswith("FAILED"): continue
            if name in ldone and f"{s}/{name}" in mdone: continue
            h = sha(dest); day = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(dest)))
            if name not in ldone: lrows.append(dict(file=name, url=url, bytes=os.path.getsize(dest), sha256=h, downloaded=day))
            if f"{s}/{name}" not in mdone: mrows.append(dict(file=f"{s}/{name}", url=url, bytes=os.path.getsize(dest), sha256=h[:16], downloaded=day))
        with open(log, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["file", "url", "bytes", "sha256", "downloaded"]); w.writeheader(); w.writerows(lrows)
    with open(man, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "url", "bytes", "sha256", "downloaded"]); w.writeheader(); w.writerows(mrows)
