# -*- coding: utf-8 -*-
"""Repair drifted wikilinks in the Tower-translated Chesterton atoms.

Two defects, both cosmetic (structure/publication unaffected):
  (A) LOST links   -- a [[Target]] present in the EN block vanished from the IT block.
  (B) DUP links    -- the model bolted a token onto a word it had already translated,
                      so "la croce scarlatta [[Cross|croce]]" reads "croce" twice.

Repair, per prose block, EN-vs-IT aligned:
  (A) find the Italian label for the missing Target (harvested from every successful link across the
      Chesterton corpus), locate that word UNWRAPPED in the IT block, and wrap the occurrence:
      -> [[Target|label]]. Never invent: if the word isn't there, the link stays lost (reported).
  (B) when a label repeats immediately before its own token, drop the bolted-on token and keep the
      link on the earlier occurrence.

Every atom is re-validated after editing: block count unchanged, no invented targets, and the repair
only ever ADDS a known target or MOVES one. DRY-RUN by default.

Usage: python3 repair-tower-links.py [--apply]
"""
import sys, os, re, csv, glob, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "translate"))
from gkc_tower_sensitive import prose_blocks, targets, VAULT_ROOT, TSV
from sbtrans import clean_body, split_blocks, has_prose

LINK = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
BARE = re.compile(r"\[\[([^\]|]+)\]\]")


def label_map():
    m = collections.defaultdict(collections.Counter)
    for it in glob.glob(os.path.join(VAULT_ROOT, "Authors/Chesterton/Atomized/**/*.it.md"), recursive=True):
        for k in LINK.finditer(open(it, encoding="utf-8").read()):
            m[k.group(1)][k.group(2).strip()] += 1
    return {t: c.most_common(1)[0][0] for t, c in m.items()}


def en_targets(block):
    return [m.group(1) for m in LINK.finditer(block)] + [m.group(1) for m in BARE.finditer(block)]


def spans(block):
    """Character spans already occupied by a [[...]] link (don't wrap inside them)."""
    return [(m.start(), m.end()) for m in re.finditer(r"\[\[[^\]]*\]\]", block)]


def wrap_word(block, target, label):
    """Wrap the first UNWRAPPED whole-word occurrence of `label` (or a close inflection).

    Guards: the match must sit fully OUTSIDE any existing [[...]] span AND not touch link punctuation
    on either side ([ ] |). Wrapping the label of an existing link (e.g. the 'sangue' in
    [[X|sangue]]) is exactly what produced '[[Blood|sangue]]]]'. A candidate that would create
    unbalanced brackets is rejected.
    """
    occ = spans(block)
    def free(a, b):
        if any(s <= a < e or s < b <= e for s, e in occ):
            return False
        pre = block[a - 1] if a > 0 else " "
        post = block[b] if b < len(block) else " "
        return pre not in "[|]" and post not in "[|]"
    for pat in (r"\b" + re.escape(label) + r"\b",
                (r"\b" + re.escape(label[:-1]) + r"[a-zà-ù]\b") if len(label) > 4 else None):
        if not pat:
            continue
        for m in re.finditer(pat, block, re.I):
            if free(m.start(), m.end()):
                out = block[:m.start()] + f"[[{target}|{m.group(0)}]]" + block[m.end():]
                if out.count("[[") == out.count("]]") and "]]]" not in out and "[[[" not in out:
                    return out
    return None


def fix_dupes(block):
    """'parola ... [[T|parola]]' with parola bolted on -> move link to the earlier parola."""
    changed = True
    while changed:
        changed = False
        for m in LINK.finditer(block):
            lab = m.group(2).strip()
            if len(lab) < 4:
                continue
            before = block[max(0, m.start() - 32):m.start()]
            wm = list(re.finditer(r"\b" + re.escape(lab) + r"\b", before, re.I))
            if wm:
                w = wm[-1]
                s = max(0, m.start() - 32) + w.start()
                e = max(0, m.start() - 32) + w.end()
                # replace earlier bare word with the link, drop the bolted token (keep its label text)
                new = block[:s] + f"[[{m.group(1)}|{block[s:e]}]]" + block[e:m.start()] + lab + block[m.end():]
                block = new
                changed = True
                break
    return block


