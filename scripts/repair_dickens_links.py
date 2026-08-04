# -*- coding: utf-8 -*-
"""Repair drifted wikilinks in Tower-translated Dickens atoms (LOST links only).

Same proven repair as repair-tower-links.py (the Chesterton one), but author-scoped to Dickens:
the Italian label for a missing [[Target]] is harvested from every successful link across the
Dickens .it.md corpus, then wrapped onto the matching Italian word in the block that lost it. Never
invents: if the word isn't in the block, the link stays lost (reported). fix_dupes stays DISABLED
(its string rewrite produced malformed markup); lost-link wrapping is the safe, re-validated repair.

Every atom is re-validated after editing (block parity, no invented targets, balanced brackets).
DRY-RUN by default.

Usage: python3 repair_dickens_links.py [--apply] [<tsv> ...]   (default TSV: oliver_twist_atoms.tsv)
"""
import sys, os, re, csv, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "translate"))
import dickens_tower as dt
from dickens_tower import prose_blocks, targets, VAULT_ROOT
from sbtrans import clean_body, split_blocks, has_prose

LINK = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
BARE = re.compile(r"\[\[([^\]|]+)\]\]")
DICKENS_GLOB = os.path.join(VAULT_ROOT, "Authors/Dickens/Atomized/**/*.it.md")


def prose_skipfm(body):
    """prose_blocks, but also skip YAML frontmatter (--- blocks). The Windows restructuring is
    adding a tags frontmatter to the EN atoms that the .it.md siblings don't carry, so dt.prose_blocks
    counts one extra block on the EN side. Frontmatter is metadata, never a translation unit; skipping
    it on both sides is the parity that matters for the emitter's prose alignment."""
    out = []
    for part in split_blocks(clean_body(body)):
        s = part.strip()
        if not s or s.startswith("<nav") or s.startswith("---") or not has_prose(s):
            continue
        out.append(s)
    return out


def label_map():
    m = collections.defaultdict(collections.Counter)
    for it in glob.glob(DICKENS_GLOB, recursive=True):
        for k in LINK.finditer(open(it, encoding="utf-8").read()):
            m[k.group(1)][k.group(2).strip()] += 1
    return {t: c.most_common(1)[0][0] for t, c in m.items()}


def en_targets(block):
    return [m.group(1) for m in LINK.finditer(block)] + [m.group(1) for m in BARE.finditer(block)]


def spans(block):
    return [(m.start(), m.end()) for m in re.finditer(r"\[\[[^\]]*\]\]", block)]


def wrap_word(block, target, label):
    """Wrap the first UNWRAPPED whole-word occurrence of `label` (or a close inflection)."""
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


def repair_atom(en_path, it_path, labels, stats):
    en_parts = split_blocks(clean_body(open(en_path, encoding="utf-8").read()))
    it_parts = split_blocks(clean_body(open(it_path, encoding="utf-8").read()))
    def is_prose(p):
        s = p.strip()
        return bool(s) and has_prose(s) and not s.startswith("<nav") and not s.startswith("---")
    ep = [p for p in en_parts if is_prose(p)]
    ip = [p for p in it_parts if is_prose(p)]
    if len(ep) != len(ip):
        stats["skip_parity"] += 1
        return None
    prose_idx = [i for i, p in enumerate(it_parts) if is_prose(p)]
    for e, itp_i in zip(ep, prose_idx):
        blk = it_parts[itp_i]
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
    tsvs = [a for a in sys.argv[1:] if a != "--apply"] or [
        os.path.join(HERE, "translate", "oliver_twist_atoms.tsv")]
    labels = label_map()
    print(f"harvested {len(labels)} IT labels from Dickens corpus")
    stats = collections.Counter()
    bad = []
    for tsv in tsvs:
        rows = list(csv.DictReader(open(tsv, encoding="utf-8"), delimiter="\t"))
        for r in rows:
            en = os.path.join(VAULT_ROOT, r["vault_en_path"]); it = en[:-3] + ".it.md"
            if not os.path.exists(it):
                continue
            new = repair_atom(en, it, labels, stats)
            if new is None:
                continue
            eb = open(en, encoding="utf-8").read()
            ep, np_ = prose_skipfm(eb), prose_skipfm(new)
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
    print(f"  couldn't place (word absent)  : {stats['not_found']}")
    print(f"  no known IT label             : {stats['no_label']}")
    print(f"  atoms skipped (parity)        : {stats['skip_parity']}")
    if bad:
        print(f"  !! rejected (would break)     : {len(bad)}")
        for b in bad[:8]:
            print(f"       {b}")


if __name__ == "__main__":
    main()
