#!/usr/bin/env python3
"""Print the text outputs (stream, errors) of executed notebooks, and their number of figures."""
import sys, nbformat
for p in sys.argv[1:]:
    nb = nbformat.read(p, 4); k = 0
    print("=====", p)
    for c in nb.cells:
        for o in c.get("outputs", []):
            if o.get("output_type") == "stream":
                t = "\n".join(l for l in o["text"].splitlines() if "warn" not in l.lower() and l.strip())
                print(t[-700:])
            elif o.get("output_type") == "error":
                print("ERROR", o.get("ename"), o.get("evalue")[:500])
            if "image/png" in o.get("data", {}):
                k += 1
    print(f"[{k} figures]")
