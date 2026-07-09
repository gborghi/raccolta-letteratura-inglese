# -*- coding: utf-8 -*-
"""Validate LLM block translations: 1:1 coverage + wikilink-target preservation.
Usage: gkc_validate.py <tasks_dir> <out_dir>
For each task, compares input blocks to output IT blocks:
  - every index present (coverage)
  - the multiset of wikilink TARGETS in each IT block == that of the EN block
    (target = the part before '|', or the whole link if no pipe)
Prints per-task PASS/FAIL and a list of failing (label, index) for re-run.
Exit code 0 if all pass, 1 otherwise.
"""
import os, re, sys, glob, json
from collections import Counter

WL = re.compile(r"\[\[([^\]]+)\]\]")
def targets(s):
    return Counter(m.split("|", 1)[0].strip() for m in WL.findall(s))

def main():
    tasks_dir = os.path.join("data", sys.argv[1]) if not os.path.isabs(sys.argv[1]) else sys.argv[1]
    out_dir = os.path.join("data", sys.argv[2]) if not os.path.isabs(sys.argv[2]) else sys.argv[2]
    fails = []
    ntask = nblock = 0
    for tf in sorted(glob.glob(os.path.join(tasks_dir, "*.json"))):
        t = json.load(open(tf, encoding="utf-8"))
        label, blocks = t["doc"], t["blocks"]
        its = {}
        for of in sorted(glob.glob(os.path.join(out_dir, f"{label}.*.jsonl"))):
            for ln in open(of, encoding="utf-8"):
                ln = ln.strip()
                if ln:
                    r = json.loads(ln); its[r["i"]] = r["it"]
        if not its:
            continue  # not translated yet
        ntask += 1
        task_fail = []
        for i, b in enumerate(blocks):
            nblock += 1
            if i not in its:
                task_fail.append((i, "missing")); continue
            te, ti = targets(b), targets(its[i])
            if te != ti:
                lost = list((te - ti).elements()); extra = list((ti - te).elements())
                task_fail.append((i, f"links lost={lost[:4]} extra={extra[:4]}"))
        if task_fail:
            fails.append((label, task_fail))
            print(f"FAIL {label}: {len(task_fail)}/{len(blocks)} blocks")
            for i, why in task_fail[:5]:
                print(f"      block {i}: {why}")
        else:
            print(f"PASS {label} ({len(blocks)})")
    print(f"\n{ntask} tasks checked, {nblock} blocks | {len(fails)} tasks with issues")
    # write failing labels for re-run
    if fails:
        json.dump([f[0] for f in fails], open(os.path.join(out_dir, "_failed_labels.json"), "w"), indent=1)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
