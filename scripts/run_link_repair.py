# -*- coding: utf-8 -*-
"""Run repair-tower-links.py over one or more atom TSVs.

repair-tower-links.py repairs whatever atoms are in the TSV it imports from gkc_tower_sensitive,
harvesting Italian link labels corpus-wide from every Chesterton .it.md. To repair atom sets other
than the default sensitive TSV (the Opus batch, the filter-blocked set), we override
gkc_tower_sensitive.TSV before (re)executing the repair module, once per TSV.

Usage: python3 run_link_repair.py [--apply] <tsv1> [<tsv2> ...]
  (no TSV -> uses the default sensitive TSV)
"""
import sys, os, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "translate"))
import gkc_tower_sensitive as g

args = sys.argv[1:]
apply = "--apply" in args
tsvs = [a for a in args if a != "--apply"] or [g.TSV]

REPAIR = os.path.join(HERE, "repair-tower-links.py")

for tsv in tsvs:
    g.TSV = os.path.abspath(tsv)
    print(f"\n########## link-repair over {os.path.basename(tsv)} (apply={apply}) ##########", flush=True)
    spec = importlib.util.spec_from_file_location("repair_mod", REPAIR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # `from gkc_tower_sensitive import TSV` picks up the override
    sys.argv = ["repair", "--apply"] if apply else ["repair"]
    mod.main()
