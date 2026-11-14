#!/usr/bin/env python3
"""Typed survey episodes of both halves (te_common.episodes: TASHA activity types of tasha_distributions.py, person segments,
home / work / origin / destination zones of the tract points), unchanged.

    python3 build_episodes.py      reads raw survey files, survey_pop (provided), tract_zone.csv (provided)
                                   writes rebuilt/rts_2017_18/episodes/episodes_<half>.parquet
"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import te_common as T      # noqa: E402

for half in ["estimation", "validation"]:
    e = T.episodes(half); print(half, e.shape)
