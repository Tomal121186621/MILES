#!/bin/sh
# compile-check est_mc_pooled.tex with the preamble of ../../final_tables/estimation_tables_abit.tex (tectonic)
cd "$(dirname "$0")"
sed -n '1,/\\begin{document}/p' ../../final_tables/estimation_tables_abit.tex > mp_check.tex
printf '\\input{est_mc_pooled.tex}\n\\end{document}\n' >> mp_check.tex
tectonic --keep-logs mp_check.tex > mp_check.out 2>&1
echo "errors: $(grep -c '^!' mp_check.log)  undefined: $(grep -ci 'undefined' mp_check.log)  overfull: $(grep -c 'Overfull' mp_check.log)  underfull: $(grep -c 'Underfull' mp_check.log)"
