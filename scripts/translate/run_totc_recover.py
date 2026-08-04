import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt
dt.TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "totc_recover_atoms.tsv")
dt.FIXUPS_PATH = os.path.join(dt.ROOT, "data", "a_tale_of_two_cities_tower_linkfix.jsonl")
dt.main()