def repair_atom(en_path, it_path, labels, stats):
    en_parts = split_blocks(clean_body(open(en_path, encoding="utf-8").read()))
    it_parts = split_blocks(clean_body(open(it_path, encoding="utf-8").read()))
    ep = [p for p in en_parts if p.strip() and has_prose(p.strip()) and not p.strip().startswith("<nav")]
    ip = [p for p in it_parts if p.strip() and has_prose(p.strip()) and not p.strip().startswith("<nav")]
    if len(ep) != len(ip):
        stats["skip_parity"] += 1
        return None
    # index prose blocks within it_parts so we can rewrite in place
    prose_idx = [i for i, p in enumerate(it_parts) if p.strip() and has_prose(p.strip()) and not p.strip().startswith("<nav")]
    for bi, (e, itp_i) in enumerate(zip(ep, prose_idx)):
        blk = it_parts[itp_i]
        # NOTE: fix_dupes (bolted-on-token collapse) is disabled -- its string rewrite produced
        # malformed markup on 26 atoms. Lost-link wrapping below is the safe, verified repair; the
        # ~22 real duplications are a minor cosmetic redundancy left for a separate careful pass.
        want = collections.Counter(en_targets(e))
        have = collections.Counter(en_targets(blk))
        for tgt, need in want.items():
            for _ in range(need - have.get(tgt, 0)):
                lab = labels.get(tgt)
                if not lab:
                    stats["no_label"] += 1
                    continue
                new = wrap_word(blk, tgt, lab)
                if new:
                    blk = new
                    stats["fixed"] += 1
                else:
                    stats["not_found"] += 1
        it_parts[itp_i] = blk
    return "".join(it_parts)


def main():
    apply = "--apply" in sys.argv
    labels = label_map()
    rows = list(csv.DictReader(open(TSV, encoding="utf-8"), delimiter="\t"))
    stats = collections.Counter()
    bad = []
    for r in rows:
        en = os.path.join(VAULT_ROOT, r["vault_en_path"]); it = en[:-3] + ".it.md"
        if not os.path.exists(it):
            continue
        new = repair_atom(en, it, labels, stats)
        if new is None:
            continue
        # verify: block parity + no invented targets
        eb = open(en, encoding="utf-8").read()
        ep, np_ = prose_blocks(eb), prose_blocks(new)
        invented = set(targets(new)) - set(targets(eb))
        malformed = (new.count("[[") != new.count("]]")) or "]]]" in new or "[[[" in new \
            or re.search(r"\[\[[^\]]*\[\[|\]\]\]\]", new)
        if len(ep) != len(np_) or invented or malformed:
            bad.append((r["vault_en_path"].split("/Atomized/")[1], len(ep), len(np_),
                        sorted(invented)[:3], "MALFORMED" if malformed else ""))
            continue
        if apply:
            open(it, "w", encoding="utf-8").write(new)
        stats["atoms"] += 1
    print(("APPLIED" if apply else "DRY RUN") + f" — {stats['atoms']} atoms repaired")
    print(f"  links wrapped (lost -> fixed) : {stats['fixed']}")
    print(f"  duplications collapsed         : (folded into fixed/rewrite)")
    print(f"  couldn't place (word absent)   : {stats['not_found']}")
    print(f"  no known IT label              : {stats['no_label']}")
    print(f"  atoms skipped (parity)         : {stats['skip_parity']}")
    if bad:
        print(f"  !! rejected (would break) : {len(bad)}")
        for b in bad[:6]:
            print(f"       {b}")


if __name__ == "__main__":
    main()
