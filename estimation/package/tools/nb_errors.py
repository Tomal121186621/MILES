#!/usr/bin/env python3
"""Print the failing cells (source head and error) of executed notebooks."""
import sys, re, nbformat
for p in sys.argv[1:]:
    nb = nbformat.read(p, 4)
    for i, c in enumerate(nb.cells):
        for o in c.get("outputs", []):
            if o.get("output_type") == "error":
                tb = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(o.get("traceback", [])))
                print(f"== {p} cell {i}\n{c.source[:300]}\n--\n{tb[-1500:]}")
