#!/bin/sh
: "${ORIOLE_WORKSPACE:?run through the oriole command, or set ORIOLE_WORKSPACE}"
# Build article and Supplementary Material with resolved cross-references (two passes).  The LaTeX sources, figures and
# gen_labels.py are in WORKSPACE/5_reports/article.   Usage: sh reports/article/build.sh
cd "$ORIOLE_WORKSPACE/5_reports/article"
for pass in 1 2; do
  tectonic -X compile -k main.tex >/dev/null 2>main.err || { cat main.err; exit 1; }
  tectonic -X compile -k supplementary.tex >/dev/null 2>supplementary.err || { cat supplementary.err; exit 1; }
  python3 gen_labels.py
done
tectonic -X compile -k --keep-logs main.tex >/dev/null 2>main.err
tectonic -X compile -k --keep-logs supplementary.tex >/dev/null 2>supplementary.err
