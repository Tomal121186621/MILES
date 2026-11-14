#!/bin/sh
# Build article and Supplementary Material with resolved cross-references (two passes).
cd "$(dirname "$0")"
for pass in 1 2; do
  tectonic -X compile -k main.tex >/dev/null 2>main.err || { cat main.err; exit 1; }
  tectonic -X compile -k supplementary.tex >/dev/null 2>supplementary.err || { cat supplementary.err; exit 1; }
  python3 gen_labels.py
done
tectonic -X compile -k --keep-logs main.tex >/dev/null 2>main.err
tectonic -X compile -k --keep-logs supplementary.tex >/dev/null 2>supplementary.err
