#!/usr/bin/env python3
"""Execute the notebook of a model folder in place (outputs saved in the notebook). Usage: run_notebook.py <model folder> [...]
Each run is appended to tools/notebook_runs.log (start time, folder, status, minutes, failing cell)."""
import os, sys, time
import nbformat
from nbclient import NotebookClient

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notebook_runs.log")

for d in sys.argv[1:]:
    d = os.path.normpath(d)
    p = os.path.join(d, os.path.basename(d) + "_estimation.ipynb")
    if not os.path.exists(p):
        p = os.path.join(d, os.path.basename(d) + ".ipynb")
    nb = nbformat.read(p, 4)
    t0 = time.time(); start = time.strftime("%Y-%m-%d %H:%M:%S")
    err = None
    try:
        NotebookClient(nb, timeout=None, kernel_name="biogeme", resources={"metadata": {"path": d}}).execute()
    except Exception as e:
        err = str(e)[-3000:]
    nbformat.write(nb, p)
    # cell errors recorded in the outputs
    bad = []
    for i, c in enumerate(nb.cells):
        for o in c.get("outputs", []):
            if o.get("output_type") == "error":
                bad.append(f"cell {i}: {o.get('ename')}: {str(o.get('evalue'))[:200]}")
    status = "OK" if err is None and not bad else "ERROR"
    mins = (time.time() - t0) / 60
    print(f"{d}: {status} in {mins * 60:.0f} s")
    if err:
        print(err)
    with open(LOG, "a") as f:
        f.write(f"{start}\t{os.path.basename(d)}\t{status}\t{mins:.1f} min\t{' | '.join(bad)}\n")
