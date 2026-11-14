#!/usr/bin/env python3
"""Tables-only PDFs (SILO and ABIT): the article's current estimation tables in order, with est_cars replaced by the re-specified car ownership
model (../step_by_step/car_ownership/est_cars_new.tex). Usage: python3 make_pdf.py"""
import os, re, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "..", "..", "..", "5_reports", "article", "sections", "est")
NEW = {"est_cars": os.path.join(HERE, "..", "step_by_step", "car_ownership", "est_cars_new.tex"),
       "est_region": os.path.join(HERE, "..", "step_by_step", "residential", "est_region_new.tex"),
       "est_zone": os.path.join(HERE, "..", "step_by_step", "residential", "est_zone_new.tex"),
       "est_dwelling": os.path.join(HERE, "..", "step_by_step", "residential", "est_dwelling_new.tex"),
       **{f"est_mc_{s}": os.path.join(HERE, "..", "step_by_step", "mode_choice", f"est_mc_{s}_new.tex") for s in ["work", "shopping", "other", "school"]},
       **{t: os.path.join(HERE, "..", "step_by_step", "tables_new", f"{t}_new.tex") for t in ["est_subtour", "est_return", "est_loc_daycare", "est_loc_nonstud",
                                                                                              "est_loc_wahb", "est_loc_wbhome", "est_loc_wbwork", "est_school", "est_jobchoice"]}}
for _p in ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]:
    for _t, _d in ((f"est_dc_{_p}_primary", "dest_primary"), (f"est_stop_{_p}_stop", "dest_stop")):
        _f = os.path.join(HERE, "..", "step_by_step", _d, f"{_t}_new.tex")
        if os.path.exists(_f): NEW[_t] = _f
NEW["est_mc_joint"] = os.path.join(HERE, "..", "step_by_step", "mode_choice", "est_mc_joint_new.tex")
NEW["est_dc_pooled"] = os.path.join(HERE, "..", "step_by_step", "dest_pooled", "est_dc_pooled.tex")
NEW["est_loc_edu"] = os.path.join(HERE, "..", "step_by_step", "tables_new", "est_loc_edu_new.tex")
B = os.path.join(HERE, "build")


def clean(s):
    s = re.sub(r"Variables: defined in Table~\\ref\{[^}]*\}; base component", "Base component", s)
    s = "\n".join(l for l in s.split("\n") if not re.search(r"\{Variables: Table", l))
    s = re.sub(r" ?\((?:Section|Table)~\\ref\{[^}]*\}\)", "", s)
    return s.replace(r"\citep{ManskiLerman1977}", "(Manski and Lerman, 1977)")


def main():
    os.makedirs(f"{B}/est", exist_ok=True)
    for doc in ["estimation_tables_silo", "estimation_tables_abit"]:
        tables = re.findall(r"\\input\{est/([^}]+)\}", open(f"{HERE}/{doc}.tex").read())
        for t in tables:
            open(f"{B}/est/{t}.tex", "w").write(clean(open(NEW.get(t, f"{ART}/{t}.tex")).read()))
        shutil.copy(f"{HERE}/{doc}.tex", B)
        for _ in range(2):
            r = subprocess.run(["tectonic", "-X", "compile", "-k", "--keep-logs", f"{doc}.tex"], cwd=B, capture_output=True, text=True)
            if r.returncode: print(r.stderr[-3000:]); raise SystemExit(1)
        shutil.copy(f"{B}/{doc}.pdf", HERE)
        log = open(f"{B}/{doc}.log").read()
        print(doc, "tables", len(tables), "undefined:", sorted(set(re.findall(r"(?:Reference|Citation) `([^']+)'", log))), "overfull:", log.count("Overfull \\hbox"))


if __name__ == "__main__":
    main()
