# -*- coding: utf-8 -*-
"""Post-hoc validator for the Opus-translated Shakespeare play scenes.

The Opus agents preserve [[wikilinks]] themselves (no Lnn masking - that machinery exists for
Tower 72B, which mistranslates link targets; Opus does not). This script is the check that runs
afterwards and decides OK / FAIL for every leaf.

  check <vault_rel>        -> JSON verdict for one scene
  sweep [play ...]         -> verdict for every scene (all plays if none named); prints a summary
                              and writes data/shakespeare_failures.json

A scene atom is exactly three blocks: YAML frontmatter, an `# [[Play]] - Act N, Scene M` heading,
and one markdown table `| Chi parla | Battuta |`. The table scaffolding and *(didascalia)* are
already Italian in the English source (preprocess.mjs emits them), so they pass through verbatim.
"""
import os, sys, json, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt

FAILURES = os.path.join(dt.ROOT, "data", "shakespeare_failures.json")
PLAYS_REL = "Authors/Shakespeare/Plays"
PLAYS_ABS = os.path.join(dt.VAULT_ROOT, PLAYS_REL)

# Italian is wordier than English, but a real translation stays in this band. Outside it means
# truncation (agent stopped early) or fabrication (agent started inventing) - the failure mode the
# Dickens run hit repeatedly.
MIN_RATIO, MAX_RATIO = 0.60, 1.90


def _rows(text):
    """Table rows, i.e. the speech units. Header and |---| separator excluded."""
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("|") and not re.match(r"^\|[\s\-|:]+\|$", s):
            out.append(s)
    return out


def _frontmatter(text):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    return text[:end + 4] if end != -1 else None


def _heading(text):
    for line in text.split("\n"):
        if line.startswith("#"):
            return line.strip()
    return None


def check_pair(en_path):
    """Return (status, problems) for one scene. status in OK / MISSING / FAIL."""
    it_path = en_path[:-3] + ".it.md"
    rel = os.path.relpath(en_path, dt.VAULT_ROOT)
    if not os.path.exists(it_path):
        return rel, "MISSING", ["no .it.md"]

    en = dt._read_vault(en_path)
    it = dt._read_vault(it_path)
    p = []

    if not it.strip():
        return rel, "FAIL", ["empty output"]

    # 1. Links: the whole point. Multiset of targets must be identical - none dropped, none
    #    invented, none translated into a broken Italian target.
    ten, tit = dt.targets(en), dt.targets(it)
    if ten != tit:
        miss = [x for x in ten if tit.count(x) < ten.count(x)]
        extra = [x for x in tit if tit.count(x) > ten.count(x)]
        if miss:
            p.append("dropped links: %s" % sorted(set(miss))[:8])
        if extra:
            p.append("invented links: %s" % sorted(set(extra))[:8])

    # 2. Frontmatter must survive verbatim in English (tags are concept ids, not prose).
    fen, fit = _frontmatter(en), _frontmatter(it)
    if fen and fit != fen:
        p.append("frontmatter altered")
    elif fen and not fit:
        p.append("frontmatter missing")

    # 3. One row per speech: a dropped or merged row loses a character's line.
    ren, rit = _rows(en), _rows(it)
    if len(ren) != len(rit):
        p.append("table rows %d IT vs %d EN" % (len(rit), len(ren)))

    # 4. Heading present and still a heading.
    if not _heading(it):
        p.append("heading missing")

    # 5. Length band - catches truncation and runaway generation.
    if len(en) > 0:
        r = len(it) / float(len(en))
        if r < MIN_RATIO or r > MAX_RATIO:
            p.append("length ratio %.2f" % r)

    # 6. Residual Lnn mask codes must never reach the vault (belt and braces).
    if dt.ANY_CODE_RE.search(it):
        p.append("residual mask codes")

    return rel, ("OK" if not p else "FAIL"), p


def scenes_of(play):
    """Every translatable leaf of a play: the Act_N/Scene_M.md atoms plus the play-level
    <Play>.md (editorial introduction + dramatis personae, not a table of contents)."""
    out = []
    for dirpath, _, files in os.walk(os.path.join(PLAYS_ABS, play)):
        for f in sorted(files):
            if not f.endswith(".md") or f.endswith(".it.md"):
                continue
            if f.startswith("Scene_") or f == play + ".md":
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def cmd_check(rel):
    en = rel if os.path.isabs(rel) else os.path.join(dt.VAULT_ROOT, rel)
    r, status, probs = check_pair(en)
    print(json.dumps({"atom": r, "status": status, "problems": probs}, ensure_ascii=False))
    sys.exit(0 if status == "OK" else 3)


def cmd_sweep(plays):
    if not plays:
        plays = sorted(d for d in os.listdir(PLAYS_ABS)
                       if os.path.isdir(os.path.join(PLAYS_ABS, d)))
    tally, failures = {"OK": 0, "FAIL": 0, "MISSING": 0}, []
    per_play = {}
    for play in plays:
        ok = fail = miss = 0
        for en in scenes_of(play):
            rel, status, probs = check_pair(en)
            tally[status] += 1
            if status == "OK":
                ok += 1
            else:
                (failures.append({"atom": rel, "status": status, "problems": probs}))
                fail += status == "FAIL"
                miss += status == "MISSING"
        per_play[play] = (ok, fail, miss)
        print("%-45s ok=%-4d fail=%-4d missing=%-4d" % (play, ok, fail, miss))
    os.makedirs(os.path.dirname(FAILURES), exist_ok=True)
    with open(FAILURES, "w", encoding="utf-8") as fh:
        json.dump(failures, fh, ensure_ascii=False, indent=1)
    print("-----")
    print(json.dumps({"total": sum(tally.values()), **tally, "failures_file": FAILURES}))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: shakespeare_check.py check <rel> | sweep [play ...]"); sys.exit(1)
    if sys.argv[1] == "check":
        cmd_check(sys.argv[2])
    elif sys.argv[1] == "sweep":
        cmd_sweep(sys.argv[2:])
    else:
        print("unknown cmd"); sys.exit(1)
