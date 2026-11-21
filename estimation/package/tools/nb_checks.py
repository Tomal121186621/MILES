#!/usr/bin/env python3
"""Print the rebuild verdicts, record funnels and log-likelihood lines of executed notebooks."""
import sys, re, nbformat
KEYS = ("LL at", "hold-out:", "identical", "differing columns", "used by the model", "LL at the reference", "LL(beta)", "same trip ids", "min", "skipped", "DIFFERENT", "not rebuilt", "Error", "ERROR")
for p in sys.argv[1:]:
    nb = nbformat.read(p, 4)
    print("=====", p.split("/")[-1])
    for c in nb.cells:
        for o in c.get("outputs", []):
            t = o.get("text") or o.get("data", {}).get("text/plain", "")
            if o.get("output_type") == "error":
                print("  ERROR", o.get("ename"), str(o.get("evalue"))[:200])
            for l in str(t).splitlines():
                if any(k in l for k in KEYS) and len(l) < 260 and "rows rebuilt" not in l:
                    print("  " + l.strip())
