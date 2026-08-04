import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt
dt.TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc_recover_atoms.tsv")
dt.FIXUPS_PATH = os.path.join(dt.ROOT, "data", "a_christmas_carol_tower_linkfix.jsonl")
dt.main()
