# Chain orchestration and converters
- run_chain.py: stages silo-step, abit, matsim-pop, matsim, skims, loop (see PIPELINE.md); the final run used `matsim` per seed via 4_matsim/validation/run_seeds_respec.sh
- abit_to_matsim_pop.py: ABIT activities and legs plus SILO persons -> MATSim population (needs 3_abit/abit_day.py)
- pop_scc_links.py: keep activities off dead-end car links (applied after the population is built)
- matsim_to_skim.py, transit_skim.py (+ TransitSkim.java), accessibility.py: skims from MATSim events and transit schedule (used by the 2-year feedback loop of PIPELINE.md)
- PIPELINE.md, FRAMEWORK.md: design notes
