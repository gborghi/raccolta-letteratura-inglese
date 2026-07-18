# -*- coding: utf-8 -*-
"""Deterministic mask/write helper for Opus-agent Chesterton translation.

The LLM (an Opus subagent) does ONLY translation. All structure- and link-critical logic
lives here, reusing the proven functions from dickens_tower.py:
  mask  <vault_rel>                 -> prints JSON {"atom":rel,"blocks":[masked prose blocks...]}
  write <vault_rel> <it_json>       -> unmask + validate + write <atom>.it.md; reports OK/errors

The agent's job per atom:
  1. python3 opus_atom.py mask  <rel>            # get the N masked prose blocks
  2. translate each block to Italian, keeping every [[Lnn|label]] token (translate only the label),
     returning EXACTLY N blocks in order as a JSON array -> save to <tmp>.json
  3. python3 opus_atom.py write <rel> <tmp>.json # writes the .it.md, validates, reports

Masking is a pure function of the English block, so `write` recomputes targets itself — the agent
never has to handle link targets, only carry the opaque [[Lnn|label]] tokens through.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt          # reuse mask_links/unmask_links/prose_blocks/validate/etc.
from sbtrans import clean_body, split_blocks, has_prose

FIXUPS = os.path.join(dt.ROOT, "data", "chesterton_opus_linkfix.jsonl")


def _abs(rel):
    return rel if os.path.isabs(rel) else os.path.join(dt.VAULT_ROOT, rel)


def cmd_mask(rel):
    body = open(_abs(rel), encoding="utf-8").read()
    blocks = [dt.mask_links(b)[0] for b in dt.prose_blocks(body)]
    print(json.dumps({"atom": rel, "n": len(blocks), "blocks": blocks}, ensure_ascii=False))


def cmd_write(rel, it_json):
    en_path = _abs(rel)
    body = open(en_path, encoding="utf-8").read()
    it_list = json.load(open(it_json, encoding="utf-8"))
    if isinstance(it_list, dict) and "blocks" in it_list:
        it_list = it_list["blocks"]

    parts = split_blocks(clean_body(body))
    bp = dt.boilerplate_mask(parts)
    n_prose = sum(1 for k, p in enumerate(parts)
                  if p.strip() and not p.strip().startswith("<nav") and has_prose(p.strip()) and not bp[k])
    if len(it_list) != n_prose:
        print(json.dumps({"atom": rel, "status": "ERROR",
                          "error": f"block count {len(it_list)} IT vs {n_prose} prose EN"}))
        sys.exit(2)

    out, j, fixups = [], 0, []
    for k, part in enumerate(parts):
        s = part.strip()
        if not s or s.startswith("<nav") or not has_prose(s) or bp[k]:
            out.append(part)
            continue
        masked, targets = dt.mask_links(s)
        it_raw = it_list[j]; j += 1
        it = dt.unmask_links(it_raw, targets)
        it = dt.STRAY_CODE_RE.sub(lambda m: m.group(1), it)   # drop codes the model failed to carry
        got = dt._codes_of(it_raw)
        want = ["L%02d" % (i + 1) for i in range(len(targets))]
        missing = [targets[int(c[1:]) - 1] for c in want if c not in got]
        if missing:
            fixups.append({"atom": rel, "missing": missing, "en": s, "it": it})
        lead = part[:len(part) - len(part.lstrip())]
        trail = part[len(part.rstrip()):]
        qm = __import__("re").match(r"(>+\s*)", s)
        if qm and not it.startswith(">"):
            it = qm.group(1) + it
        out.append(lead + it.strip() + trail)

    it_body = "".join(out)
    problems = dt.validate(body, it_body, verse=False)
    if problems:
        print(json.dumps({"atom": rel, "status": "REJECT", "problems": problems}, ensure_ascii=False))
        sys.exit(3)
    with open(en_path[:-3] + ".it.md", "w", encoding="utf-8") as fh:
        fh.write(it_body)
    if fixups:
        os.makedirs(os.path.dirname(FIXUPS), exist_ok=True)
        with open(FIXUPS, "a", encoding="utf-8") as fh:
            for f in fixups:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(json.dumps({"atom": rel, "status": "OK", "blocks": n_prose,
                      "links_need_repair": sum(len(f["missing"]) for f in fixups)}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: opus_atom.py mask <rel> | write <rel> <it.json>"); sys.exit(1)
    if sys.argv[1] == "mask":
        cmd_mask(sys.argv[2])
    elif sys.argv[1] == "write":
        cmd_write(sys.argv[2], sys.argv[3])
    else:
        print("unknown cmd"); sys.exit(1)
