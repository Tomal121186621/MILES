"""Paths of the shared preparation chain.  SHARED: the provided data (00_shared_data); RAW: your downloads (00_shared_data/raw);
REBUILT: what this chain writes (00_shared_data/rebuilt, or the folder in the environment variable ABIT_REBUILT).  The chain never
overwrites provided files; compare a rebuilt file with the provided one with check_against_provided.py."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.abspath(os.path.join(HERE, "..", "..", "00_shared_data"))
RAW = os.environ.get("ABIT_RAW", os.path.join(SHARED, "raw"))
REBUILT = os.environ.get("ABIT_REBUILT", os.path.join(SHARED, "rebuilt"))


def out(rel):
    p = os.path.join(REBUILT, rel); os.makedirs(os.path.dirname(p), exist_ok=True); return p
