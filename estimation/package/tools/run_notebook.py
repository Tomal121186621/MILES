#!/usr/bin/env python3
"""Execute the notebook of a model folder in place (outputs saved in the notebook). Usage: run_notebook.py <model folder> [...]"""
import os, sys, time
import nbformat
from nbclient import NotebookClient

for d in sys.argv[1:]:
    p = os.path.join(d, os.path.basename(os.path.normpath(d)) + "_estimation.ipynb")
    if not os.path.exists(p):
        p = os.path.join(d, os.path.basename(os.path.normpath(d)) + ".ipynb")
    nb = nbformat.read(p, 4)
    t0 = time.time()
    err = None
    try:
        NotebookClient(nb, timeout=None, kernel_name="biogeme", resources={"metadata": {"path": d}}).execute()
    except Exception as e:
        err = str(e)[-3000:]
    nbformat.write(nb, p)
    print(f"{d}: {'OK' if err is None else 'ERROR'} in {time.time()-t0:.0f} s")
    if err:
        print(err)
